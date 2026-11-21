"""离线校验 magic5-root.so 的尾部载荷：偏移、长度、sha256。"""
import hashlib
import struct
from pathlib import Path

TOOLS = Path(r"C:\Users\ljw\WorkBuddy\2026-11-16-16-52-47\work\tools")
WORK = TOOLS.parent
SO = TOOLS / "magic5-root.so"

blob = SO.read_bytes()
magic, ver, *sizes = struct.unpack("<8s6I", blob[-32:])
print(f"magic={magic!r} version={ver}")
print(f"sizes={sizes} sum={sum(sizes):,}")

start = len(blob) - 32 - sum(sizes)
print(f"wrapper={start:,}  payload_start={start:,}  file={len(blob):,}")

expect = [
    ("profile", WORK / "profile_175.bin"),
    ("helper", TOOLS / "glk_helper"),
    ("exploit", WORK.parent / "ghostlock" / "build" / "native" / "ghostlock"),
    ("su", TOOLS / "su"),
    ("su-perm", TOOLS / "su-perm"),
]

off = start
all_ok = True
for (name, path), size in zip(expect, sizes):
    part = blob[off:off + size]
    off += size
    same = hashlib.sha256(part).digest() == hashlib.sha256(path.read_bytes()).digest()
    all_ok &= same
    print(f"  {name:<8} {size:>9,}  {'一致' if same else '不一致'}")

print(f"EOF 对齐={off + 32 == len(blob)}  全部一致={all_ok}")
