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
REM  个人知识库 - 一键启动器 (双击运行)
REM ============================================================
echo.
echo ============================================================
echo   个人知识库 - 正在准备 ...
echo ============================================================

REM --- 检测服务是否已运行 ---
set "RUNNING=0"
for /f "tokens=5" %%p in ('netstat -ano -p tcp ^| findstr ":5000" ^| findstr "LISTENING"') do (
    set "RUNNING=1"
)

if "!RUNNING!"=="0" (
    echo [*] Flask 未运行，正在启动 ...
    call "%PROJ_DIR%start.bat" >nul 2>&1
    REM 等待最多 10 秒
    for /l %%i in (1,1,10) do (
        timeout /t 1 /nobreak >nul
        netstat -ano -p tcp | findstr ":5000" | findstr "LISTENING" >nul && goto :open
    )
    echo [X] 启动超时，请手动运行 start.bat 查看日志
    pause
    exit /b 1
) else (
    echo [OK] Flask 已在运行
)

:open
echo [*] 打开浏览器 ...
start "" http://127.0.0.1:5000/
echo [OK] 已打开 http://127.0.0.1:5000/
echo.
echo 提示: 服务在后台运行，关闭本窗口不影响。
echo       如需停止服务请双击 stop.bat
timeout /t 3 /nobreak >nul
exit /b 0
