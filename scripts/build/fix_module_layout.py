#!/usr/bin/env python3
"""Align struct kobject / struct module with the device's BTF layout.

Device deltas found with -fdump-record-layouts vs /sys/kernel/btf/vmlinux:

  struct kobject        96 -> 64   : device dropped the 4 ANDROID_KABI slots
  struct module         mid +32    : same kobject shrink pushes modinfo_attrs..init
  struct module         +btf_data  : device is built with DEBUG_INFO_BTF_MODULES,
                                     our tree disables BTF generation for the build
  struct module         tail -32   : device dropped the 4 tail ANDROID_KABI slots

Result: every struct module member lands on the device offset, and sizeof stays
960 (0x3c0) because the alignment padding absorbs the delta.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

TREE = Path("/data/local/tmp/build/ack")


def drop_kabi(text: str) -> tuple[str, int]:
    pattern = re.compile(r"^[ \t]*ANDROID_KABI_RESERVE\([1-4]\);[ \t]*\n", re.M)
    text, n = pattern.subn("", text)
    return text, n


def patch_kobject() -> None:
    p = TREE / "include/linux/kobject.h"
    src = p.read_text()
    out, n = drop_kabi(src)
    p.write_text(out)
    print(f"kobject.h: removed {n} KABI reserve slots")


def patch_module() -> None:
    p = TREE / "include/linux/module.h"
    src = p.read_text()
    out, n = drop_kabi(src)
    print(f"module.h : removed {n} KABI reserve slots")
    marker = "#ifdef CONFIG_DEBUG_INFO_BTF_MODULES"
    if marker in out:
        out = out.replace(
            marker + "\n\tunsigned int btf_data_size;\n\tvoid *btf_data;\n#endif",
            "/* device kernel is built with CONFIG_DEBUG_INFO_BTF_MODULES=y */\n"
            "\tunsigned int btf_data_size;\n\tvoid *btf_data;",
            1,
        )
        print("module.h : forced btf_data_size/btf_data in")
    p.write_text(out)


if __name__ == "__main__":
    if not TREE.is_dir():
        raise SystemExit(f"{TREE} not found")
    patch_kobject()
    patch_module()
    print("done")
