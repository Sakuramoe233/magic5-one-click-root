#!/system/bin/sh
# Stage B：装载 KSU 模块。
# 日志文件名每次唯一 —— permissive 窗口里新建的文件没有 SELinux 标签，复用一个
# 固定名字在 enforcing 下会被静默丢弃，看起来像"没有日志"。
MOD=${1:-/data/local/tmp/ksu-kit.ko}
cd /data/local/tmp || exit 1

TAG=$(date +%H%M%S 2>/dev/null || echo manual)
KM=/data/local/tmp/km-$TAG.log

./su -c 'echo 0 > /proc/sys/kernel/panic_on_oops; echo 0 > /proc/sys/kernel/panic_on_warn; echo 0 > /proc/sys/kernel/hung_task_panic' 2>/dev/null
./su -c "rm -f $KM /data/local/tmp/insmod.rc" 2>/dev/null

setsid ./su -c "/data/local/tmp/kmsgsync $KM" >/dev/null 2>&1 &
sleep 1

# 必须后台执行：init 阶段一旦 oops，前台 insmod 会让 adb 永远不返回。
setsid ./su -c "insmod $MOD; echo rc=\$? > /data/local/tmp/insmod.rc" >/dev/null 2>&1 &

echo "kmlog=$KM"
