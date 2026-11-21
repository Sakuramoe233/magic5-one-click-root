# kit/tools/

PC 端主流程与 adb。

| 文件 | 说明 |
|---|---|
| `kit.ps1` | 主流程（PowerShell 5.1）：机型/内核硬校验、adb 通信、`Patch-Module` ELF64 kallsyms 补丁器、日志、状态检查、自动安装管理器。文件必须为 **UTF-8 BOM** |
| `adb.exe`、`AdbWinApi.dll`、`AdbWinUsbApi.dll` | **不在本仓库中**（见 `.gitignore`）。来自 [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools)，从官方下载或本项目 Release ZIP 中提取后放到本目录 |

完整说明见 [../../docs/BINARY_SOURCES.md](../../docs/BINARY_SOURCES.md)。

`kit.ps1` 命令行参数：

```
-Status      只读状态检查
-RootOnly    只取临时 root，不加载模块
-Shell       取到 root 后进交互式 shell
-Module x.ko 指定另一个已编译好的模块
-Force       跳过机型/内核校验（危险，请勿使用）
```
