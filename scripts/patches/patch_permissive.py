#!/usr/bin/env python3
"""Keep SELinux permissive after a late load.

apply_kernelsu_rules() rebuilds the whole in-kernel policy with an AOSP
policydb layout.  Honor ships a Huawei-patched SELinux (HKIP), so the
rebuilt policy loses the secmark/netif type mappings and netd's DNS
packets end up labelled u:object_r:unlabeled:s0 -> every send() denied
-> no network at all, while WiFi/mobile still look "connected".

Until the policydb layout is aligned, the safe path is to never flip the
system back to enforcing: in permissive mode the bogus labels are simply
not denied.  This patch removes the single setenforce(true) call in
ksu_initialize()'s late-load branch.
"""

import os
import sys

INIT_C = "/data/local/tmp/build/bakasu/kernel/core/init.c"

OLD = """        if (!getenforce()) {
            pr_info("Permissive SELinux, enforcing\\n");
            setenforce(true);
        }"""

NEW = """        if (!getenforce()) {
            /* Honor/HKIP: policy rebuilt here loses secmark type mappings,
             * so flipping back to enforcing kills netd (unlabeled packets).
             * Stay permissive until the policydb layout is aligned. */
            pr_info("Permissive SELinux, keeping permissive (Honor policy compat)\\n");
        }"""


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else INIT_C
    if not os.path.exists(path):
        print("missing:", path)
        return 1
    with open(path, "r", encoding="utf-8", errors="surrogateescape") as fh:
        src = fh.read()

    if NEW.splitlines()[2].strip() in src:
        print("already patched")
        return 0
    if OLD not in src:
        print("pattern not found -- check init.c")
        return 2

    src = src.replace(OLD, NEW, 1)
    with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(src)
    print("patched: setenforce(true) removed from late-load branch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
