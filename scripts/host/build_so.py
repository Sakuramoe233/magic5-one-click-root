#!/usr/bin/env python3
"""打包 magic5-root.so：外壳 ELF + 尾部载荷。

布局（从文件尾往前）：
    [profile][helper][exploit][su][su-perm][footer 32B]
footer = "GLKPAYLD" + version + 5 个 u32 长度
外壳启动时按 footer 从自身文件里读回这些段，落盘到固定的 /data/local/tmp 路径。

用法:
    python build_so.py
"""
from __future__ import annotations

import struct
import subprocess
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
WORK = TOOLS.parent
OUT = TOOLS / "magic5-root.so"

NDK = Path("C:/Users/ljw/WorkBuddy/2026-11-16-16-52-47/work/ndk_root/android-ndk-r27c")
CC = NDK / "toolchains/llvm/prebuilt/windows-x86_64/bin/aarch64-linux-android35-clang.cmd"

WRAPPER = TOOLS / "glk_so"
PROFILE = WORK / "profile_175.bin"
HELPER = TOOLS / "glk_helper"
EXPLOIT = WORK.parent / "ghostlock" / "build" / "native" / "ghostlock"
SU = TOOLS / "su"
PERM = TOOLS / "su-perm"

FOOTER_MAGIC = b"GLKPAYLD"
FOOTER_VERSION = 1


def build_wrapper() -> None:
    cmd = [str(CC), "-O2", "-static", "-Wall", "-o", str(WRAPPER), str(TOOLS / "glk_so.c"), "-ldl"]
    print("[*]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    for f in (PROFILE, HELPER, EXPLOIT, SU, PERM):
        if not f.is_file():
            print(f"[!] 缺少 {f}")
            return 1

    build_wrapper()

    parts = [PROFILE.read_bytes(), HELPER.read_bytes(), EXPLOIT.read_bytes(),
             SU.read_bytes(), PERM.read_bytes()]
    names = ["profile", "helper", "exploit", "su", "su-perm"]
    base = WRAPPER.read_bytes()
    footer = struct.pack("<8s6I", FOOTER_MAGIC, FOOTER_VERSION, *[len(p) for p in parts])

    OUT.write_bytes(base + b"".join(parts) + footer)

    print(f"[+] {OUT.name}: {OUT.stat().st_size:,} 字节")
    for n, p in zip(names, parts):
        print(f"    {n:<8} {len(p):>9,}")
    print(f"    wrapper  {len(base):>9,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
