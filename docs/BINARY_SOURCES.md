# 二进制资产来源与获取方式

本仓库**只收录文本源码与文档**。下面的文件是成品 ZIP（Release 资产 `Magic5-OneClickRoot-USB-v1.0.0.zip`）中的二进制资产，通过 GitHub Releases 分发，也可按本表从上游 / 源码自行生成。

## 资产清单

| Release 中的路径 | 来源 | 是否修改 | 许可证 / 条款 |
|---|---|---|---|
| `payload/magic5-root.so` | 由本项目 `src/glk_so.c`、`glk_helper.c`、`glk_su.c` 与 `scripts/host/build_so.py` 打包；内含 [GhostLock](https://github.com/YuKongA/ghostlock-app) 的 `ghostlock` 原生二进制、helper、`su` / `su-perm` 与 profile | **是，衍生作品** | Apache-2.0（须保留 LICENSE / NOTICE 并标注修改） |
| `payload/profile_175.bin` | GhostLock kernel profile（本机内核 `5.15.180-android13-8-g1c54d617912d`）；文本版见 [profiles/profile_175.conf](../profiles/profile_175.conf) | **是**：`prepare_max_attempts` 4 → 60 | Apache-2.0 |
| `payload/ksu-magic5-35257-uapi6.ko` | [BakaSU](https://github.com/Baka-SU/BakaSU) `kernel/` 源码，应用 `scripts/patches/` 与 `scripts/build/` 的适配后编译 | **是，衍生作品** | **GPL-2.0-only**；对应源码 = 上游 kernel/ 快照 + 本仓库补丁（见 [BUILD.md](BUILD.md)） |
| `payload/kmsgsync` | 本项目 [`src/kmsgsync.c`](../src/kmsgsync.c) 编译（内核 oops 时把日志同步落盘） | 自研 | Apache-2.0 |
| `payload/ReSukiSU-4.2.0-rc3.apk` | BakaSU / ReSukiSU 官方 Release 的管理器 | 未修改 | GPL-3.0-or-later（美术资源见上游 `ASSETS_LICENSE.md`） |
| `tools/adb.exe`、`AdbWinApi.dll`、`AdbWinUsbApi.dll` | [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools) | 未修改 | Android SDK 许可协议（`adb` 源码为 AOSP / Apache-2.0） |
| `usb_driver/*` | [Google USB Driver](https://developer.android.com/studio/run/win-usb) | 未修改 | Android SDK 许可协议 |

## 自行获取 / 放置

从本仓库 `kit/` 出发，补齐以下文件即可还原完整工具包：

```
kit/tools/adb.exe
kit/tools/AdbWinApi.dll
kit/tools/AdbWinUsbApi.dll
kit/usb_driver/                      # 官方 Google USB Driver 解压
kit/payload/magic5-root.so
kit/payload/profile_175.bin
kit/payload/ksu-magic5-35257-uapi6.ko
kit/payload/kmsgsync
kit/payload/ReSukiSU-4.2.0-rc3.apk
```

- 前四项：从 Google 官方渠道下载官方原版，或从本项目 Release 的 ZIP 中提取。
- `magic5-root.so` / `profile_175.bin` / `.ko`：按 [BUILD.md](BUILD.md) 从源码生成，或从 Release 提取。
- `kmsgsync`：用 NDK 交叉编译 `src/kmsgsync.c`（arm64 静态链接）。

## 合规提示

- `ksu-magic5-35257-uapi6.ko` 是 GPL-2.0 衍生作品。分发该二进制时，须同时提供对应源码或有效的获取途径；本仓库的 `scripts/patches/` + 明确的上游快照引用即为该途径。
- `magic5-root.so` 是 Apache-2.0 衍生作品。分发时须随附 LICENSE、NOTICE 与修改说明（见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)）。
- 若你希望以最保守的方式分发，可只发布**源码仓库**，让用户按上表自行获取第三方二进制；工具包在缺少二进制时会明确报错，不会静默降级。

## 打包成 ZIP

补齐二进制后，用任意压缩工具把 `kit/` 整个目录打包，顶层目录改名为 `Magic5一键提权-USB版` 即可。

> **Release 资产名请用纯 ASCII**（如 `Magic5-OneClickRoot-USB-v1.0.0.zip`）：GitHub 上传 API 会把资产名里的中文字符吞掉，导致下载到的文件名变成 `Magic5.-USB.zip`。ZIP 内部的中文目录名不受影响。

注意：

- 三个 `.bat` 必须保持 **GBK(cp936) + CRLF**，否则中文窗口标题会乱码；
- `tools/kit.ps1` 必须保持 **UTF-8 BOM**，否则 PowerShell 5.1 会把中文按 ANSI 读取；
- `payload/*.sh` 必须是 **LF**，否则设备端 `/system/bin/sh` 会报 `\r: not found`；
- ZIP 中的中文文件名建议带 UTF-8 标志位（0x0800），避免在部分解压工具中乱码。
