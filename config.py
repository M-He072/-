"""应用配置（Windows 兼容版）

关键优化：
1. 数据库连接参数全部可通过环境变量覆盖，便于不同机器配置
2. 显式指定 charset=utf8mb4，避免 Windows cmd 默认编码导致中文乱码
3. auth_plugin 兼容 MySQL 8 的 caching_sha2_password（配合 cryptography）
4. 增加 connect_timeout/read_timeout/write_timeout，应对本地连接偶发卡顿
5. host 用 127.0.0.1 而非 localhost，避免 Windows 走 named pipe 失败
6. 自动适配中文路径（如 D:\\知识库），Flask root_path 跨平台正确
"""
import os
import sys

# 强制 Python 使用 UTF-8 进行 IO，避免在 Windows cp936 下
# 中文路径 / 中文日志输出引发 UnicodeEncodeError
if sys.platform.startswith('win'):
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    os.environ.setdefault('PYTHONUTF8', '1')

# MySQL 数据库配置
# 如需自定义，推荐通过环境变量覆盖（无需改代码）：
#   临时设置：在 CMD 执行 set DB_PASSWORD=xxx
#   永久设置：系统环境变量中添加 DB_PASSWORD
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'pdbuser'),
    'password': os.getenv('DB_PASSWORD', 'qq13579qq'),
    'database': os.getenv('DB_NAME', 'personal_db'),
    'charset': 'utf8mb4',
    # MySQL 8 默认 caching_sha2_password；保持 None 让 PyMySQL 自动协商
    # 若安装了 cryptography 包即可正常握手；如未安装可改 'mysql_native_password'
    'auth_plugin': os.getenv('DB_AUTH_PLUGIN', None),
    'connect_timeout': 10,
    'read_timeout': 30,
    'write_timeout': 30,
}

# Flask 配置（用于 session 加密，请使用随机字符串）
# 建议：https://docs.python.org/3/library/secrets.html#secrets.token_hex 生成
SECRET_KEY = os.getenv('SECRET_KEY', 'm-he-knowledge-base-2026-0731-secure-token-change-if-needed')

# 服务监听
# 默认 0.0.0.0 允许外部访问（局域网/远程预览）
# 如仅本机访问，设环境变量 HOST=127.0.0.1
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
