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


# 建表 SQL（IF NOT EXISTS，幂等，可重复调用）
_INIT_SQL = """
-- 分类
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255) DEFAULT '',
    color VARCHAR(20) DEFAULT '#6366f1',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 笔记
CREATE TABLE IF NOT EXISTS notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content MEDIUMTEXT,
    category_id INT DEFAULT NULL,
    tags VARCHAR(255) DEFAULT '',
    is_pinned TINYINT(1) DEFAULT 0,
    views INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
    INDEX idx_category (category_id),
    INDEX idx_pinned (is_pinned),
    INDEX idx_title (title),
    INDEX idx_tags (tags)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 周报新闻
CREATE TABLE IF NOT EXISTS weekly_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    region ENUM('domestic', 'international') NOT NULL DEFAULT 'domestic',
    section ENUM('tech', 'military', 'ai', 'economy') NOT NULL DEFAULT 'tech',
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    source VARCHAR(128) DEFAULT '',
    url VARCHAR(1024) DEFAULT '',
    published_at DATETIME DEFAULT NULL,
    week_of DATE NOT NULL,
    importance INT DEFAULT 10,
    content MEDIUMTEXT,
    images TEXT,
    ai_summary MEDIUMTEXT,
    fetched_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_week_url (week_of, url(255)),
    INDEX idx_region_section (region, section),
    INDEX idx_week_of (week_of),
    INDEX idx_importance (importance),
    INDEX idx_published_at (published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

_INIT_SEED_SQL = [
    # 初始分类（仅当 categories 为空时插入）
    "INSERT INTO categories (name, description, color) "
    "SELECT * FROM (SELECT '学习笔记' AS n, '课程、书籍、技术学习记录' AS d, '#6366f1' AS c "
    "UNION SELECT '工作记录', '工作相关文档与总结', '#10b981' "
    "UNION SELECT '生活随笔', '日常生活感悟与记录', '#f59e0b' "
    "UNION SELECT '技术摘录', '技术文章收藏与摘录', '#ef4444' "
    "UNION SELECT '读书笔记', '书籍阅读笔记与心得', '#8b5cf6') AS seed "
    "WHERE (SELECT COUNT(*) FROM categories) = 0",
]


def _strip_sql_comments(sql):
    """移除 SQL 中的 -- 行注释，避免整段以注释开头时被整体跳过。"""
    import re
    return re.sub(r'--[^\n]*', '', sql)


def init_db():
    """初始化数据库：建表 + 写入种子数据（幂等，可重复执行）。

    用法：python -c "from db import init_db; init_db()"
    """
    created = 0
    with get_db() as conn:
        with conn.cursor() as cur:
            # 去注释后按分号拆分，逐条 CREATE TABLE 执行
            cleaned = _strip_sql_comments(_INIT_SQL).strip()
            for stmt in cleaned.split(';'):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
                    created += 1
            # 种子数据
            for stmt in _INIT_SEED_SQL:
                cur.execute(stmt)
    print(f'[init_db] 完成，已建/检查表 {created} 张，种子数据已写入（若为空库）。')
    return created
