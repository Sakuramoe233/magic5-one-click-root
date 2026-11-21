/* drop to an arbitrary uid, then exec the su client: proves the helper's
 * SO_PEERCRED allowlist actually rejects non-allowlisted callers. */
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    if (argc < 3) return 2;
    uid_t u = (uid_t) strtoul(argv[1], NULL, 10);
    if (setresgid(u, u, u) != 0 || setresuid(u, u, u) != 0) { perror("setresuid"); return 3; }
    execv(argv[2], &argv[2]);
    perror("execv");
    return 4;
}
