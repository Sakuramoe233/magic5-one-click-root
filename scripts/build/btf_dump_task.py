#!/usr/bin/env python3
"""Dump every task_struct member offset from the device's BTF.

Used to generate compile-time static asserts so a mismatched build fails early
instead of faulting the kernel at insmod time.
"""
import struct
import sys
from pathlib import Path


def parse(btf_path):
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
        vlen, kind, kflag = info & 0xFFFF, (info >> 24) & 0x1F, (info >> 31) & 1
        p += 12
        if kind in (4, 5):
            nm = s(name_off)
            members = []
            for _ in range(vlen):
                mo, mt, moff = struct.unpack_from("<III", d, p)
                p += 12
                if kflag:
                    bit_off = moff & 0xFFFFFF
                    bit_sz = moff >> 24
                else:
                    bit_off, bit_sz = moff, 0
                members.append([s(mo), bit_off, bit_sz])
            if nm == "task_struct":
                out[nm] = members
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


def main():
    btf = sys.argv[1] if len(sys.argv) > 1 else "vmlinux.btf"
    members = parse(btf)["task_struct"]
    print(f"# {len(members)} members")
    maxoff = 0
    for name, bit_off, bit_sz in members:
        if name in ("", "__unused"):
            continue
        if bit_sz:
            print(f"# bitfield {name} @{bit_off//8} bit{bit_off%8} size{bit_sz}")
            continue
        print(f"0x{bit_off//8:04x} {name}")
        maxoff = max(maxoff, bit_off // 8)
    print(f"# last member offset 0x{maxoff:x}")


if __name__ == "__main__":
    main()
