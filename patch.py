#!/usr/bin/env python3
"""
Minecraft Resource Pack File Deletion and Override Tool

Deletes files and folders in specified resource pack directory based on delete.json configuration file.
Supports two modes: whitelist (keep only specified items) and blacklist (delete only specified items).
After deletion, copies the contents of overrides directory to the target resource pack.
"""

import json
import logging
import shutil
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any, Dict, List, Union

# JSON configuration type definition
JsonValue = Union[str, Dict[str, Any], List[Any]]

# Configure logger
logger = logging.getLogger(__name__)


def find_pack_mcmeta(target_dir: Path) -> Path | None:
    """
    Find pack.mcmeta file in the specified directory

    Args:
        target_dir: The target directory to search

    Returns:
        Path object of the directory containing pack.mcmeta file, or None if not found
    """
    if not target_dir.exists():
        logger.error(f"Directory does not exist: {target_dir}")
        return None

    # Check the target directory itself first
    pack_meta = target_dir / "pack.mcmeta"
    if pack_meta.exists():
        return target_dir

    # Recursively search subdirectories
    for pack_meta in target_dir.rglob("pack.mcmeta"):
        return pack_meta.parent

    return None


def delete_path(path: Path) -> None:
    """
    Delete a file or directory

    Args:
        path: The path to delete
    """
    if not path.exists():
        logger.warning(f"Path does not exist: {path}")
        return

    if path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def process_rule(
    base_path: Path,
    relative_path: str,
    rule: JsonValue
) -> None:
    """
    Process a single rule (recursive function core)

    Args:
        base_path: Absolute path to the assets directory
        relative_path: Path relative to assets
        rule: Current rule (can be string, object, or array)
    """
    current_path = base_path / relative_path

    # Case 1: String rule
    if isinstance(rule, str):
        if rule == "delete":
            delete_path(current_path)
        elif rule == "preserve":
            pass  # Do nothing, preserve the item
        else:
            logger.warning(f"Unknown rule '{rule}' at {relative_path}")
        return

    # Case 2: Object rule (recursively process children, don't delete directory itself)
    if isinstance(rule, dict):
        for name, sub_rule in rule.items():
            sub_relative_path = f"{relative_path}/{name}" if relative_path else name
            process_rule(base_path, sub_relative_path, sub_rule)
        return

    # Case 3: Array rule (whitelist/blacklist mode)
    if isinstance(rule, list):
        if len(rule) != 2:
            logger.warning(f"Incorrect array rule format at {relative_path}")
            return

        mode: str = rule[0]  # "preserve" or "delete"
        declarations: Dict[str, JsonValue] = rule[1]

        if not isinstance(mode, str) or mode not in ("preserve", "delete"):
            logger.warning(f"Unknown mode '{mode}' at {relative_path}")
            return

        if not isinstance(declarations, dict):
            logger.warning(f"Declaration list is not an object at {relative_path}")
            return

        # Check if directory exists
        if not current_path.exists():
            logger.warning(f"Directory does not exist: {relative_path}")
            return

        if not current_path.is_dir():
            logger.warning(f"Path is not a directory: {relative_path}")
            return

        # Get all actual files and subdirectories in the directory
        existing_items = {item.name for item in current_path.iterdir()}
        declared_items = set(declarations.keys())

        if mode == "preserve":
            # Whitelist mode: delete undeclared items
            items_to_delete = existing_items - declared_items

            for item_name in items_to_delete:
                delete_path(current_path / item_name)

            # Process items in declaration list (may have nested rules)
            for item_name, sub_rule in declarations.items():
                item_relative_path = f"{relative_path}/{item_name}" if relative_path else item_name
                process_rule(base_path, item_relative_path, sub_rule)

        elif mode == "delete":
            # Blacklist mode: only process declared items
            for item_name, sub_rule in declarations.items():
                item_relative_path = f"{relative_path}/{item_name}" if relative_path else item_name
                process_rule(base_path, item_relative_path, sub_rule)

        return


def modify_pack_mcmeta(pack_root: Path) -> None:
    """
    Modify pack.mcmeta file by adding a prefix to the description and modifying second line

    Args:
        pack_root: Resource pack root directory
    """
    pack_meta_path: Path = pack_root / "pack.mcmeta"

    if not pack_meta_path.exists():
        logger.warning("pack.mcmeta does not exist, skipping modification")
        return

    try:
        # Read pack.mcmeta
        with pack_meta_path.open("r", encoding="utf-8") as f:
            pack_data: Dict[str, Any] = json.load(f)

        # Check and modify description
        if "pack" in pack_data and "description" in pack_data["pack"]:
            original_desc: str = pack_data["pack"]["description"]
            prefix: str = "§dMINI §7"
            second_line: str = "§8modified by §7TunaFish2K"

            # Split description into lines
            lines = original_desc.split("\n")

            # Add prefix to first line if not already present
            if not lines[0].startswith(prefix):
                lines[0] = prefix + lines[0]

            # Replace or add second line
            if len(lines) >= 2:
                lines[1] = second_line
            else:
                lines.append(second_line)

            # Merge lines back
            new_desc = "\n".join(lines)

            # Only write if description changed
            if new_desc != original_desc:
                pack_data["pack"]["description"] = new_desc

                # Write back to file, maintaining formatting
                with pack_meta_path.open("w", encoding="utf-8") as f:
                    json.dump(pack_data, f, indent=2, ensure_ascii=False)
        else:
            logger.warning("pack.mcmeta format is incorrect, missing pack.description field")

    except json.JSONDecodeError as e:
        logger.error(f"pack.mcmeta is not a valid JSON file: {e}")
    except Exception as e:
        logger.error(f"Error occurred while modifying pack.mcmeta: {e}")


def modify_credits(pack_root: Path, script_root: Path) -> None:
    """
    Modify credits.txt file by adding attribution at the end

    Args:
        pack_root: Resource pack root directory
        script_root: Script root directory (where credits.txt template is located)
    """
    credits_path: Path = pack_root / "credits.txt"
    signature_path: Path = script_root / "credits.txt"

    # Read signature from root credits.txt
    if not signature_path.exists():
        logger.warning("credits.txt template not found in script directory, skipping")
        return

    try:
        with signature_path.open("r", encoding="utf-8") as f:
            signature: str = f.read().strip()

        # Check if file exists
        if credits_path.exists():
            # Read existing content
            with credits_path.open("r", encoding="utf-8") as f:
                content: str = f.read()

            # Check if attribution already exists
            if signature in content:
                return

            # Add attribution with blank line before
            new_content: str = content.rstrip() + "\n\n" + signature + "\n"

            with credits_path.open("w", encoding="utf-8") as f:
                f.write(new_content)
        else:
            # Create new file
            with credits_path.open("w", encoding="utf-8") as f:
                f.write(signature + "\n")

    except Exception as e:
        logger.error(f"Error occurred while modifying credits.txt: {e}")


def copy_overrides(script_dir: Path, target_dir: Path) -> None:
    """
    Copy contents of overrides folder under script directory to target directory

    Args:
        script_dir: Script directory
        target_dir: Target directory (resource pack root directory)
    """
    overrides_dir: Path = script_dir / "overrides"

    if not overrides_dir.exists():
        logger.warning("overrides directory does not exist, skipping override step")
        return

    if not overrides_dir.is_dir():
        logger.warning("overrides is not a directory, skipping override step")
        return

    # Iterate through all contents in overrides directory
    for item in overrides_dir.rglob("*"):
        if not item.is_file():
            continue

        # Calculate relative path
        relative_path: Path = item.relative_to(overrides_dir)
        target_path: Path = target_dir / relative_path

        # Create target directory
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        shutil.copy2(item, target_path)


def main() -> int:
    """
    Main function

    Returns:
        Exit code (0 for success)
    """
    parser = ArgumentParser(
        description="Delete files in Minecraft resource pack according to delete.json and override with overrides contents"
    )
    parser.add_argument(
        "pack_dir",
        type=Path,
        help="Resource pack directory path (directory containing pack.mcmeta or with pack.mcmeta in subdirectories)"
    )
    parser.add_argument(
        "--type",
        choices=["legacy", "modern"],
        default="legacy",
        help="Resource pack type (legacy or modern), default: legacy"
    )

    args: Namespace = parser.parse_args()

    # Configure logging - only warnings and errors
    logging.basicConfig(
        level=logging.WARNING,
        format='%(levelname)s: %(message)s'
    )

    # Get script root directory (where patch.py is located)
    script_root: Path = Path(__file__).parent

    # Get script directory based on pack type
    if args.type == "legacy":
        script_dir: Path = script_root / "legacy"
    else:
        script_dir: Path = script_root / "modern"

    # Read configuration file (always use delete.json in script directory)
    config_path: Path = script_dir / "delete.json"
    if not config_path.exists():
        logger.error(f"Configuration file does not exist: {config_path}")
        return 1

    with config_path.open("r", encoding="utf-8") as f:
        config: Dict[str, Any] = json.load(f)

    # Find pack.mcmeta
    pack_dir: Path = args.pack_dir
    pack_root: Path | None = find_pack_mcmeta(pack_dir)
    if pack_root is None:
        logger.error("pack.mcmeta file not found")
        return 1

    # Verify assets directory exists
    assets_dir: Path = pack_root / "assets"
    if not assets_dir.exists():
        logger.error(f"assets directory does not exist: {assets_dir}")
        return 1

    # Configuration file should start with "assets" key
    if "assets" not in config:
        logger.error("Configuration file format error, missing 'assets' key")
        return 1

    # Process all rules under assets
    assets_rules: Dict[str, Any] = config["assets"]
    for namespace, rules in assets_rules.items():
        process_rule(assets_dir, namespace, rules)

    # Override with overrides contents
    copy_overrides(script_dir, pack_root)

    # Modify pack.mcmeta description
    modify_pack_mcmeta(pack_root)

    # Modify credits.txt
    modify_credits(pack_root, script_root)

    print("Complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
