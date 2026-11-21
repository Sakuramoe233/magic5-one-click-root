#!/system/bin/sh
# Incremental rebuild of the KSU module on the phone.
# CONFIG_KSU* are not in .config: the LKM is built by passing them to make.
PREFIX=/data/local/tmp/tc/usr
export PATH=$PREFIX/bin:/system/bin:/system/xbin
export LD_LIBRARY_PATH=$PREFIX/lib

if [ "$1" = "patch" ]; then
	cd /data/local/tmp/build || exit 1
	python3 patch_observer.py || exit 1
fi

. /data/local/tmp/build/env_kernel.sh
export TMPDIR=/data/local/tmp/build/tmpmk
mkdir -p $TMPDIR
cd /data/local/tmp/build/bakasu/kernel || exit 1
rm -f manager/pkg_observer.o kernelsu.o kernelsu.ko
make -C /data/local/tmp/build/ack M=$PWD modules -j$2 \
	SHELL=/system/bin/sh CONFIG_SHELL=/system/bin/sh \
	CONFIG_KSU=m CONFIG_KSU_MULTI_MANAGER_SUPPORT=y CONFIG_KSU_TRACEPOINT_HOOK=y \
	> /data/local/tmp/build/ksu6.log 2>&1
echo "make_rc=$?"
grep -E '^(  CC|  LD|  MODPOST|make.*Error)' /data/local/tmp/build/ksu6.log | tail -12
tail -6 /data/local/tmp/build/ksu6.log
ls -la kernelsu.ko
