/* kmsgfsync: mirror /dev/kmsg to a file, flushing every record with O_SYNC so
 * that a panic trace survives an immediate reboot. */
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define OUT "/data/local/tmp/kmsg-sync.log"

int main(void) {
    int in = open("/dev/kmsg", O_RDONLY);
    if (in < 0) { perror("open /dev/kmsg"); return 1; }

    int out = open(OUT, O_WRONLY | O_CREAT | O_APPEND | O_SYNC, 0666);
    if (out < 0) { perror("open out"); return 1; }

    static char buf[8192];
    for (;;) {
        ssize_t n = read(in, buf, sizeof(buf) - 1);
        if (n <= 0) {
            if (n < 0) { usleep(20000); continue; }
            continue;
        }
        buf[n] = '\n';
        ssize_t off = 0, total = n + 1;
        while (off < total) {
            ssize_t w = write(out, buf + off, (size_t) (total - off));
            if (w <= 0) break;
            off += w;
        }
    }
    return 0;
}
