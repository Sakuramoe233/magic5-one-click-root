#!/usr/bin/env python3
"""Second round of ABI alignment: kill the remaining KABI reserve mismatches."""
import re

ROOT = "/data/local/tmp/build/ack"


def read(p):
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def write(p, s):
    with open(p, "w") as f:
        f.write(s)


def set_reserves(path, name, n):
    s = read(path)
    m = re.search(r"(struct %s \{\n)(.*?)(\n\}.*?;)" % re.escape(name), s, re.S)
    if not m:
        raise SystemExit(f"struct {name} not found in {path}")
    body = "\n".join(l for l in m.group(2).split("\n")
                     if "ANDROID_KABI_RESERVE(" not in l)
    if n:
        body = body.rstrip("\n") + "\n" + "\n".join(
            f"\tANDROID_KABI_RESERVE({i + 1});" for i in range(n))
    write(path, s[:m.start()] + m.group(1) + body + m.group(3) + s[m.end():])
    print(f"  {name}: reserves -> {n}")


def drop_line(path, needle):
    s = read(path)
    out = [l for l in s.split("\n") if needle not in l]
    if len(out) != len(s.split("\n")):
        write(path, "\n".join(out))
        print(f"  dropped: {needle}")


set_reserves(f"{ROOT}/include/linux/timer.h", "timer_list", 0)
set_reserves(f"{ROOT}/include/linux/sched.h", "task_struct", 0)
drop_line(f"{ROOT}/include/linux/sched.h", "__glk_pad_timer")
print("done")
