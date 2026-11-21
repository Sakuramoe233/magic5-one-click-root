# kit/payload/

设备端脚本与载荷。所有 `.sh` 必须是 **LF** 换行，否则 `/system/bin/sh` 会报 `\r: not found`。

| 文件 | 收录 | 说明 |
|---|---|---|
| `kit-root.sh` | ✅ | Stage A：解包载荷 → 临时 root → 清 `sig_enforce` → 导出本次开机 kallsyms |
| `kit-load.sh` | ✅ | Stage B：`kmsgsync` 落盘内核日志 + 后台 `insmod` + `insmod.rc` 记录返回码 |
| `magic5-root.so` | ❌ | 单文件 root 载荷（GhostLock 衍生，Apache-2.0） |
| `profile_175.bin` | ❌ | 内核 profile（`prepare_max_attempts=60`），文本版见 `profiles/profile_175.conf` |
| `ksu-magic5-35257-uapi6.ko` | ❌ | KSU 内核模块（BakaSU kernel/ 衍生，GPL-2.0） |
| `kmsgsync` | ❌ | 由 `src/kmsgsync.c` 编译的内核日志同步工具 |
| `ReSukiSU-4.2.0-rc3.apk` | ❌ | 上游官方管理器（GPL-3.0） |

未收录的二进制由 GitHub Releases 提供，或按 [docs/BINARY_SOURCES.md](../../docs/BINARY_SOURCES.md) 自行生成 / 获取后放到本目录。
