@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 知识库本地部署同步工具

REM ============================================================
REM  知识库本地部署同步脚本
REM  作用：从远程服务下载最新源码包，覆盖本地 D:\知识库 并重启服务
REM
REM  使用方法：
REM    1. 用记事本打开本文件，修改下面 REM_SERVER 的地址
REM       为远程沙箱的实际访问地址（如 http://1.2.3.4:5000）
REM    2. 双击运行本脚本即可同步
REM
REM  注意：本脚本会覆盖本地源码文件（不影响数据库与日志）
REM ============================================================

REM ↓↓↓ 请修改为远程沙箱的实际地址 ↓↓↓
set "REM_SERVER=http://127.0.0.1:5000"
REM ↑↑↑ 请修改为远程沙箱的实际地址 ↑↑↑

REM 本地部署目录（默认 D:\知识库，可按需修改）
set "LOCAL_DIR=%~dp0"
set "LOCAL_DIR=%LOCAL_DIR:~0,-1%"

echo ============================================================
echo   知识库本地部署同步
echo   远程源:    %REM_SERVER%
echo   本地目录:  %LOCAL_DIR%
echo ============================================================
echo.

REM 1. 下载最新源码包
echo [1/4] 正在从 %REM_SERVER%/sync/pack 下载最新源码包...
set "ZIPFILE=%TEMP%\kb_sync.zip"
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%REM_SERVER%/sync/pack' -OutFile '%ZIPFILE%' -UseBasicParsing -TimeoutSec 30 } catch { Write-Host '下载失败:' $_.Exception.Message; exit 1 }"
if errorlevel 1 (
    echo [错误] 下载失败，请检查 REM_SERVER 地址是否正确，以及远程服务是否在运行。
    pause
    exit /b 1
)
if not exist "%ZIPFILE%" (
    echo [错误] 未下载到文件。
    pause
    exit /b 1
)
echo       下载完成。
echo.

REM 2. 停止本地服务（避免文件占用）
echo [2/4] 正在停止本地服务...
REM 优先用 stop.bat
if exist "%LOCAL_DIR%\stop.bat" (
    call "%LOCAL_DIR%\stop.bat" >nul 2>&1
) else (
    REM 兜底：按端口杀进程
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000.*LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
    )
)
timeout /t 2 /nobreak >nul
echo       已停止。
echo.

REM 3. 解压覆盖源码文件（排除运行时数据）
echo [3/4] 正在解压覆盖源码文件...
powershell -NoProfile -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; $zip = [System.IO.Compression.ZipFile]::OpenRead('%ZIPFILE%'); $entries = $zip.Entries; foreach ($e in $entries) { $dest = Join-Path '%LOCAL_DIR%' $e.FullName; $dir = Split-Path $dest -Parent; if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }; [System.IO.Compression.ZipFileExtensions]::ExtractToFile($e, $dest, $true) }; $zip.Dispose()"
if errorlevel 1 (
    echo [错误] 解压失败。
    del "%ZIPFILE%" >nul 2>&1
    pause
    exit /b 1
)
del "%ZIPFILE%" >nul 2>&1
echo       覆盖完成。
echo.

REM 4. 重启本地服务
echo [4/4] 正在重启本地服务...
if exist "%LOCAL_DIR%\start.bat" (
    start "" /D "%LOCAL_DIR%" "%LOCAL_DIR%\start.bat"
    echo       已通过 start.bat 启动。
) else (
    echo       未找到 start.bat，请手动启动 app.py。
)
echo.

echo ============================================================
echo   同步完成！
echo   请访问 http://127.0.0.1:5000 验证
echo ============================================================
pause
