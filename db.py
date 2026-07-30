"""数据库连接管理（Windows 兼容版）

优化点：
1. 从 DB_CONFIG 读取所有连接参数（含 auth_plugin、超时）
2. auth_plugin 为 None 时自动剔除该 key，避免 PyMySQL 报未知参数
3. 连接建立后执行 SET time_zone='+08:00'，确保 Windows 系统时区
   与 MySQL 会话时区一致，CURRENT_TIMESTAMP 写入时间正确
"""
import pymysql
from contextlib import contextmanager
from config import DB_CONFIG


def _build_kwargs():
    """构造 pymysql.connect 参数，剔除 None 值"""
    kw = dict(DB_CONFIG)
    if kw.get('auth_plugin') is None:
        kw.pop('auth_plugin', None)
    return kw


def get_connection():
    """获取数据库连接"""
    conn = pymysql.connect(
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        **_build_kwargs(),
    )
    # 统一会话时区为东八区，避免 Windows 系统时区差异
    with conn.cursor() as cur:
        cur.execute("SET time_zone='+08:00'")
    return conn


@contextmanager
def get_db():
    """数据库连接上下文管理器，自动提交/回滚与关闭"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query(sql, args=(), one=False):
    """执行查询并返回结果"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            result = cur.fetchall()
    return result[0] if one and result else result


def execute(sql, args=()):
    """执行写操作，返回受影响行数与 lastrowid"""
    with get_db() as conn:
        with conn.cursor() as cur:
            affected = cur.execute(sql, args)
            last_id = cur.lastrowid
    return affected, last_id
