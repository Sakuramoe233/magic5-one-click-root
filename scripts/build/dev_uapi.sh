#!/system/bin/sh
F=/data/local/tmp/build/bakasu/uapi/supercall.h
if grep -q 'KERNEL_SU_UAPI_VERSION = 6' $F; then
	echo "already 6"
else
	sed -i 's/static const __u32 KERNEL_SU_UAPI_VERSION = 4;/static const __u32 KERNEL_SU_UAPI_VERSION = 6;/' $F
	grep -n 'KERNEL_SU_UAPI_VERSION =' $F
fi
