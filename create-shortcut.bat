@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "PROJ_DIR=%~dp0"
set "PID_FILE=%PROJ_DIR%flask.pid"
set "LOG_FILE=%PROJ_DIR%flask.log"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM ============================================================
REM  个人知识库 - 创建桌面快捷方式
REM ============================================================
echo.
echo ============================================================
echo   创建桌面快捷方式
echo ============================================================

REM 获取桌面路径（兼容中英文系统）
for /f "usebackq tokens=2,*" %%A in (`reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop 2^>nul`) do set "DESKTOP=%%B"
if not defined DESKTOP set "DESKTOP=%USERPROFILE%\Desktop"
if not exist "%DESKTOP%" mkdir "%DESKTOP%"

set "LNK=%DESKTOP%\个人知识库.lnk"
set "TARGET=%PROJ_DIR%launcher.bat"
set "ICON=%PROJ_DIR%static\icon-128.png"

REM 用 PowerShell 创建 .lnk（VBScript 方式在部分精简系统不可用）
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$sc = $ws.CreateShortcut('%LNK%'); " ^
  "$sc.TargetPath = '%TARGET%'; " ^
  "$sc.WorkingDirectory = '%PROJ_DIR%'; " ^
  "$sc.IconLocation = '%ICON%, 0'; " ^
  "$sc.Description = '个人知识库 - Flask + MySQL'; " ^
  "$sc.WindowStyle = 7; " ^
  "$sc.Save(); " ^
  "Write-Host '[OK] 快捷方式已创建'"

if exist "%LNK%" (
    echo [OK] 桌面快捷方式已创建:
    echo      %LNK%
) else (
    echo [X] 快捷方式创建失败，可手动右键 launcher.bat 发送到桌面
)
echo.
pause
