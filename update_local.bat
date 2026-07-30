@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 知识库更新工具

REM ============================================================
REM  知识库本地更新脚本
REM  作用：从 GitHub 拉取最新代码，覆盖本地并重启服务
REM
REM  使用方法：双击运行即可
REM
REM  首次使用前：
REM    1. 确保已安装 Git（https://git-scm.com/download/win）
REM    2. 本目录需已是 git 仓库（若不是，脚本会自动 clone）
REM ============================================================

REM GitHub 仓库地址
set "REPO_URL=https://github.com/M-He072/-.git"

REM 本地部署目录（脚本所在目录）
set "LOCAL_DIR=%~dp0"
set "LOCAL_DIR=%LOCAL_DIR:~0,-1%"

echo ============================================================
echo   知识库更新
echo   仓库:    %REPO_URL%
echo   本地目录: %LOCAL_DIR%
echo ============================================================
echo.

REM 1. 检查 git 是否安装
echo [检查] Git 是否安装...
where git >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Git，请先安装：https://git-scm.com/download/win
    echo        安装时一路下一步即可，安装完成后重新运行本脚本。
    pause
    exit /b 1
)
echo       Git 已安装。
echo.

REM 2. 停止本地服务（避免文件占用）
echo [1/4] 正在停止本地服务...
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

REM 3. 拉取最新代码
echo [2/4] 正在从 GitHub 拉取最新代码...
cd /d "%LOCAL_DIR%"

REM 检查是否已是 git 仓库
if not exist "%LOCAL_DIR%\.git" (
    echo       本地非 git 仓库，正在初始化并拉取...
    git init >nul 2>&1
    git remote add origin "%REPO_URL%" >nul 2>&1
    git fetch origin main >nul 2>&1
    if errorlevel 1 (
        echo [错误] 拉取失败，请检查网络或仓库地址。
        echo        若为私有仓库，可能需要配置 Git 凭据。
        echo        参考: https://docs.github.com/zh/authentication
        pause
        exit /b 1
    )
    git checkout -t origin/main >nul 2>&1
    if errorlevel 1 (
        git reset --hard origin/main >nul 2>&1
    )
) else (
    echo       本地已是 git 仓库，正在拉取更新...
    git fetch origin main 2>&1 | findstr /v "^remote:"
    if errorlevel 1 (
        echo [错误] 拉取失败，请检查网络。
        pause
        exit /b 1
    )
    REM 强制用远程覆盖本地修改（保留 .gitignore 排除的本地数据）
    git reset --hard origin/main >nul 2>&1
)
echo       代码已更新到最新版本。
echo.

REM 4. 检查依赖是否有变化（可选）
echo [3/4] 检查依赖...
where python >nul 2>&1
if errorlevel 1 (
    echo       未检测到 python，跳过依赖检查。
) else (
    echo       依赖如有新增，请手动执行: pip install -r requirements.txt
)
echo.

REM 5. 重启本地服务
echo [4/4] 正在重启本地服务...
if exist "%LOCAL_DIR%\start.bat" (
    start "" /D "%LOCAL_DIR%" "%LOCAL_DIR%\start.bat"
    echo       已通过 start.bat 启动。
) else (
    echo       未找到 start.bat，请手动启动 app.py。
)
echo.

echo ============================================================
echo   更新完成！
echo   请访问 http://127.0.0.1:5000 验证
echo.
echo   提示: 若有新依赖，运行 pip install -r requirements.txt
echo ============================================================
pause
