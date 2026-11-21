#!/usr/bin/env python3
"""Run a command through the glk_helper root socket, without adb forward.

Uses `adb shell 'nc 127.0.0.1 2323'` with the command piped over stdin, so a
restarting adb server can never drop the port forward mid-session.
"""
from __future__ import annotations

import subprocess
import sys

ADB = r"G:\ADB-platform-tools\adb.exe"
MARKER = "__GLK_END__"


def run(cmd: str, timeout: int = 40) -> str:
    payload = (cmd + f"\necho {MARKER}\n").encode()
    proc = subprocess.run(
        [ADB, "shell", "nc 127.0.0.1 2323"],
        input=payload,
        capture_output=True,
        timeout=timeout,
    )
    out = proc.stdout.decode("utf-8", "replace")
    if MARKER in out:
        out = out.split(MARKER)[0]
    return out


if __name__ == "__main__":
    print(run(" ".join(sys.argv[1:]) or "id"))
