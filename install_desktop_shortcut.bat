@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 知识库 - 安装桌面快捷方式
REM ============================================================
REM  一键创建桌面快捷方式（启动知识库 + 停止服务）
REM
REM  使用方法：
REM    1. 双击运行本脚本（无需管理员权限）
REM    2. 桌面会出现 "启动知识库.ico" 和 "停止知识库服务.ico" 两个快捷方式
REM    3. 想删除快捷方式：右键桌面图标直接删除，或运行 uninstall_desktop_shortcut.bat
REM ============================================================

cd /d "%~dp0"
set "PROJ_DIR=%~dp0"
set "PROJ_DIR=%PROJ_DIR:~0,-1%"

REM --- 找到用户桌面路径（兼容中文/漫游配置）---
set "DESKTOP_DIR=%USERPROFILE%\Desktop"
if not exist "%DESKTOP_DIR%" (
    for /f "tokens=3* skip=1" %%a in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" /v Desktop 2^>nul') do (
        set "DESKTOP_DIR=%%~b"
        goto :got_desktop
    )
)
:got_desktop
if not exist "%DESKTOP_DIR%" (
    echo [错误] 无法定位桌面目录: %DESKTOP_DIR%
    pause
    exit /b 1
)

REM --- 图标：项目自带 favicon.ico ---
set "ICON_FILE=%PROJ_DIR%\static\favicon.ico"
if not exist "%ICON_FILE%" (
    echo [警告] 未找到 %ICON_FILE%，将使用系统默认图标。
    set "ICON_FILE="
)

REM --- 生成 VBS 临时文件用于创建快捷方式（无需管理员权限）---
set "VBS_FILE=%TEMP%\kb_install_shortcut_%RANDOM%.vbs"

REM --- 快捷方式 1：启动知识库（指向 start.bat，最小化窗口，启动后自动打开浏览器）---
echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_FILE%"
REM --- 启动快捷方式 ---
echo Set Lnk1 = WshShell.CreateShortcut("%DESKTOP_DIR%\启动知识库.lnk") >> "%VBS_FILE%"
echo Lnk1.TargetPath = "%PROJ_DIR%\start.bat" >> "%VBS_FILE%"
echo Lnk1.WorkingDirectory = "%PROJ_DIR%" >> "%VBS_FILE%"
echo Lnk1.WindowStyle = 7 >> "%VBS_FILE%"
echo Lnk1.Description = "启动个人知识库服务，打开 http://127.0.0.1:5000" >> "%VBS_FILE%"
if defined ICON_FILE (
    echo Lnk1.IconLocation = "%ICON_FILE%,0" >> "%VBS_FILE%"
)
echo Lnk1.Save >> "%VBS_FILE%"
REM --- 停止快捷方式 ---
echo Set Lnk2 = WshShell.CreateShortcut("%DESKTOP_DIR%\停止知识库服务.lnk") >> "%VBS_FILE%"
echo Lnk2.TargetPath = "%PROJ_DIR%\stop.bat" >> "%VBS_FILE%"
echo Lnk2.WorkingDirectory = "%PROJ_DIR%" >> "%VBS_FILE%"
echo Lnk2.WindowStyle = 7 >> "%VBS_FILE%"
echo Lnk2.Description = "停止正在运行的知识库后台服务" >> "%VBS_FILE%"
if defined ICON_FILE (
    echo Lnk2.IconLocation = "%ICON_FILE%,0" >> "%VBS_FILE%"
)
echo Lnk2.Save >> "%VBS_FILE%"
REM --- 更新快捷方式 ---
echo Set Lnk3 = WshShell.CreateShortcut("%DESKTOP_DIR%\更新知识库.lnk") >> "%VBS_FILE%"
echo Lnk3.TargetPath = "%PROJ_DIR%\update_local.bat" >> "%VBS_FILE%"
echo Lnk3.WorkingDirectory = "%PROJ_DIR%" >> "%VBS_FILE%"
echo Lnk3.WindowStyle = 1 >> "%VBS_FILE%"
echo Lnk3.Description = "从 GitHub 拉取最新代码并重启服务" >> "%VBS_FILE%"
if defined ICON_FILE (
    echo Lnk3.IconLocation = "%ICON_FILE%,0" >> "%VBS_FILE%"
)
echo Lnk3.Save >> "%VBS_FILE%"
REM --- 推送快捷方式 ---
echo Set Lnk4 = WshShell.CreateShortcut("%DESKTOP_DIR%\推送GitHub.lnk") >> "%VBS_FILE%"
echo Lnk4.TargetPath = "%PROJ_DIR%\push_github.bat" >> "%VBS_FILE%"
echo Lnk4.WorkingDirectory = "%PROJ_DIR%" >> "%VBS_FILE%"
echo Lnk4.WindowStyle = 1 >> "%VBS_FILE%"
echo Lnk4.Description = "提交本地代码变更并推送到 GitHub" >> "%VBS_FILE%"
if defined ICON_FILE (
    echo Lnk4.IconLocation = "%ICON_FILE%,0" >> "%VBS_FILE%"
)
echo Lnk4.Save >> "%VBS_FILE%"

REM --- 执行 VBS ---
echo.
echo ============================================================
echo   知识库 - 安装桌面快捷方式
echo ============================================================
echo   项目目录: %PROJ_DIR%
echo   桌面目录: %DESKTOP_DIR%
echo   图标文件: %ICON_FILE%
echo.
echo [1/2] 正在创建桌面快捷方式 ...
cscript //nologo "%VBS_FILE%" 2>nul
del "%VBS_FILE%" >nul 2>&1

REM --- 验证 ---
set /a created=0
if exist "%DESKTOP_DIR%\启动知识库.lnk" set /a created+=1
if exist "%DESKTOP_DIR%\停止知识库服务.lnk" set /a created+=1
if exist "%DESKTOP_DIR%\更新知识库.lnk" set /a created+=1
if exist "%DESKTOP_DIR%\推送GitHub.lnk" set /a created+=1

if %created% gtr 0 (
    echo [OK] 已创建 %created% 个桌面快捷方式:
    echo      1. 启动知识库       （双击启动服务并打开浏览器）
    echo      2. 停止知识库服务   （双击停止后台服务）
    echo      3. 更新知识库       （从 GitHub 拉取代码并重启）
    echo      4. 推送GitHub       （提交变更并推送到远程仓库）
    echo.
    echo [提示] 想删除快捷方式：运行 uninstall_desktop_shortcut.bat
    echo       或直接在桌面选中图标后按 Delete
) else (
    echo [错误] 快捷方式创建失败，请检查桌面目录权限。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   是否立即启动知识库？(Y/N)
set /p "choice=  请选择 (默认 Y): "
if /i not "%choice%"=="N" (
    echo.
    echo [启动中] 正在启动知识库服务 ...
    call "%PROJ_DIR%\start.bat"
)
endlocal
pause
