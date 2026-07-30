#!/usr/bin/env python3
"""周报新闻抓取器（RSS + WebSearch JSON 导入双模式）

用法：
  1. RSS 抓取入库：    python3 news_fetcher.py
  2. 导入 WebSearch 结果：python3 news_fetcher.py --import results.json

RSS 模式：抓取国内外主流媒体 RSS，按版块分类，评分后入库
Import 模式：读取 JSON 文件（WebSearch 整理结果），入库

JSON 格式：
  [{"region":"domestic","section":"tech","title":"...","summary":"...","source":"...","url":"...","published_at":"2026-07-30T08:00:00"}]
"""
import os
import sys
import json
import time
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

# 跨平台 UTF-8
if sys.platform.startswith('win'):
    os.environ.setdefault('PYTHONUTF8', '1')
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# 添加项目目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import execute, query

# ============================================================
# RSS 源配置：(region, section) -> [feed_urls]
# ============================================================
RSS_SOURCES = {
    # 国内
    ('domestic', 'tech'): [
        'https://36kr.com/feed',
        'https://rsshub.app/ithome/rsshub',
    ],
    ('domestic', 'military'): [
        'https://rsshub.app/huanqiu/military',
    ],
    ('domestic', 'ai'): [
        'https://rsshub.app/jiqizhixin/news',
    ],
    ('domestic', 'economy'): [
        'https://rsshub.app/wallstreetcn/news',
        'https://rsshub.app/caixin/latest',
    ],
    # 国外
    ('international', 'tech'): [
        'https://www.theverge.com/rss/index.xml',
        'https://techcrunch.com/feed/',
    ],
    ('international', 'military'): [
        'https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml',
    ],
    ('international', 'ai'): [
        'https://venturebeat.com/category/ai/feed/',
    ],
    ('international', 'economy'): [
        'https://feeds.bloomberg.com/markets/news.rss',
        'https://www.reutersagency.com/feed/?best-topics=business-finance',
    ],
}

# ============================================================
# 关键词分类（用于 RSS 源未明确版块时的二次分类）
# ============================================================
SECTION_KEYWORDS = {
    'ai': ['AI', '人工智能', '大模型', 'GPT', 'LLM', '机器学习', '深度学习',
           'Claude', 'Gemini', 'OpenAI', 'Anthropic', '算力', '智能体', 'agent'],
    'military': ['军事', '导弹', '战机', '航母', '国防', '军演', '武器', '驻军',
                 'military', 'missile', 'defense', 'navy', 'air force', 'Pentagon'],
    'economy': ['经济', '金融', '股市', 'GDP', '通胀', '利率', '央行', '降息',
                'economy', 'market', 'stock', 'GDP', 'inflation', 'Fed', 'Treasury'],
    'tech': ['科技', '芯片', '半导体', '量子', '5G', '6G', '火箭', '卫星', '手机',
             'technology', 'chip', 'semiconductor', 'quantum', 'satellite', 'Apple',
             'Google', 'Microsoft', 'Meta', 'Tesla', 'SpaceX'],
}

# 重要性加分关键词
IMPORTANCE_KEYWORDS = [
    '重大', '突破', '首次', '最大', '宣布', '发射', '成功', '收购', '上市', '禁令',
    '危机', '制裁', '冲突', '协议', '签署', '爆雷', '崩盘', '历史',
    'breakthrough', 'first', 'largest', 'biggest', 'announce', 'launch', 'deal',
    'ban', 'crisis', 'sanction', 'historic', 'major',
]

# 来源权威度权重
SOURCE_WEIGHTS = {
    '36kr.com': 8, 'theverge.com': 8, 'techcrunch.com': 8,
    'reuters': 10, 'bloomberg': 10, 'caixin': 9, 'wallstreetcn': 8,
    'defensenews': 9, 'venturebeat': 7, 'jiqizhixin': 7,
    'ithome': 6, 'huanqiu': 7, 'sina': 5,
}


def get_week_of():
    """获取本周五日期（若今天是周五则用今天，否则取最近的已过周五）"""
    today = datetime.now().date()
    # weekday(): 周一=0, 周五=4
    days_since_friday = (today.weekday() - 4) % 7
    friday = today - timedelta(days=days_since_friday)
    return friday


def classify_section(title, default_section):
    """根据标题关键词二次分类版块"""
    for section, keywords in SECTION_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in title.lower():
                return section
    return default_section


def score_importance(title, source_url, summary=''):
    """重要性评分：来源权重 + 标题关键词 + 长度"""
    score = 0
    # 来源权重
    domain = urlparse(source_url).netloc.lower() if source_url else ''
    for src, w in SOURCE_WEIGHTS.items():
        if src in domain:
            score += w
            break
    else:
        score += 3  # 未知来源基础分
    # 重要性关键词
    title_lower = title.lower()
    for kw in IMPORTANCE_KEYWORDS:
        if kw.lower() in title_lower:
            score += 5
    # 标题长度（适中加分，过短或过长减分）
    tlen = len(title)
    if 15 <= tlen <= 60:
        score += 3
    elif tlen < 8:
        score -= 2
    # 摘要存在加分
    if summary and len(summary) > 20:
        score += 2
    return max(score, 1)


def fetch_rss_feed(url, timeout=15):
    """抓取单个 RSS 源，返回条目列表"""
    try:
        import feedparser
    except ImportError:
        os.system(f'{sys.executable} -m pip install feedparser --quiet')
        import feedparser

    try:
        feed = feedparser.parse(url, request_headers={
            'User-Agent': 'Mozilla/5.0 (compatible; PersonalKnowledgeBot/1.0)'
        })
        if feed.bozo and not feed.entries:
            return [], f'解析失败: {feed.bozo_exception}'
        return feed.entries, None
    except Exception as e:
        return [], str(e)


def parse_entry_date(entry):
    """解析 RSS 条目发布时间"""
    for field in ['published_parsed', 'updated_parsed']:
        if hasattr(entry, field) and getattr(entry, field):
            try:
                t = time.struct_time(getattr(entry, field))
                return datetime(*t[:6])
            except Exception:
                pass
    # 回退：从字符串解析
    for field in ['published', 'updated']:
        if hasattr(entry, field) and getattr(entry, field):
            try:
                return datetime.fromisoformat(
                    getattr(entry, field).replace('Z', '+00:00')[:19])
            except Exception:
                pass
    return datetime.now()


def insert_news(region, section, title, summary, source, url, published_at, importance):
    """插入新闻（去重）"""
    week_of = get_week_of()
    if published_at and isinstance(published_at, str):
        try:
            published_at = datetime.fromisoformat(published_at.replace('Z', '')[:19])
        except Exception:
            published_at = None
    try:
        execute(
            'INSERT IGNORE INTO weekly_reports '
            '(region, section, title, summary, source, url, published_at, week_of, importance) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (region, section, title[:500], summary or '', source or '',
             url or '', published_at, week_of, importance),
        )
        return True
    except Exception as e:
        print(f'  [!] 插入失败: {e}')
        return False


def fetch_all_rss():
    """抓取所有 RSS 源并入库"""
    total = 0
    errors = 0
    for (region, section), urls in RSS_SOURCES.items():
        region_name = '国内' if region == 'domestic' else '国外'
        section_name = {'tech': '科技', 'military': '军事', 'ai': 'AI', 'economy': '经济'}[section]
        print(f'\n[{region_name}-{section_name}] 抓取 {len(urls)} 个源...')
        for url in urls:
            entries, err = fetch_rss_feed(url)
            if err:
                print(f'  [X] {url}: {err}')
                errors += 1
                continue
            count = 0
            for entry in entries[:15]:  # 每源最多取 15 条
                title = getattr(entry, 'title', '').strip()
                if not title:
                    continue
                # 二次分类
                actual_section = classify_section(title, section)
                summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                # 清理 HTML 标签
                summary = re.sub(r'<[^>]+>', '', summary)[:300]
                link = getattr(entry, 'link', '')
                source = urlparse(link).netloc if link else urlparse(url).netloc
                pub_date = parse_entry_date(entry)
                importance = score_importance(title, link, summary)
                if insert_news(region, actual_section, title, summary,
                               source, link, pub_date, importance):
                    count += 1
            print(f'  [OK] {url}: 获取 {len(entries)} 条，入库 {count} 条')
            total += count
            time.sleep(0.5)  # 礼貌延迟
    return total, errors


def import_from_json(json_path):
    """从 JSON 文件导入 WebSearch 结果"""
    with open(json_path, 'r', encoding='utf-8') as f:
        items = json.load(f)
    count = 0
    for item in items:
        title = item.get('title', '').strip()
        if not title:
            continue
        importance = item.get('importance', score_importance(
            title, item.get('url', ''), item.get('summary', '')))
        # WebSearch 来源额外加分
        importance += 3
        if insert_news(
            item['region'], item['section'], title,
            item.get('summary', ''), item.get('source', 'WebSearch'),
            item.get('url', ''), item.get('published_at'),
            importance,
        ):
            count += 1
    return count


def main():
    print('=' * 60)
    print('  周报新闻抓取器')
    print(f'  本周周五: {get_week_of()}')
    print('=' * 60)

    if len(sys.argv) > 2 and sys.argv[1] == '--import':
        json_path = sys.argv[2]
        print(f'\n[导入模式] 读取 {json_path}')
        count = import_from_json(json_path)
        print(f'\n✅ 导入完成，共 {count} 条')
    else:
        print('\n[RSS 模式] 抓取所有源...')
        total, errors = fetch_all_rss()
        print(f'\n{"=" * 60}')
        print(f'  抓取完成：入库 {total} 条，源错误 {errors} 个')
        print(f'  访问 http://127.0.0.1:5000/weekly 查看周报')
        print(f'{"=" * 60}')

    # 统计本周数据
    week_of = get_week_of()
    stats = query(
        'SELECT region, section, COUNT(*) AS cnt '
        'FROM weekly_reports WHERE week_of = %s '
        'GROUP BY region, section ORDER BY region, section',
        (week_of,),
    )
    print(f'\n本周（{week_of}）数据统计：')
    for r in stats:
        rn = '国内' if r['region'] == 'domestic' else '国外'
        sn = {'tech': '科技', 'military': '军事', 'ai': 'AI', 'economy': '经济'}[r['section']]
        print(f'  {rn}-{sn}: {r["cnt"]} 条')


if __name__ == '__main__':
    main()
