# source me: build environment for the ACK tree on the phone
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
# bionic has no bcmp and a minimal elf.h; the arm64 asm headers are needed by
# a few scripts/ tools that pull in <linux/rwonce.h>.
export HOSTCFLAGS="-Dbcmp=memcmp -I/data/local/tmp/build/shim"
