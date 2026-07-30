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
REM  个人知识库 - 环境安装脚本 (Windows)
REM ============================================================
echo.
echo ============================================================
echo   个人知识库 - 环境安装
echo ============================================================
echo.

REM --- 1. 检查 Python ---
echo [1/4] 检查 Python ...
where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo [X] 未找到 python 或 py，请先安装 Python 3.8+ (勾选 Add to PATH)
        echo     下载: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set "PY=py -3"
) else (
    set "PY=python"
)
%PY% --version
echo.

REM --- 2. 检查 MySQL ---
echo [2/4] 检查 MySQL ...
where mysql >nul 2>&1
if errorlevel 1 (
    echo [!] 未在 PATH 找到 mysql 命令。
    echo     请确认已安装 MySQL 5.7+ (推荐 8.x)，并将其 bin 目录加入 PATH。
    echo     下载: https://dev.mysql.com/downloads/installer/
    echo     若已安装但未加入 PATH，可手动执行后续数据库初始化步骤。
    echo.
    set /p "MYSQL_OK=是否已手动准备好数据库 personal_db 与用户 pdbuser? (y/n): "
    if /i not "!MYSQL_OK!"=="y" (
        echo 请先完成数据库配置后再运行本脚本。
        pause
        exit /b 1
    )
) else (
    echo [OK] mysql 命令可用
)
echo.

REM --- 3. 安装 Python 依赖 ---
echo [3/4] 安装 Python 依赖 ...
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [X] 依赖安装失败，请检查网络或 pip 配置
    pause
    exit /b 1
)
echo [OK] 依赖安装完成
echo.

REM --- 4. 初始化数据库 ---
echo [4/4] 初始化数据库 ...
where mysql >nul 2>&1
if errorlevel 1 (
    echo [!] mysql 命令不可用，跳过自动建库。
    echo     请手动执行:
    echo       mysql -u root -p ^< schema.sql
    echo     并确保已创建数据库 personal_db 与用户 pdbuser/pdbpass123
) else (
    set /p "MYSQL_ROOT_PWD=请输入 MySQL root 密码 (回车跳过自动建库): "
    if "!MYSQL_ROOT_PWD!"=="" (
        echo [!] 未输入密码，跳过自动建库。请手动导入 schema.sql
    ) else (
        echo 正在创建数据库与用户 ...
        mysql -u root -p!MYSQL_ROOT_PWD! -e "CREATE DATABASE IF NOT EXISTS personal_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER IF NOT EXISTS 'pdbuser'@'%%' IDENTIFIED BY 'pdbpass123'; GRANT ALL PRIVILEGES ON personal_db.* TO 'pdbuser'@'%%'; ALTER USER 'pdbuser'@'%%' IDENTIFIED WITH mysql_native_password BY 'pdbpass123'; FLUSH PRIVILEGES;" 2>nul
        if errorlevel 1 (
            echo [X] 数据库创建失败，请检查密码或手动执行
        ) else (
            echo [OK] 数据库与用户已创建
            echo 正在导入表结构与示例数据 ...
            mysql --default-character-set=utf8mb4 -u pdbuser -ppdbpass123 personal_db < schema.sql
            if errorlevel 1 (
                echo [X] schema.sql 导入失败
            ) else (
                echo [OK] 表结构与示例数据导入完成
            )
        )
    )
)
echo.
echo ============================================================
echo   安装完成！
echo   双击 start.bat 启动服务，或双击 launcher.bat 一键启动并打开
echo ============================================================
echo.
pause
