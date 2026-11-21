@echo off
setlocal
cd /d "%~dp0"
title Magic5 ÁÙÊ± Root by£ºÒ¹¿ÕµÄ»¨»ði

set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS%" set "PS=powershell"

"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\kit.ps1" -RootOnly %*

echo.
echo ----------------------------------------------
echo  Press any key to close this window.
pause >nul
