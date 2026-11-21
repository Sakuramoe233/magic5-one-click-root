#!/system/bin/sh
# Fully detached instrumented load: nothing here blocks the calling adb shell.
cd /data/local/tmp || exit 1
rm -f /data/local/tmp/insmod.rc /data/local/tmp/insmod.err
rm -f /data/local/tmp/kmsg-ksu.log

./su -c 'echo 0 > /proc/sys/kernel/panic_on_oops; echo 0 > /proc/sys/kernel/hung_task_panic; echo 0 > /proc/sys/kernel/hung_task_timeout_secs; echo 0 > /proc/sys/kernel/kptr_restrict' >/dev/null 2>&1

# kernel log side channel: survives an init that never returns
./su -c 'cat /dev/kmsg > /data/local/tmp/kmsg-ksu.log' >/dev/null 2>&1 &
sleep 1

# detached load; rc lands in a file because the caller must not wait
./su -c 'insmod /data/local/tmp/ksu-ready.ko; echo rc=$? > /data/local/tmp/insmod.rc' >/data/local/tmp/insmod.err 2>&1 &

echo started
