#!/usr/bin/env python3
"""Make the LKM report the same version code as the BakaSU v4.2.0-rc3 manager.

The tarball checkout has no git metadata, so Kbuild falls back to a hardcoded
commit count (4471 -> version code 35171) while the manager expects 35257.
That mismatch makes the app show "kernel needs update". Set the count and the
cosmetic tag/sha strings to fixed values.
"""
from pathlib import Path

P = Path("/data/local/tmp/build/bakasu/kernel/Kbuild")

SUBS = [
    ("KSU_LOCAL_VERSION := 4471", "KSU_LOCAL_VERSION := 4557"),
    ('KSU_TAG_NAME    := $(shell cd $(KSU_SRC); $(GIT_BIN) describe --abbrev=0 --tags 2>/dev/null || echo "v4.1.0")',
     "KSU_TAG_NAME    := v4.2.0-rc3"),
    ("KSU_COMMIT_SHA  := $(shell cd $(KSU_SRC); $(GIT_BIN) rev-parse --short=8 HEAD 2>/dev/null || echo \"unknown\")",
     "KSU_COMMIT_SHA  := 1c54d617"),
    ("ifneq ($(shell cd $(KSU_SRC); $(GIT_BIN) diff-index --quiet HEAD; echo $$?),0)",
     "ifeq (0,1)"),
    ("KSU_BRANCH_NAME := $(shell cd $(KSU_SRC); $(GIT_BIN) branch --show-current 2>/dev/null || echo \"unknown\")",
     "KSU_BRANCH_NAME := main"),
]


def main() -> int:
    src = P.read_text()
    if "4557" in src:
        print("already patched")
        return 0
    for old, new in SUBS:
        if old not in src:
            print("MISS:", old[:60])
            continue
        src = src.replace(old, new, 1)
    P.write_text(src)
    print("version pinned to 35257 / v4.2.0-rc3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
