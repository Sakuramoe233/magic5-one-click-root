# Magic5 一键临时提权（PC / USB 版）

> by：夜空的花火i
>
> 仓库：<https://github.com/Sakuramoe233/magic5-one-click-root>

针对 **荣耀 Magic5（PGT-AN00）某一特定内核构建** 的临时 root 工具。电脑插上 USB 数据线，双击一个批处理，手机由 KernelSU 系（BakaSU / ReSukiSU）接管 root。

**不解锁 Bootloader、不刷写 boot 分区、不改动系统分区**，一切只发生在内存与 `/data/local/tmp`。因此**每次手机重启后 root 都会消失，需要重新运行一次**。

本项目是**适配性工程，不是新的漏洞研究**。提权原语完全复用已公开的 [GhostLock](https://github.com/YuKongA/ghostlock-app)（CVE-2026-43499），内核 root 方案来自 [BakaSU / ReSukiSU](https://github.com/Baka-SU/BakaSU) 与 [KernelSU](https://github.com/tiann/KernelSU)。本仓库的工作是把这两者在这台 Honor 内核上跑通：BTF 结构体布局对齐、按本次开机 KASLR 重定位模块符号、关闭模块验签、处理 SELinux 兼容，以及封装一个免安装的 PC 端一键脚本。

完整的开源引用、许可证与二进制资产来源见 **[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)**。

---

## ⚠️ 硬性适配条件（务必先读）

| 项目 | 值 |
|---|---|
| 机型 | HONOR Magic5 `PGT-AN00` |
| 内核 `uname -r` | `5.15.180-android13-8-g1c54d617912d` |
| 系统 | 与该内核对应的同一版 MagicOS（10.0.0.175） |
| 电脑 | Windows 10/11，自带 PowerShell 5.1，USB 数据线 |
| 手机 | 已打开「USB 调试」，BL 锁定 / AVB green 均可 |

模块内 `task_struct` / `struct module` / `policydb` 的结构偏移、KASLR 常量、符号地址都是针对**这一颗内核**实测对齐的。换机型、换系统 OTA 之后内核变了，**直接运行会 oops 并可能从内核重启，甚至造成数据丢失**。`kit.ps1` 会先核对 `uname -r` 与机型，不匹配就主动停止（只有显式 `-Force` 才放行，请不要用）。

---

## 快速开始

1. 从本仓库 [Releases](https://github.com/Sakuramoe233/magic5-one-click-root/releases) 下载 `Magic5一键提权-USB调试版.zip`，解压到任意目录。
2. 手机：设置 → 关于手机 → 连点版本号 7 次 → 开发者选项 → 打开「USB 调试」。
3. 数据线连接，解锁屏幕，弹出「允许 USB 调试」时勾选「一律允许」。
4. 首次连接若电脑没有 ADB 驱动，先装包内 `usb_driver`（设备管理器手动指向该目录）。
5. 双击 **`一键提权.bat`**，等窗口跑完（约 1–2 分钟）。
6. 打开手机上的 ReSukiSU / BakaSU，应显示「工作中 · LKM · 越狱模式」。

工具包自带 adb 与全部载荷，**不需要在电脑上安装 Python / Java / Android SDK / adb**，绿色免安装。

三个入口：

| 入口 | 作用 |
|---|---|
| `一键提权.bat` | 完整流程：临时 root → 关模块验签 → 导出 kallsyms → 按 KASLR 重写模块符号 → insmod → 交给管理器 |
| `仅临时root.bat` | 只取 adb shell 的 root，不加载 KSU 模块 |
| `查看状态.bat` | 只读检查：机型、内核、SELinux、模块状态、管理器状态 |

命令行：`tools\kit.ps1 -Status` / `-RootOnly` / `-Shell` / `-Module x.ko`。

更多细节见 [docs/USAGE.md](docs/USAGE.md)。

---

## 它做了什么

1. 用 GhostLock 的漏洞原语取得临时 root，同时把模块验签开关 `sig_enforce` 清零（每次开机都会复位）。
2. 以 root 导出 `/proc/kallsyms`（约 59 万行）—— Honor 内核只导出一部分符号，直接 `insmod` 会报 `Unknown symbol`。
3. 把 `kernelsu.ko` 中约 208 个未定义符号改写成 `SHN_ABS` 绝对符号，地址取本次开机的 KASLR 实际值。此逻辑已用 PowerShell 在 `kit.ps1` 中重写，PC 端无需 Python。
4. 后台 `insmod` 装载（异步执行，避免 oops 时 adb 永不返回），KSU 接管 root。
5. 保持 SELinux **Permissive**：这台 Honor 的 SELinux 是 HKIP 定制策略，KSU 按 AOSP 布局重载策略会把网络包标成 `unlabeled`，导致 WiFi/数据「有信号、有 IP、全都不通」。这是功能取舍，不是疏漏。

技术细节见 [docs/TECHNICAL.md](docs/TECHNICAL.md)，复现编译见 [docs/BUILD.md](docs/BUILD.md)。

---

## 仓库结构

```
kit/          分享即用工具包的文本部分（bat / kit.ps1 / 设备端 sh / 说明）
scripts/host/     PC 端 Python 工具（kallsyms 补丁、profile 处理、日志抓取等）
scripts/device/   设备端 shell（取 root、装载、重启后恢复）
scripts/build/    内核编译与 BTF 布局对齐（_Static_assert 校验）
scripts/patches/  对上游 BakaSU/KernelSU 源码的适配补丁脚本
src/              自研 C 源码（单文件 root 载荷打包器、helper、su、kmsg 同步）
profiles/         GhostLock HOCON 内核 profile（文本）
licenses/         上游许可证原文备份
docs/             使用、构建、技术原理、二进制来源
```

**本仓库不含**第三方二进制（`.ko` / `.so` / `.apk` / `adb.exe` / USB 驱动 / `profile_175.bin`）、内核源码树、NDK、Termux 工具链、kallsyms 快照与调试日志。成品 ZIP 与二进制资产通过 [GitHub Releases](https://github.com/Sakuramoe233/magic5-one-click-root/releases) 分发，获取方式见 [docs/BINARY_SOURCES.md](docs/BINARY_SOURCES.md)。

---

## 开源引用速览

本项目直接依赖或引用了以下开源项目，**各项的完整信息（上游地址、许可证、使用方式、是否修改）见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)**：

| 项目 | 许可证 | 在本项目中的作用 |
|---|---|---|
| [GhostLock](https://github.com/YuKongA/ghostlock-app) | Apache-2.0 | CVE-2026-43499 临时 root 原语、kernel profile 格式、`ghostlock` 二进制 |
| [BakaSU（原 ReSukiSU）](https://github.com/Baka-SU/BakaSU) | kernel `GPL-2.0-only`；其余 `GPL-3.0-or-later` | KSU 内核模块源码基线、管理器 APK、`ksud` |
| [KernelSU](https://github.com/tiann/KernelSU) | `GPL-3.0-or-later`（kernel/ 为 GPL-2.0） | 最上游的 kernel root 方案 |
| [SukiSU-Ultra](https://github.com/SukiSU-Ultra/SukiSU-Ultra) | GPL 系 | BakaSU 的 fork 来源 |
| [Android Common Kernel](https://android.googlesource.com/kernel/common) `android13-5.15-lts` | GPL-2.0 | 编译 LKM 的内核源码树、`.config`、BTF |
| AOSP / BoringSSL / fiat-crypto | Apache-2.0 等 | WiFi 配对 SPAKE2 协议调研（未落地为成品） |
| Android NDK / SDK Platform Tools / Google USB Driver | 各自 SDK 许可 | 交叉编译、adb、USB 驱动（工具与随包二进制，不入库） |
| Termux / termux-packages、Eclipse Temurin JDK 17 | 各自许可证 | 设备端与 PC 端构建工具链（不分发） |

---

## 免责声明

- **仅用于你本人拥有、且你有权修改的设备。** 请勿用于他人设备或任何未授权场景。
- 本项目复用的是**上游已公开**的漏洞利用与 root 方案，不提供任何新的漏洞、不绕过账号/DRM/设备保护机制。
- 加载内核模块会改变内核运行行为，工具会让 SELinux 停留在 Permissive、关闭模块签名强制，**存在系统不稳定、数据丢失、安全风险**。重要资料请先备份。
- 工具为「临时」root：不持久化、不写 boot 分区；重启手机且不运行本工具时，系统恢复原状（SELinux 回到 Enforcing）。
- 作者与贡献者对使用本工具造成的任何损坏、数据丢失或违反厂商条款不承担责任。**使用即表示你已理解并接受上述风险。**

---

## 许可证

本仓库中**自研的脚本、补丁与文档**采用 **Apache-2.0**，见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。

第三方组件**各自保留其原许可证**，本项目不对其重新授权；应用 `scripts/patches/` 中的补丁后生成的 `kernelsu.ko` 属于 GPL-2.0 衍生作品，须遵守对应上游许可证。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
