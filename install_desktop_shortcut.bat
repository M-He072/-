@echo off
chcp 936 >nul
setlocal enabledelayedexpansion
title KB - Install Desktop Shortcuts
REM ============================================================
REM  One-click install desktop shortcuts (Start / Stop / Update / Push)
REM  Uses PowerShell (WScript.Shell COM object) which handles
REM  Chinese paths / Unicode correctly, unlike VBS in some CMD code pages.
REM ============================================================

cd /d "%~dp0"
set "PROJ_DIR=%~dp0"
set "PROJ_DIR=%PROJ_DIR:~0,-1%"

set "DESKTOP_DIR=%USERPROFILE%\Desktop"
if not exist "%DESKTOP_DIR%" (
    for /f "tokens=2*" %%a in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" /v Desktop 2^>nul ^| find "Desktop"') do (
        set "DESKTOP_DIR=%%~b"
        goto :got_desktop
    )
)
:got_desktop
if not exist "%DESKTOP_DIR%" (
    echo [ERROR] Cannot resolve desktop directory: %DESKTOP_DIR%
    pause
    exit /b 1
)

set "ICON_FILE=%PROJ_DIR%\static\favicon.ico"
if not exist "%ICON_FILE%" set "ICON_FILE="

echo.
echo ============================================================
echo   Knowledge Base - Install Desktop Shortcuts
echo ============================================================
echo   Project: %PROJ_DIR%
echo   Desktop: %DESKTOP_DIR%
echo   Icon   : %ICON_FILE%
echo.
echo [1/2] Creating shortcuts via PowerShell ...

set "PS_ERR=%TEMP%\kb_sc_err_%RANDOM%.txt"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$links = @(" ^
  "  @{N='启动知识库';         T='%PROJ_DIR%\start.bat';             W=7; D='启动个人知识库服务，自动打开 http://127.0.0.1:5000'}," ^
  "  @{N='停止知识库服务';     T='%PROJ_DIR%\stop.bat';              W=7; D='停止正在运行的知识库后台服务'}," ^
  "  @{N='更新知识库';         T='%PROJ_DIR%\update_local.bat';      W=1; D='从 GitHub 拉取最新代码并重启服务'}," ^
  "  @{N='推送GitHub';         T='%PROJ_DIR%\push_github.bat';       W=1; D='提交本地代码变更并推送到 GitHub 仓库'}" ^
  ");" ^
  "foreach ($l in $links) {" ^
  "  $p = Join-Path '%DESKTOP_DIR%' ($l.N + '.lnk');" ^
  "  $s = $ws.CreateShortcut($p);" ^
  "  $s.TargetPath = $l.T;" ^
  "  $s.WorkingDirectory = '%PROJ_DIR%';" ^
  "  $s.WindowStyle = $l.W;" ^
  "  $s.Description = $l.D;" ^
  "  if ('%ICON_FILE%' -ne '') { $s.IconLocation = '%ICON_FILE%,0'; }" ^
  "  $s.Save();" ^
  "  Write-Host ('  [OK] ' + $l.N + '.lnk');" ^
  "}" 2>"%PS_ERR%"
set "PS_RC=%ERRORLEVEL%"

if exist "%PS_ERR%" (
    for /f "delims=" %%a in ('type "%PS_ERR%" 2^>nul') do echo [PS-ERR] %%a
    del "%PS_ERR%" >nul 2>&1
)

set /a created=0
for %%f in ("启动知识库.lnk" "停止知识库服务.lnk" "更新知识库.lnk" "推送GitHub.lnk") do (
    if exist "%DESKTOP_DIR%\%%~f" set /a created+=1
)

echo.
if %created% gtr 0 (
    echo [OK] %created% shortcut(s) created on desktop:
    echo      1. 启动知识库        - Start service ^& open browser
    echo      2. 停止知识库服务    - Stop background service
    echo      3. 更新知识库        - Pull latest code from GitHub ^& restart
    echo      4. 推送GitHub        - Commit ^& push changes to GitHub
    echo.
    echo [Tip] To remove: run uninstall_desktop_shortcut.bat or press Delete on icons.
) else (
    echo [ERROR] Failed to create shortcuts.
    echo   PowerShell exit code: %PS_RC%
    echo   Please check if you have write permission to:
    echo     %DESKTOP_DIR%
    echo   Or run CMD as normal user (not Run As Administrator, which uses a different Desktop).
    pause
    exit /b 1
)

echo.
echo ============================================================
set /p "choice=  Start Knowledge Base now? (Y/N, default Y): "
if /i not "%choice%"=="N" (
    echo.
    echo [Starting] Launching Knowledge Base service ...
    call "%PROJ_DIR%\start.bat"
)
endlocal
pause
