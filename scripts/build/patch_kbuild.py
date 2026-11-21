#!/usr/bin/env python3
"""Make BakaSU's Kbuild buildable from a source tarball (no .git present)."""
KBUILD = "/data/local/tmp/build/bakasu/kernel/Kbuild"
COMMITS = 4471  # git rev-list --count for tag v4.2.0-rc3

src = open(KBUILD, encoding="utf-8", errors="replace").read()
subs = [
    ("LOCAL_GIT_EXISTS := $(shell test -e $(KSU_SRC)/../.git && echo 1 || echo 0)",
     "LOCAL_GIT_EXISTS := 1"),
    ("KSU_LOCAL_VERSION := $(shell cd $(KSU_SRC); $(GIT_BIN) rev-list --count HEAD)",
     f"KSU_LOCAL_VERSION := {COMMITS}"),
    ("$(shell cd $(KSU_SRC); [ -f ../.git/shallow ] && $(GIT_BIN) fetch --unshallow)",
     "# no git metadata in a tarball checkout"),
]
for old, new in subs:
    if old in src:
        src = src.replace(old, new)
    else:
        print("MISS:", old[:50])
open(KBUILD, "w").write(src)
print("patched Kbuild")
