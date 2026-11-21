#!/usr/bin/env python3
"""Trim scripts/Makefile down to the host tools an out-of-tree module needs.

The SELinux/asn1/sign-file helpers pull kernel headers into the same search
path as bionic's libc headers, which bionic cannot survive; they are only used
when building the kernel image itself.
"""
import sys

PATH = "/data/local/tmp/build/ack/scripts/Makefile"
DROP = (
    "+= sorttable",
    "+= asn1_compiler",
    "+= sign-file",
    "+= extract-cert",
    "+= insert-sys-cert",
    "CONFIG_SECURITY_SELINUX) += selinux",
)

lines = open(PATH).read().split("\n")
changed = 0
for i, line in enumerate(lines):
    if line.startswith("#"):
        continue
    if any(d in line for d in DROP):
        lines[i] = "# " + line
        changed += 1
open(PATH, "w").write("\n".join(lines))
print(f"patched {changed} lines in scripts/Makefile")
