#!/usr/bin/env python3
"""Re-enable the SELinux header generator and make it compile against bionic.

bionic's <sys/types.h> pulls in <linux/types.h>; if the kernel's include/ dir
comes first in the search path that resolves to the internal kernel header and
bionic's own headers stop parsing.  -idirafter keeps the libc headers winning
while still letting genheaders find classmap.h and the uapi headers.
"""
import re

ROOT = "/data/local/tmp/build/ack"


def edit(path, fn):
    s = open(path, encoding="utf-8", errors="replace").read()
    s2 = fn(s)
    if s2 != s:
        open(path, "w").write(s2)
        print("patched", path)
    else:
        print("unchanged", path)


def scripts_mk(s):
    return s.replace("# subdir-$(CONFIG_SECURITY_SELINUX) += selinux",
                     "subdir-$(CONFIG_SECURITY_SELINUX) += selinux")


def genheaders_mk(s):
    s = s.replace("-I$(srctree)/include ", "-idirafter $(srctree)/include ")
    return s.replace("-I$(srctree)/include/uapi", "-idirafter $(srctree)/include/uapi")


edit(f"{ROOT}/scripts/Makefile", scripts_mk)
edit(f"{ROOT}/scripts/selinux/genheaders/Makefile", genheaders_mk)
edit(f"{ROOT}/scripts/selinux/mdp/Makefile", genheaders_mk)
