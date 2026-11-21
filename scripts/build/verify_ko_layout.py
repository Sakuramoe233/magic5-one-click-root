#!/usr/bin/env python3
"""Check whether a KernelSU LKM was compiled against this device's task_struct layout.

Usage:
    python verify_ko_layout.py <kernelsu.ko> [vmlinux.btf]

It reads the device's BTF to learn the real field offsets, then reads the
function prologue that walks the process list inside the .ko and compares the
hard-coded constant against `task_struct.tasks`.  Exit code 0 = ABI matches.
"""
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

FIELDS = ["tasks", "mm", "cred", "real_cred", "nsproxy", "comm", "pid", "signal"]


def btf_task_offsets(btf_path):
    d = Path(btf_path).read_bytes()
    magic, ver, flags, hdr_len = struct.unpack_from("<HBBI", d, 0)
    if magic != 0xEB9F:
        raise SystemExit("not a BTF file")
    t_off, t_len, s_off, s_len = struct.unpack_from("<IIII", d, 8)
    tb, sb = hdr_len + t_off, hdr_len + s_off

    def s(o):
        e = d.find(b"\0", sb + o)
        return d[sb + o:e].decode(errors="replace")

    out = {}
    p = tb
    while p < tb + t_len:
        name_off, info, sot = struct.unpack_from("<III", d, p)
        vlen, kind, kflag = info & 0xffff, (info >> 24) & 0x1F, (info >> 31) & 1
        p += 12
        if kind in (4, 5):
            nm = s(name_off)
            members = []
            for _ in range(vlen):
                mo, mt, moff = struct.unpack_from("<III", d, p)
                p += 12
                members.append((s(mo), (moff & 0xFFFFFF if kflag else moff) // 8))
            if nm == "task_struct":
                for f in FIELDS:
                    for mn, off in members:
                        if mn == f:
                            out[f] = off
                            break
        elif kind == 1:
            p += 4
        elif kind == 3:
            p += 12 * vlen
        elif kind == 6:
            p += 12 * vlen
        elif kind == 7:
            p += 16 * vlen
        elif kind == 11:
            p += 12 * vlen
        elif kind in (13, 14):
            p += 8 * vlen
        elif kind in (16, 17):
            p += 4
    return out


def find_objdump():
    for c in ("llvm-objdump", "aarch64-linux-gnu-objdump", "objdump"):
        p = shutil.which(c)
        if p:
            return p
    raise SystemExit("no objdump found (install llvm or binutils)")


def ko_tasks_offset(ko, objdump):
    txt = subprocess.run([objdump, "-d", "--no-show-raw-insn", str(ko)],
                         capture_output=True, text=True).stdout
    lines = txt.splitlines()
    start = next((i for i, l in enumerate(lines) if "<ksu_mark_running_process_locked>:" in l), None)
    if start is None:
        return None, None
    # for_each_process compiles to:  add xN, xM, #tasks_off ; ldar xP, [xN]
    for i in range(start + 1, min(start + 60, len(lines))):
        if not re.search(r"ldar\s+x\d+, \[x\d+\]", lines[i]):
            continue
        m = re.search(r"add\s+x\d+, x\d+, #0x([0-9a-f]+)", lines[i - 1])
        if m:
            return int(m.group(1), 16), "ksu_mark_running_process_locked"
    return None, None


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    ko = Path(sys.argv[1])
    btf = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).with_name("vmlinux.btf")
    real = btf_task_offsets(btf)
    print("device task_struct offsets:")
    for f in FIELDS:
        if f in real:
            print(f"   {f:10s} 0x{real[f]:04x}")

    off, fn = ko_tasks_offset(ko, find_objdump())
    if off is None:
        print("\n[!] no process-list walker found in this .ko (too old, or stripped).")
        print("    Cannot verify ABI from the binary; prefer a v3.x build.")
        return 2
    print(f"\n{ko.name}: {fn} assumes tasks=0x{off:x}")
    if real.get("tasks") == off:
        print("[OK] ABI matches this device. Safe to patch symbols and load.")
        return 0
    print(f"[FAIL] device has tasks=0x{real.get('tasks', -1):x} -- module was built "
          f"against a different config. Do not load: it will fault.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
