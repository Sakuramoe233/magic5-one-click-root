#!/system/bin/sh
. /data/local/tmp/build/env_kernel.sh
export TMPDIR=/data/local/tmp/build/tmpdbg
mkdir -p $TMPDIR
cd /data/local/tmp/build/bakasu/kernel || exit 1
echo "--- config:"; grep -E '^CONFIG_(KSU|MODVERSIONS|MODULES)=' /data/local/tmp/build/ack/.config
echo "--- dry run (M only):"
make -C /data/local/tmp/build/ack M=$PWD modules -j1 -n SHELL=/system/bin/sh 2>&1 | grep -vE '^-- |compat' | head -30
