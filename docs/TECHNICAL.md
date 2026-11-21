# 技术原理与适配记录

本文记录把 GhostLock 临时 root 与 BakaSU/KernelSU LKM 装进这台 Honor 内核时遇到的每一道关卡，以及仓库里对应脚本的位置。定位是**适配记录**，不是漏洞分析：漏洞原语来自上游已公开的 GhostLock（CVE-2026-43499）。

## 整体链路

```
PC (kit.ps1)
  │  adb push 载荷 / 脚本
  ▼
Stage A (kit-root.sh)
  magic5-root.so --unpack-only  →  glk-bin / helper / su / su-perm
  GLK_ZERO_ADDR=<名义地址> glk-bin --load-prebuilt-profile profile_175.bin
      → 临时 uid=0，同时把 sig_enforce 清零
  su -c 'echo 0 > /proc/sys/kernel/kptr_restrict; cat /proc/kallsyms'  →  ks.txt
  ▼
PC (kit.ps1 / Patch-Module)
  读取 ks.txt（约 59 万行）→ 把 .ko 中约 208 个 UNDEF 符号改写为
  SHN_ABS + 本次开机 KASLR 绝对地址 → 得到打过补丁的 .ko
  ▼
Stage B (kit-load.sh)
  kmsgsync 后台落盘内核日志 + 后台 insmod（避免 oops 时 adb 永不返回）
  ▼
KSU 接管 root → 管理器显示「工作中 · LKM · 越狱模式」
```

## 关卡与解法

| # | 关卡 | 现象 | 解法 | 对应文件 |
|---|---|---|---|---|
| 1 | 模块签名强制 | `insmod` 返回 `EKEYREJECTED`；每次开机 `sig_enforce` 复位为 Y | 用 GhostLock 任意写把 `sig_enforce` 清零 | `kit-root.sh`、`scripts/device/pb.sh` |
| 2 | 符号未导出 | `Unknown symbol avtab_search_node` 等约 208 个 | 从 `/proc/kallsyms` 取地址，把 ELF 符号表 UNDEF 项改成 `SHN_ABS` 绝对符号 | `scripts/host/patch_ko_kallsyms.py`、`kit/tools/kit.ps1` 的 `Patch-Module` |
| 3 | 结构体布局不符 | 模块把 `init_task.mm`（NULL）当链表头，读 `NULL+0x320` 后 panic | 用设备 BTF 对齐 `task_struct` / `struct module`，203 + 95 个 `_Static_assert` 校验 | `scripts/build/` 全部脚本 |
| 4 | `struct inode` 偏移不符 | `ksu_observer_init()` 里 `fsnotify_add_mark` 收到错误 connp，NULL deref | 直接 `return 0` 禁用 observer（它只监听 `packages.list`，不影响 root/su） | `scripts/patches/patch_observer.py` |
| 5 | `crypto_shash` 布局不符 | `apk_sign.c` 的 `crypto_free_shash()` 崩溃 | 用自带 SHA-256 实现（含 55/56/63/64/119/120 字节边界自测）替换该路径 | `scripts/patches/patch_sha256.py` |
| 6 | 版本 / UAPI 不一致 | 管理器红条「需要更新内核」、`isFullFeatured` 为 false | Kbuild 版本 4471→4557、固定 `KSU_TAG_NAME=v4.2.0-rc3` 与 commit sha、`KERNEL_SU_UAPI_VERSION = 6` | `scripts/build/dev_ver.sh`、`dev_uapi.sh`、`scripts/patches/patch_ver.py` |
| 7 | SELinux 策略不兼容 | 重载策略后 `avc: denied { send } ... tcontext=unlabeled`，WiFi / 数据「有信号、有 IP、全都不通」 | late-load 末尾**不恢复 enforcing**，保持 Permissive | `scripts/patches/patch_permissive.py` |
| 8 | 提权成功率低 | profile 默认 `prepare_max_attempts=4`，多次失败 | 改成 60；并在 kit 中显式传随包 profile 而非内嵌旧版 | `profiles/profile_175.conf`、`kit-root.sh` |
| 9 | oops 时 adb 卡死 | 前台 `insmod` 触发 oops 后命令永不返回 | `setsid` 后台 insmod + `insmod.rc` 记录返回码；`kmsgsync` 把内核日志同步落盘 | `src/kmsgsync.c`、`kit-load.sh` |
| 10 | PC 端零依赖 | 分享包不想要求用户装 Python | 把 ELF64 kallsyms 补丁器完整移植进 PowerShell 5.1，输出与 Python 版逐字节一致 | `kit/tools/kit.ps1` |

## 几个容易踩的点

- **KASLR 每次开机都变**：`ks.txt` 与 `.ko` 补丁必须在**同一开机周期**内生成。重启后必须重新导出、重新打补丁，`kit.ps1` 每次运行都会重做。
- **`GLK_ZERO_ADDR` 用名义地址**：`0xffffffc0830c7708` 是 `KIMAGE_TEXT_BASE + 0x30c7708`，exploit 内部按本次 KASLR 通过 `data_alias()` 换算；传真实地址会被 W1c 校验拒绝。
- **文件格式**：`.bat` 必须 GBK + CRLF（cmd 默认代码页 936，中文窗口标题才不乱码）；`kit.ps1` 必须 UTF-8 BOM（PowerShell 5.1 否则按 ANSI 读中文）；设备端 `.sh` 必须 LF。
- **`hwtransport.exe` 抢 5037**：荣耀电脑管家会占用 adb 端口，`adb.sh` / `kit.ps1` 会尝试结束它并重启 adb server。
- **Permissive 窗口内新建文件没有 SELinux 标签**：复用固定日志名会被 enforcing 静默丢弃，所以 `kit-load.sh` 每次用唯一文件名。
- **`/system/bin/su` 不存在是设计**：`sucompat` 用 execve 钩子按管理器授权列表放行；未授权 uid 落到原路径，表现为 `inaccessible or not found`。

## 已验证的状态

真机冷启动全流程实测通过：机型 / 内核匹配 → 临时 root `uid=0` → `sig_enforce=N` → kallsyms 591599 行 → 208 个未定义符号中 207 个改写为绝对地址（`commit_creds` 交内核 `__ksymtab`）→ insmod 后 `kernelsu ... Live` → 管理器显示 `35257/6`、无红条 → SELinux Permissive → `ping 223.5.5.5` 0% 丢包、5G/WiFi 正常。

## 未落地方向

- **手机端 WiFi 配对提权 APK**：AOSP 无线配对的 SPAKE2 密码 = 配对码 + TLS exporter 64 字节，Java `SSLSocket` 不暴露 exporter，需要 BoringSSL native 实现。该方向已中止，**成品不含此能力**，调研来源见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。
- **回到 Enforcing**：需要对齐 Honor HKIP 定制 `policydb` / `selinux_policy` / `sidtab` 结构布局，当前以保持 Permissive 换取网络可用。
