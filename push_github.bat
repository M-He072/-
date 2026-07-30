@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 知识库 - 推送到 GitHub

REM ============================================================
REM  知识库一键推送脚本
REM  作用：将本地代码变更提交并推送到 GitHub 仓库
REM
REM  使用方法：
REM    1. 双击运行 = 自动提交所有变更并推送（提交信息含时间戳）
REM    2. 命令行带参数 = 自定义提交信息
REM       例: push_github.bat "新增周报完整性检查功能"
REM
REM  首次使用前：
REM    1. 确保已安装 Git（https://git-scm.com/download/win）
REM    2. 确保已配置 GitHub 凭据（Git Credential Manager 会自动缓存）
REM       若推送时提示认证失败，请使用 Personal Access Token (PAT) 登录
REM       PAT 申请: https://github.com/settings/tokens
REM ============================================================

REM GitHub 仓库地址
set "REPO_URL=https://github.com/M-He072/-.git"

REM 本地部署目录（脚本所在目录）
set "LOCAL_DIR=%~dp0"
set "LOCAL_DIR=%LOCAL_DIR:~0,-1%"

REM 提交信息：优先使用命令行参数，否则用默认时间戳信息
if "%~1"=="" (
    for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value 2^>nul ^| find "="') do set "DT=%%a"
    if defined DT (
        set "TS=!DT:~0,4!-!DT:~4,2!-!DT:~6,2! !DT:~8,2!:!DT:~10,2!:!DT:~12,2!"
    ) else (
        set "TS=%date% %time%"
    )
    set "COMMIT_MSG=自动更新: !TS!"
) else (
    set "COMMIT_MSG=%~1"
)

echo ============================================================
echo   知识库 - 推送到 GitHub
echo   仓库:    %REPO_URL%
echo   本地目录: %LOCAL_DIR%
echo   提交信息: !COMMIT_MSG!
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

cd /d "%LOCAL_DIR%"

REM 2. 检查是否为 git 仓库，不是则初始化
if not exist "%LOCAL_DIR%\.git" (
    echo [初始化] 本地非 git 仓库，正在初始化...
    git init >nul 2>&1
    git remote add origin "%REPO_URL%" >nul 2>&1
    if errorlevel 1 (
        echo [错误] 初始化失败，请检查目录权限。
        pause
        exit /b 1
    )
    git branch -M main >nul 2>&1
    echo       已初始化并关联远程仓库。
    echo.
)

REM 3. 检查是否有变更
echo [1/4] 检查文件变更...
git add -A >nul 2>&1
git diff --cached --quiet >nul 2>&1
if not errorlevel 1 (
    echo       没有需要提交的变更（工作区已是最新）。
    echo       提示: .gitignore 排除的文件（数据库、缓存图片等）不会被提交。
    echo.
    echo ============================================================
    echo   无变更，跳过推送。
    echo ============================================================
    timeout /t 3 >nul
    exit /b 0
)

REM 显示变更概要
echo       检测到以下变更:
git diff --cached --stat
echo.

REM 4. 提交
echo [2/4] 正在提交变更...
git commit -m "!COMMIT_MSG!" >nul 2>&1
if errorlevel 1 (
    echo [错误] 提交失败。可能原因：
    echo        - 未配置 git 用户信息（执行下方命令修复）：
    echo          git config --global user.name "你的名字"
    echo          git config --global user.email "你的邮箱"
    pause
    exit /b 1
)
echo       提交成功。
echo.

REM 5. 推送
echo [3/4] 正在推送到 GitHub...
git pull --rebase origin main >nul 2>&1
git push -u origin main
if errorlevel 1 (
    echo.
    echo [错误] 推送失败。常见原因：
    echo        1. 认证失败：GitHub 已不支持密码认证，需使用 Personal Access Token (PAT)
    echo           申请地址: https://github.com/settings/tokens
    echo           生成后在弹出的凭据框输入用户名和 PAT 即可（Git Credential Manager 会缓存）
    echo        2. 网络问题：请检查网络连接或代理设置
    echo        3. 仓库未初始化：首次推送需确保远程 main 分支已存在
    echo.
    echo        若要手动配置凭据，可执行：
    echo          git remote set-url origin https://M-He072:你的PAT@github.com/M-He072/-.git
    pause
    exit /b 1
)
echo       推送成功！
echo.

REM 6. 重启本地服务（让更新立即生效）
echo [4/4] 正在重启本地服务...
if exist "%LOCAL_DIR%\stop.bat" (
    call "%LOCAL_DIR%\stop.bat" >nul 2>&1
    timeout /t 2 /nobreak >nul
)
if exist "%LOCAL_DIR%\start.bat" (
    start "" /D "%LOCAL_DIR%" "%LOCAL_DIR%\start.bat"
    echo       已重启服务。
) else (
    echo       未找到 start.bat，请手动重启。
)

echo.
echo ============================================================
echo   推送完成！
echo   仓库地址: https://github.com/M-He072/-
echo   本地服务: http://127.0.0.1:5000
echo ============================================================
echo.
echo   说明: 数据库文件、缓存图片、日志等（见 .gitignore）不会上传，
echo        仅同步源代码与配置，保护你的数据隐私。
pause
