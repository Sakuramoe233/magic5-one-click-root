#!/usr/bin/env bash
# 在 Linux x86_64 上为 Honor Magic5（5.15.180-android13-8, KASAN 构建）编译
# 与设备 ABI 匹配的 KernelSU LKM。产物用于本仓库已验证的“内存加载”流程。
#
# 依赖：git make bc bison flex libssl-dev python3 xz-utils lz4 curl（约 40GB 磁盘）
# 用法：bash build_lkm.sh /path/to/magic5-config.gz
set -euo pipefail

CONFIG_GZ="${1:-./magic5-config.gz}"
WORK="${WORK:-$HOME/ksu-lkm-build}"
KSU_REF="${KSU_REF:-main}"

mkdir -p "$WORK"
cd "$WORK"

# 1) GKI android13-5.15 源码（与设备同代 KMI）
if [ ! -d ack/.git ]; then
  git clone --depth 1 -b android13-5.15-lts \
    https://android.googlesource.com/kernel/common ack
fi

# 2) 用设备真实 config（关键：KASAN/SCHEDSTATS 等会改变 task_struct 布局）
zcat "$CONFIG_GZ" > ack/.config
(cd ack && make ARCH=arm64 LLVM=1 olddefconfig)

# 3) KernelSU 内核模块源码
if [ ! -d KernelSU ]; then
  git clone --depth 1 -b "$KSU_REF" https://github.com/tiann/KernelSU
fi

# 4) 以外部模块方式编译 LKM
#    make 参数请对照 KernelSU 仓库 .github/workflows/kernel.yml 的 LKM 任务，
#    不同版本可能要求 KSU_LKM=1 等变量。
cd KernelSU/kernel
make -C "$WORK/ack" M="$PWD" ARCH=arm64 LLVM=1 \
     CC=clang LD=ld.lld AR=llvm-ar NM=llvm-nm OBJCOPY=llvm-objcopy \
     OBJDUMP=llvm-objdump STRIP=llvm-strip \
     modules -j"$(nproc)"

cp kernelsu.ko "$WORK/kernelsu-$(uname -r).ko" 2>/dev/null || true
echo
echo "产物：$(ls -1 "$WORK"/KernelSU/kernel/kernelsu.ko)"
echo "下一步：python verify_ko_layout.py <该 .ko> vmlinux.btf"
echo "  [OK] 才能拿去设备上加载，否则说明 config 仍不匹配。"
