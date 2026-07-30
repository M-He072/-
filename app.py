"""个人知识库 Flask 应用（Windows 兼容版）

关键优化：
1. 关闭 debug 模式（避免 Windows reloader 子进程 PID 失效、端口占用难停）
2. 跨平台 favicon 路径用 os.path.join(app.root_path, 'static')
3. 提供 waitress 生产 WSGI 入口：python app.py 时优先用 waitress
4. 所有路径基于 app.root_path，自动适配 D:\\知识库 等中文路径
"""
import os
import sys
from datetime import datetime, timedelta, date
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, abort, g, send_from_directory,
    send_file, Response,
)
import markdown as md
import bleach

from config import SECRET_KEY, HOST, PORT
from db import query, execute

app = Flask(__name__)
app.secret_key = SECRET_KEY

# AI 分析 Markdown 允许的标签
AI_ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'p', 'br', 'hr',
    'ul', 'ol', 'li', 'strong', 'em', 'blockquote', 'code', 'pre',
]


# ---------- 防缓存响应头：确保动态页面每次都拿最新数据 ----------
@app.after_request
def add_no_cache_headers(resp):
    """对 HTML 动态页面禁用缓存，避免增删笔记后看到旧列表"""
    if resp.content_type and 'text/html' in resp.content_type:
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
    return resp


# ---------- favicon：浏览器默认请求根路径 ----------
@app.route('/favicon.ico')
def favicon():
    """根路径 favicon，避免 404"""
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon',
    )


# ---------- Jinja 过滤器 ----------
@app.template_filter('markdown')
def render_markdown(text):
    """将 Markdown 渲染为安全的 HTML"""
    if not text:
        return ''
    html = md.markdown(text, extensions=['extra', 'codehilite', 'toc'])
    return bleach.clean(
        html,
        tags=['p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
              'ul', 'ol', 'li', 'a', 'b', 'strong', 'i', 'em',
              'code', 'pre', 'blockquote', 'hr', 'img', 'table',
              'thead', 'tbody', 'tr', 'th', 'td', 'span', 'div'],
        attributes={
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'title'],
            'code': ['class'],
            'span': ['class'],
            'div': ['class'],
        },
        strip=True,
    )


@app.template_filter('truncate_text')
def truncate_text(text, length=100):
    if not text:
        return ''
    plain = bleach.clean(text, tags=[], strip=True)
    return plain[:length] + '...' if len(plain) > length else plain


# ---------- 每个请求前加载分类 ----------
@app.before_request
def load_categories():
    g.categories = query('SELECT * FROM categories ORDER BY name')


@app.context_processor
def inject_stats():
    stats = query(
        'SELECT '
        '(SELECT COUNT(*) FROM notes) AS note_count, '
        '(SELECT COUNT(*) FROM categories) AS cat_count',
        one=True,
    )
    return dict(stats=stats or {'note_count': 0, 'cat_count': 0})


# ---------- 路由 ----------
@app.route('/')
def index():
    category_id = request.args.get('category', type=int)
    tag = request.args.get('tag', '').strip()

    if category_id:
        notes = query(
            'SELECT n.*, c.name AS category_name, c.color AS category_color '
            'FROM notes n LEFT JOIN categories c ON n.category_id = c.id '
            'WHERE n.category_id = %s '
            'ORDER BY n.is_pinned DESC, n.updated_at DESC',
            (category_id,),
        )
    elif tag:
        notes = query(
            "SELECT n.*, c.name AS category_name, c.color AS category_color "
            "FROM notes n LEFT JOIN categories c ON n.category_id = c.id "
            "WHERE n.tags LIKE %s "
            "ORDER BY n.is_pinned DESC, n.updated_at DESC",
            (f'%{tag}%',),
        )
    else:
        notes = query(
            'SELECT n.*, c.name AS category_name, c.color AS category_color '
            'FROM notes n LEFT JOIN categories c ON n.category_id = c.id '
            'ORDER BY n.is_pinned DESC, n.updated_at DESC'
        )

    return render_template('index.html', notes=notes,
                           current_category=category_id, current_tag=tag)


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    notes = []
    if q:
        notes = query(
            'SELECT n.*, c.name AS category_name, c.color AS category_color '
            'FROM notes n LEFT JOIN categories c ON n.category_id = c.id '
            'WHERE n.title LIKE %s OR n.content LIKE %s OR n.tags LIKE %s '
            'ORDER BY n.is_pinned DESC, n.updated_at DESC',
            (f'%{q}%', f'%{q}%', f'%{q}%'),
        )
    return render_template('search.html', notes=notes, q=q)


@app.route('/note/<int:note_id>')
def view_note(note_id):
    note = query(
        'SELECT n.*, c.name AS category_name, c.color AS category_color '
        'FROM notes n LEFT JOIN categories c ON n.category_id = c.id '
        'WHERE n.id = %s', (note_id,), one=True,
    )
    if not note:
        abort(404)
    execute('UPDATE notes SET views = views + 1 WHERE id = %s', (note_id,))
    note['views'] += 1
    return render_template('note.html', note=note)


@app.route('/note/new', methods=['GET', 'POST'])
def create_note():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        category_id = request.form.get('category_id') or None
        tags = request.form.get('tags', '').strip()
        is_pinned = 1 if request.form.get('is_pinned') else 0

        if not title:
            flash('标题不能为空', 'error')
            return render_template('form.html', note=request.form,
                                   mode='create')

        execute(
            'INSERT INTO notes (title, content, category_id, tags, is_pinned) '
            'VALUES (%s, %s, %s, %s, %s)',
            (title, content, category_id, tags, is_pinned),
        )
        flash('笔记创建成功！', 'success')
        return redirect(url_for('index'))
    return render_template('form.html', note=None, mode='create')


@app.route('/note/<int:note_id>/edit', methods=['GET', 'POST'])
def edit_note(note_id):
    note = query('SELECT * FROM notes WHERE id = %s', (note_id,), one=True)
    if not note:
        abort(404)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        category_id = request.form.get('category_id') or None
        tags = request.form.get('tags', '').strip()
        is_pinned = 1 if request.form.get('is_pinned') else 0

        if not title:
            flash('标题不能为空', 'error')
            return render_template('form.html', note=note, mode='edit')

        execute(
            'UPDATE notes SET title=%s, content=%s, category_id=%s, '
            'tags=%s, is_pinned=%s WHERE id=%s',
            (title, content, category_id, tags, is_pinned, note_id),
        )
        flash('笔记已更新', 'success')
        return redirect(url_for('view_note', note_id=note_id))
    return render_template('form.html', note=note, mode='edit')


@app.route('/note/<int:note_id>/delete', methods=['POST'])
def delete_note(note_id):
    execute('DELETE FROM notes WHERE id = %s', (note_id,))
    flash('笔记已删除', 'success')
    return redirect(url_for('index'))


@app.route('/note/<int:note_id>/pin', methods=['POST'])
def toggle_pin(note_id):
    execute('UPDATE notes SET is_pinned = 1 - is_pinned WHERE id = %s',
            (note_id,))
    return redirect(url_for('index'))


@app.route('/categories', methods=['GET', 'POST'])
def categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        color = request.form.get('color', '#6366f1').strip()
        if name:
            execute(
                'INSERT INTO categories (name, description, color) '
                'VALUES (%s, %s, %s)',
                (name, description, color),
            )
            flash('分类已添加', 'success')
        else:
            flash('分类名称不能为空', 'error')
        return redirect(url_for('categories'))

    cats = query(
        'SELECT c.*, '
        '(SELECT COUNT(*) FROM notes n WHERE n.category_id = c.id) AS note_count '
        'FROM categories c ORDER BY c.name'
    )
    return render_template('categories.html', categories=cats)


@app.route('/categories/<int:cat_id>/delete', methods=['POST'])
def delete_category(cat_id):
    execute('DELETE FROM categories WHERE id = %s', (cat_id,))
    flash('分类已删除（相关笔记将变为未分类）', 'success')
    return redirect(url_for('categories'))


# ---------- 周报功能 ----------
SECTIONS = [
    ('tech', '科技', '🔬'),
    ('military', '军事', '⚔️'),
    ('ai', 'AI', '🤖'),
    ('economy', '经济', '📊'),
]


@app.route('/weekly')
def weekly():
    """周报：国内外新闻，按版块分类"""
    region = request.args.get('region', 'domestic')  # domestic / international
    if region not in ('domestic', 'international'):
        region = 'domestic'

    # 获取可用周列表
    weeks = query(
        'SELECT DISTINCT week_of FROM weekly_reports '
        'ORDER BY week_of DESC LIMIT 8'
    )
    selected_week = request.args.get('week', type=str)
    if selected_week:
        try:
            selected_week = datetime.strptime(selected_week, '%Y-%m-%d').date()
        except Exception:
            selected_week = None
    if not selected_week and weeks:
        selected_week = weeks[0]['week_of']
    if not selected_week:
        # 本周五
        today = date.today()
        days_since_friday = (today.weekday() - 4) % 7
        selected_week = today - timedelta(days=days_since_friday) if today.weekday() >= 4 else today

    # 按版块获取新闻（每版块 Top 8）
    news_by_section = {}
    for key, name, icon in SECTIONS:
        items = query(
            'SELECT * FROM weekly_reports '
            'WHERE region = %s AND section = %s AND week_of = %s '
            'ORDER BY importance DESC, published_at DESC LIMIT 8',
            (region, key, selected_week),
        )
        news_by_section[key] = {'name': name, 'icon': icon, 'items': items}

    # 统计
    stats = query(
        'SELECT region, section, COUNT(*) AS cnt '
        'FROM weekly_reports WHERE week_of = %s '
        'GROUP BY region, section',
        (selected_week,),
    )
    stats_map = {}
    for s in stats:
        stats_map[f"{s['region']}_{s['section']}"] = s['cnt']

    return render_template(
        'weekly.html',
        region=region,
        sections=SECTIONS,
        news_by_section=news_by_section,
        weeks=weeks,
        selected_week=selected_week,
        stats_map=stats_map,
    )


@app.route('/weekly/refresh', methods=['POST'])
def weekly_refresh():
    """手动触发 RSS 抓取"""
    import subprocess
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(app.root_path, 'news_fetcher.py')],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'},
        )
        if proc.returncode == 0:
            flash('周报抓取完成，已更新最新新闻', 'success')
        else:
            flash(f'抓取过程有错误: {proc.stderr[-200:]}', 'error')
    except subprocess.TimeoutExpired:
        flash('抓取超时（120s），部分源可能不可达', 'error')
    except Exception as e:
        flash(f'抓取失败: {e}', 'error')
    return redirect(url_for('weekly'))


@app.route('/weekly/note/<int:news_id>')
def weekly_note(news_id):
    """周报新闻详情页：原文 + 附图 + 底部 AI 总结分析

    未缓存时立即渲染摘要并后台异步抓取，页面自动刷新展示完整内容，
    避免首次访问长时间空白卡顿。
    """
    import json as _json
    item = query('SELECT * FROM weekly_reports WHERE id = %s', (news_id,), one=True)
    if not item:
        abort(404)

    # 首次访问：后台异步抓取（不阻塞响应）
    needs_fetch = not item.get('content') or not item.get('ai_summary')
    if needs_fetch:
        try:
            import subprocess
            subprocess.Popen(
                [sys.executable, os.path.join(app.root_path, 'news_analyzer.py'), str(news_id)],
                stdout=open(os.devnull, 'w'),
                stderr=open(os.devnull, 'w'),
                env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'},
            )
        except Exception as e:
            flash(f'后台抓取启动失败: {e}', 'error')

    # 解析图片 JSON
    images = []
    if item.get('images'):
        try:
            images = _json.loads(item['images'])
        except Exception:
            images = []

    # 渲染 AI 分析（Markdown）
    ai_html = ''
    if item.get('ai_summary'):
        ai_html = md.markdown(
            item['ai_summary'],
            extensions=['extra', 'sane_lists', 'nl2br'],
        )
        ai_html = bleach.clean(ai_html, tags=AI_ALLOWED_TAGS, attributes={}, strip=True)

    # 段落化原文，并将图片内联插入段落之间（与原文关联，不单列一栏）
    content_html = ''
    if item.get('content'):
        paras = [p.strip() for p in item['content'].split('\n') if p.strip()]
        # 计算图片插入位置：均匀分布在段落之间
        # 策略：第1张插在第1段后，其余按段落间隔插入
        html_parts = []
        img_idx = 0
        img_count = len(images)
        for i, p in enumerate(paras):
            html_parts.append(f'<p>{bleach.clean(p, tags=[], strip=True)}</p>')
            # 在段落间插入图片（跳过最后一段后）
            if img_idx < img_count and i < len(paras) - 1:
                # 第1张插在第1段后；之后每隔一定段落插一张
                insert_after = (i == 0) or (img_count > 1 and (i + 1) >= max(1, len(paras) // img_count) * (img_idx + 1))
                if insert_after:
                    img = images[img_idx]
                    caption = bleach.clean(img.get('caption') or img.get('alt', ''), tags=[], strip=True)
                    # 不用 loading=lazy（部分环境首屏不触发），onerror 只隐藏 img 不隐藏 figure 避免误伤
                    html_parts.append(
                        f'<figure class="inline-image" data-full="{img["src"]}">'
                        f'<img src="{img["src"]}" alt="{caption}" '
                        f'title="双击放大查看" '
                        f'onerror="this.style.display=\'none\'">'
                        f'{f"<figcaption>{caption}</figcaption>" if caption else ""}'
                        f'</figure>'
                    )
                    img_idx += 1
        # 若还有剩余图片未插入（段落太少），追加到末尾
        while img_idx < img_count:
            img = images[img_idx]
            caption = bleach.clean(img.get('caption') or img.get('alt', ''), tags=[], strip=True)
            html_parts.append(
                f'<figure class="inline-image" data-full="{img["src"]}">'
                f'<img src="{img["src"]}" alt="{caption}" '
                f'title="双击放大查看" '
                f'onerror="this.style.display=\'none\'">'
                f'{f"<figcaption>{caption}</figcaption>" if caption else ""}'
                f'</figure>'
            )
            img_idx += 1
        content_html = ''.join(html_parts)

    return render_template(
        'weekly_detail.html',
        item=item,
        images=images,
        content_html=content_html,
        ai_html=ai_html,
        needs_refresh=needs_fetch,
    )


@app.route('/weekly/note/<int:news_id>/reanalyze', methods=['POST'])
def weekly_reanalyze(news_id):
    """手动重新抓取原文并生成 AI 分析（清空旧缓存）"""
    item = query('SELECT id, url FROM weekly_reports WHERE id = %s', (news_id,), one=True)
    if not item:
        abort(404)
    # 清空旧缓存，强制重新抓取
    execute(
        'UPDATE weekly_reports SET content = NULL, images = NULL, '
        'ai_summary = NULL, fetched_at = NULL WHERE id = %s',
        (news_id,),
    )
    try:
        import subprocess
        proc = subprocess.run(
            [sys.executable, os.path.join(app.root_path, 'news_analyzer.py'), str(news_id)],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'},
        )
        if proc.returncode == 0:
            flash('AI 分析已重新生成', 'success')
        else:
            flash(f'重新生成失败: {proc.stderr[-200:]}', 'error')
    except subprocess.TimeoutExpired:
        flash('抓取超时，请稍后重试或检查源站可达性', 'error')
    except Exception as e:
        flash(f'重新生成失败: {e}', 'error')
    return redirect(url_for('weekly_note', news_id=news_id))


@app.route('/dashboard')
def dashboard():
    """知识库可视化仪表盘"""
    from collections import Counter

    overview = query(
        'SELECT '
        '(SELECT COUNT(*) FROM notes) AS note_count, '
        '(SELECT COUNT(*) FROM categories) AS cat_count, '
        '(SELECT COALESCE(SUM(views), 0) FROM notes) AS total_views, '
        '(SELECT COUNT(*) FROM notes WHERE is_pinned = 1) AS pinned_count, '
        '(SELECT COUNT(*) FROM notes WHERE tags IS NOT NULL AND tags != "") AS tagged_count',
        one=True,
    )

    cat_dist = query(
        'SELECT c.name, c.color, COUNT(n.id) AS count '
        'FROM categories c LEFT JOIN notes n ON n.category_id = c.id '
        'GROUP BY c.id, c.name, c.color '
        'HAVING count > 0 '
        'ORDER BY count DESC'
    )

    tag_rows = query('SELECT tags FROM notes WHERE tags IS NOT NULL AND tags != ""')
    tag_counter = Counter()
    for row in tag_rows:
        for t in (row['tags'] or '').split(','):
            t = t.strip()
            if t:
                tag_counter[t] += 1
    top_tags = tag_counter.most_common(10)

    trend = query(
        'SELECT DATE(created_at) AS d, COUNT(*) AS c '
        'FROM notes '
        'WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) '
        'GROUP BY DATE(created_at) '
        'ORDER BY d'
    )
    trend = [{'d': str(r['d']), 'c': r['c']} for r in trend]

    top_views = query(
        'SELECT title, views FROM notes ORDER BY views DESC LIMIT 5'
    )

    return render_template(
        'dashboard.html',
        overview=overview,
        cat_dist=cat_dist,
        top_tags=top_tags,
        trend=trend,
        top_views=top_views,
    )


# ---------- 本地部署同步：打包最新源码供本地下载覆盖 ----------
SYNC_INCLUDE = [
    'app.py', 'config.py', 'db.py', 'news_analyzer.py', 'news_fetcher.py',
    'schema.sql', 'requirements.txt', 'README.md',
    'start.bat', 'stop.bat', 'launcher.bat', 'install.bat',
    'create-shortcut.bat', 'sync_local.bat',
]
SYNC_DIRS = ['templates', 'static']
# 排除运行时文件，避免覆盖本地数据/日志/缓存图片
SYNC_EXCLUDE_SUFFIX = ('.pyc', '.log', '.pid', '.json')
SYNC_EXCLUDE_NAMES = {
    '__pycache__', 'websearch_news.json', 'flask.log', 'flask.pid',
    'news_images',  # 图片本地缓存，各环境独立生成，不同步
}


@app.route('/sync/pack')
def sync_pack():
    """打包项目源码为 zip，供本地部署同步下载。

    用法：浏览器访问 /sync/pack 即下载 knowledge_base_sync.zip，
    解压覆盖本地 D:\\知识库 后重启服务即可。
    """
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        root = app.root_path
        # 单文件
        for f in SYNC_INCLUDE:
            fp = os.path.join(root, f)
            if os.path.isfile(fp):
                zf.write(fp, f)
        # 目录
        for d in SYNC_DIRS:
            dp = os.path.join(root, d)
            if not os.path.isdir(dp):
                continue
            for dirpath, dirnames, filenames in os.walk(dp):
                # 排除缓存目录
                dirnames[:] = [x for x in dirnames if x not in SYNC_EXCLUDE_NAMES]
                for fn in filenames:
                    if fn in SYNC_EXCLUDE_NAMES:
                        continue
                    if any(fn.endswith(s) for s in SYNC_EXCLUDE_SUFFIX):
                        continue
                    fp = os.path.join(dirpath, fn)
                    arc = os.path.relpath(fp, root)
                    zf.write(fp, arc)
    buf.seek(0)
    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    fname = f'knowledge_base_sync_{stamp}.zip'
    return send_file(
        buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=fname,
    )


@app.route('/sync/info')
def sync_info():
    """同步说明页：显示当前版本与同步步骤"""
    from flask import jsonify
    # 统计源码文件
    root = app.root_path
    files = list(SYNC_INCLUDE)
    for d in SYNC_DIRS:
        dp = os.path.join(root, d)
        if os.path.isdir(dp):
            for dirpath, _, fns in os.walk(dp):
                for fn in fns:
                    files.append(os.path.relpath(os.path.join(dirpath, fn), root))
    return jsonify({
        'version': 'v2.1',
        'pack_url': url_for('sync_pack', _external=True),
        'file_count': len(files),
        'files': sorted(files),
    })


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


# ---------- 入口：优先用 waitress 生产 WSGI，回退到 Flask dev server ----------
def run_server():
    """启动服务：优先 waitress（生产级，Windows 友好），失败回退 Flask"""
    try:
        from waitress import serve
        print(f'[waitress] 个人知识库启动于 http://{HOST}:{PORT}/')
        serve(app, host=HOST, port=PORT, threads=8)
    except ImportError:
        print('[flask] waitress 未安装，回退到 Flask dev server')
        print(f'个人知识库启动于 http://{HOST}:{PORT}/')
        # Windows 下关闭 debug 与 reloader，避免 PID 管理混乱
        app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


if __name__ == '__main__':
    run_server()
