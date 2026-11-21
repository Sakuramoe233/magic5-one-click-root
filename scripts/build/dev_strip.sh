#!/system/bin/sh
export PATH=/data/local/tmp/tc/usr/bin:/system/bin
export LD_LIBRARY_PATH=/data/local/tmp/tc/usr/lib
cd /data/local/tmp/build/bakasu/kernel || exit 1
llvm-strip -g kernelsu.ko -o /data/local/tmp/ksu-r4.ko || exit 1
ls -la /data/local/tmp/ksu-r4.ko
