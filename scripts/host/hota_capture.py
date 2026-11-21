#!/usr/bin/env python3
"""实时抓取 adb logcat 并逐行落盘（行缓冲，避免 Windows CRT 全缓冲导致文件为空）。

用法: python -u hota_capture.py [输出文件]
停止: 结束该进程即可（或按 Ctrl+C）
"""
import subprocess
import sys
import time

out_path = sys.argv[1] if len(sys.argv) > 1 else "hota_live.log"

proc = subprocess.Popen(
    ["adb", "logcat", "-b", "all", "-v", "threadtime"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    errors="replace",
    bufsize=1,
)

print(f"[+] logcat 采集启动 -> {out_path}", flush=True)
count = 0
with open(out_path, "a", encoding="utf-8", errors="replace", buffering=1) as f:
    try:
        for line in proc.stdout:
            f.write(line)
            count += 1
            if count % 500 == 0:
                print(f"[+] 已写入 {count} 行", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        print(f"[+] 采集结束，共 {count} 行", flush=True)
