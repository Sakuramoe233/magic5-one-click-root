#!/usr/bin/env python3
"""Force the ACK task_struct to the Honor 5.15.180 layout.

The vendor tree carries fields ACK does not have (cpu_power, wb_stat, a whole
QoS block, ...) and a different KABI reserve count per struct.  We only build
an out-of-tree module, so mirroring the device layout with explicit padding is
both safe and necessary: every later offset (tasks, cred, mm, ...) depends on
it.

Run with "check" to list what is currently inserted.
"""
import sys

SCHED = "/data/local/tmp/build/ack/include/linux/sched.h"

# (anchor line fragment, padding declaration, comment)
PADS = [
    ("unsigned int\t\t\tmax_state;",
     "\tu64\t\t\t\t__glk_cpu_power;",
     "Honor: cpu_power"),
    ("struct blk_plug\t\t\t*plug;",
     "\tvoid\t\t\t\t*__glk_wb_stat;",
     "Honor: wb_stat"),
    ("struct timer_list\t\toom_reaper_timer;",
     "\tchar\t\t\t\t__glk_pad_timer[16];",
     "timer_list size delta"),
    ("struct bpf_run_ctx\t\t*bpf_ctx;",
     "\tchar\t\t\t\t__glk_pad_qos[120];",
     "Honor: rtg/qos block"),
]


def main():
    src = open(SCHED, encoding="utf-8", errors="replace").read()
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        for _a, pad, note in PADS:
            name = pad.strip().split("__glk_")[-1].rstrip(";[]0123456789")
            print(f"  __glk_{name}: {'present' if pad.strip() in src else 'MISSING'}")
        return

    out = []
    for line in src.split("\n"):
        out.append(line)
        for anchor, pad, note in PADS:
            if line.strip() == anchor.strip() and pad.strip() not in src:
                out.append(f"{pad}\t/* {note} */")
    open(SCHED, "w").write("\n".join(out))
    print(f"task_struct pads: {sum(1 for _, p, _ in PADS if p.strip() in open(SCHED).read())}/{len(PADS)}")


if __name__ == "__main__":
    main()
