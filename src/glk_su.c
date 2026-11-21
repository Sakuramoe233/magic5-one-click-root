/*
 * glk_su: client side of the authenticated temporary-root su.
 *
 * Talks to the unix socket served by glk_helper (the post-exploit root
 * helper). The helper checks SO_PEERCRED against its uid allowlist, so this
 * client gives you real root command execution without leaving an
 * unauthenticated root shell listening on loopback.
 *
 *   su                     -> interactive root shell
 *   su -c "id; getenforce" -> run one command as root
 *
 * The socket only exists while the exploit's helper is alive, i.e. until the
 * next reboot. When it is gone this prints a pointer to glk_root.py.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#define SU_SOCK "/data/local/tmp/.glk/su.sock"

/* Tail kept back from stdout so the exit trailer the helper appends after the
 * child is reaped can be stripped before it reaches the terminal. Large enough
 * for the trailer, small enough that streaming still feels immediate. */
#define TAIL_CAP 128
#define TRAILER_MAGIC "\001\001GLKRC="
#define TRAILER_MAGIC_LEN 8

static int write_all(int fd, const char *p, size_t n) {
    size_t off = 0;
    while (off < n) {
        ssize_t w = write(fd, p + off, n - off);
        if (w <= 0) return -1;
        off += (size_t) w;
    }
    return 0;
}

/* Returns the child's exit status, or 0 when no trailer is present (e.g. the
 * helper is an older build, or the connection was denied mid-write). *out_len
 * receives the number of bytes that are real output. */
static int parse_trailer(const char *tail, size_t len, size_t *out_len) {
    *out_len = len;
    /* magic(8) + at least one digit + two control bytes */
    if (len < TRAILER_MAGIC_LEN + 3) return 0;
    /* The trailer is always the last thing on the stream; 40 bytes is more than
     * enough to cover it, and keeps a stray match deep in real output harmless. */
    size_t lowest = len > 40 ? len - 40 : 0;
    for (size_t i = lowest; i + TRAILER_MAGIC_LEN + 3 <= len; i++) {
        if (memcmp(tail + i, TRAILER_MAGIC, TRAILER_MAGIC_LEN) != 0) continue;
        if (tail[len - 2] != '\001' || tail[len - 1] != '\001') return 0;
        size_t digits_start = i + TRAILER_MAGIC_LEN;
        size_t digits_end = len - 2;
        if (digits_end <= digits_start || digits_end - digits_start > 4) continue;
        int rc = 0;
        int ok = 1;
        for (size_t k = digits_start; k < digits_end; k++) {
            if (tail[k] < '0' || tail[k] > '9') { ok = 0; break; }
            rc = rc * 10 + (tail[k] - '0');
        }
        if (!ok) continue;
        *out_len = i;
        return rc;
    }
    return 0;
}

/* Pump bytes both ways until the remote closes, holding back a short tail so
 * the exit trailer can be stripped. Returns the remote command's exit status. */
static int relay(int s) {
    char buf[8192];
    char tail[TAIL_CAP];
    size_t taillen = 0;
    int stdin_open = 1;
    int rc = 0;

    for (;;) {
        struct pollfd fds[2];
        nfds_t n = 0;
        fds[n].fd = s;
        fds[n].events = POLLIN;
        n++;
        if (stdin_open) {
            fds[n].fd = STDIN_FILENO;
            fds[n].events = POLLIN;
            n++;
        }
        int r = poll(fds, n, -1);
        if (r < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (fds[0].revents & (POLLIN | POLLHUP)) {
            ssize_t got = read(s, buf, sizeof(buf));
            if (got <= 0) break;
            ssize_t off = 0;
            while (off < got) {
                size_t space = TAIL_CAP - taillen;
                size_t take = (size_t) (got - off) < space ? (size_t) (got - off) : space;
                memcpy(tail + taillen, buf + off, take);
                taillen += take;
                off += (ssize_t) take;
                if (taillen == TAIL_CAP) {
                    /* Flush only the older half: the trailer is <= 20 bytes, so
                     * it can never straddle a flush boundary. */
                    size_t flush = TAIL_CAP / 2;
                    if (write_all(STDOUT_FILENO, tail, flush) != 0) return rc;
                    memmove(tail, tail + flush, taillen - flush);
                    taillen -= flush;
                }
            }
        }
        if (stdin_open && n > 1 && (fds[1].revents & (POLLIN | POLLHUP))) {
            ssize_t got = read(STDIN_FILENO, buf, sizeof(buf));
            if (got <= 0) {
                stdin_open = 0;
                shutdown(s, SHUT_WR);
            } else if (write_all(s, buf, (size_t) got) != 0) {
                break;
            }
        }
    }

    size_t out_len = taillen;
    rc = parse_trailer(tail, taillen, &out_len);
    if (out_len > 0) (void) write_all(STDOUT_FILENO, tail, out_len);
    return rc;
}

static int connect_su(void) {
    int s = socket(AF_UNIX, SOCK_STREAM, 0);
    if (s < 0) return -1;
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, SU_SOCK, sizeof(addr.sun_path) - 1);
    if (connect(s, (struct sockaddr *) &addr, sizeof(addr)) != 0) {
        close(s);
        return -1;
    }
    return s;
}

static void usage(void) {
    fprintf(stderr,
            "usage: su [-c command] [-h]\n"
            "  no args     interactive root shell\n"
            "  -c CMD      run CMD as root and exit\n");
}

int main(int argc, char **argv) {
    signal(SIGPIPE, SIG_IGN);
    const char *cmd = NULL;
    int i = 1;
    while (i < argc) {
        if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            usage();
            return 0;
        }
        if (strcmp(argv[i], "-c") == 0) {
            if (i + 1 >= argc) {
                usage();
                return 2;
            }
            /* Everything after -c is the command, joined with spaces so that
             * `su -c pm list packages` works like the real thing. */
            size_t total = 1;
            for (int j = i + 1; j < argc; j++) total += strlen(argv[j]) + 1;
            char *joined = calloc(1, total);
            if (!joined) return 1;
            for (int j = i + 1; j < argc; j++) {
                if (j > i + 1) strncat(joined, " ", total - strlen(joined) - 1);
                strncat(joined, argv[j], total - strlen(joined) - 1);
            }
            cmd = joined;
            break;
        }
        i++;
    }

    int s = connect_su();
    if (s < 0) {
        fprintf(stderr,
                "su: root helper is not running (no %s)\n"
                "    run  python glk_root.py  on the PC first; root only lives\n"
                "    until the next reboot.\n",
                SU_SOCK);
        return 1;
    }

    if (cmd) {
        char header[64];
        int n = snprintf(header, sizeof(header), "EXEC %zu\n", strlen(cmd));
        /* A rejected caller gets its socket closed as soon as the helper has
         * written the reason, so these writes may fail with EPIPE. That is not
         * an error worth reporting: relay() still drains the socket and prints
         * whatever the helper sent. */
        (void) write(s, header, (size_t) n);
        (void) write(s, cmd, strlen(cmd));
    } else {
        (void) write(s, "SHELL\n", 6);
    }

    int rc = relay(s);
    close(s);
    return rc;
}
