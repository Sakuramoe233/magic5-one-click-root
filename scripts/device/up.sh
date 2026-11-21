#!/usr/bin/env bash
# 重启后一键恢复 BakaSU（LKM）：
#   拿临时 root → 清零 sig_enforce → 导当次 kallsyms → 按本次 KASLR 打补丁
#   → insmod → 触发 ksud post-fs-data / services
#
# 用法：bash up.sh [模块.ko]
# 默认模块：ksu-r8.ko（已 llvm-strip -g、已把 __ubsan_handle_cfi_check_fail_abort
# 改名成本内核存在的 __ubsan_handle_cfi_check_fail）
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
MOD=${1:-$HERE/ksu-r8.ko}
ADB=/g/ADB-platform-tools/adb
export MSYS_NO_PATHCONV=1

say() { printf '\n== %s\n' "$*"; }
# adb/python 都是 Windows 程序，本地路径要转成 C:/... 形式；
# 远端路径必须保持 /data/... 原样，所以全局关掉 MSYS 路径转换。
win() { cygpath -w "$1"; }

say "1/6 连接设备"
$ADB devices | grep -q "device$" || { echo "设备未就绪"; exit 1; }

say "2/6 取 root + 导 kallsyms（约 30s，可能 panic 一次，重跑即可）"
OUT=$($ADB shell "sh /data/local/tmp/pb.sh" 2>&1)
echo "$OUT" | tail -6
UID_=$(echo "$OUT" | sed -n 's/^uid=//p' | tail -1)
KS=$(echo "$OUT" | sed -n 's/^ks=//p' | tail -1)
TEXT=$(echo "$OUT" | sed -n 's/^text=//p' | tail -1)
[ "$UID_" = "0" ] || { echo "没拿到 root"; exit 1; }
echo "ks=$KS  _text=$TEXT"

say "3/6 拉符号表并按本次 KASLR 打补丁"
$ADB pull "/data/local/tmp/$KS" "$(win "$HERE/ks-last.txt")" >/dev/null || exit 1
cp "$MOD" "$HERE/ksu-last-ready.ko"
python - "$(win "$HERE/ksu-last-ready.ko")" <<'PY'
import sys
p = sys.argv[1]
d = bytearray(open(p, "rb").read())
OLD = b"__ubsan_handle_cfi_check_fail_abort"
NEW = b"__ubsan_handle_cfi_check_fail"
i = 0
while True:
    i = d.find(OLD, i)
    if i < 0:
        break
    d[i:i + len(OLD)] = NEW + b"\0" * (len(OLD) - len(NEW))
    i += len(OLD)
open(p, "wb").write(d)
PY
python "$(win "$HERE/../tools/patch_ko_kallsyms.py")" \
    "$(win "$HERE/ksu-last-ready.ko")" "$(win "$HERE/ks-last.txt")" \
    "$(win "$HERE/ksu-last-ready.ko")" | tail -3

say "4/6 装载"
$ADB push "$(win "$HERE/ksu-last-ready.ko")" /data/local/tmp/ksu-last-ready.ko >/dev/null
$ADB shell "sh /data/local/tmp/load2.sh /data/local/tmp/ksu-last-ready.ko" | tail -2

i=0
while [ $i -lt 30 ]; do
    sleep 2
    L=$($ADB shell "grep kernelsu /proc/modules" 2>/dev/null)
    case "$L" in *Live*) echo "$L"; break;; esac
    i=$((i + 1))
done
case "${L:-}" in *Live*) ;; *) echo "模块没起来，看 /data/local/tmp/km-*.log"; exit 1;; esac

say "5/6 触发 ksud 事件（best effort）"
# 加载后临时 root 的 su 守护经常会被 KSU 的 SELinux 收尾杀掉，
# 而且 late load 模式下 ksud 会跳过 post-fs-data，所以这一步失败无害。
$ADB shell "./data/local/tmp/su -c '/data/adb/ksu/bin/ksud post-fs-data'" 2>&1 | tail -2 || true

say "6/6 状态"
$ADB shell "grep kernelsu /proc/modules; ls -l /data/adb/ksud 2>/dev/null" 2>&1 | tail -3
echo
echo "完成。打开 BakaSU 管理器应显示「工作中 LKM 越狱模式」。"
