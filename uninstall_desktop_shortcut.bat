@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 知识库 - 卸载桌面快捷方式
REM ============================================================
REM  一键删除桌面快捷方式
REM  与 install_desktop_shortcut.bat 成对使用
REM ============================================================

REM --- 找到用户桌面路径（兼容中文/漫游配置）---
set "DESKTOP_DIR=%USERPROFILE%\Desktop"
if not exist "%DESKTOP_DIR%" (
    for /f "tokens=3* skip=1" %%a in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" /v Desktop 2^>nul') do (
        set "DESKTOP_DIR=%%~b"
        goto :got_desktop
    )
)
:got_desktop

echo.
echo ============================================================
echo   知识库 - 卸载桌面快捷方式
echo   桌面目录: %DESKTOP_DIR%
echo ============================================================
echo.

set /a deleted=0
for %%f in ("启动知识库.lnk" "停止知识库服务.lnk" "更新知识库.lnk" "推送GitHub.lnk") do (
    if exist "%DESKTOP_DIR%\%%~f" (
        del /q "%DESKTOP_DIR%\%%~f"
        echo [已删除] %%~f
        set /a deleted+=1
    ) else (
        echo [跳过] %%~f（不存在）
    )
)

echo.
if %deleted% gtr 0 (
    echo [完成] 已删除 %deleted% 个桌面快捷方式。
) else (
    echo [完成] 桌面没有找到知识库的快捷方式。
)
echo.
pause
