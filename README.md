# 精简Furfsky Reborn并替换了部分更好看的旧版材质

中文版 | [English](README.en_US.md)
## 生成
通过对Furfsky Reborn原版进行即时修改生成本材质包。  
将原版(Overlay版本)解压，记下文件夹位置(该位置下有`pack.mcmeta`文件)。  
安装Python，运行：
```
# 1.8.9
python patch.py /path/to/original/pack
```
替换`/path/to/original/pack`为实际的路径。

## TBD
- 高版本的实现
- 更清晰的`patch.py`编写。