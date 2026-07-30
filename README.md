# 个人知识库 · Windows 部署版

基于 Flask + MySQL 的个人知识库与笔记管理 Web 应用，已针对 Windows 系统做兼容性优化。

## 快速部署（3 步）

### 1. 拷贝到 D:\知识库

将本目录的所有文件拷贝到 `D:\知识库`，目录结构如下：

```
D:\知识库\
├── app.py              Flask 主应用
├── config.py           配置（数据库/端口，可改环境变量）
├── db.py               数据库连接
├── schema.sql          数据库表结构 + 示例数据
├── requirements.txt    Python 依赖
├── install.bat         一键安装（检查环境+装依赖+建库）
├── start.bat           启动服务（后台）
├── stop.bat            停止服务
├── launcher.bat        一键启动并打开浏览器（双击友好）
├── create-shortcut.bat 创建桌面快捷方式
├── static\             静态资源（CSS/JS/图标）
└── templates\          HTML 模板
```

### 2. 安装前置软件

| 软件 | 版本要求 | 下载地址 |
|------|---------|---------|
| **Python** | 3.8+（建议 3.10/3.11/3.12） | https://www.python.org/downloads/ |
| **MySQL** | 5.7+（建议 8.x） | https://dev.mysql.com/downloads/installer/ |

安装时务必：
- Python 勾选 **Add Python to PATH**
- MySQL 安装时记住 root 密码；安装完成后将 `MySQL Server X.x\bin` 加入系统 PATH

### 3. 双击 install.bat

脚本会自动完成：
1. 检查 Python / MySQL 是否可用
2. `pip install -r requirements.txt` 安装依赖
3. 创建数据库 `personal_db` 与用户 `pdbuser`（会提示输入 root 密码）
4. 导入 `schema.sql`（表结构 + 5 个分类 + 3 篇示例笔记）

> 若 mysql 不在 PATH，脚本会跳过自动建库，请手动执行：
> ```cmd
> mysql -u root -p < schema.sql
> ```
> 并提前创建用户：
> ```sql
> CREATE DATABASE personal_db CHARACTER SET utf8mb4;
> CREATE USER 'pdbuser'@'%' IDENTIFIED BY 'pdbpass123';
> ALTER USER 'pdbuser'@'%' IDENTIFIED WITH mysql_native_password BY 'pdbpass123';
> GRANT ALL PRIVILEGES ON personal_db.* TO 'pdbuser'@'%';
> FLUSH PRIVILEGES;
> ```

## 日常使用

| 操作 | 双击文件 |
|------|---------|
| 一键启动并打开网页 | `launcher.bat` |
| 仅启动后台服务 | `start.bat` |
| 停止服务 | `stop.bat` |
| 创建桌面快捷方式 | `create-shortcut.bat` |

启动后访问：**http://127.0.0.1:5000/**

## 配置修改

若数据库密码、端口等与默认不同，编辑 [config.py](config.py) 或设置环境变量：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `DB_HOST` | 127.0.0.1 | MySQL 主机 |
| `DB_PORT` | 3306 | MySQL 端口 |
| `DB_USER` | pdbuser | 数据库用户 |
| `DB_PASSWORD` | pdbpass123 | 数据库密码 |
| `DB_NAME` | personal_db | 数据库名 |
| `DB_AUTH_PLUGIN` | (空) | 认证插件，可选 `mysql_native_password` |
| `HOST` | 127.0.0.1 | Flask 监听地址 |
| `PORT` | 5000 | Flask 监听端口 |

## Windows 兼容性优化清单

- **数据库认证**：兼容 MySQL 8 `caching_sha2_password`（依赖 cryptography 包）
- **字符编码**：Python 强制 UTF-8 IO（`PYTHONUTF8=1`），bat 用 `chcp 65001`
- **中文路径**：`D:\知识库` 等中文路径完全支持，跨平台路径用 `os.path.join`
- **中文搜索**：基于 LIKE + 普通索引，兼容 MySQL 与 MariaDB，无需 ngram parser
- **时区**：连接建立后 `SET time_zone='+08:00'`，时间戳正确
- **生产 WSGI**：优先用 waitress（线程池），回退 Flask dev server，关闭 reloader
- **bat 脚本**：UTF-8 with BOM + CRLF 行尾，中文 echo 不乱码
- **进程管理**：用 `netstat+taskkill` 替代 Unix 的 `pkill`，PID 记录到 flask.pid
- **依赖完整**：bleach / Pygments / cryptography / waitress 全部列入 requirements.txt

## 故障排查

**Q: 启动报 `ModuleNotFoundError: No module named 'xxx'`**
A: 依赖未装全，重新运行 `install.bat` 或手动 `pip install -r requirements.txt`

**Q: 数据库连接失败 `Access denied` / `caching_sha2_password`**
A:
1. 确认用户密码正确
2. 运行 `pip install cryptography`
3. 或在 MySQL 里 `ALTER USER 'pdbuser'@'%' IDENTIFIED WITH mysql_native_password BY 'pdbpass123';`

**Q: 端口 5000 被占用**
A: 双击 `stop.bat` 停止旧进程；或编辑 [config.py](config.py) 改 `PORT=5001`

**Q: bat 中文显示乱码**
A: 确保 cmd 代码页为 UTF-8（脚本已自动 `chcp 65001`）；若仍乱码，用 PowerShell 运行 `.bat`

**Q: schema.sql 导入报语法错误**
A: 文件必须是 UTF-8 无 BOM。若被编辑器加了 BOM，用记事本另存为 UTF-8 即可

## 技术栈

- Python 3.8+ / Flask 3.1
- MySQL 5.7+ / PyMySQL
- waitress（生产 WSGI）
- Chart.js 4.4（数据可视化）
- bleach + markdown + Pygments（Markdown 渲染）
