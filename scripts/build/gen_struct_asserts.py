#!/usr/bin/env python3
"""Generate compile-time asserts for every struct type embedded in task_struct.

Reads the device's vmlinux.btf, resolves each task_struct member to its struct
type and asserts sizeof() against the device size.  A build with a different
config then fails with the exact struct that diverged.
"""
import struct
import sys
from pathlib import Path

K_STRUCT, K_UNION, K_INT, K_PTR, K_ARRAY = 4, 5, 1, 2, 3
K_TYPEDEF, K_VOLATILE, K_CONST, K_RESTRICT, K_TYPE_TAG = 8, 9, 10, 11, 18


def load(path):
    d = Path(path).read_bytes()
    assert struct.unpack_from("<H", d, 0)[0] == 0xEB9F, "not BTF"
    hdr_len = struct.unpack_from("<H", d, 4)[0]
    t_off, t_len, s_off = struct.unpack_from("<III", d, 8)
    tb, sb = hdr_len + t_off, hdr_len + s_off

    def s(o):
        e = d.find(b"\0", sb + o)
        return d[sb + o:e].decode(errors="replace")

    types, p, tid = {}, tb, 1
    while p < tb + t_len:
        name_off, info, body = struct.unpack_from("<III", d, p)
        vlen, kind, kflag = info & 0xFFFF, (info >> 24) & 0x1F, info >> 31
        p += 12
        rec = {"name": s(name_off), "kind": kind, "size": body, "members": None, "ref": None}
        if kind in (K_STRUCT, K_UNION):
            members = []
            for _ in range(vlen):
                mo, mt, moff = struct.unpack_from("<III", d, p)
                p += 12
                bit = (moff & 0xFFFFFF) if kflag else moff
                members.append((s(mo), mt, bit // 8))
            rec["members"] = members
        elif kind == K_INT:
            p += 4
        elif kind == K_PTR:
            rec["ref"] = struct.unpack_from("<I", d, p)[0]
            p += 4
        elif kind == K_ARRAY:
            elem, _idx, n = struct.unpack_from("<III", d, p)
            rec["ref"], rec["n"] = elem, n
            p += 12
        elif kind in (K_TYPEDEF, K_VOLATILE, K_CONST, K_RESTRICT, K_TYPE_TAG):
            rec["ref"] = struct.unpack_from("<I", d, p)[0]
            p += 4
        elif kind == 6:      # ENUM
            p += 8 * vlen
        elif kind == 13:     # FUNC_PROTO
            p += 8 * vlen
        elif kind == 14:     # VAR
            p += 4
        elif kind == 15:     # DATASEC
            p += 12 * vlen
        elif kind == 17:     # DECL_TAG
            p += 4
        elif kind == 19:     # ENUM64
            p += 12 * vlen
        types[tid] = rec
        tid += 1
    return types


def resolve(types, tid):
    for _ in range(16):
        t = types.get(tid)
        if not t:
            return None
        if t["kind"] in (K_STRUCT, K_UNION):
            return t
        if t["kind"] in (K_TYPEDEF, K_VOLATILE, K_CONST, K_RESTRICT, K_TYPE_TAG, K_ARRAY):
            tid = t["ref"]
            continue
        return None
    return None


def main():
    types = load(sys.argv[1] if len(sys.argv) > 1 else "vmlinux.btf")
    task = next((t for t in types.values() if t["name"] == "task_struct"), None)
    if not task:
        raise SystemExit("no task_struct in BTF")

    lines = ["#include <linux/sched.h>", "#include <linux/sched/signal.h>",
             "#include <linux/sched/mm.h>", "#include <linux/sched/task.h>",
             "#include <linux/cred.h>", "#include <linux/mm_types.h>",
             "#include <linux/nsproxy.h>", "#include <linux/fs_struct.h>",
             "#include <linux/fdtable.h>", "#include <linux/seccomp.h>",
             "#include <linux/audit.h>", "#include <linux/plist.h>",
             "#include <linux/sched/deadline.h>", "#include <linux/io_uring.h>",
             "#include <linux/perf_event.h>", "#include <linux/futex.h>",
             "#include <linux/task_io_accounting.h>", "#include <linux/rcupdate.h>",
             "#include <linux/bpf.h>", "#include <linux/android_vendor.h>",
             "#include <linux/sched/numa_balancing.h>", "#include <linux/kcov.h>",
             "#include <linux/latencytop.h>", "#include <linux/sched/autogroup.h>",
             "#include <linux/swap.h>", "#include <linux/oom.h>", ""]
    seen, n = set(), 0
    for name, tid, _off in task["members"]:
        st = resolve(types, tid)
        if not st or not st["name"] or st["name"] in seen:
            continue
        seen.add(st["name"])
        n += 1
        lines.append(f"_Static_assert(sizeof(struct {st['name']}) == {st['size']}, "
                     f"\"sizeof {st['name']} device={st['size']}\");")
    lines.append(f"/* {n} structs */")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
