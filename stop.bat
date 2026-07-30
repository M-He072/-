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
REM  个人知识库 - 停止服务
REM ============================================================
echo.
echo ============================================================
echo   个人知识库 - 停止服务
echo ============================================================

set "KILLED=0"

REM --- 按 PID 文件停止 ---
if exist "%PID_FILE%" (
    set /p "PID="<"%PID_FILE%"
    if not "!PID!"=="" (
        echo [*] 停止进程 PID !PID! ...
        taskkill /PID !PID! /T /F >nul 2>&1
        if not errorlevel 1 (
            echo [OK] 已停止 PID !PID!
            set "KILLED=1"
        )
    )
    del "%PID_FILE%" >nul 2>&1
)

REM --- 兜底：按端口停止所有监听 5000 的进程 ---
for /f "tokens=5" %%p in ('netstat -ano -p tcp ^| findstr ":5000" ^| findstr "LISTENING"') do (
    echo [*] 兜底停止端口 5000 占用进程 PID %%p ...
    taskkill /PID %%p /T /F >nul 2>&1
    set "KILLED=1"
)

if "!KILLED!"=="0" (
    echo [i] 未发现运行中的 Flask 服务
) else (
    echo [OK] 服务已停止
)
echo.
pause
