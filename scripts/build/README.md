# Magic5 上的 KernelSU / BaKaSU LKM：现状与续做方式

设备：PGT-AN00，内核 `5.15.180-android13-8-g1c54d617912d`（Honor，`CONFIG_KASAN=y` 的构建）

## 一、已经打通的

| 关卡 | 状态 | 做法 |
|---|---|---|
| 内核模块签名强制 | **已绕过** | 用 ghostlock 任意写把 `sig_enforce` 清零（`rb_erase` case-2 relink 形状，target=`S+1` 省掉颜色位） |
| 模块能否加载 | **可以** | 清零后 `insmod` 只 taint 不拒绝；KernelSU 的 `kernelsu_init` 实际跑起来了 |
| 符号解析 | **已解决** | `patch_ko_kallsyms.py` 把 200/201 个未导出符号按本次开机的 `/proc/kallsyms` 写成绝对地址 |

也就是说，“Honor 内核装不了第三方模块”这个结论已经被推翻了。现在只剩最后一关。

## 二、唯一的拦路点：`task_struct` 布局不匹配

用设备自带 BTF（`/sys/kernel/btf/vmlinux`）量出来的真实偏移，与任何官方 LKM 的假设都不同：

| 字段 | 本机真实 | GKI 系 LKM 假设 |
|---|---|---|
| `tasks` | `0x480` | `0x4d0` |
| `mm` | `0x4d0` | `0x520`(推) |
| `nsproxy` | `0x7a0` | `0x7e8` |
| `cred` | `0x750` | `0x7a8`(推) |

崩点因此很具体：模块把 `init_task.mm`（内核线程为 NULL）当成进程链表头，读 `NULL+0x320`。

差异来源：这台内核是 **KASAN + SCHEDSTATS + SCHED_INFO + TASK_DELAY_ACCT** 全开的构建，
这些选项都会往 `task_struct` 里插字段。所以：

- 官方 `lkm-aarch64-android13-5.15_kernelsu.ko`（vermagic `5.15.202-android13-5.15.202_r00-dirty`）不行
- 历史版本 v0.9.0 → v3.3.1 全部不行（都是 GKI 量产 config 编的）
- 只有**用设备自己的 config 编出来的 .ko** 才对得上

## 三、续做：在 Linux 机器上编一份

本机的构建条件不具备（无 make/gcc，WSL 被安全策略禁用），所以这一步需要在
一台 Linux x86_64 机器或 CI 上完成：

```bash
# 需要：git make bc bison flex libssl-dev python3 xz-utils lz4，约 40GB 磁盘
bash build_lkm.sh ./magic5-config.gz
```

编完先做 **ABI 校验**（不用连设备）：

```bash
python verify_ko_layout.py <编出来的 kernelsu.ko> vmlinux.btf
# 输出 [OK] 才能往下走；[FAIL] 说明 config 还没对上
```

## 四、拿到匹配的 .ko 之后（这部分已验证可用）

```bash
# 1) 取临时 root，同时把 sig_enforce 清零（约 20 秒，可能 panic 一次，重跑即可）
GLK_ZERO_LEAF=0 GLK_ZERO_ADDR=0xffffffc0830c7708 /data/local/tmp/magic5-root.so

# 2) 同一次开机内导出符号并打补丁（必须在同一开机周期，KASLR 会变）
su -c "echo 0 > /proc/sys/kernel/kptr_restrict; cat /proc/kallsyms > /data/local/tmp/ks.txt"
adb pull /data/local/tmp/ks.txt
python ../tools/patch_ko_kallsyms.py <kernelsu.ko> ks.txt ksu-ready.ko
adb push ksu-ready.ko /data/local/tmp/

# 3) 让 oops 不再重启整机，便于排错
su -c "echo 0 > /proc/sys/kernel/panic_on_oops; echo 0 > /proc/sys/kernel/hung_task_panic"

# 4) 加载
su -c "insmod /data/local/tmp/ksu-ready.ko; ls /sys/module | grep ksu"
```

加载成功后，ReSukiSU / BaKaSU 管理器应能识别到驱动；若管理器提示版本不匹配，
换成对应版本的 KernelSU 管理器即可（内核侧协议由 `KERNEL_SU_VERSION` 决定）。

## 五、文件说明

- `magic5-config.gz` —— 从设备 `/proc/config.gz` 提取的真实构建配置（编 LKM 必需）
- `vmlinux.btf` —— 设备 `/sys/kernel/btf/vmlinux`，用于校验结构体布局
- `build_lkm.sh` —— Linux 上的编译脚本
- `verify_ko_layout.py` —— 不连设备就能判断某个 .ko 是否与本机 ABI 兼容
