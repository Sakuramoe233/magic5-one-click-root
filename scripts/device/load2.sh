#!/system/bin/sh
# Load a module with a crash-proof kernel log.
#   usage: load2.sh /data/local/tmp/<module>.ko
# The log path is unique per run: files created during the permissive window
# carry no SELinux label, so reusing one across boots silently swallows writes.
MOD=${1:-/data/local/tmp/ksu-dbg.ko}
cd /data/local/tmp || exit 1
TAG=$(date +%H%M%S 2>/dev/null || echo manual)
KMLOG="/data/local/tmp/km-$TAG.log"

./su -c 'echo 0 > /proc/sys/kernel/panic_on_oops; echo 0 > /proc/sys/kernel/panic_on_warn; echo 0 > /proc/sys/kernel/hung_task_panic'
./su -c "rm -f $KMLOG /data/local/tmp/insmod.rc"

setsid ./su -c "kmsgsync $KMLOG" >/dev/null 2>&1 &
sleep 1

setsid ./su -c "insmod $MOD; echo rc=\$? > /data/local/tmp/insmod.rc" >/dev/null 2>&1 &
echo "module=$MOD"
echo "kmlog=$KMLOG"
