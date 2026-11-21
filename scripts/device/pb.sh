#!/system/bin/sh
# One-shot post-reboot bootstrap: temp root + sig_enforce zero + kallsyms dump.
# The su socket needs a few seconds after "child is root", so poll it instead of
# reading kallsyms straight away (a too-early dump yields an empty file).
cd /data/local/tmp || exit 1
TAG=$(date +%H%M%S 2>/dev/null || echo manual)
LOG="glk-$TAG.log"
KS="ks-$TAG.txt"

rm -f "$LOG"
GLK_ZERO_LEAF=0 GLK_ZERO_ADDR=0xffffffc0830c7708 setsid ./glk-bin \
    --load-prebuilt-profile /data/local/tmp/profile_175.bin > "$LOG" 2>&1 &

i=0
while [ $i -lt 40 ]; do
    sleep 2
    grep -qa "child is root" "$LOG" && break
    i=$((i + 1))
done

U=""
i=0
while [ $i -lt 20 ]; do
    U=$(./su -c 'id -u' 2>/dev/null)
    [ "$U" = "0" ] && break
    sleep 2
    i=$((i + 1))
done

if [ "$U" = "0" ]; then
    ./su -c 'echo 0 > /proc/sys/kernel/kptr_restrict; cat /proc/kallsyms' > "$KS" 2>/dev/null
fi

echo "TAG=$TAG"
echo "uid=$U"
echo "ks=$KS"
echo "ks_lines=$(wc -l < "$KS" 2>/dev/null)"
echo "sig=$(./su -c 'cat /sys/module/module/parameters/sig_enforce' 2>/dev/null)"
echo "text=$(grep -m1 ' _text$' "$KS" 2>/dev/null | cut -d' ' -f1)"
