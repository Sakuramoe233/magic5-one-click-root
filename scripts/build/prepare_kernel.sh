#!/system/bin/sh
# Configure the ACK tree with the device's own /proc/config.gz and prepare it
# for out-of-tree module builds.  Runs on the phone (Termux userland in
# /data/local/tmp/tc/usr).
set -e

PREFIX=/data/local/tmp/tc/usr
export PATH=$PREFIX/bin:/system/bin:/system/xbin
export LD_LIBRARY_PATH=$PREFIX/lib
export TMPDIR=/data/local/tmp/tmp
export HOME=/data/local/tmp
mkdir -p $TMPDIR

export ARCH=arm64
export LLVM=1
export CC=$PREFIX/bin/clang
export HOSTCC=$PREFIX/bin/clang
export HOSTCXX=$PREFIX/bin/clang++
export LD=$PREFIX/bin/ld.lld
export AR=$PREFIX/bin/llvm-ar
export NM=$PREFIX/bin/llvm-nm
export OBJCOPY=$PREFIX/bin/llvm-objcopy
export OBJDUMP=$PREFIX/bin/llvm-objdump
export STRIP=$PREFIX/bin/llvm-strip
export READELF=$PREFIX/bin/llvm-readelf
export CROSS_COMPILE=aarch64-linux-gnu-
# bionic only declares bcmp from API 28 on; the host tools are just memcmp users
export HOSTCFLAGS="-Dbcmp=memcmp"

cd /data/local/tmp/build/ack

# 1) device config
if [ ! -f .config ] || [ "$1" = "reset" ]; then
	gzip -dc /data/local/tmp/build/magic5-config.gz > .config
	# Build-host only switches: none of these change any struct layout.
	sed -i 's/^CONFIG_MODULE_SIG_ALL=y/# CONFIG_MODULE_SIG_ALL is not set/' .config
	sed -i 's/^CONFIG_DEBUG_INFO_BTF_MODULES=y/# CONFIG_DEBUG_INFO_BTF_MODULES is not set/' .config
	# BTF generation needs pahole + pulls in tools/bpf/resolve_btfids; debug only
	sed -i 's/^CONFIG_DEBUG_INFO_BTF=y/# CONFIG_DEBUG_INFO_BTF is not set/' .config
	sed -i 's/^CONFIG_WERROR=y/# CONFIG_WERROR is not set/' .config
	sed -i 's/^CONFIG_LOCALVERSION_AUTO=y/# CONFIG_LOCALVERSION_AUTO is not set/' .config
	echo 'CONFIG_LOCALVERSION="-android13-8-g1c54d617912d"' >> .config
	# match the device's 5.15.180 release string exactly
	sed -i 's/^SUBLEVEL = 195$/SUBLEVEL = 180/' Makefile
	grep -E '^(VERSION|PATCHLEVEL|SUBLEVEL) =' Makefile
fi

echo "=== olddefconfig ==="
make -j6 olddefconfig

echo "=== modules_prepare ==="
make -j6 modules_prepare

echo "=== done ==="
make kernelrelease
