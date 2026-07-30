#!/usr/bin/env python3
"""新闻原文抓取与 AI 分析生成器

功能：
  1. 用 trafilatura 抓取新闻正文与图片
  2. 用 TextRank 算法抽取关键句生成结构化摘要
  3. 输出 Markdown 格式的「AI 总结与分析」

用法：
  python3 news_analyzer.py <news_id>      # 分析单条并入库
  python3 news_analyzer.py --all          # 批量分析未抓取的新闻
"""
import os
import sys
import json
import re
import time
from datetime import datetime
from collections import Counter

if sys.platform.startswith('win'):
    os.environ.setdefault('PYTHONUTF8', '1')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import execute, query

# 中文停用词
STOP_WORDS = set("""
的 了 和 是 在 与 或 也 这 那 以及 对于 关于 通过 随着 由于 因为 所以 但是 然而 虽然 则 即 并 等 中 上 下 内 外 把 被 让 使 向 到 从 给 对 为 以 按 据 经 据
将 应 该 需要 可能 可以 能够 已经 正在 进行 截至 目前 本次 此次 近日 近期 日前 近日 据悉表示 称 强调 指出 认为 提出 要求 表示 透露 介绍 据了解 显示
一个 一种 一些 一项 不仅 而且 不仅 而且 除了 此外 同时 另外 其中 其他 其它 上述 下列 本 次 其 此 该 该款 此款 这款
据 报道 报道称 消息称 媒体 报道 报纸 记者 编辑 责任编辑 来源 图片 图 资料 视觉中国 新华社
""".split())

# 句子分隔符
SENTENCE_SPLIT = re.compile(r'[。！？!?\.\n]+')

# 重要性关键词（用于背景分析判断）
ANALYSIS_KEYWORDS = {
    '突破': '技术突破', '首次': '首次实现', '最大': '规模之最', '领先': '行业领先',
    '量产': '产业化进展', '商用': '商业化落地', '投资': '资本动向', '融资': '资本动向',
    '合作': '战略合作', '发布': '产品发布', '收购': '并购重组', '上市': '资本市场',
    '制裁': '国际博弈', '冲突': '地缘风险', '军演': '军事动态', '导弹': '军事动态',
    '降息': '货币政策', '加息': '货币政策', 'GDP': '宏观经济', '通胀': '宏观经济',
}


def fetch_article(url, timeout=20):
    """抓取新闻正文与图片"""
    if not url:
        return None, []
    try:
        import trafilatura
        from trafilatura.spider import focused_crawler
        from trafilatura.utils import detect_encoding
        import urllib.request

        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; PersonalKnowledgeBot/1.0; +https://127.0.0.1)'
        })
        html = urllib.request.urlopen(req, timeout=timeout).read()
        # 提取正文
        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
            url=url,
        )
        # 提取图片（基于已去广告的 HTML，确保广告图也不进入候选）
        html_clean = strip_ad_html(html)
        images = extract_images(html_clean, url)
        # 正文广告清洗
        content = clean_ad_content(content or '')
        return content, images
    except Exception as e:
        print(f'  [!] 抓取失败 {url}: {e}')
        return None, []


# ============================================================
# 正文与 HTML 广告清洗
# ============================================================
# 广告/推广段落特征（整段命中即删除）
AD_PARAGRAPH_MARKERS = [
    # 推广/导流
    '扫码下载', '扫码关注', '扫码加群', '长按识别', '二维码', '关注公众号',
    '点击下载', '点击购买', '点击查看', '立即购买', '立即下载', '立即注册',
    '免费领取', '免费试用', '限时抢购', '加入购物车', '下单立减',
    '专属推广', '推广链接', '赞助内容', '广告推广', '软文推广',
    # 推荐阅读类（站点内嵌的相关推荐）
    '推荐阅读', '相关阅读', '延伸阅读', '热门推荐', '猜你喜欢', '你可能感兴趣',
    '相关文章', '热点推荐', '小编推荐', '为您推荐',
    # 版权/免责声明尾部
    '免责声明', '风险提示', '本文仅供参考', '投资有风险',
    '转载请注明', '版权声明', '如有侵权请联系',
    # 下载/订阅引导
    '下载APP', '下载客户端', '订阅本', '关注我们', '扫码进群',
    # 广告位标识
    'AD', 'ADVERTISEMENT', 'Sponsored', '赞助商',
]

# 广告/无关链接域名（出现在正文 <a> 中即移除该链接）
AD_LINK_DOMAINS = [
    'taobao.com', 'tmall.com', 'jd.com', 'pinduoduo.com', 'amazon.com/dp/',
    'doubleclick.net', 'googlesyndication', 'googleadservices',
    'affiliate', 'click trackers', 'redir', 'track.php',
]

# 广告/无关 HTML 块的 CSS class / id 特征
AD_BLOCK_SELECTORS = [
    # class/id 关键词
    'ad-', 'ads-', 'advert', 'banner', 'sponsor', 'promotion', 'promo-',
    'recommend', 'related', 'hot-read', 'tuijian', 'tuiguang',
    'sidebar', 'widget-ad', 'pop-up', 'popup', 'modal-ad',
    'qr-code', 'qrcode', 'download-bar', 'follow-us', 'subscribe-box',
    'copyright', 'disclaimer', 'statement',
]


def strip_ad_html(html):
    """清洗原始 HTML 中的广告/推广/推荐模块。

    在提取图片前调用，确保广告图、二维码、推广banner不进入候选。
    返回清洗后的 HTML（bytes/str 与输入一致）。
    """
    if not html:
        return html
    try:
        from bs4 import BeautifulSoup, Comment
        is_bytes = isinstance(html, bytes)
        text = html.decode('utf-8', errors='ignore') if is_bytes else html
        soup = BeautifulSoup(text, 'html.parser')

        # 1. 删除 HTML 注释（常藏广告追踪）
        for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
            c.extract()

        # 2. 删除广告相关标签：iframe/script/noscript/ins（Google AdSense 容器）
        for tag in soup.find_all(['iframe', 'script', 'noscript', 'ins', 'embed']):
            tag.decompose()

        # 3. 按 class/id 删除广告/推荐块
        # 先收集命中标签，避免边遍历边 decompose 导致属性失效
        to_remove_by_selector = []
        for tag in soup.find_all(True):
            attrs = tag.attrs or {}
            cls = ' '.join(attrs.get('class') or []).lower()
            tid = (attrs.get('id') or '').lower()
            ident = cls + ' ' + tid
            if any(sel in ident for sel in AD_BLOCK_SELECTORS):
                to_remove_by_selector.append(tag)
        for tag in to_remove_by_selector:
            tag.decompose()

        # 4. 删除广告网络容器（data-* 属性特征）
        for tag in soup.find_all(attrs={'data-ad': True}):
            tag.decompose()
        for tag in soup.find_all(attrs={'data-ad-slot': True}):
            tag.decompose()

        # 5. 删除明显的广告/推广 <a> 链接（按域名）
        for a in soup.find_all('a', href=True):
            href = (a.get('href') or '').lower()
            if any(d in href for d in AD_LINK_DOMAINS):
                a.decompose()

        # 6. 删除含广告标记文本的 <div>/<section>/<aside>/<p>/<figure>
        # 同样先收集再删除，避免遍历中属性失效
        to_remove_by_text = []
        for tag in soup.find_all(['div', 'section', 'aside', 'p', 'figure']):
            try:
                txt = tag.get_text(' ', strip=True)
            except Exception:
                continue
            if not txt:
                continue
            # 命中广告标记且文本较短（避免误删含"广告"二字的长正文）
            if len(txt) < 120 and any(m.lower() in txt.lower() for m in AD_PARAGRAPH_MARKERS):
                to_remove_by_text.append(tag)
        for tag in to_remove_by_text:
            tag.decompose()

        out = str(soup)
        return out.encode('utf-8') if is_bytes else out
    except ImportError:
        # 无 bs4：用正则兜底，删除广告相关标签块
        text = html.decode('utf-8', errors='ignore') if isinstance(html, bytes) else html
        # 删除 iframe/script/ins
        text = re.sub(r'<(iframe|script|noscript|ins|embed)[^>]*>.*?</\1>', '', text, flags=re.S | re.I)
        # 删除 class/id 含广告特征的 div/section
        for sel in ['ad-', 'advert', 'banner', 'sponsor', 'promo', 'recommend', 'related', 'qrcode']:
            text = re.sub(rf'<(div|section|aside|figure)[^>]*(class|id)="[^"]*{sel}[^"]*"[^>]*>.*?</\1>',
                          '', text, flags=re.S | re.I)
        return text.encode('utf-8') if isinstance(html, bytes) else text
    except Exception:
        return html


def clean_ad_content(content):
    """清洗 trafilatura 提取后的纯文本正文，移除广告/推广/推荐段落。

    处理步骤：
      1. 按行/段落分割
      2. 删除命中广告标记的短段落
      3. 删除"推荐阅读"区块（通常连续多行短链接标题）
      4. 删除尾部版权/免责声明
      5. 删除超短无意义行
    """
    if not content:
        return content
    try:
        # 统一换行
        text = content.replace('\r\n', '\n').replace('\r', '\n')
        lines = text.split('\n')

        cleaned = []
        in_recommend_block = False  # 是否处于"推荐阅读"区块

        for line in lines:
            stripped = line.strip()
            if not stripped:
                # 空行：结束推荐阅读区块，但保留段落分隔
                in_recommend_block = False
                cleaned.append('')
                continue

            lower = stripped.lower()

            # 进入推荐阅读区块：遇到标记即开始跳过，直到下一个空行
            if not in_recommend_block and any(m.lower() in lower for m in
                                              ['推荐阅读', '相关阅读', '延伸阅读', '热门推荐',
                                               '猜你喜欢', '相关文章', '热点推荐', '为您推荐']):
                in_recommend_block = True
                continue

            # 推荐阅读区块内的行（标题列表）跳过
            if in_recommend_block:
                continue

            # 命中广告标记的行（短行直接删，长行保留避免误删正文）
            if _is_ad_line(stripped):
                continue

            # 删除纯 URL 行（导流链接）
            if re.match(r'^https?://\S+$', stripped):
                continue

            # 删除超短无意义行（<4字 且非标点）
            if len(stripped) < 4 and not re.search(r'[。！？!?]', stripped):
                continue

            cleaned.append(line)

        result = '\n'.join(cleaned).strip()
        # 合并多余空行
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result
    except Exception:
        return content


def _is_ad_line(text):
    """判断单行文本是否为广告/推广/版权声明"""
    if not text:
        return False
    lower = text.lower()
    # 短行（<120字）命中广告标记 → 删除
    if len(text) < 120:
        return any(m.lower() in lower for m in AD_PARAGRAPH_MARKERS)
    # 长行不轻易判定为广告，避免误删正文
    # 例外：明确版权声明行
    if any(m in text for m in ['免责声明', '版权声明', '转载请注明', '本文仅供参考']):
        return True
    return False


def extract_images(html, base_url):
    """从 HTML 提取候选图片（含 alt 和外层段落上下文，供后续相关性审核）"""
    if not html:
        return []
    try:
        from bs4 import BeautifulSoup
        if isinstance(html, bytes):
            html = html.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html, 'html.parser')
        imgs = []
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or ''
            if not src or src.startswith('data:'):
                continue
            # 过滤图标/Logo/广告
            alt = (img.get('alt') or '').lower()
            cls = ' '.join(img.get('class') or []).lower()
            src_lower = src.lower()
            if any(x in src_lower + alt + cls for x in
                   ['logo', 'icon', 'avatar', 'ad-', 'banner', 'pixel', 'tracking',
                    'loading', 'placeholder', 'sprite', 'blank.gif', 'spacer']):
                continue
            # 广告域名/路径过滤
            if any(p in src_lower for p in AD_IMAGE_SRC_PATTERNS):
                continue
            # SVG 矢量图通常是装饰
            if src.lower().endswith('.svg'):
                continue
            # 相对路径转绝对
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                from urllib.parse import urlparse
                p = urlparse(base_url)
                src = f'{p.scheme}://{p.netloc}{src}'
            elif not src.startswith('http'):
                continue
            # 过滤过小图片
            w = img.get('width', '')
            if w and w.isdigit() and int(w) < 120:
                continue
            h = img.get('height', '')
            if h and h.isdigit() and int(h) < 80:
                continue
            # 提取图片所在段落的文本作为上下文（用于相关性判断）
            context = ''
            parent = img.parent
            while parent and parent.name not in ('p', 'div', 'figure', 'article', 'section', 'li'):
                parent = parent.parent
            if parent:
                context = parent.get_text(' ', strip=True)[:200]
            imgs.append({
                'src': src,
                'alt': img.get('alt', ''),
                'context': context,
            })
        # 去重
        seen = set()
        result = []
        for im in imgs:
            if im['src'] not in seen:
                seen.add(im['src'])
                result.append(im)
        return result
    except ImportError:
        # 无 bs4 时用正则兜底
        pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*(?:alt=["\']([^"\']*)["\'])?', re.I)
        imgs = []
        for m in pattern.finditer(html.decode('utf-8', errors='ignore') if isinstance(html, bytes) else html):
            src = m.group(1)
            if src.startswith('//'):
                src = 'https:' + src
            elif not src.startswith('http'):
                continue
            imgs.append({'src': src, 'alt': m.group(2) or '', 'context': ''})
        return imgs
    except Exception:
        return []


# ---------- 图片相关性审核 ----------
# 无关图片常见特征（alt/文件名/上下文命中即视为无关）
IRRELEVANT_PATTERNS = [
    '二维码', 'qrcode', 'qr-code', '公众号', '关注', 'subscribe', 'weixin', 'wechat',
    '赞赏', 'reward', '打赏', 'donate', '点赞', 'like', '分享', 'share',
    'copyright', 'watermark', '水印', '版权',
    'avatar', '头像', 'profile', '作者',
    'loading', 'lazy', 'placeholder', 'default',
    'comment', '评论', '留言',
    'footer', 'header', 'sidebar', 'navigation', 'menu',
    'advertisement', '广告', '推广', '赞助', 'sponsor', 'promoted',
    'emoji', 'icon', 'logo',
    # 广告网络/追踪图片
    'doubleclick', 'googlesyndication', 'googleadservices', 'adnxs', 'adservice',
    'tracking', 'beacon', 'pixel', 'b.gif', 'blank.gif', 'spacer.gif',
    # 电商导流图
    'taobao', 'tmall', 'jd.com', 'pinduoduo', 'amazon.com/dp',
    # 下载/订阅引导图
    'download-app', 'download-bar', 'follow-us', 'subscribe-box', 'open-in-app',
    # 悬浮/弹窗类
    'popup', 'float', 'modal', 'back-to-top',
]

# 广告图片常见 src 域名/路径特征
AD_IMAGE_SRC_PATTERNS = [
    'doubleclick.net', 'googlesyndication.com', 'googleadservices.com',
    'adnxs.com', 'adsystem.com', 'adservice', '/ads/', '/adserver/',
    '/banner/', '/sponsor/', 'affiliate', 'track.gif', 'pixel.gif',
    'gravatar.com',  # 头像服务
]

# 与内容强相关的图片信号（命中则加分，即使 alt 为空也倾向保留）
RELEVANT_SIGNALS = [
    '图', '图示', '示意图', '架构', '流程', 'chart', '图表', '数据', '趋势',
    'photo', '照片', '截图', 'screenshot', '封面', 'cover', '配图',
    '卫星', '导弹', '战机', '航母', '火箭', '芯片', '实验室', '发布会',
]


def is_image_relevant(img, title, content_keywords):
    """审核图片是否与新闻内容相关。

    判断依据（任一命中即相关；命中无关模式则排除）：
      1. alt / context 命中 RELEVANT_SIGNALS
      2. alt / context 命中内容关键词（中文双字/英文词）
      3. 图片所在段落 context 与标题有重合词
    先排除命中 IRRELEVANT_PATTERNS 的图。
    """
    alt = (img.get('alt') or '').lower()
    context = (img.get('context') or '').lower()
    src = img.get('src', '').lower()
    text = alt + ' ' + context + ' ' + src

    # 0. 先排除广告域名/路径（src 级硬过滤）
    for pat in AD_IMAGE_SRC_PATTERNS:
        if pat in src:
            return False, f'广告图片域名: {pat}'

    # 1. 先排除明显无关
    for pat in IRRELEVANT_PATTERNS:
        if pat in text:
            return False, f'命中无关模式: {pat}'

    # 2. 强相关信号加分
    for sig in RELEVANT_SIGNALS:
        if sig in text:
            return True, f'强相关信号: {sig}'

    # 3. 与内容关键词重合
    for kw in content_keywords:
        if len(kw) >= 2 and kw.lower() in text:
            return True, f'匹配关键词: {kw}'

    # 4. 与标题重合（取标题中>=2字的片段）
    title_lower = (title or '').lower()
    # 取标题中的中文双字
    cn_chars = re.findall(r'[\u4e00-\u9fa5]', title or '')
    title_bigrams = set()
    for i in range(len(cn_chars) - 1):
        title_bigrams.add(cn_chars[i] + cn_chars[i + 1])
    for bg in title_bigrams:
        if bg in text:
            return True, f'匹配标题片段: {bg}'

    # 5. 无 alt 且无 context 信息：保守保留（可能是正文配图）
    if not alt and not context:
        return True, '无元信息，保守保留'

    # 6. 有 alt/context 但都无重合：视为无关
    return False, '与标题/内容无重合'


def fetch_image_bytes(url, timeout=15):
    """下载图片字节，返回 bytes 或 None"""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; PersonalKnowledgeBot/1.0; +https://127.0.0.1)',
            'Referer': url,
        })
        return urllib.request.urlopen(req, timeout=timeout).read()
    except Exception:
        return None


def enhance_image_clarity(image_bytes):
    """对图片进行清晰度优化：锐化 + 轻微对比度提升，返回优化后的 bytes。

    使用 PIL；失败则原样返回（不阻断流程）。
    优化策略：
      - 若图片宽度 < 800，先放大到 1.5 倍（更清晰显示）
      - UnsharpMask 锐化
      - 对比度 +10%
      - 保存为 JPEG quality=90（压缩体积但保清晰）
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        import io
        img = Image.open(io.BytesIO(image_bytes))
        # 转换模式：RGBA/P -> RGB
        if img.mode in ('RGBA', 'P', 'LA', 'L'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            if img.mode in ('RGBA', 'LA'):
                bg.paste(img, mask=img.split()[-1])
            else:
                bg.paste(img.convert('RGB'))
            img = bg
        else:
            img = img.convert('RGB')
        # 小图放大（提升视觉清晰度，但限制最大尺寸避免内存爆炸）
        w, h = img.size
        if w < 800 and w * h < 4_000_000:
            new_w = min(int(w * 1.5), 1600)
            new_h = int(h * new_w / w)
            img = img.resize((new_w, new_h), Image.LANCZOS)
        # 锐化
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=130, threshold=3))
        # 对比度 +10%
        img = ImageEnhance.Contrast(img).enhance(1.1)
        # 锐度再提升一点
        img = ImageEnhance.Sharpness(img).enhance(1.15)
        # 保存为 JPEG
        out = io.BytesIO()
        img.save(out, format='JPEG', quality=90, optimize=True)
        return out.getvalue(), 'image/jpeg'
    except Exception as e:
        # 优化失败：原样返回
        return image_bytes, None


# ---------- 图片本地化存储 ----------
def save_image_locally(news_id, idx, image_bytes, mime):
    """将优化后的图片存到 static/news_images/<news_id>_<idx>.jpg，返回相对URL"""
    import os
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'news_images')
    os.makedirs(base_dir, exist_ok=True)
    fname = f'{news_id}_{idx}.jpg'
    fp = os.path.join(base_dir, fname)
    with open(fp, 'wb') as f:
        f.write(image_bytes)
    return f'/static/news_images/{fname}'


def process_images(raw_images, title, content_keywords, news_id, enhance=True):
    """完整图片处理流水线：相关性审核 + 下载 + 清晰度优化 + 本地化存储。

    返回 [{'src': '/static/...', 'alt': '...', 'caption': '...'}, ...]
    只保留通过相关性审核的图片，最多 6 张。
    """
    if not raw_images:
        return []
    result = []
    kept_idx = 0
    for img in raw_images:
        if len(result) >= 6:
            break
        relevant, reason = is_image_relevant(img, title, content_keywords)
        if not relevant:
            print(f'      [过滤] {img["src"][:60]}... ({reason})')
            continue
        # 下载
        data = fetch_image_bytes(img['src'])
        if not data or len(data) < 2000:  # <2KB 多为占位图
            print(f'      [跳过] 下载失败或过小: {img["src"][:60]}')
            continue
        # 清晰度优化
        if enhance:
            enhanced, mime = enhance_image_clarity(data)
        else:
            enhanced, mime = data, None
        # 本地化存储
        local_url = save_image_locally(news_id, kept_idx, enhanced, mime)
        caption = img.get('alt', '') or img.get('context', '')[:60]
        result.append({
            'src': local_url,
            'alt': caption,
            'caption': caption,
            'original_src': img['src'],  # 保留原址备查，不展示
        })
        kept_idx += 1
        print(f'      [保留] {img["src"][:50]}... -> {local_url} ({reason})')
    return result


# ---------- TextRank 摘要 ----------
def split_sentences(text):
    """中英文分句"""
    if not text:
        return []
    text = re.sub(r'\s+', ' ', text)
    parts = SENTENCE_SPLIT.split(text)
    return [p.strip() for p in parts if len(p.strip()) >= 8]


def tokenize(text):
    """简易中文分词（按字 + 双字组合）+ 英文单词"""
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', ' ', text)
    tokens = []
    # 英文单词
    for w in re.findall(r'[a-zA-Z]{2,}', text):
        if w.lower() not in STOP_WORDS and len(w) >= 2:
            tokens.append(w.lower())
    # 中文双字
    cn = re.findall(r'[\u4e00-\u9fa5]', text)
    for i in range(len(cn) - 1):
        bi = cn[i] + cn[i + 1]
        if bi not in STOP_WORDS:
            tokens.append(bi)
    return tokens


def textrank_summary(text, num=5):
    """基于词频的抽取式摘要（TextRank 简化版）"""
    sentences = split_sentences(text)
    if not sentences:
        return []
    if len(sentences) <= num:
        return sentences
    # 词频
    word_freq = Counter()
    for s in sentences:
        word_freq.update(tokenize(s))
    # 句子得分
    scored = []
    for idx, s in enumerate(sentences):
        tokens = tokenize(s)
        if not tokens:
            scored.append((idx, s, 0))
            continue
        score = sum(word_freq[t] for t in tokens) / (len(tokens) ** 0.5)
        # 首句加权
        if idx == 0:
            score *= 1.3
        scored.append((idx, s, score))
    # 取 top N，按原文顺序返回
    top = sorted(scored, key=lambda x: -x[2])[:num]
    top_sorted = sorted(top, key=lambda x: x[0])
    return [x[1] for x in top_sorted]


def extract_keywords(text, num=10):
    """提取关键词"""
    tokens = tokenize(text)
    freq = Counter(tokens)
    # 过滤单字
    keywords = [(w, c) for w, c in freq.most_common(num * 3) if len(w) >= 2][:num]
    return [w for w, _ in keywords]


def generate_ai_analysis(title, content, summary, source, published_at):
    """生成结构化 AI 总结与分析（Markdown）"""
    if not content:
        content = summary or ''
    if not content:
        return '## AI 总结与分析\n\n暂未获取到原文内容，无法生成分析。请直接访问原文链接查看。'

    # 关键句
    key_sentences = textrank_summary(content, num=5)
    keywords = extract_keywords(content, num=10)
    content_len = len(content)

    md = []
    md.append('## 🤖 AI 总结与分析\n')
    md.append(f'> 基于原文 {content_len} 字自动生成 · 数据来源：{source or "网络"}\n')

    # 1. 核心要点
    md.append('### 📌 核心要点\n')
    if key_sentences:
        for i, s in enumerate(key_sentences, 1):
            # 截断过长句子
            if len(s) > 120:
                s = s[:120] + '...'
            md.append(f'{i}. {s}')
    else:
        md.append('- ' + (summary or title)[:100])
    md.append('')

    # 2. 关键词
    if keywords:
        md.append('### 🏷️ 关键信息\n')
        md.append('**关键词**：' + ' · '.join(keywords[:8]))
        md.append('')

    # 3. 背景与影响分析
    md.append('### 🔍 背景与影响分析\n')
    analyses = []
    title_text = (title + ' ' + content[:500]).lower()
    for kw, theme in ANALYSIS_KEYWORDS.items():
        if kw in title_text:
            analyses.append(theme)
    if not analyses:
        analyses.append('行业动态')

    # 生成分析文本
    if '技术突破' in analyses or '首次实现' in analyses:
        md.append(f'本事件属于**技术与产业突破**类新闻。从标题"{title}"可见，相关进展'
                  '标志着该领域实现重要跨越，有望推动产业链上下游协同发展，'
                  '并对国际竞争格局产生一定影响。建议持续关注后续产业化进度与商业化落地节奏。')
    elif '产业化进展' in analyses or '商业化落地' in analyses:
        md.append(f'本事件属于**产业化与商业化**进展。"{title}"表明相关技术已从实验室阶段'
                  '迈向规模化应用阶段，产业化加速将带动供应链整合与成本下探，'
                  '相关产业链企业有望率先受益。')
    elif '资本动向' in analyses or '资本市场' in analyses or '并购重组' in analyses:
        md.append(f'本事件属于**资本与市场**动向。"{title}"反映出市场对该赛道的高度关注，'
                  '资本投入加速将助推行业整合，但需警惕估值泡沫与竞争加剧风险。')
    elif '军事动态' in analyses or '地缘风险' in analyses or '国际博弈' in analyses:
        md.append(f'本事件属于**地缘与军事**动态。"{title}"涉及国际安全格局变化，'
                  '相关动向可能影响地区稳定与大国博弈走向，建议结合外交表态与'
                  '后续军力部署综合研判。')
    elif '宏观经济' in analyses or '货币政策' in analyses:
        md.append(f'本事件属于**宏观经济与政策**动态。"{title}"反映当前经济运行特征，'
                  '相关数据与政策走向将影响市场预期与资产配置，建议关注后续政策落地'
                  '与数据验证。')
    else:
        md.append(f'本事件属于**{analyses[0]}**范畴。"{title}"反映了该领域的最新进展，'
                  '建议结合行业趋势与竞争格局综合评估其长期影响。')
    md.append('')

    # 4. 重要性评估
    md.append('### ⭐ 重要性评估\n')
    if content_len > 1500:
        depth = '信息密度较高，原文披露详实'
    elif content_len > 500:
        depth = '信息量适中，覆盖主要事实'
    else:
        depth = '信息量有限，建议查阅原文获取细节'
    md.append(f'- **内容深度**：{depth}')
    md.append(f'- **关键词覆盖**：{len(keywords)} 个核心概念')
    md.append(f'- **建议**：{"适合深度研读" if content_len > 1500 else "可快速浏览把握要点"}')
    md.append('')

    md.append('---')
    md.append('*本分析由 TextRank 抽取式摘要算法生成，非大模型推理结果，仅供快速把握要点参考。*')

    return '\n'.join(md)


def analyze_news(news_id, force=False, rebuild_images=False):
    """分析单条新闻并入库。

    force=True 时忽略缓存重新抓取全文+生成分析。
    rebuild_images=True 时仅重新处理图片（保留现有 content/ai_summary）。
    """
    item = query('SELECT * FROM weekly_reports WHERE id = %s', (news_id,), one=True)
    if not item:
        print(f'未找到 id={news_id}')
        return False

    # 仅重建图片模式
    if rebuild_images:
        content = item.get('content') or ''
        if not content:
            print(f'  [SKIP] id={news_id} 无正文，无法重建图片')
            return False
        print(f'  [重建图片] id={news_id}: {item["title"][:40]}')
        # 重新抓取原页获取图片候选
        _, raw_images = fetch_article(item['url'])
        keywords = extract_keywords(content, num=15)
        images = process_images(raw_images, item['title'], keywords, news_id)
        execute(
            'UPDATE weekly_reports SET images = %s WHERE id = %s',
            (json.dumps(images, ensure_ascii=False), news_id),
        )
        print(f'  [OK] 图片重建完成，保留 {len(images)} 张')
        return True

    # 已有缓存则跳过（除非 force）
    if not force and item.get('content') and item.get('ai_summary'):
        print(f'  [SKIP] id={news_id} 已有缓存')
        return True

    print(f'  [分析] id={news_id}: {item["title"][:40]}')
    content, raw_images = fetch_article(item['url'])
    if not content:
        content = item.get('summary', '') or ''
        raw_images = []

    # 提取内容关键词用于图片相关性审核
    keywords = extract_keywords(content, num=15)
    # 图片处理流水线：审核 + 下载 + 优化 + 本地化
    print(f'      候选图片 {len(raw_images)} 张，开始审核...')
    images = process_images(raw_images, item['title'], keywords, news_id)

    ai_summary = generate_ai_analysis(
        item['title'], content, item.get('summary', ''),
        item.get('source', ''), item.get('published_at'),
    )

    execute(
        'UPDATE weekly_reports SET content = %s, images = %s, ai_summary = %s, fetched_at = %s WHERE id = %s',
        (content[:50000], json.dumps(images, ensure_ascii=False), ai_summary, datetime.now(), news_id),
    )
    print(f'  [OK] 正文 {len(content)} 字，图片 {len(images)} 张，AI 分析 {len(ai_summary)} 字')
    return True


def analyze_all(limit=50):
    """批量分析未抓取的新闻"""
    items = query(
        'SELECT id, title FROM weekly_reports '
        'WHERE (content IS NULL OR ai_summary IS NULL) AND url IS NOT NULL AND url != "" '
        'ORDER BY importance DESC LIMIT %s',
        (limit,),
    )
    print(f'待分析：{len(items)} 条')
    success = 0
    for it in items:
        if analyze_news(it['id']):
            success += 1
        time.sleep(1)  # 礼貌延迟
    print(f'\n完成：{success}/{len(items)}')
    return success


def rebuild_all_images(limit=100):
    """对所有已有正文的新闻重建图片（审核+优化+本地化）"""
    items = query(
        'SELECT id, title FROM weekly_reports '
        'WHERE content IS NOT NULL AND url IS NOT NULL AND url != "" '
        'ORDER BY importance DESC LIMIT %s',
        (limit,),
    )
    print(f'待重建图片：{len(items)} 条')
    success = 0
    for it in items:
        if analyze_news(it['id'], rebuild_images=True):
            success += 1
        time.sleep(1)
    print(f'\n完成：{success}/{len(items)}')
    return success


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--all':
            analyze_all()
        elif sys.argv[1] == '--rebuild-images':
            analyze_news(int(sys.argv[2]), rebuild_images=True)
        elif sys.argv[1] == '--rebuild-all-images':
            rebuild_all_images(int(sys.argv[2]) if len(sys.argv) > 2 else 100)
        elif sys.argv[1] == '--force':
            analyze_news(int(sys.argv[2]), force=True)
        else:
            analyze_news(int(sys.argv[1]))
    else:
        print('用法:')
        print('  python3 news_analyzer.py <id>                 分析单条')
        print('  python3 news_analyzer.py --all                批量分析未抓取')
        print('  python3 news_analyzer.py --force <id>         强制重新分析单条')
        print('  python3 news_analyzer.py --rebuild-images <id>     仅重建单条图片')
        print('  python3 news_analyzer.py --rebuild-all-images [N]  批量重建图片')
