@echo off
setlocal
chcp 65001 >nul

if "%~1"=="" goto usage
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\proxy.ps1" -Branch "%~1" -Confirm
exit /b %ERRORLEVEL%

:usage
echo Usage: .\proxy-confirm BRANCH
echo Example: .\proxy-confirm yh-submission2
exit /b 2
