#!/system/bin/sh
export PATH=/data/local/tmp/tc/usr/bin:/system/bin
export LD_LIBRARY_PATH=/data/local/tmp/tc/usr/lib
llvm-objdump -d --no-show-raw-insn /data/local/tmp/ksu-r4.ko 2>/dev/null | awk '/<ksu_sha256>:/{f=1} f{print} f&&/^$/{exit}' | head -45
