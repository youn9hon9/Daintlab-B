@echo off
setlocal

if "%~1"=="" goto usage
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\proxy.ps1" -Branch "%~1"
exit /b %ERRORLEVEL%

:usage
echo Usage: .\proxy BRANCH
echo Example: .\proxy yh-submission
exit /b 2
