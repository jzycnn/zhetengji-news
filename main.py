import feedparser
import datetime
import urllib.parse
from bs4 import BeautifulSoup
import ssl
import json
import random
import concurrent.futures
import time
import socket

# 1. 基础网络设置
# 修复 SSL 报错
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context
# 设置全局超时，防止脚本卡死
socket.setdefaulttimeout(30)

# 2. RSS 源配置 (精选高质量、高配图率的源)
feeds = [
    # --- 核心科技 ---
    {"id": "ithome", "name": "IT之家", "url": "https://www.ithome.com/rss/"},
    {"id": "jiemian", "name": "界面科技", "url": "https://www.jiemian.com/rss/119.xml"},
    {"id": "landian", "name": "蓝点网", "url": "https://www.landiannews.com/feed"},
    {"id": "pingwest", "name": "品玩", "url": "https://www.pingwest.com/feed/all"},
    
    # --- 极客与软件 ---
    {"id": "sspai", "name": "少数派", "url": "https://sspai.com/feed"},
    {"id": "appinn", "name": "小众软件", "url": "https://www.appinn.com/feed/"},
    {"id": "v2ex", "name": "V2EX", "url": "https://www.v2ex.com/index.xml"},
    
    # --- 游戏与娱乐 ---
    {"id": "gcores", "name": "机核网", "url": "https://www.gcores.com/rss"},
    {"id": "yystv", "name": "游研社", "url": "https://www.yystv.cn/rss/feed"},
    {"id": "douban", "name": "豆瓣影评", "url": "https://www.douban.com/feed/movie/review/best"},
]

def get_image_from_html(html_content):
    """ 智能提取图片 URL """
    if not html_content: return None
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        imgs = soup.find_all('img')
        for img in imgs:
            # 优先找懒加载属性
            candidates = ['data-original', 'data-src', 'data-url', 'src']
            for attr in candidates:
                url = img.get(attr)
                if url and url.startswith('http'):
                    # 过滤掉表情包、统计像素、小图标
                    if any(x in url for x in ['emoji', '.gif', 'avatar', 'stat', 'icon', 'button', 'share', 'pixel', 'logo']):
                        continue
                    return url
    except: return None
    return None

def process_image_url(original_url):
    """ 图片代理与压缩 (使用 wsrv.nl) """
    if not original_url: return None
    original_url = original_url.strip()
    if not original_url.startswith('http'): return None
    
    # 再次清洗 URL，防止包含奇怪字符
    try:
        encoded_url = urllib.parse.quote(original_url)
        # w=280&h=200: 卡片尺寸
        # fit=cover: 裁剪填满
        # q=80: 质量 80%
        return f"https://wsrv.nl/?url={encoded_url}&w=280&h=200&fit=cover&output=webp&q=80"
    except:
        return None

def clean_text(html):
    """ 获取纯文本摘要 """
    if not html: return ""
    return BeautifulSoup(html, 'html.parser').get_text().strip()

def fetch_feed(feed):
    """ 单个 Feed 抓取逻辑 """
    feed_articles = []
    try:
        # 增加 headers 模拟浏览器，减少 403 概率
        d = feedparser.parse(feed["url"], agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        if not d.entries: return []

        # 每个源多抓一点(35条)，因为严苛模式下会过滤掉很多
        for entry in d.entries[:35]: 
            content_html = ""
            if hasattr(entry, 'content'): content_html = entry.content[0].value
            elif hasattr(entry, 'summary'): content_html = entry.summary
            elif hasattr(entry, 'description'): content_html = entry.description
            
            raw_img = get_image_from_html(content_html)
            final_img = process_image_url(raw_img)
            
            # 【严苛模式】核心：没有图片，直接跳过，不录入
            if not final_img: 
                continue

            soup_text = clean_text(content_html)
            summary_short = soup_text[:85] + "..." if soup_text else entry.title
            full_content_for_ai = soup_text[:3500]

            # 时间标准化
            try:
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    ts = datetime.datetime(*entry.published_parsed[:6]).timestamp()
                    dt = datetime.datetime(*entry.published_parsed[:6])
                    pub_time = (dt + datetime.timedelta(hours=8)).strftime("%m-%d %H:%M")
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    ts = datetime.datetime(*entry.updated_parsed[:6]).timestamp()
                    dt = datetime.datetime(*entry.updated_parsed[:6])
                    pub_time = (dt + datetime.timedelta(hours=8)).strftime("%m-%d %H:%M")
                else:
                    ts = datetime.datetime.now().timestamp()
                    pub_time = "最新"
            except:
                ts = datetime.datetime.now().timestamp()
                pub_time = "最新"

            feed_articles.append({
                "title": entry.title,
                "link": entry.link,
                "date": pub_time,
                "source": feed["name"],
                "source_id": feed["id"],
                "image": final_img,
                "summary": summary_short,
                "full_content": full_content_for_ai,
                "timestamp": ts
            })
    except Exception as e:
        print(f"Error fetching {feed['name']}: {e}")
        return []
    
    return feed_articles

def generate_html():
    articles = []
    print(f"开始并行抓取 {len(feeds)} 个源 (严苛模式)...")
    
    # 线程池抓取
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_feed = {executor.submit(fetch_feed, feed): feed for feed in feeds}
        for future in concurrent.futures.as_completed(future_to_feed):
            try:
                data = future.result()
                if data:
                    articles.extend(data)
            except Exception: pass

    # 排序
    articles.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # 去重
    unique_articles = []
    seen = set()
    for art in articles:
        if art['title'] not in seen:
            unique_articles.append(art)
            seen.add(art['title'])
    articles = unique_articles
    
    print(f"有效文章数: {len(articles)}")

    news_list_html = ""
    for index, art in enumerate(articles):
        # 分页逻辑：前20条显示，后面的隐藏
        hidden_class = "" if index < 20 else "news-item-hidden"
        display_style = "flex" if index < 20 else "none"

        # 安全转义
        safe_content = json.dumps(art['full_content']).replace('"', '&quot;')

        # 【严苛模式】前端二次保障：如果图片加载失败，直接移除整个卡片
        img_html = f'''
        <div class="item-img">
            <img src="{art["image"]}" loading="lazy" alt="封面" 
                 onerror="this.closest('.news-item').remove()">
        </div>
        '''

        news_list_html += f"""
        <article class="news-item {hidden_class}" style="display:{display_style};" data-source="{art['source_id']}" onclick="openModal({index})">
            {img_html}
            <div class="item-content">
                <h2 class="item-title">{art['title']}</h2>
                <div class="item-meta">
                    <span class="source-badge">{art['source']}</span>
                    <span class="meta-date">{art['date']}</span>
                </div>
                <p class="item-summary">{art['summary']}</p>
                <!-- 隐藏数据 -->
                <div id="data-{index}" style="display:none;" 
                     data-title="{art['title']}" 
                     data-link="{art['link']}"
                     data-source="{art['source']}"
                     data-date="{art['date']}">
                     {art['full_content']}
                </div>
            </div>
        </article>
        """
    
    tabs_html = '<button class="nav-btn active" onclick="filterNews(\'all\', this)">全部</button>'
    seen_ids = set()
    for feed in feeds:
        if feed['id'] not in seen_ids:
            tabs_html += f'<button class="nav-btn" onclick="filterNews(\'{feed["id"]}\', this)">{feed["name"]}</button>'
            seen_ids.add(feed['id'])

    utc_now = datetime.datetime.utcnow()
    beijing_now = utc_now + datetime.timedelta(hours=8)
    update_time = beijing_now.strftime("%Y-%m-%d %H:%M")

    template = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        <meta name="referrer" content="no-referrer">
        <title>折疼记 - 聚合资讯</title>
        <script src="//unpkg.com/valine/dist/Valine.min.js"></script>
        <style>
            :root {{ 
                --primary: #0b63b6; 
                --primary-soft: rgba(11, 99, 182, 0.08);
                --bg-body: #f5f7fa; 
                --bg-card: #ffffff; 
                --text-main: #333; 
                --text-sub: #888;
                --radius: 12px;
                --shadow: 0 4px 12px rgba(0,0,0,0.03);
            }}
            
            * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                background-color: var(--bg-body); margin: 0; color: var(--text-main); 
                display: flex; flex-direction: column; min-height: 100vh;
            }}
            
            /* --- 导航栏 (毛玻璃) --- */
            header {{ 
                background: rgba(255,255,255,0.85); backdrop-filter: blur(12px);
                position: sticky; top: 0; z-index: 100; border-bottom: 1px solid rgba(0,0,0,0.05);
            }}
            .header-inner {{ max-width: 800px; margin: 0 auto; height: 60px; display: flex; align-items: center; padding: 0 16px; }}
            .logo {{ color: var(--primary); font-size: 20px; font-weight: 800; margin-right: 20px; }}
            .nav-scroll {{ flex: 1; overflow-x: auto; white-space: nowrap; scrollbar-width: none; display: flex; }}
            .nav-scroll::-webkit-scrollbar {{ display: none; }}
            .nav-btn {{ 
                background: none; border: none; color: var(--text-sub); 
                font-size: 15px; padding: 0 14px; height: 60px; cursor: pointer; font-weight: 500; transition: color 0.2s;
            }}
            .nav-btn.active {{ color: var(--primary); font-weight: 700; position: relative; }}
            .nav-btn.active::after {{ content:''; position:absolute; bottom:0; left:14px; right:14px; height:3px; background:var(--primary); border-radius:3px 3px 0 0; }}
            
            /* --- 列表区域 --- */
            .container {{ max-width: 800px; margin: 24px auto; padding: 0 16px; width: 100%; flex: 1; }}
            
            .news-item {{ 
                background: var(--bg-card); margin-bottom: 20px; padding: 16px; 
                display: flex; border-radius: var(--radius); 
                box-shadow: var(--shadow); border: 1px solid rgba(0,0,0,0.02);
                cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;
            }}
            .news-item:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.06); }}
            .news-item:active {{ transform: scale(0.99); }}
            
            .item-img {{ 
                width: 140px; height: 105px; flex-shrink: 0; margin-right: 20px; 
                border-radius: 8px; overflow: hidden; background: #eee;
            }}
            .item-img img {{ width: 100%; height: 100%; object-fit: cover; transition: transform 0.5s; }}
            .news-item:hover .item-img img {{ transform: scale(1.05); }}
            
            .item-content {{ flex: 1; display: flex; flex-direction: column; justify-content: space-between; padding-top: 2px; }}
            .item-title {{ 
                margin: 0 0 8px 0; font-size: 18px; font-weight: 700; line-height: 1.4; color: #222;
                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
            }}
            .item-meta {{ font-size: 13px; color: #999; display: flex; align-items: center; }}
            .source-badge {{ 
                color: var(--primary); background: var(--primary-soft); 
                padding: 2px 8px; border-radius: 4px; font-weight: 600; margin-right: 12px; 
            }}
            .item-summary {{ 
                font-size: 14px; color: #666; line-height: 1.6; margin: 0;
                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
            }}

            .load-more-status {{ text-align: center; color: #aaa; font-size: 13px; padding: 20px; }}

            .main-footer {{ text-align: center; padding: 40px 0; color: #ccc; font-size: 12px; background: #fff; margin-top: 40px; border-top: 1px solid #eee; }}
            .main-footer a {{ color: #ccc; text-decoration: none; }}

            @media (max-width: 600px) {{
                .item-img {{ width: 110px; height: 80px; margin-right: 12px; }}
                .item-title {{ font-size: 16px; margin-bottom: 4px; }}
                .item-summary {{ display: none; }}
                .news-item {{ padding: 12px; margin-bottom: 12px; }}
                .container {{ margin: 16px auto; }}
            }}

            /* --- 模态框 --- */
            .modal-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); z-index: 2000; display: none; opacity: 0; transition: opacity 0.3s; }}
            .modal-overlay.open {{ display: block; opacity: 1; }}
            .modal-card {{ 
                position: fixed; bottom: 0; left: 0; width: 100%; height: 95vh; 
                background: #fff; border-radius: 20px 20px 0 0; 
                transform: translateY(100%); transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
                z-index: 2001; display: flex; flex-direction: column;
                box-shadow: 0 -10px 40px rgba(0,0,0,0.2);
            }}
            .modal-overlay.open .modal-card {{ transform: translateY(0); }}
            
            @media (min-width: 769px) {{
                .modal-card {{ 
                    width: 720px; height: 90vh; left: 50%; top: 50%; bottom: auto;
                    transform: translate(-50%, -45%) scale(0.95); opacity: 0; border-radius: 16px; 
                }}
                .modal-overlay.open .modal-card {{ transform: translate(-50%, -50%) scale(1); opacity: 1; }}
            }}
            
            .modal-header {{ 
                padding: 0 24px; height: 60px; border-bottom: 1px solid #eee; 
                display: flex; justify-content: space-between; align-items: center; 
                background: #fff; border-radius: 20px 20px 0 0; flex-shrink: 0; 
            }}
            .close-btn {{ font-size: 24px; color: #888; cursor: pointer; padding: 5px; }}
            
            .modal-scroll-area {{ flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; }}
            .modal-body {{ padding: 30px; }}

            .article-title {{ font-size: 24px; font-weight: 800; margin-bottom: 12px; color: #111; line-height: 1.3; }}
            .article-meta {{ color: #999; font-size: 14px; margin-bottom: 30px; }}
            .article-content {{ font-size: 17px; line-height: 1.8; color: #333; }}
            .read-more-btn {{ 
                display: block; width: 100%; text-align: center; 
                background: var(--primary-soft); color: var(--primary); font-weight: 600;
                padding: 14px; margin-top: 40px; border-radius: 10px; 
                text-decoration: none; font-size: 15px; 
            }}
            
            .ai-section, .comment-section {{ border-top: 1px solid #f0f0f0; background: #fafafa; padding: 24px 30px; }}
            .section-title {{ font-size: 15px; font-weight: 700; color: #333; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
            
            .ai-chat-box {{ height: 200px; overflow-y: auto; background: #fff; border: 1px solid #eee; border-radius: 12px; padding: 16px; margin-bottom: 12px; font-size: 15px; }}
            .ai-msg {{ margin-bottom: 12px; line-height: 1.6; }}
            .ai-msg.user {{ color: #fff; background: var(--primary); padding: 8px 14px; border-radius: 14px 14px 2px 14px; float: right; clear: both; max-width: 85%; }}
            .ai-msg.bot {{ color: #333; background: #f2f4f7; padding: 8px 14px; border-radius: 14px 14px 14px 2px; float: left; clear: both; max-width: 90%; }}
            .ai-msg::after {{ content: ""; display: table; clear: both; }}
            
            .ai-input-area {{ display: flex; position: relative; }}
            .ai-input {{ flex: 1; padding: 12px 16px; border: 1px solid #ddd; border-radius: 24px; font-size: 15px; padding-right: 80px; outline: none; }}
            .ai-input:focus {{ border-color: var(--primary); }}
            .ai-send-btn {{ position: absolute; right: 5px; top: 5px; bottom: 5px; background: var(--primary); color: #fff; border: none; padding: 0 16px; border-radius: 20px; cursor: pointer; font-weight: 600; }}
            .ai-send-btn:disabled {{ background: #ccc; }}
            
            #vcomments .vbtn {{ background: var(--primary); color: #fff; border: none; }}
        </style>
    </head>
    <body>
        <header>
            <div class="header-inner">
                <div class="logo">折疼记</div>
                <div class="nav-scroll">
                    {tabs_html}
                </div>
            </div>
        </header>

        <div class="container">
            <main id="newsContainer">
                {news_list_html}
            </main>
            <div id="loadStatus" class="load-more-status">下拉加载更多...</div>
        </div>

        <footer class="main-footer">
            <p>文章总数: {len(articles)} | 更新于: {update_time}</p>
            <p><a href="https://beian.miit.gov.cn/" target="_blank">浙ICP备2025183710号-1</a></p>
            <p>&copy; 折疼记</p>
        </footer>

        <div class="modal-overlay" id="articleModal" onclick="closeModal(event)">
            <div class="modal-card" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <span style="font-weight:700; color:var(--primary); font-size:16px;">✨ 沉浸阅读</span>
                    <div class="close-btn" onclick="closeModal()">×</div>
                </div>
                
                <div class="modal-scroll-area">
                    <div class="modal-body">
                        <h1 class="article-title" id="mTitle"></h1>
                        <div class="article-meta" id="mMeta"></div>
                        <div class="article-content" id="mContent"></div>
                        <a href="" target="_blank" id="mLink" class="read-more-btn">🔗 跳转至源网站查看全文</a>
                    </div>
                    
                    <div class="ai-section">
                        <div class="section-title">🧠 AI 深度搜索 <span>(已联网)</span></div>
                        <div class="ai-chat-box" id="aiChatBox"></div>
                        <div class="ai-input-area">
                            <input type="text" class="ai-input" id="aiInput" placeholder="对此有疑问？问问 AI..." onkeypress="handleEnter(event)">
                            <button class="ai-send-btn" id="aiBtn" onclick="sendToAI()">发送</button>
                        </div>
                    </div>

                    <div class="comment-section">
                        <div class="section-title">💬 评论区</div>
                        <div id="vcomments"></div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let currentArticleContext = "";
            let currentFilter = 'all';
            const API_KEY = "sk-bcc4ef2185e24dce86a028982862a81e"; 
            const API_URL = "https://api.deepseek.com/chat/completions";

            // --- 无限滚动逻辑 ---
            const PAGE_SIZE = 20; 
            window.addEventListener('scroll', () => {{
                if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 500) {{
                    loadMore();
                }}
            }});

            function loadMore() {{
                const allItems = document.querySelectorAll('.news-item');
                let newlyShown = 0;
                
                for (let i = 0; i < allItems.length; i++) {{
                    const item = allItems[i];
                    if (item.classList.contains('news-item-hidden')) {{
                        if (currentFilter === 'all' || item.getAttribute('data-source') === currentFilter) {{
                            item.style.display = 'flex';
                            item.classList.remove('news-item-hidden');
                            newlyShown++;
                            if (newlyShown >= PAGE_SIZE) break;
                        }}
                    }}
                }}
                
                const statusDiv = document.getElementById('loadStatus');
                if (newlyShown === 0) {{
                    statusDiv.innerHTML = "🎉 内容已全部加载完毕";
                }} else {{
                    statusDiv.innerHTML = "⏳ 正在加载更多...";
                }}
            }}

            function filterNews(sourceId, btn) {{
                currentFilter = sourceId;
                document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                const items = document.querySelectorAll('.news-item');
                let shownCount = 0;
                
                items.forEach(item => {{
                    const match = (sourceId === 'all' || item.getAttribute('data-source') === sourceId);
                    if (match) {{
                        if (shownCount < PAGE_SIZE) {{
                            item.style.display = 'flex';
                            item.classList.remove('news-item-hidden');
                        }} else {{
                            item.style.display = 'none';
                            item.classList.add('news-item-hidden');
                        }}
                        shownCount++;
                    }} else {{
                        item.style.display = 'none';
                        item.classList.add('news-item-hidden');
                    }}
                }});
                
                document.getElementById('loadStatus').innerHTML = "⏳ 正在加载更多...";
                window.scrollTo({{ top: 0, behavior: 'smooth' }});
            }}

            function openModal(index) {{
                const dataDiv = document.getElementById('data-' + index);
                if(!dataDiv) return;
                
                const title = dataDiv.getAttribute('data-title');
                const source = dataDiv.getAttribute('data-source');
                const date = dataDiv.getAttribute('data-date');
                const link = dataDiv.getAttribute('data-link');
                const content = dataDiv.innerText.trim();

                document.getElementById('mTitle').innerText = title;
                document.getElementById('mMeta').innerHTML = `<span class='source-badge'>${{source}}</span> ${{date}}`;
                document.getElementById('mContent').innerHTML = content.length > 5 ? content : '<p>暂无详细摘要，请让 AI 进行分析。</p>';
                document.getElementById('mLink').href = link;
                
                currentArticleContext = `【文章】${{title}}\\n${{content.substring(0, 2000)}}`;

                const chatBox = document.getElementById('aiChatBox');
                chatBox.innerHTML = '<div class="ai-msg bot">💡 你好！我是 AI 助手。</div>';

                document.getElementById('vcomments').innerHTML = ''; 
                new Valine({{
                    el: '#vcomments',
                    appId: 'DZ02oi5Bbo1wRzqukVZFcSZt-MdYXbMMI',
                    appKey: '7nqxYp6qhm48DoFB7eIgJyBi',
                    placeholder: '既然来了，就说两句吧...',
                    avatar: 'monsterid',
                    path: title, 
                    visitor: true
                }});

                const overlay = document.getElementById('articleModal');
                overlay.style.display = 'block';
                overlay.offsetHeight; 
                overlay.classList.add('open');
                document.body.style.overflow = 'hidden';
            }}

            function closeModal(e) {{
                const overlay = document.getElementById('articleModal');
                overlay.classList.remove('open');
                setTimeout(() => {{ overlay.style.display = 'none'; }}, 300);
                document.body.style.overflow = '';
            }}

            async function sendToAI() {{
                const input = document.getElementById('aiInput');
                const btn = document.getElementById('aiBtn');
                const chatBox = document.getElementById('aiChatBox');
                const question = input.value.trim();
                
                if (!question) return;

                input.value = '';
                input.disabled = true;
                btn.disabled = true;
                btn.innerText = '...';
                
                chatBox.innerHTML += `<div class="ai-msg user">${{question}}</div>`;
                chatBox.scrollTop = chatBox.scrollHeight;

                try {{
                    const systemPrompt = "你是一个功能强大的 AI 搜索助手。用户正在阅读一篇新闻，并可能会根据新闻提问，或者问完全无关的问题。\\n\\n你的任务是：\\n1. 如果用户的问题与【当前阅读文章】相关，请结合文章内容深入解答。\\n2. 如果用户的问题与文章无关，请**忽略参考文章**，直接调用你的互联网知识储备回答。\\n3. 回答风格要像搜索引擎一样客观、精准。";

                    const response = await fetch(API_URL, {{
                        method: "POST",
                        headers: {{
                            "Content-Type": "application/json",
                            "Authorization": `Bearer ${{API_KEY}}`
                        }},
                        body: JSON.stringify({{
                            model: "deepseek-chat",
                            messages: [
                                {{role: "system", content: systemPrompt}},
                                {{role: "user", content: `${{currentArticleContext}}\\n\\n----------------\\n用户问题：${{question}}`}}
                            ],
                            stream: false
                        }})
                    }});
                    
                    if (!response.ok) {{
                        throw new Error("API 请求失败");
                    }}
                    
                    const data = await response.json();
                    const aiResponseText = data.choices[0].message.content;
                    chatBox.innerHTML += `<div class="ai-msg bot">${{aiResponseText}}</div>`;

                }} catch (err) {{
                    chatBox.innerHTML += `<div class="ai-msg bot" style="color:red">⚠️ 错误: ${{err.message}}</div>`;
                }} finally {{
                    input.disabled = false;
                    btn.disabled = false;
                    btn.innerText = '发送';
                    chatBox.scrollTop = chatBox.scrollHeight;
                    input.focus();
                }}
            }}

            function handleEnter(e) {{
                if (e.key === 'Enter') sendToAI();
            }}
        </script>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(template)

if __name__ == "__main__":
    generate_html()
