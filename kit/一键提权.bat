@echo off
setlocal
cd /d "%~dp0"
title Magic5 一键提权 by：夜空的花火i

set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS%" set "PS=powershell"

"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\kit.ps1" %*

echo.
echo ----------------------------------------------
echo  Press any key to close this window.
pause >nul
