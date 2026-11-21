#!/usr/bin/env python3
"""Force selected struct definitions in the ACK tree to match the device's ABI.

The Honor 5.15.180 tree froze its KABI with a different number of
ANDROID_KABI_RESERVE slots per struct than ACK 5.15.195, which shifts every
later field of task_struct.  We only ever build an out-of-tree module, so
patching the headers here is safe and keeps the module's offsets identical to
the running kernel.
"""
import re
import sys

ROOT = "/data/local/tmp/build/ack"


def read(p):
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def write(p, s):
    with open(p, "w") as f:
        f.write(s)


def patch_struct(path, name, reserves, extra=""):
    """Rewrite the ANDROID_KABI_RESERVE block of one struct definition."""
    s = read(path)
    pat = re.compile(r"(struct %s \{\n)(.*?)(\n\}.*?;)" % re.escape(name), re.S)
    m = pat.search(s)
    if not m:
        raise SystemExit(f"struct {name} not found in {path}")
    body = m.group(2)
    body = "\n".join(l for l in body.split("\n")
                     if "ANDROID_KABI_RESERVE(" not in l)
    if reserves:
        body = body.rstrip("\n") + "\n" + "\n".join(
            f"\tANDROID_KABI_RESERVE({i + 1});" for i in range(reserves))
    if extra:
        body = body.rstrip("\n") + "\n" + extra
    new = m.group(1) + body + m.group(3)
    s = s[:m.start()] + new + s[m.end():]
    write(path, s)
    print(f"  {name}: reserves -> {reserves}")


def main():
    sched = f"{ROOT}/include/linux/sched.h"
    hrt = f"{ROOT}/include/linux/hrtimer.h"
    if sys.argv[1:] == ["check"]:
        for p, n in ((sched, "sched_entity"), (sched, "sched_rt_entity"),
                     (hrt, "hrtimer")):
            body = re.search(r"struct %s \{.*?\n\};" % n, read(p), re.S).group(0)
            print(n, "reserves:", body.count("ANDROID_KABI_RESERVE("))
        return
    patch_struct(sched, "sched_entity", 0)
    patch_struct(sched, "sched_rt_entity", 0)
    patch_struct(hrt, "hrtimer", 2)
    print("done")


if __name__ == "__main__":
    main()
