#!/usr/bin/env python3
"""Dump members + size of one or more BTF structs from the device's vmlinux.btf."""
import struct
import sys
from pathlib import Path


def iter_types(d):
    t_off, t_len, s_off, _ = struct.unpack_from("<IIII", d, 8)
    hdr_len = struct.unpack_from("<H", d, 4)[0]
    tb, sb = hdr_len + t_off, hdr_len + s_off

    def s(o):
        e = d.find(b"\0", sb + o)
        return d[sb + o:e].decode(errors="replace")

    p = tb
    while p < tb + t_len:
        name_off, info, size = struct.unpack_from("<III", d, p)
        vlen, kind, kflag = info & 0xFFFF, (info >> 24) & 0x1F, info >> 31
        p += 12
        if kind in (4, 5):
            members = []
            for _ in range(vlen):
                mo, mt, moff = struct.unpack_from("<III", d, p)
                p += 12
                bit_off = (moff & 0xFFFFFF) if kflag else moff
                bit_sz = (moff >> 24) if kflag else 0
                members.append((s(mo), bit_off // 8, bit_sz))
            yield s(name_off), size, members
        elif kind == 1:
            p += 4
        elif kind == 3:
            p += 12 * vlen
        elif kind == 6:
            p += 12 * vlen
        elif kind == 7:
            p += 16 * vlen
            yield s(name_off), size, None
        elif kind == 11:
            p += 12 * vlen
        elif kind in (13, 14):
            p += 8 * vlen
        elif kind in (16, 17):
            p += 4


def main():
    btf = Path(sys.argv[1] if len(sys.argv) > 1 else "vmlinux.btf").read_bytes()
    want = set(sys.argv[2:])
    for name, size, members in iter_types(btf):
        if want and name not in want:
            continue
        if members is None:
            continue
        print(f"=== {name}  size=0x{size:x} ({size})")
        for mn, off, bit in members:
            extra = f" bit{bit}" if bit else ""
            print(f"  0x{off:04x} {mn}{extra}")


if __name__ == "__main__":
    main()
