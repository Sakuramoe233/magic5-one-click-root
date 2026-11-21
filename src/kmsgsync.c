/* kmsg log mirror with per-record O_SYNC so a panic trace survives reboot.
 * argv[1] = output path (fresh file per boot keeps SELinux labels sane). */
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv) {
    const char *out = argc > 1 ? argv[1] : "/data/local/tmp/kmsg-sync.log";
    int in = open("/dev/kmsg", O_RDONLY);
    if (in < 0) { perror("open /dev/kmsg"); return 1; }
    int fd = open(out, O_WRONLY | O_CREAT | O_TRUNC | O_SYNC, 0666);
    if (fd < 0) { perror("open out"); return 1; }
    static char buf[8192];
    for (;;) {
        ssize_t n = read(in, buf, sizeof(buf) - 1);
        if (n <= 0) continue;
        buf[n] = '\n';
        ssize_t off = 0, total = n + 1;
        while (off < total) {
            ssize_t w = write(fd, buf + off, total - off);
            if (w <= 0) break;
            off += w;
        }
    }
    return 0;
}
