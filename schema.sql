-- 个人知识库数据库结构（Windows 兼容版）
-- 数据库: personal_db
-- 字符集: utf8mb4 (支持完整中文与 emoji)
-- 导入时务必: mysql --default-character-set=utf8mb4 -u root -p < schema.sql
-- 本文件必须保存为 UTF-8 无 BOM（带 BOM 会导致 MySQL 语法错误）

CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255) DEFAULT '',
    color VARCHAR(20) DEFAULT '#6366f1',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
    -- 普通索引加速 LIKE 搜索（app.py 搜索基于 LIKE，兼容 MySQL/MariaDB）
    INDEX idx_title (title),
    INDEX idx_tags (tags)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 初始分类数据
INSERT INTO categories (name, description, color) VALUES
('学习笔记', '课程、书籍、技术学习记录', '#6366f1'),
('工作记录', '工作相关文档与总结', '#10b981'),
('生活随笔', '日常生活感悟与记录', '#f59e0b'),
('技术摘录', '技术文章收藏与摘录', '#ef4444'),
('读书笔记', '书籍阅读笔记与心得', '#8b5cf6');

-- 示例笔记（可选，便于首次体验）
INSERT INTO notes (title, content, category_id, tags, is_pinned) VALUES
('Flask 快速入门', '# Flask 快速入门\n\nFlask 是一个轻量级的 Python Web 框架。\n\n## 核心概念\n\n- **路由**：通过 `@app.route` 装饰器定义 URL\n- **视图函数**：处理请求并返回响应\n- **模板**：使用 Jinja2 渲染 HTML\n\n## 示例代码\n\n```python\nfrom flask import Flask\napp = Flask(__name__)\n\n@app.route("/")\ndef hello():\n    return "Hello, World!"\n```\n\n> Flask 适合中小型项目和快速原型开发。', 1, 'Python,Flask,Web', 1),
('MySQL 索引优化笔记', '# MySQL 索引优化\n\n合理使用索引能大幅提升查询性能。\n\n## 索引类型\n\n| 类型 | 说明 |\n|------|------|\n| 主键 | 唯一标识，自动创建 |\n| 唯一 | 确保列值唯一 |\n| 全文 | 用于文本搜索 |\n| 普通 | 加速查询 |\n\n## 优化建议\n\n1. 在 `WHERE`、`JOIN`、`ORDER BY` 涉及的列上建索引\n2. 避免在索引列上使用函数\n3. 使用 `EXPLAIN` 分析查询计划', 5, 'MySQL,数据库,优化', 0),
('本周工作总结', '## 本周完成事项\n\n- 完成知识库应用的需求评审\n- 搭建开发环境\n- 编写数据库设计文档\n\n## 下周计划\n\n- 实现核心功能模块\n- 编写单元测试\n- 准备联调', 2, '工作,周报', 0);

-- ============================================================
-- 周报新闻表
-- ============================================================
CREATE TABLE IF NOT EXISTS weekly_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    -- 国内/国外
    region ENUM('domestic', 'international') NOT NULL DEFAULT 'domestic',
    -- 版块: tech/military/ai/economy
    section ENUM('tech', 'military', 'ai', 'economy') NOT NULL DEFAULT 'tech',
    -- 新闻标题
    title VARCHAR(500) NOT NULL,
    -- 摘要（抓自 RSS/WebSearch）
    summary TEXT,
    -- 来源站点标识（如 36kr.com）
    source VARCHAR(128) DEFAULT '',
    -- 原文链接
    url VARCHAR(1024) DEFAULT '',
    -- 发布时间
    published_at DATETIME DEFAULT NULL,
    -- 所属周（每周五基准，DATE 类型，格式 YYYY-MM-DD）
    week_of DATE NOT NULL,
    -- 重要性评分（越大越靠前，0-100）
    importance INT DEFAULT 10,
    -- 抓取的正文（纯文本/Markdown）
    content MEDIUMTEXT,
    -- 关联图片（JSON 数组，[{src, alt, caption}...]）
    images TEXT,
    -- AI 总结分析（Markdown）
    ai_summary MEDIUMTEXT,
    -- 原文抓取完成时间（NULL=未抓取，详情页加载时后台异步补抓）
    fetched_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 去重：同周同 URL 只保留一条
    UNIQUE KEY uk_week_url (week_of, url(255)),
    INDEX idx_region_section (region, section),
    INDEX idx_week_of (week_of),
    INDEX idx_importance (importance),
    INDEX idx_published_at (published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
