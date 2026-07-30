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
REM  个人知识库 - 启动服务 (后台)
REM ============================================================
echo.
echo ============================================================
echo   个人知识库 - 启动服务
echo ============================================================

REM --- 选择 python 命令 ---
set "PY=python"
where python >nul 2>&1 || set "PY=py -3"

REM --- 检查是否已在运行 ---
if exist "%PID_FILE%" (
    set /p "OLD_PID="<"%PID_FILE%"
    tasklist /FI "PID eq !OLD_PID!" 2>nul | find "!OLD_PID!" >nul
    if not errorlevel 1 (
        echo [!] Flask 已在运行 (PID !OLD_PID!)
        echo     如需重启请先运行 stop.bat
        echo.
        start "" http://127.0.0.1:5000/
        exit /b 0
    ) else (
        echo [i] 清理失效的 PID 文件
        del "%PID_FILE%" >nul 2>&1
    )
)

REM --- 启动（后台 start /b，日志写入 flask.log）---
echo [*] 正在启动 Flask 服务 ...
start "PersonalKnowledgeBase" /b cmd /c "%PY% app.py > "%LOG_FILE%" 2>&1"

REM --- 等待并获取 PID ---
set "FOUND_PID="
for /l %%i in (1,1,15) do (
    timeout /t 1 /nobreak >nul
    for /f "tokens=5" %%p in ('netstat -ano -p tcp ^| findstr ":5000" ^| findstr "LISTENING"') do (
        set "FOUND_PID=%%p"
    )
    if defined FOUND_PID goto :gotpid
)
:gotpid
if defined FOUND_PID (
    echo !FOUND_PID!>"%PID_FILE%"
    echo [OK] Flask 已启动 (PID !FOUND_PID!)
    echo      日志: %LOG_FILE%
    echo      地址: http://127.0.0.1:5000/
    echo.
    echo 3 秒后自动打开浏览器 ...
    timeout /t 3 /nobreak >nul
    start "" http://127.0.0.1:5000/
) else (
    echo [X] 启动失败，请查看日志: %LOG_FILE%
    type "%LOG_FILE%"
)
echo.
pause
