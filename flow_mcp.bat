@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

where pwsh.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0flow_mcp.ps1" %*
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0flow_mcp.ps1" %*
)

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Process exited with code %ERRORLEVEL%
)
