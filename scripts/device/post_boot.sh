#!/system/bin/sh
# Post-reboot bootstrap: temp root -> kallsyms dump -> ready-to-patch state.
# Deliberately does NOT pass GLK_ZERO_ADDR: the address embeds the boot's KASLR
# slide, so a stale value writes into vmalloc space. Read sig_enforce first and
# only zero it if the boot really came up enforcing.
cd /data/local/tmp || exit 1
rm -f glk-run.log ks-boot.txt root-state.txt

{
    echo "sig_enforce_before=$(cat /sys/module/module/parameters/sig_enforce 2>/dev/null)"
    echo "uptime_before=$(cut -d' ' -f1 /proc/uptime)"
} > root-state.txt

GLK_ZERO_LEAF=0 setsid ./glk-bin --load-prebuilt-profile /data/local/tmp/profile_175.bin \
    > /data/local/tmp/glk-run.log 2>&1 &

for i in $(seq 1 40); do
    sleep 2
    grep -qa "child is root" /data/local/tmp/glk-run.log && break
done

echo "reached_root_at=$((i*2))s" >> root-state.txt
sleep 2

./su -c 'echo 0 > /proc/sys/kernel/kptr_restrict; cat /proc/kallsyms' > ks-boot.txt 2>/dev/null
{
    echo "ks_lines=$(wc -l < ks-boot.txt)"
    echo "text=$(grep -m1 " _text$" ks-boot.txt | cut -d" " -f1)"
    echo "sig_enforce_sym=$(grep -m1 " sig_enforce$" ks-boot.txt | cut -d" " -f1)"
    echo "sig_enforce_after=$(cat /sys/module/module/parameters/sig_enforce 2>/dev/null)"
    echo "uid=$(./su -c id -u 2>/dev/null)"
} >> root-state.txt
echo BOOTSTRAP_DONE
