#!/bin/sh
# HONOR's hwtransport.exe sometimes squats on TCP 5037 speaking a different
# protocol, making adb fail with "could not read ok from ADB Server".  Try the
# plain call first, and only evict it when adb actually fails.
export PATH="/g/ADB-platform-tools:$PATH"
export MSYS_NO_PATHCONV=1

out=$(adb "$@" 2>&1)
rc=$?
case "$out" in
*"could not read ok from ADB Server"*|*"cannot connect to daemon"*|*"protocol fault"*)
	taskkill //F //IM hwtransport.exe >/dev/null 2>&1
	sleep 0.3
	adb start-server >/dev/null 2>&1
	sleep 0.5
	exec adb "$@"
	;;
esac
printf '%s\n' "$out"
exit $rc
