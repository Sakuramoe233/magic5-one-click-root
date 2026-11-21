# 第三方开源引用与许可证声明

本文件列出 **Magic5 一键临时提权** 项目所引用、复用、修改或随包分发的全部第三方开源组件。各组件的权利归其原作者所有，本项目**不对任何第三方组件重新授权**。

> 说明：本项目是适配性工程。漏洞利用原语与内核 root 方案分别来自下列已公开项目；本仓库新增的是「让它们在这台 Honor 内核上协同工作」的适配脚本、补丁与封装。

---

## 一、直接依赖（本项目对其源码或产物有修改 / 衍生）

### 1. GhostLock（`ghostlock-app`）

| | |
|---|---|
| 上游 | <https://github.com/YuKongA/ghostlock-app> |
| 许可证 | **Apache-2.0**（原文备份：[licenses/Apache-2.0-GhostLock.txt](licenses/Apache-2.0-GhostLock.txt)） |
| 用途 | 利用 **CVE-2026-43499** 在受支持内核上取得临时 root；提供 kernel profile 的 HOCON 格式、`ghostlock` 原生二进制、`ghostlock-extract` 偏移提取工具、内置 kernel profiles 集合 |
| 本项目中的形态 | `profiles/profile_175.conf`（该内核的 HOCON profile）、`src/glk_so.c` / `src/glk_helper.c` / `src/glk_su.c` / `scripts/host/build_so.py` 打包出的单文件载荷 `magic5-root.so`、Release 包中的 `profile_175.bin` |
| 修改 / 衍生 | ① 基于上游 profile 生成本机 profile，并把 `prepare_max_attempts` 从 4 调整为 60 以提高成功率；② 把上游 `ghostlock` 二进制、helper、`su`、`su-perm` 与 profile 重打包为**单文件自解包载荷**（`--unpack-only` 模式），以适应 permissive 窗口内 SELinux 标签丢失的环境；③ `scripts/device/kit-root.sh` 显式传入随包 profile 而非使用内嵌旧版 |
| 义务 | 保留 Apache-2.0 许可证与 NOTICE、标注修改；`magic5-root.so` 属于衍生作品，随 Release 分发时须附带本文件与 LICENSE |

上游项目自身也引用了 KernelSU / SukiSU-Ultra / BakaSU / KowSU 等 root 管理器，以及其 `docs/` 中的移植指南，此处一并致谢。

### 2. BakaSU（原名 ReSukiSU）

| | |
|---|---|
| 上游 | <https://github.com/Baka-SU/BakaSU>（前身 <https://github.com/ReSukiSU/ReSukiSU>）；本项目源码取自仓库树 `7b65bde0710b5e7c6f755545cb15a4abd417f3a8` 附近的快照 |
| 许可证 | **`kernel/` 目录：GPL-2.0-only**；**其余部分：GPL-3.0-or-later**；图标 / 美术资源另见上游 `ASSETS_LICENSE.md`（作者 OukaroMF，分层授权）。原文备份：[licenses/GPL-2.0-BakaSU-kernel.txt](licenses/GPL-2.0-BakaSU-kernel.txt)、[licenses/GPL-3.0-BakaSU.txt](licenses/GPL-3.0-BakaSU.txt) |
| 用途 | 本项目 `kernelsu.ko` 的源码基线；管理器 `com.resukisu.resukisu`（`ReSukiSU-4.2.0-rc3.apk`）、`ksud` / `libksud.so`、UAPI 定义、管理器与内核侧版本校验逻辑 |
| 修改 / 衍生 | 通过 `scripts/patches/` 中的补丁脚本对上游内核源码做适配：<br>• `patch_observer.py` —— 因 `struct inode` 布局不符，禁用 `ksu_observer_init()` 的 fsnotify mark；<br>• `patch_sha256.py` —— 用自带 SHA-256 实现替换 `apk_sign.c` 的 `crypto_shash` 路径，规避 `crypto_free_shash()` 布局崩溃；<br>• `patch_ver.py` / `dev_ver.sh` —— 对齐 Kbuild 版本与 `KSU_TAG_NAME`，使内核版本 `35257` 与管理期一致；<br>• `dev_uapi.sh` —— 固定 `KERNEL_SU_UAPI_VERSION = 6`，消除管理器红条；<br>• `patch_permissive.py` —— late-load 末尾不再恢复 enforcing（见「SELinux」说明）；<br>• 结构体布局由 `scripts/build/` 按设备 BTF 对齐（`task_struct` / `struct module` 等，203 + 95 个 `_Static_assert` 校验） |
| 产物 | `ksu-magic5-35257-uapi6.ko`（**GPL-2.0 衍生作品**）。其对应源码 = 上游 `kernel/` 快照 + 本仓库 `scripts/patches/` 全部补丁 + `scripts/build/` 布局修正；源码获取方式见 [docs/BINARY_SOURCES.md](docs/BINARY_SOURCES.md) |
| 义务 | 分发该 `.ko` 二进制须按 GPL-2.0 提供对应源码、保留版权声明与许可证；管理器 APK 按 GPL-3.0-or-later |

### 3. Android Common Kernel（ACK）`android13-5.15-lts`

| | |
|---|---|
| 上游 | <https://android.googlesource.com/kernel/common>（分支 `android13-5.15-lts`）；设备侧 `/proc/config.gz`、`/sys/kernel/btf/vmlinux` |
| 许可证 | **GPL-2.0**（Linux 内核） |
| 用途 | 编译 LKM 所需的内核源码树、真实构建配置、BTF 类型信息（用于校验 `task_struct` / `struct module` 等结构偏移） |
| 修改 / 衍生 | `scripts/build/prepare_kernel.sh`、`patch_scripts_mk.py`、`fix_selinux_tools.py` 等：裁剪 `scripts/`、为 SELinux `genheaders` 增加 `-idirafter`、定义 `-Dbcmp=memcmp` 等，使内核树能在设备端 Termux 工具链中编译 |
| 说明 | 内核源码树（约 1.8 GB）、`magic5-config.gz`、`vmlinux.btf` **不纳入本仓库**，仅提供获取与复现步骤 |

---

## 二、间接引用（上游项目的上游 / 协议来源）

| 项目 | 上游 | 许可证 | 关系 |
|---|---|---|---|
| KernelSU | <https://github.com/tiann/KernelSU> | **GPL-3.0-or-later**（其 `kernel/` 为 GPL-2.0；原文备份见 `licenses/` 中 GPL-3.0 文本） | 最上游的 kernel-based root 方案；BakaSU 的下游基线、LKM 加载 / syscall hook / tracepoint hook / sucompat / ksud / UAPI 的设计来源 |
| SukiSU-Ultra | <https://github.com/SukiSU-Ultra/SukiSU-Ultra> | GPL 系（kernel GPL-2.0） | ReSukiSU / BakaSU 的 fork 来源 |
| suSFS | <https://gitlab.com/simonpunk/susfs4ksu> | GPL-2.0 | BakaSU 支持的 `SUSFS Inline Hook` 来源；**本项目未启用**，仅作上游关系说明 |
| Kernel-Assisted Superuser | <https://git.zx2c4.com/kernel-assisted-superuser/about/> | — | KernelSU 思路来源（BakaSU 上游 Credit 中列出） |
| Magisk | <https://github.com/topjohnwu/Magisk> | GPL-3.0 | BakaSU 上游 Credit 中列出 |
| genuine | <https://github.com/brevent/genuine/> | GPL-3.0 | APK v2 签名校验思路（BakaSU 上游 Credit 中列出） |
| Diamorphine | <https://github.com/m0nad/Diamorphine> | GPL-2.0 | 内核 hook 技巧参考（BakaSU 上游 Credit 中列出） |

### AOSP / BoringSSL / fiat-crypto（调研参考，未进入成品）

| | |
|---|---|
| 上游 | AOSP `platform/external/boringssl`、AOSP pairing / SPAKE2 相关代码、<https://github.com/mit-plv/fiat-crypto> |
| 许可证 | Apache-2.0 / BoringSSL 混合许可（含 OpenSSL 遗留条款）/ fiat-crypto MIT 等，以各上游为准 |
| 用途 | 曾用于调研「手机端通过 WiFi 配对调试实现一键提权」的 APK 方案：AOSP 无线配对的密码为「配对码 + TLS exporter 64 字节」，SPAKE2 曲线运算参考 curve25519 实现。**该方向因 Java `SSLSocket` 不暴露 TLS exporter、需要 BoringSSL native 实现而中止，未纳入任何分发产物** |
| 说明 | 本仓库不包含这些代码，仅在此说明调研来源，避免读者误以为成品包含该能力 |

---

## 三、构建工具与随包分发的第三方二进制（不纳入 git 仓库）

这些组件不被本仓库收录，但成品 ZIP 中包含其官方二进制，或在复现过程中需要用到。使用者应从各自官方渠道获取并遵守其许可条款。

| 组件 | 来源 | 许可证 / 条款 | 在成品中的位置与用途 |
|---|---|---|---|
| Android SDK Platform Tools（`adb.exe`、`AdbWinApi.dll`、`AdbWinUsbApi.dll`） | <https://developer.android.com/tools/releases/platform-tools> | Android SDK 许可协议；`adb` 源码位于 AOSP，Apache-2.0 | `tools/`，PC 与手机的 USB 通信。免安装工具包自带，避免用户装 SDK |
| Google USB Driver | <https://developer.android.com/studio/run/win-usb> | Android SDK 许可协议 | `usb_driver/`，Windows ADB 驱动 |
| Android NDK r27c | <https://developer.android.com/ndk> | Android NDK 许可（部分组件 Apache-2.0） | 交叉编译 arm64 的 helper / `magic5-root.so` / `kmsgsync`（工具，不分发） |
| Termux / termux-packages | <https://github.com/termux/termux-packages> | 各包各自许可证（LLVM/Clang 等） | 手机端原生编译工具链（clang、make、bison、flex、python）（工具，不分发） |
| Eclipse Temurin JDK 17 | <https://github.com/adoptium/jdk17u> | GPLv2 + Classpath Exception | APK / DEX 分析辅助（工具，不分发） |
| Python 3 | <https://www.python.org/> | PSF License | 开发 / 构建脚本运行时（成品不需要） |
| PowerShell 5.1 / .NET Framework | Microsoft（Windows 系统组件） | 系统组件 | PC 端主流程 `kit/tools/kit.ps1` 的运行时 |

> **关于再分发**：`adb.exe`、USB 驱动与管理器 APK 均为第三方官方构建产物。本仓库不把它们纳入版本控制；成品 ZIP 中随附时保留原文件名、未作修改，并在此注明出处。若你需要以更严格的方式合规分发，可从 Release 包中移除这些文件，改为按 [docs/BINARY_SOURCES.md](docs/BINARY_SOURCES.md) 从官方渠道获取后放入对应目录。

---

## 四、本项目自研部分

以下为本仓库新增、由本项目作者编写的内容，采用 **Apache-2.0**（见根目录 `LICENSE` / `NOTICE`）：

- `kit/`：PC 端 PowerShell 主流程、三个批处理入口、设备端 `kit-root.sh` / `kit-load.sh`、中文使用说明；其中 `kit.ps1` 内含 ELF64 kallsyms 补丁器（把未定义符号改写为 `SHN_ABS` + 本次开机 KASLR 绝对地址）、机型 / 内核硬校验、日志与状态检查。
- `scripts/host/`、`scripts/device/`、`scripts/build/`、`scripts/patches/`：符号补丁、profile 处理、日志抓取、内核编译适配、BTF 布局对齐与上游源码适配补丁。
- `src/`：单文件 root 载荷打包器、helper / su、内核日志落盘工具。
- `docs/`、根目录 README / 本文件：全部文档。

**自研许可证不延伸至第三方组件**；任何把本仓库自研代码与上述 GPL 组件组合形成衍生作品的使用，须同时遵守对应 GPL 条款。

---

## 五、致谢

感谢 [YuKongA](https://github.com/YuKongA)（GhostLock）、[tiann](https://github.com/tiann)（KernelSU）、SukiSU-Ultra 团队、BakaSU / ReSukiSU 团队，以及 AOSP、Linux 内核、Termux、LLVM 社区的所有贡献者。没有这些公开项目，本适配工作无从谈起。

本项目同时感谢 GhostLock issue 讨论区中关于 `5.15.180` 内核 profile 与补丁几何的公开讨论。
