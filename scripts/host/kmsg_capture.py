#!/usr/bin/env python3
"""在电脑侧接收设备推送的 /dev/kmsg 流，落盘以便事后分析 panic。

配合:
    adb reverse tcp:9000 tcp:9000
    (设备 root shell) setsid sh -c 'cat /dev/kmsg | nc 127.0.0.1 9000' &
"""
import socket
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "kmsg_capture.log"
PORT = 9000


def main() -> int:
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", PORT))
    srv.listen(1)
    srv.settimeout(180)
    print(f"[*] 监听 127.0.0.1:{PORT}，输出 {OUT}", flush=True)
    try:
        conn, _ = srv.accept()
    except socket.timeout:
        print("[!] 180 秒内没有设备连上")
        return 1
    conn.settimeout(600)
    total = 0
    with OUT.open("wb") as fh:
        started = time.time()
        while True:
            try:
                chunk = conn.recv(65536)
            except (socket.timeout, OSError):
                break
            if not chunk:
                break
            fh.write(chunk)
            fh.flush()
            total += len(chunk)
    print(f"[+] 结束，收到 {total} 字节，{time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
