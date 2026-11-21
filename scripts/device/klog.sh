#!/system/bin/sh
# Mirror the kernel ring buffer to disk with a per-block fsync, so the last
# messages before a panic survive the immediate reboot.
exec cat /dev/kmsg | dd of=/data/local/tmp/k2.log conv=fsync bs=4096 status=none
