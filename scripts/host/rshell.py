#!/usr/bin/env python3
"""Run a command on the device through the glk_helper root socket.

Keeps adb forward and the socket in one process so intervening adb calls
(which restart the server and drop forwards) cannot break it.
"""
from __future__ import annotations

import socket
import subprocess
import sys

ADB = r"G:\ADB-platform-tools\adb.exe"
PORT = 2323


def forward() -> None:
    subprocess.run([ADB, "start-server"], capture_output=True, timeout=30)
    subprocess.run([ADB, "forward", f"tcp:{PORT}", f"tcp:{PORT}"], capture_output=True, timeout=30)


def run(cmd: str, timeout: int = 30) -> str:
    forward()
    sock = socket.create_connection(("127.0.0.1", PORT), timeout=10)
    marker = "__GLK_END__"
    try:
        sock.sendall((cmd + f"\necho {marker}\n").encode())
        buf = b""
        sock.settimeout(timeout)
        try:
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                if marker.encode() in buf:
                    break
        except OSError:
            pass
        text = buf.decode("utf-8", "replace")
        return text.split(marker)[0]
    finally:
        sock.close()


if __name__ == "__main__":
    cmd = " ".join(sys.argv[1:]) or "id"
    print(run(cmd))
