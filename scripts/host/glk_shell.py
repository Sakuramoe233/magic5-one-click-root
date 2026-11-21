#!/usr/bin/env python3
"""进入 GhostLock 临时 root shell（通过带鉴权的 su 客户端）。

前置：exploit 已跑完并起了 /data/local/tmp/glk_helper，它把 su socket 挂在
/data/local/tmp/.glk/su.sock（SO_PEERCRED 白名单，默认只放行 root 和 shell）。

用法:
    python glk_shell.py            # 交互式 root shell
    python glk_shell.py "id -u"    # 单条命令
退出: Ctrl+D（或 exit）
"""
import subprocess
import sys

DEV_SU = "/data/local/tmp/su"


def shell_quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def main() -> int:
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
        return subprocess.call(["adb", "exec-out", f"{DEV_SU} -c {shell_quote(cmd)}"])
    return subprocess.call(["adb", "shell", "-t", DEV_SU])


if __name__ == "__main__":
    sys.exit(main())
