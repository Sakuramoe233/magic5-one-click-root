#!/usr/bin/env python3
"""Disable KSU's package observer.

ksu_observer_init() adds an fsnotify inode mark on /data/system. It hands
fsnotify `&inode->i_fsnotify_marks`, an offset from *our* kernel tree's
`struct inode`. That layout does not match the device (Honor patches + a
different config), so fsnotify receives a bogus connp and dies in
fsnotify_attach_connector_to_object.

The observer only watches for packages.list updates (throne tracking); root and
su keep working without it. Real fix later: align struct inode from BTF.
"""
from pathlib import Path

P = Path("/data/local/tmp/build/bakasu/kernel/manager/pkg_observer.c")

OLD = """int ksu_observer_init(void)
{
    int ret = 0;
"""

NEW = """int ksu_observer_init(void)
{
    int ret = 0;

    /* patched: struct inode layout differs from the device kernel */
    pr_info("observer: disabled (inode layout mismatch)\\n");
    return 0;
"""


def main() -> int:
    src = P.read_text()
    if "observer: disabled" in src:
        print("already patched")
        return 0
    if OLD not in src:
        raise SystemExit("anchor not found")
    P.write_text(src.replace(OLD, NEW, 1))
    print("observer disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
