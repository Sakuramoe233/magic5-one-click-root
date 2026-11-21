# 从源码复现

> 只想使用成品？看 [USAGE.md](USAGE.md) 与 Releases，不需要本文件。
> 本文件描述如何重新生成 `profile_175.bin`、`magic5-root.so`、`kmsgsync` 与 `ksu-magic5-35257-uapi6.ko`。

## 0. 前置条件

| 需要 | 说明 |
|---|---|
| 设备 | HONOR Magic5 `PGT-AN00`，内核 `5.15.180-android13-8-g1c54d617912d`，已开 USB 调试 |
| 设备文件 | `/proc/config.gz`（真实构建配置）、`/sys/kernel/btf/vmlinux`（BTF）、`/proc/kallsyms`（需 root） |
| 源码 | [ACK `android13-5.15-lts`](https://android.googlesource.com/kernel/common) 内核树、[BakaSU](https://github.com/Baka-SU/BakaSU) 源码快照（本项目对应树 `7b65bde…`） |
| 工具链 | 一台 Linux x86_64（或手机 Termux + [Android NDK r27c](https://developer.android.com/ndk)）；`make`、`bison`、`flex`、`python3`、`clang`、`xz`、`lz4`；约 40 GB 磁盘 |
| 上游工具 | [GhostLock](https://github.com/YuKongA/ghostlock-app) 的 `ghostlock-extract`、`ghostlock` 原生二进制与内置 profiles |

本项目的编译环境是「手机端 Termux 原生编译」：Windows 主机没有 make/gcc/docker，因此 `scripts/build/` 里的脚本同时兼顾了 Termux 的目录布局（`/data/local/tmp/tc/usr`）与裁剪内核 `scripts/` 的需要。

## 1. 准备内核树

```bash
bash scripts/build/prepare_kernel.sh          # 解包、裁剪 scripts/
python scripts/build/patch_scripts_mk.py      # 修正 Makefile 依赖
python scripts/build/fix_selinux_tools.py     # genheaders 加 -idirafter / -Dbcmp=memcmp
source scripts/build/env_kernel.sh            # 交叉编译环境变量
```

## 2. 按 BTF 对齐结构体布局（**最关键**）

这台内核是 `KASAN + SCHEDSTATS + SCHED_INFO + TASK_DELAY_ACCT` 全开的构建，`task_struct` 与 GKI 量产 config 差异很大：

| 字段 | 本机真实 | GKI 系 LKM 假设 |
|---|---|---|
| `tasks` | `0x480` | `0x4d0` |
| `mm` | `0x4d0` | `0x520` |
| `nsproxy` | `0x7a0` | `0x7e8` |
| `cred` | `0x750` | `0x7a8` |

不对齐的话模块会把 `init_task.mm`（内核线程为 NULL）当成进程链表头，读 `NULL+0x320` 直接 panic。

```bash
python scripts/build/gen_struct_asserts.py    # 从 vmlinux.btf 生成 ent_asserts.h / sg_asserts.h
python scripts/build/fix_layout.py            # task_struct 偏移
python scripts/build/fix_layout2.py
python scripts/build/fix_module_layout.py     # struct module 偏移
python scripts/build/pad_task.py
bash scripts/build/verify_ko_layout.py <candidate.ko> vmlinux.btf   # 不连设备即可判 ABI 兼容
```

生成了 203 + 95 个 `_Static_assert`，全部通过才算布局对齐。`scripts/build/README.md` 有更详细的现状说明。

## 3. 应用对上游 KSU 源码的适配补丁

按顺序在 BakaSU `kernel/` 源码树上执行：

```bash
python scripts/patches/patch_observer.py       # 禁用 struct inode 布局不符的 fsnotify observer
python scripts/patches/patch_sha256.py         # 自带 SHA-256 替换 crypto_shash 路径
bash   scripts/build/dev_ver.sh                # Kbuild 版本 4471→4557、固定 KSU_TAG_NAME
bash   scripts/build/dev_uapi.sh               # KERNEL_SU_UAPI_VERSION = 6
python scripts/patches/patch_permissive.py     # late-load 末尾保持 permissive
```

各补丁的原因见脚本头部注释与 [TECHNICAL.md](TECHNICAL.md)。

## 4. 编译内核模块

```bash
bash scripts/build/build_lkm.sh ./magic5-config.gz    # Linux 主机路径
# 或 Termux 路径：
bash scripts/build/dev_build.sh
make ... CONFIG_KSU=m CONFIG_KSU_MULTI_MANAGER_SUPPORT=y CONFIG_KSU_TRACEPOINT_HOOK=y
bash scripts/build/dev_strip.sh
```

注意：`CONFIG_KSU*` 不在设备 `.config` 里，必须在 make 命令行显式给出。

## 5. 生成 root 载荷与 profile

```bash
# profile：以 profiles/profile_175.conf 为输入，用 GhostLock 工具导出
# 把 prepare_max_attempts 从 4 改成 60（提高成功率），得到 profile_175.bin
python scripts/host/glk_profile.py ...
python scripts/host/build_so.py          # 打包出单文件 magic5-root.so
# kmsgsync
${NDK}/toolchains/llvm/prebuilt/.../aarch64-linux-android31-clang -static src/kmsgsync.c -o kmsgsync
```

`magic5-root.so` 是单文件自解包载荷，内含 `ghostlock` / `glk-helper-bin` / `su` / `su-perm` / profile。`kit/payload/kit-root.sh` 用 `--unpack-only` 后**显式传入随包的 `profile_175.bin`**，而不是用内嵌的早期 profile。

## 6. 按本次开机的 KASLR 重定位符号（每次开机都要做）

Honor 内核只导出部分符号，直接 insmod 会报 `Unknown symbol`（约 208 个）。`CONFIG_KALLSYMS_ALL=y` 意味着这些符号仍有地址：

```bash
# 同一开机周期内，取得临时 root 后导出
su -c "echo 0 > /proc/sys/kernel/kptr_restrict; cat /proc/kallsyms" > ks.txt
python scripts/host/patch_ko_kallsyms.py kernelsu.ko ks.txt ksu-ready.ko
```

原理：把 ELF 符号表中每个 UNDEF 符号改成 `SHN_ABS` + 本次开机的绝对地址，加载器便不会再走 `resolve_symbol()`。该逻辑已完整移植进 `kit/tools/kit.ps1`（`Patch-Module` 函数），**成品工具包在 PC 端不需要 Python**。

> KASLR 每次开机都变，所以 kallsyms 必须**每次重新导出、重新打补丁**。`GLK_ZERO_ADDR=0xffffffc0830c7708` 是名义地址（`KIMAGE_TEXT_BASE + 0x30c7708`），exploit 内部自行换算；传真实地址会被 W1c 校验拒绝。

## 7. 装载与验证

```bash
su -c "echo 0 > /proc/sys/kernel/panic_on_oops; echo 0 > /proc/sys/kernel/hung_task_panic"
su -c "insmod /data/local/tmp/ksu-ready.ko"     # 必须后台执行，见 kit-load.sh
adb shell ls /sys/module | grep ksu
adb shell getenforce                             # Permissive
adb shell ksud -V                                # uapi 6
adb shell ping -c 3 223.5.5.5                    # 验证网络未被 SELinux 打挂
```

`kit/payload/kit-load.sh` 用 `kmsgsync` + 后台 `insmod` + `insmod.rc` 实现异步装载，避免 init 阶段 oops 时前台 adb 永不返回。

## 8. 打包

按 [BINARY_SOURCES.md](BINARY_SOURCES.md) 把二进制补齐到 `kit/`，压缩成 ZIP 并作为 Release 资产上传。
