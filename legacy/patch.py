#!/usr/bin/env python3
"""
Minecraft 材质包文件删除和覆盖工具

根据 delete.json 配置文件，删除指定材质包目录中的文件和文件夹。
支持白名单（只保留指定项）和黑名单（只删除指定项）两种模式。
删除完成后，将 overrides 目录的内容覆盖到目标材质包。
"""

import json
import shutil
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any, Dict, List, Union

# JSON 配置类型定义
JsonValue = Union[str, Dict[str, Any], List[Any]]


def find_pack_mcmeta(target_dir: Path) -> Path | None:
    """
    在指定目录中查找 pack.mcmeta 文件

    Args:
        target_dir: 要搜索的目标目录

    Returns:
        找到的 pack.mcmeta 文件所在目录的 Path 对象，未找到返回 None
    """
    if not target_dir.exists():
        print(f"错误: 目录不存在: {target_dir}")
        return None

    # 首先检查目标目录本身
    pack_meta = target_dir / "pack.mcmeta"
    if pack_meta.exists():
        return target_dir

    # 递归搜索子目录
    for pack_meta in target_dir.rglob("pack.mcmeta"):
        return pack_meta.parent

    return None


def delete_path(path: Path) -> None:
    """
    删除文件或目录

    Args:
        path: 要删除的路径
    """
    if not path.exists():
        print(f"  [跳过] 路径不存在: {path}")
        return

    if path.is_file():
        path.unlink()
        print(f"  [删除文件] {path}")
    elif path.is_dir():
        shutil.rmtree(path)
        print(f"  [删除目录] {path}")


def process_rule(
    base_path: Path,
    relative_path: str,
    rule: JsonValue,
    dry_run: bool = False
) -> None:
    """
    处理单个规则（递归函数核心）

    Args:
        base_path: assets 目录的绝对路径
        relative_path: 相对于 assets 的路径
        rule: 当前规则（可以是字符串、对象或数组）
        dry_run: 是否为试运行模式（不实际删除）
    """
    current_path = base_path / relative_path

    # 情况 1: 字符串规则
    if isinstance(rule, str):
        if rule == "delete":
            print(f"{'[试运行] ' if dry_run else ''}删除: {relative_path}")
            if not dry_run:
                delete_path(current_path)
        elif rule == "preserve":
            print(f"保留: {relative_path}")
        else:
            print(f"警告: 未知规则 '{rule}' 于 {relative_path}")
        return

    # 情况 2: 对象规则（递归处理子项，不删除目录本身）
    if isinstance(rule, dict):
        print(f"进入目录: {relative_path}")
        for name, sub_rule in rule.items():
            sub_relative_path = f"{relative_path}/{name}" if relative_path else name
            process_rule(base_path, sub_relative_path, sub_rule, dry_run)
        return

    # 情况 3: 数组规则（白名单/黑名单模式）
    if isinstance(rule, list):
        if len(rule) != 2:
            print(f"警告: 数组规则格式错误于 {relative_path}")
            return

        mode: str = rule[0]  # "preserve" 或 "delete"
        declarations: Dict[str, JsonValue] = rule[1]

        if not isinstance(mode, str) or mode not in ("preserve", "delete"):
            print(f"警告: 未知模式 '{mode}' 于 {relative_path}")
            return

        if not isinstance(declarations, dict):
            print(f"警告: 声明列表不是对象于 {relative_path}")
            return

        # 检查目录是否存在
        if not current_path.exists():
            print(f"警告: 目录不存在: {relative_path}")
            return

        if not current_path.is_dir():
            print(f"警告: 路径不是目录: {relative_path}")
            return

        # 获取目录中的所有实际文件和子目录
        existing_items = {item.name for item in current_path.iterdir()}
        declared_items = set(declarations.keys())

        if mode == "preserve":
            # 白名单模式：删除未声明的项
            items_to_delete = existing_items - declared_items
            print(f"[白名单模式] {relative_path}: 保留 {len(declared_items)} 项，删除 {len(items_to_delete)} 项")

            for item_name in items_to_delete:
                item_relative_path = f"{relative_path}/{item_name}" if relative_path else item_name
                print(f"{'[试运行] ' if dry_run else ''}删除(未声明): {item_relative_path}")
                if not dry_run:
                    delete_path(current_path / item_name)

            # 处理声明列表中的项（可能有嵌套规则）
            for item_name, sub_rule in declarations.items():
                item_relative_path = f"{relative_path}/{item_name}" if relative_path else item_name
                process_rule(base_path, item_relative_path, sub_rule, dry_run)

        elif mode == "delete":
            # 黑名单模式：只处理声明的项
            print(f"[黑名单模式] {relative_path}: 处理 {len(declared_items)} 项声明")

            for item_name, sub_rule in declarations.items():
                item_relative_path = f"{relative_path}/{item_name}" if relative_path else item_name
                process_rule(base_path, item_relative_path, sub_rule, dry_run)

        return


def modify_pack_mcmeta(pack_root: Path, dry_run: bool = False) -> None:
    """
    修改 pack.mcmeta 文件，在 description 前添加前缀

    Args:
        pack_root: 材质包根目录
        dry_run: 是否为试运行模式（不实际修改）
    """
    pack_meta_path: Path = pack_root / "pack.mcmeta"

    if not pack_meta_path.exists():
        print(f"\n警告: pack.mcmeta 不存在，跳过修改")
        return

    print(f"\n修改 pack.mcmeta...")

    try:
        # 读取 pack.mcmeta
        with pack_meta_path.open("r", encoding="utf-8") as f:
            pack_data: Dict[str, Any] = json.load(f)

        # 检查并修改 description
        if "pack" in pack_data and "description" in pack_data["pack"]:
            original_desc: str = pack_data["pack"]["description"]
            prefix: str = "§dMINI §7"

            # 检查是否已经有前缀
            if not original_desc.startswith(prefix):
                pack_data["pack"]["description"] = prefix + original_desc
                print(f"  原描述: {original_desc}")
                print(f"  新描述: {pack_data['pack']['description']}")

                if not dry_run:
                    # 写回文件，保持格式化
                    with pack_meta_path.open("w", encoding="utf-8") as f:
                        json.dump(pack_data, f, indent=2, ensure_ascii=False)
                    print("  [已修改] pack.mcmeta")
                else:
                    print("  [试运行] 将修改 pack.mcmeta")
            else:
                print("  描述已有前缀，跳过")
        else:
            print("  警告: pack.mcmeta 格式不正确，缺少 pack.description 字段")

    except json.JSONDecodeError as e:
        print(f"  错误: pack.mcmeta 不是有效的 JSON 文件: {e}")
    except Exception as e:
        print(f"  错误: 修改 pack.mcmeta 时出错: {e}")


def modify_credits(pack_root: Path, dry_run: bool = False) -> None:
    """
    修改 credits.txt 文件，在末尾添加署名

    Args:
        pack_root: 材质包根目录
        dry_run: 是否为试运行模式（不实际修改）
    """
    credits_path: Path = pack_root / "credits.txt"

    print(f"\n修改 credits.txt...")

    signature: str = """Mini version by TunaFish2K
Used textures of older version of Furfsky Reborn
    """

    try:
        # 检查文件是否存在
        if credits_path.exists():
            # 读取现有内容
            with credits_path.open("r", encoding="utf-8") as f:
                content: str = f.read()

            # 检查是否已有署名
            if signature in content:
                print(f"  credits.txt 已包含署名，跳过")
                return

            # 添加署名
            new_content: str = content.rstrip() + "\n" + signature + "\n"
            print(f"  在末尾添加: {signature}")

            if not dry_run:
                with credits_path.open("w", encoding="utf-8") as f:
                    f.write(new_content)
                print("  [已修改] credits.txt")
            else:
                print("  [试运行] 将修改 credits.txt")
        else:
            # 创建新文件
            print(f"  credits.txt 不存在，创建新文件")
            if not dry_run:
                with credits_path.open("w", encoding="utf-8") as f:
                    f.write(signature + "\n")
                print("  [已创建] credits.txt")
            else:
                print("  [试运行] 将创建 credits.txt")

    except Exception as e:
        print(f"  错误: 修改 credits.txt 时出错: {e}")


def copy_overrides(script_dir: Path, target_dir: Path, dry_run: bool = False) -> None:
    """
    将脚本目录下的 overrides 文件夹内容覆盖到目标目录

    Args:
        script_dir: 脚本所在目录
        target_dir: 目标目录（材质包根目录）
        dry_run: 是否为试运行模式（不实际复制）
    """
    overrides_dir: Path = script_dir / "overrides"

    if not overrides_dir.exists():
        print(f"\n提示: overrides 目录不存在，跳过覆盖步骤")
        return

    if not overrides_dir.is_dir():
        print(f"\n警告: overrides 不是目录，跳过覆盖步骤")
        return

    print(f"\n开始覆盖 overrides 内容到: {target_dir}")

    if dry_run:
        print("[试运行模式] 不会实际复制文件")

    # 遍历 overrides 目录中的所有内容
    for item in overrides_dir.rglob("*"):
        if not item.is_file():
            continue

        # 计算相对路径
        relative_path: Path = item.relative_to(overrides_dir)
        target_path: Path = target_dir / relative_path

        # 创建目标目录
        if not dry_run:
            target_path.parent.mkdir(parents=True, exist_ok=True)

        # 复制文件
        action: str = "覆盖" if target_path.exists() else "新建"
        print(f"  [{action}] {relative_path}")

        if not dry_run:
            shutil.copy2(item, target_path)

    print("覆盖完成!")


def main() -> int:
    """
    主函数

    Returns:
        退出码（0 表示成功）
    """
    parser = ArgumentParser(
        description="根据 delete.json 删除 Minecraft 材质包中的文件，并覆盖 overrides 内容"
    )
    parser.add_argument(
        "pack_dir",
        type=Path,
        help="材质包目录路径（包含或其子目录包含 pack.mcmeta 的目录）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行模式，不实际删除或复制文件"
    )

    args: Namespace = parser.parse_args()

    # 1. 获取脚本所在目录
    script_dir: Path = Path(__file__).parent.resolve()

    # 2. 读取配置文件（固定使用脚本目录下的 delete.json）
    config_path: Path = script_dir / "delete.json"
    if not config_path.exists():
        print(f"错误: 配置文件不存在: {config_path}")
        return 1

    print(f"读取配置文件: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        config: Dict[str, Any] = json.load(f)

    # 3. 查找 pack.mcmeta
    pack_dir: Path = args.pack_dir
    print(f"\n在目录中搜索 pack.mcmeta: {pack_dir}")

    pack_root: Path | None = find_pack_mcmeta(pack_dir)
    if pack_root is None:
        print(f"错误: 未找到 pack.mcmeta 文件")
        return 1

    print(f"找到材质包根目录: {pack_root}")

    # 4. 确认 assets 目录存在
    assets_dir: Path = pack_root / "assets"
    if not assets_dir.exists():
        print(f"错误: assets 目录不存在: {assets_dir}")
        return 1

    print(f"assets 目录: {assets_dir}")

    # 5. 开始处理删除
    if args.dry_run:
        print("\n[试运行模式] 不会实际删除文件\n")
    else:
        print("\n开始删除文件...\n")

    # 配置文件应该从 "assets" 键开始
    if "assets" not in config:
        print("错误: 配置文件格式错误，缺少 'assets' 键")
        return 1

    # 处理 assets 下的所有规则
    assets_rules: Dict[str, Any] = config["assets"]
    for namespace, rules in assets_rules.items():
        process_rule(assets_dir, namespace, rules, args.dry_run)

    print("\n删除完成!")

    # 6. 覆盖 overrides 内容
    copy_overrides(script_dir, pack_root, args.dry_run)

    # 7. 修改 pack.mcmeta 描述
    modify_pack_mcmeta(pack_root, args.dry_run)

    # 8. 修改 credits.txt
    modify_credits(pack_root, args.dry_run)

    print("\n全部完成!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
