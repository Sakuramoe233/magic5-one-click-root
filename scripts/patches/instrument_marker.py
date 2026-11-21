#!/usr/bin/env python3
"""Add step-by-step tracing to ksu_mark_running_process_locked().

The module dies inside this loop before printing a single mark/unmark line, so
the failing call is one of the four helpers in the body. These prints bracket
each one; the last line in the O_SYNC kernel log names the culprit.
"""
from pathlib import Path

P = Path("/data/local/tmp/build/bakasu/kernel/hook/tp_marker.c")

OLD = """        int uid = task_uid(t).val;
        const struct cred *cred = get_task_cred(t);
        bool ksu_root_process = uid == 0 && is_task_ksu_domain(cred);
        bool is_zygote_process = is_zygote(cred);
        bool is_shell = uid == 2000;"""

NEW = """        int uid = task_uid(t).val;
        const struct cred *cred = get_task_cred(t);
        pr_info("ksu_dbg: t=%px pid=%d mm=%px cr=%px uid=%d sec=%px\\n",
                t, t->pid, t->mm, cred, uid, cred ? cred->security : NULL);
        bool ksu_root_process = uid == 0 && is_task_ksu_domain(cred);
        pr_info("ksu_dbg: step ksu_domain done=%d\\n", ksu_root_process);
        bool is_zygote_process = is_zygote(cred);
        pr_info("ksu_dbg: step zygote done=%d\\n", is_zygote_process);
        bool is_shell = uid == 2000;"""


def main() -> int:
    src = P.read_text()
    if "ksu_dbg" in src:
        print("already instrumented")
        return 0
    if OLD not in src:
        raise SystemExit("anchor not found")
    P.write_text(src.replace(OLD, NEW, 1))
    print("instrumented tp_marker.c")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
