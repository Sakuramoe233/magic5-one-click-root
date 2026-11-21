#!/usr/bin/env python3
"""Convert a kernel module's undefined symbols into absolute definitions.

The Honor kernel exports only a subset of its symbols, so a stock KernelSU LKM
fails to load with "Unknown symbol avtab_search_node" (and ~200 friends) even
after module signature enforcement is disabled. CONFIG_KALLSYMS_ALL=y means
every one of those symbols still has an address, so the fix is the classic
"insmod with kallsyms" trick: rewrite the ELF symbol table so each imported
symbol becomes a defined absolute symbol at its runtime address. The loader
then never calls resolve_symbol() for them.

Usage:
    python patch_ko_kallsyms.py <module.ko> <kallsyms.txt> <out.ko>
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

SHN_ABS = 0xFFF1
STB_GLOBAL = 1


def parse_kallsyms(path: Path) -> dict[str, int]:
    """name -> address; first occurrence wins (aliases share an address)."""
    table: dict[str, int] = {}
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        addr_s, _typ, name = parts[0], parts[1], parts[2]
        try:
            addr = int(addr_s, 16)
        except ValueError:
            continue
        if addr == 0:
            continue
        table.setdefault(name, addr)
    return table


def section_slice(data: bytes, shoff: int, shentsize: int, idx: int) -> tuple[int, int, int, int]:
    b = shoff + idx * shentsize
    name, typ, flags, addr, off, size, link, info, align, entsize = struct.unpack_from(
        "<IIQQQQIIQQ", data, b
    )
    return off, size, link, entsize


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    mod_path, sym_path, out_path = (Path(a) for a in sys.argv[1:])

    data = bytearray(mod_path.read_bytes())
    ks = parse_kallsyms(sym_path)
    print(f"[*] kallsyms entries: {len(ks):,}")

    if data[:4] != b"\x7fELF" or data[4] != 2:
        raise SystemExit("not an ELF64 file")

    e_shoff, = struct.unpack_from("<Q", data, 0x28)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", data, 0x3A)

    # locate .symtab / .strtab via the section-name table
    shstr_off, shstr_size, _, _ = section_slice(data, e_shoff, e_shentsize, e_shstrndx)
    shstr = bytes(data[shstr_off:shstr_off + shstr_size])

    def sname(nm_off: int) -> str:
        end = shstr.find(b"\0", nm_off)
        return shstr[nm_off:end].decode(errors="replace")

    symtab = strtab = None
    for i in range(e_shnum):
        off, size, link, entsize = section_slice(data, e_shoff, e_shentsize, i)
        nm, = struct.unpack_from("<I", data, e_shoff + i * e_shentsize)
        name = sname(nm)
        if name == ".symtab":
            symtab = (off, size, link, entsize)
        elif name == ".strtab":
            strtab = (off, size)
    if not symtab or not strtab:
        raise SystemExit("no symtab/strtab")

    sym_off, sym_size, sym_link, sym_entsize = symtab
    sym_entsize = sym_entsize or 24
    str_off, str_size = strtab
    strs = bytes(data[str_off:str_off + str_size])

    count = resolved = missing = already = 0
    unresolved: list[str] = []
    for i in range(sym_size // sym_entsize):
        b = sym_off + i * sym_entsize
        st_name, st_info, st_other, st_shndx, st_value, st_size = struct.unpack_from(
            "<IBBHQQ", data, b
        )
        if st_shndx != 0 or st_name == 0:
            continue  # not undefined
        count += 1
        end = strs.find(b"\0", st_name)
        name = strs[st_name:end].decode(errors="replace")
        addr = ks.get(name)
        if addr is None:
            missing += 1
            unresolved.append(name)
            continue
        # SHN_ABS + runtime address: the loader applies S = addr + addend
        struct.pack_into("<H", data, b + 6, SHN_ABS)
        struct.pack_into("<Q", data, b + 8, addr)
        resolved += 1

    print(f"[*] undefined symbols: {count}")
    print(f"[+] resolved via kallsyms: {resolved}")
    if unresolved:
        print(f"[!] still missing ({missing}):")
        for n in unresolved[:40]:
            print("      ", n)

    out_path.write_bytes(bytes(data))
    print(f"[+] wrote {out_path} ({len(data):,} bytes)")
    return 0 if missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
