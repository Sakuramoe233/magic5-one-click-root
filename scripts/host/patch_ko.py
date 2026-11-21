#!/usr/bin/env python3
"""Patch a KernelSU LKM for the Honor 5.15.180 kernel:
- rename an undefined UBSAN symbol to a symbol this kernel exports
- rewrite vermagic to the running kernel's
"""
import struct
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "lkm/android13-5.15_kernelsu.ko"
DST = sys.argv[2] if len(sys.argv) > 2 else "lkm/kernelsu-patched.ko"
VERMAGIC = "5.15.180-android13-8-g1c54d617912d SMP preempt mod_unload modversions aarch64"

d = bytearray(open(SRC, "rb").read())

# ---- 1. rename the unresolvable UBSAN symbol -------------------------------
OLD = b"__ubsan_handle_cfi_check_fail_abort"
NEW = b"panic"
idx = d.find(OLD)
if idx < 0:
    print("ubsan symbol not found (already patched?)")
else:
    d[idx:idx + len(OLD)] = NEW + b"\0" * (len(OLD) - len(NEW))
    print(f"renamed {OLD.decode()} -> {NEW.decode()} at {hex(idx)}")

# ---- 2. rewrite the vermagic entry inside .modinfo -------------------------
e_shoff, = struct.unpack_from("<Q", d, 0x28)
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", d, 0x3a)
shstr_off, = struct.unpack_from("<Q", d, e_shoff + e_shstrndx * e_shentsize + 0x18)
names = bytes(d[shstr_off:shstr_off + 4000])

modinfo = None
for i in range(e_shnum):
    b = e_shoff + i * e_shentsize
    nm, = struct.unpack_from("<I", d, b)
    name = names[nm:names.find(b"\0", nm)].decode()
    if name == ".modinfo":
        off_, size = struct.unpack_from("<QQ", d, b + 0x18)
        modinfo = (off_, size)
        break

if modinfo is None:
    raise SystemExit("no .modinfo section")

off_, size = modinfo
entries = [e for e in bytes(d[off_:off_ + size]).split(b"\0") if e]
out = []
for e in entries:
    if e.startswith(b"vermagic="):
        e = b"vermagic=" + VERMAGIC.encode()
        print("vermagic ->", VERMAGIC)
    out.append(e)
blob = b"\0".join(out) + b"\0"
if len(blob) > size:
    raise SystemExit(f"new modinfo is {len(blob)} bytes, section only {size}")
d[off_:off_ + size] = blob + b"\0" * (size - len(blob))

open(DST, "wb").write(bytes(d))
print(f"wrote {DST} ({len(d)} bytes)")
