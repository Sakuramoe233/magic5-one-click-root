#!/system/bin/sh
export PATH=/data/local/tmp/tc/usr/bin:/system/bin
export LD_LIBRARY_PATH=/data/local/tmp/tc/usr/lib
cd /data/local/tmp/build || exit 1
python3 patch_ver.py || exit 1
# the version string is compiled into these two objects; touch so make rebuilds
touch bakasu/kernel/core/init.c bakasu/kernel/supercall/dispatch.c
grep -E 'KSU_LOCAL_VERSION :=|KSU_TAG_NAME' bakasu/kernel/Kbuild
