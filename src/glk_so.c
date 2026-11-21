/*
 * magic5-root.so -- single-file payload wrapper for the GhostLock root chain.
 *
 * Why a wrapper: the exploit binary is a normal PIE executable, but it insists
 * on finding its post-exploitation helper at /data/local/tmp/glk-helper-bin
 * (hardcoded in victim_process.cpp) and needs a profile blob next to it. A host
 * that imports one ".so" cannot ship four files, so everything is appended to
 * this ELF and unpacked at start-up.
 *
 * Note on the ".so" name: like Stellar's own libstellar.so, this is an
 * executable ELF that happens to carry a .so suffix -- the kernel does not care
 * about the extension, and hosts in this scene launch their payloads with
 * execve(). It is therefore NOT a dlopen()able plugin.
 *
 *   magic5-root.so                 unpack, then run the exploit
 *   magic5-root.so su -c "id"      use the su client (after a successful run)
 *   magic5-root.so perm list       use the permission manager
 *   magic5-root.so --status        is the root helper alive?
 *   magic5-root.so --unpack-only   just drop the files
 *
 * It must run with write access to /data/local/tmp (uid 2000 shell or root),
 * because that is where the exploit looks for its helper.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

/* 载荷一律落 /data/local/tmp 顶层：该目录对 shell 可写，而 .glk 在拿到 root 后
 * 会被 helper 建成 root:root 0755，shell 再进去就写不动了。 */
#define GLK_DIR "/data/local/tmp"
#define P_PROFILE "/data/local/tmp/glk-profile.bin"
#define P_HELPER "/data/local/tmp/glk-helper-bin"
#define P_EXE "/data/local/tmp/glk-bin"
#define P_SU "/data/local/tmp/su"
#define P_PERM "/data/local/tmp/su-perm"

#define FOOTER_MAGIC "GLKPAYLD"
#define FOOTER_SIZE 32

struct footer {
    char magic[8];
    uint32_t version;
    uint32_t n_profile;
    uint32_t n_helper;
    uint32_t n_exe;
    uint32_t n_su;
    uint32_t n_perm;
};

static const char *self_path(char *buf, size_t len) {
    ssize_t n = readlink("/proc/self/exe", buf, len - 1);
    if (n > 0) {
        buf[n] = '\0';
        /* readlink follows the exec'd file; for a dlopen'd library it reports
         * the host process instead, so fall back to dladdr below. */
        if (strstr(buf, "magic5-root") || strstr(buf, ".so")) return buf;
    }
    Dl_info info;
    if (dladdr((void *) self_path, &info) && info.dli_fname) {
        strncpy(buf, info.dli_fname, len - 1);
        buf[len - 1] = '\0';
        return buf;
    }
    return NULL;
}

static int write_blob(int src, const char *dst, uint32_t size, mode_t mode) {
    char tmp[256];
    snprintf(tmp, sizeof(tmp), "%s.tmp%d", dst, (int) getpid());

    int out = open(tmp, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, mode);
    if (out < 0) {
        fprintf(stderr, "magic5-root: 无法写入 %s: %s\n", dst, strerror(errno));
        return -1;
    }
    char buf[65536];
    uint32_t left = size;
    while (left) {
        size_t want = left < sizeof(buf) ? left : sizeof(buf);
        ssize_t got = read(src, buf, want);
        if (got <= 0) {
            close(out);
            unlink(tmp);
            fprintf(stderr, "magic5-root: 读取载荷失败\n");
            return -1;
        }
        ssize_t off = 0;
        while (off < got) {
            ssize_t w = write(out, buf + off, (size_t) (got - off));
            if (w <= 0) {
                close(out);
                unlink(tmp);
                return -1;
            }
            off += w;
        }
        left -= (uint32_t) got;
    }
    close(out);
    chmod(tmp, mode);
    if (rename(tmp, dst) != 0) {
        unlink(tmp);
        fprintf(stderr, "magic5-root: 落盘 %s 失败: %s\n", dst, strerror(errno));
        return -1;
    }
    return 0;
}

static int unpack(const char *argv0) {
    char path[512];
    const char *self = self_path(path, sizeof(path));
    if (!self) {
        fprintf(stderr, "magic5-root: 找不到自身路径\n");
        return 1;
    }

    int fd = open(self, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        fprintf(stderr, "magic5-root: 打不开自身 %s: %s\n", self, strerror(errno));
        return 1;
    }
    off_t end = lseek(fd, 0, SEEK_END);
    if (end < FOOTER_SIZE) {
        close(fd);
        fprintf(stderr, "magic5-root: 文件不完整\n");
        return 1;
    }
    struct footer f;
    lseek(fd, end - FOOTER_SIZE, SEEK_SET);
    if (read(fd, &f, sizeof(f)) != (ssize_t) sizeof(f) || memcmp(f.magic, FOOTER_MAGIC, 8) != 0) {
        close(fd);
        fprintf(stderr, "magic5-root: 载荷尾标损坏\n");
        return 1;
    }

    uint32_t total = f.n_profile + f.n_helper + f.n_exe + f.n_su + f.n_perm;
    off_t start = end - FOOTER_SIZE - (off_t) total;
    if (start < 0) {
        close(fd);
        fprintf(stderr, "magic5-root: 载荷长度异常\n");
        return 1;
    }

    mkdir(GLK_DIR, 0755);
    if (access(GLK_DIR, W_OK) != 0) {
        close(fd);
        fprintf(stderr, "magic5-root: 需要 /data/local/tmp 的写权限（shell 或 root 身份运行）\n");
        return 1;
    }

    lseek(fd, start, SEEK_SET);
    int rc = 0;
    rc |= write_blob(fd, P_PROFILE, f.n_profile, 0644);
    rc |= write_blob(fd, P_HELPER, f.n_helper, 0755);
    rc |= write_blob(fd, P_EXE, f.n_exe, 0755);
    rc |= write_blob(fd, P_SU, f.n_su, 0755);
    rc |= write_blob(fd, P_PERM, f.n_perm, 0755);
    close(fd);
    return rc == 0 ? 0 : 1;
}

static void usage(void) {
    fprintf(stderr,
            "usage: magic5-root.so [--status|--unpack-only|su ...|perm ...]\n"
            "  默认        解包并执行提权链\n"
            "  su ...      调用 su 客户端（提权成功之后）\n"
            "  perm ...    调用 su-perm 权限管理\n"
            "  --status    root helper 是否存活\n"
            "  --unpack-only  只解包，不执行\n");
}

int main(int argc, char **argv) {
    if (argc > 1 && (strcmp(argv[1], "-h") == 0 || strcmp(argv[1], "--help") == 0)) {
        usage();
        return 0;
    }

    if (unpack(argv[0]) != 0) return 1;

    if (argc > 1 && strcmp(argv[1], "--unpack-only") == 0) {
        printf("已解包到 %s\n", GLK_DIR);
        return 0;
    }
    if (argc > 1 && strcmp(argv[1], "--status") == 0) {
        execl(P_PERM, "su-perm", "status", (char *) NULL);
        perror("magic5-root: exec su-perm");
        return 1;
    }
    if (argc > 1 && strcmp(argv[1], "su") == 0) {
        char **sub = &argv[1];
        sub[0] = (char *) P_SU;
        execv(P_SU, sub);
        perror("magic5-root: exec su");
        return 1;
    }
    if (argc > 1 && strcmp(argv[1], "perm") == 0) {
        char **sub = &argv[1];
        sub[0] = (char *) P_PERM;
        execv(P_PERM, sub);
        perror("magic5-root: exec su-perm");
        return 1;
    }

    fprintf(stderr, "[*] magic5-root: 载荷已就位，开始提权（约 15-20 秒，可能触发一次内核重启）\n");
    fflush(stderr);
    execl(P_EXE, P_EXE, "--load-prebuilt-profile", P_PROFILE, (char *) NULL);
    perror("magic5-root: exec exploit");
    return 1;
}
