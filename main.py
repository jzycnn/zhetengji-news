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
from deep_translator import GoogleTranslator

# 1. 基础网络设置
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context
socket.setdefaulttimeout(60) 

# 2. 全球顶级科技 RSS 源
feeds = [
    # --- 综合巨头 ---
    {"id": "verge", "name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "color": "#e10087"},
    {"id": "techcrunch", "name": "TechCrunch", "url": "https://techcrunch.com/feed/", "color": "#029f76"},
    {"id": "wired", "name": "Wired", "url": "https://www.wired.com/feed/rss", "color": "#000000"},
    {"id": "engadget", "name": "Engadget", "url": "https://www.engadget.com/rss.xml", "color": "#9059ff"},
    
    # --- 苹果/硬件 ---
    {"id": "macrumors", "name": "MacRumors", "url": "https://www.macrumors.com/macrumors.xml", "color": "#cd201f"},
    {"id": "9to5google", "name": "9to5Google", "url": "https://9to5google.com/feed/", "color": "#f4b400"},
    
    # --- 编程与极客 ---
    {"id": "hackernews", "name": "HackerNews", "url": "https://hnrss.org/newest?points=100", "color": "#ff6600"},
    {"id": "arstechnica", "name": "Ars Technica", "url": "https://arstechnica.com/feed/", "color": "#ff4e00"},
    {"id": "readwrite", "name": "ReadWrite", "url": "https://readwrite.com/feed/", "color": "#ff0000"},
]

# 初始化翻译器
translator = GoogleTranslator(source='auto', target='zh-CN')

def translate_text(text):
    """ 调用翻译接口 """
    if not text: return ""
    try:
        # 限制长度防止报错，只翻译精华部分
        return translator.translate(text[:900])
    except:
        return text

def get_image_from_html(html_content):
    """ 智能提取图片 """
    if not html_content: return None
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        imgs = soup.find_all('img')
        for img in imgs:
            candidates = ['src', 'data-src', 'data-original']
            for attr in candidates:
                url = img.get(attr)
                if url and url.startswith('http'):
                    if any(x in url for x in ['pixel', 'stat', 'share', 'feedburner', 'doubleclick', 'emoji', '1x1']):
                        continue
                    return url
    except: return None
    return None

def process_image_url(original_url):
    """ 图片代理与压缩 """
    if not original_url: return None
    original_url = original_url.strip()
    if not original_url.startswith('http'): return None
    try:
        encoded_url = urllib.parse.quote(original_url)
        return f"https://wsrv.nl/?url={encoded_url}&w=280&h=200&fit=cover&output=webp&q=80"
    except: return None

def clean_text(html):
    """ 清洗文本 """
    if not html: return ""
    return BeautifulSoup(html, 'html.parser').get_text().strip()

def fetch_feed(feed):
    """ 单个 Feed 抓取逻辑 """
    feed_articles = []
    try:
        print(f"正在抓取并翻译: {feed['name']}...")
        d = feedparser.parse(feed["url"])
        
        if not d.entries: return []

        # 抓取 15 条，防止翻译超时
        for entry in d.entries[:15]: 
            content_html = ""
            if hasattr(entry, 'content'): content_html = entry.content[0].value
            elif hasattr(entry, 'summary'): content_html = entry.summary
            elif hasattr(entry, 'description'): content_html = entry.description
            
            raw_img = get_image_from_html(content_html)
            final_img = process_image_url(raw_img)
            
            # 强过滤：无图跳过 (HackerNews除外)
            if not final_img and feed['id'] != 'hackernews': 
                continue

            # 1. 准备原始文本
            en_title = entry.title
            soup_text = clean_text(content_html)
            # 截取较长的段落作为正文摘要
            en_summary = soup_text[:800] if soup_text else en_title
            
            # 2. 【核心】预先翻译成中文
            zh_title = translate_text(en_title)
            zh_summary = translate_text(en_summary)
            
            # 3. 保留英文全文供 AI 搜索使用
            full_content_for_ai = soup_text[:4000]

            try:
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    ts = datetime.datetime(*entry.published_parsed[:6]).timestamp()
                    dt = datetime.datetime(*entry.published_parsed[:6])
                    pub_time = (dt + datetime.timedelta(hours=8)).strftime("%m-%d %H:%M")
                else:
                    ts = datetime.datetime.now().timestamp()
                    pub_time = "最新"
            except:
                ts = datetime.datetime.now().timestamp()
                pub_time = "最新"

            feed_articles.append({
                "title": zh_title,     # 标题已是中文
                "en_title": en_title,  
                "link": entry.link,
                "date": pub_time,
                "source": feed["name"],
                "source_id": feed["id"],
                "source_color": feed.get("color", "#333"),
                "image": final_img,
                "summary": zh_summary, # 正文已是中文
                "full_content": full_content_for_ai,
                "timestamp": ts
            })
    except Exception as e:
        print(f"Error fetching {feed['name']}: {e}")
        return []
    
    return feed_articles

def generate_html():
    articles = []
    feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    print(f"开始抓取...")
    
    # 限制并发数，防止翻译API报错
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_feed = {executor.submit(fetch_feed, feed): feed for feed in feeds}
        for future in concurrent.futures.as_completed(future_to_feed):
            try:
                data = future.result()
                if data: articles.extend(data)
            except Exception: pass

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
        hidden_class = "" if index < 20 else "news-item-hidden"
        display_style = "flex" if index < 20 else "none"

        # 图片回退
        if art["image"]:
            img_html = f'''
            <div class="item-img" data-type="image">
                <img src="{art["image"]}" loading="lazy" alt="封面" 
                     onerror="this.parentElement.setAttribute('data-type', 'fallback'); this.style.display='none';">
                <div class="img-fallback" style="background-color: {art['source_color']}15; color: {art['source_color']};">
                    {art['source'][0]}
                </div>
            </div>
            '''
        else:
            img_html = f'''
            <div class="item-img" data-type="fallback">
                <div class="img-fallback" style="background-color: {art['source_color']}15; color: {art['source_color']};">
                    {art['source'][0]}
                </div>
            </div>
            '''

        # 【核心修复】ensure_ascii=False 确保输出中文而不是Unicode编码
        safe_content = json.dumps(art['full_content'], ensure_ascii=False).replace('"', '&quot;')
        safe_zh_summary = json.dumps(art['summary'], ensure_ascii=False).replace('"', '&quot;') 
        safe_en_title = json.dumps(art['en_title'], ensure_ascii=False).replace('"', '&quot;')

        news_list_html += f"""
        <article class="news-item {hidden_class}" style="display:{display_style};" data-source="{art['source_id']}" onclick="openModal({index})">
            {img_html}
            <div class="item-content">
                <h2 class="item-title">{art['title']}</h2>
                <div class="item-meta">
                    <span class="source-badge" style="color:{art['source_color']}; background:{art['source_color']}15;">
                        {art['source']}
                    </span>
                    <span class="meta-date">{art['date']}</span>
                </div>
                <p class="item-summary">{art['summary'][:60]}...</p>
                <!-- 隐藏数据 -->
                <div id="data-{index}" style="display:none;" 
                     data-title="{art['title']}" 
                     data-en-title='{safe_en_title}'
                     data-link="{art['link']}"
                     data-source="{art['source']}"
                     data-date="{art['date']}"
                     data-zh-content='{safe_zh_summary}'>
                     {art['full_content']}
                </div>
            </div>
        </article>
        """
    
    tabs_html = '<button class="nav-btn active" onclick="filterNews(\'all\', this)">All</button>'
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
        <title>折疼记 - 全球科技情报</title>
        <script src="//unpkg.com/valine/dist/Valine.min.js"></script>
        <style>
            :root {{ 
                --primary: #0070f3; 
                --bg-body: #fafafa; 
                --bg-card: #ffffff; 
                --text-main: #111; 
                --text-sub: #666;
                --radius: 8px;
                --shadow: 0 2px 5px rgba(0,0,0,0.05);
            }}
            
            * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: var(--bg-body); margin: 0; color: var(--text-main); 
                display: flex; flex-direction: column; min-height: 100vh;
            }}
            
            header {{ 
                background: rgba(255,255,255,0.9); backdrop-filter: blur(20px);
                position: sticky; top: 0; z-index: 100; border-bottom: 1px solid #eaeaea;
            }}
            .header-inner {{ max-width: 800px; margin: 0 auto; height: 60px; display: flex; align-items: center; padding: 0 16px; }}
            .logo {{ color: #000; font-size: 18px; font-weight: 900; margin-right: 20px; letter-spacing: -0.5px; }}
            .logo span {{ color: var(--primary); }}
            
            .nav-scroll {{ flex: 1; overflow-x: auto; white-space: nowrap; scrollbar-width: none; display: flex; }}
            .nav-scroll::-webkit-scrollbar {{ display: none; }}
            .nav-btn {{ 
                background: none; border: none; color: var(--text-sub); 
                font-size: 14px; padding: 0 12px; height: 60px; cursor: pointer; font-weight: 500; 
            }}
            .nav-btn.active {{ color: #000; font-weight: 700; }}
            
            .container {{ max-width: 800px; margin: 24px auto; padding: 0 16px; width: 100%; flex: 1; }}
            
            .news-item {{ 
                background: var(--bg-card); margin-bottom: 16px; padding: 16px; 
                display: flex; border-radius: var(--radius); 
                box-shadow: var(--shadow); border: 1px solid #eaeaea;
                cursor: pointer; transition: all 0.2s ease;
            }}
            .news-item:hover {{ transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,0,0,0.08); }}
            
            .item-img {{ 
                width: 120px; height: 90px; flex-shrink: 0; margin-right: 16px; 
                border-radius: 4px; overflow: hidden; background: #f5f5f5; position: relative;
            }}
            .item-img img {{ width: 100%; height: 100%; object-fit: cover; }}
            
            .img-fallback {{ 
                position: absolute; top: 0; left: 0; width: 100%; height: 100%; 
                display: none; align-items: center; justify-content: center; 
                font-size: 32px; font-weight: 800;
            }}
            .item-img[data-type="fallback"] .img-fallback {{ display: flex; }}
            .item-img[data-type="fallback"] img {{ display: none; }}

            .item-content {{ flex: 1; display: flex; flex-direction: column; justify-content: space-between; }}
            .item-title {{ 
                margin: 0 0 6px 0; font-size: 17px; font-weight: 700; line-height: 1.4; color: #000;
                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
            }}
            .item-meta {{ font-size: 12px; color: #888; display: flex; align-items: center; }}
            .source-badge {{ padding: 2px 6px; border-radius: 4px; font-weight: 600; margin-right: 10px; font-size: 11px; text-transform: uppercase; }}
            .item-summary {{ 
                font-size: 14px; color: #555; line-height: 1.6; margin: 0;
                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
            }}

            .load-more-status {{ text-align: center; color: #aaa; font-size: 13px; padding: 20px; }}
            .main-footer {{ text-align: center; padding: 40px 0; color: #ccc; font-size: 12px; background: #fff; border-top: 1px solid #eaeaea; }}
            .main-footer a {{ color: #999; text-decoration: none; }}

            @media (max-width: 600px) {{
                .item-img {{ width: 100px; height: 75px; margin-right: 12px; }}
                .item-title {{ font-size: 16px; }}
                .item-summary {{ display: none; }}
            }}

            /* 模态框 */
            .modal-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); backdrop-filter: blur(5px); z-index: 2000; display: none; opacity: 0; transition: opacity 0.3s; }}
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
                padding: 0 20px; height: 60px; border-bottom: 1px solid #eaeaea; 
                display: flex; justify-content: space-between; align-items: center; 
                background: #fff; border-radius: 20px 20px 0 0; flex-shrink: 0; 
            }}
            .close-btn {{ font-size: 24px; color: #888; cursor: pointer; }}
            
            .modal-scroll-area {{ flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; }}
            .modal-body {{ padding: 30px; }}

            .article-title {{ font-size: 24px; font-weight: 800; margin-bottom: 8px; color: #000; line-height: 1.3; }}
            .article-en-title {{ font-size: 14px; color: #666; margin-bottom: 15px; font-style: italic; }}
            .article-meta {{ color: #999; font-size: 13px; margin-bottom: 25px; }}
            .article-content {{ font-size: 17px; line-height: 1.8; color: #333; white-space: pre-wrap; }}
            .read-more-btn {{ 
                display: block; width: 100%; text-align: center; 
                background: #f5f5f5; color: #333; 
                padding: 14px; margin-top: 30px; border-radius: 8px; 
                text-decoration: none; font-size: 14px; font-weight: 600;
            }}
            
            /* AI 报告区 */
            .ai-section {{ border-top: 1px solid #eaeaea; background: #fafafa; padding: 24px 30px; }}
            .section-title {{ font-size: 14px; font-weight: 700; color: var(--primary); margin-bottom: 12px; letter-spacing: 0.5px; text-transform: uppercase; }}
            
            .ai-chat-box {{ min-height: 100px; max-height: 300px; overflow-y: auto; background: #fff; border: 1px solid #eee; border-radius: 8px; padding: 20px; font-size: 15px; line-height: 1.7; color: #222; }}
            
            /* 评论 */
            .comment-section {{ border-top: 1px solid #eaeaea; background: #fff; padding: 24px 30px; }}
            #vcomments .vbtn {{ background: var(--primary); color: #fff; border: none; }}
        </style>
    </head>
    <body>
        <header>
            <div class="header-inner">
                <div class="logo">折疼记 <span>Global</span></div>
                <div class="nav-scroll">
                    {tabs_html}
                </div>
            </div>
        </header>

        <div class="container">
            <main id="newsContainer">
                {news_list_html}
            </main>
            <div id="loadStatus" class="load-more-status">Loading more...</div>
        </div>

        <footer class="main-footer">
            <p>文章总数: {len(articles)} | Updated: {update_time}</p>
            <p><a href="https://beian.miit.gov.cn/" target="_blank">浙ICP备2025183710号-1</a></p>
            <p>&copy; 折疼记</p>
        </footer>

        <div class="modal-overlay" id="articleModal" onclick="closeModal(event)">
            <div class="modal-card" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <span style="font-weight:700; color:#000;">深度阅读 (已译中文)</span>
                    <div class="close-btn" onclick="closeModal()">×</div>
                </div>
                
                <div class="modal-scroll-area">
                    <div class="modal-body">
                        <h1 class="article-title" id="mTitle"></h1>
                        <div class="article-en-title" id="mEnTitle"></div>
                        <div class="article-meta" id="mMeta"></div>
                        <!-- 这里直接显示预先翻译好的中文 -->
                        <div class="article-content" id="mContent"></div> 
                        <a href="" target="_blank" id="mLink" class="read-more-btn">🔗 阅读英文原文</a>
                    </div>
                    
                    <!-- 恢复 AI 提问功能 -->
                    <div class="ai-section">
                        <div class="section-title">🧠 AI 助手 (Ask DeepSeek)</div>
                        <div class="ai-chat-box" id="aiChatBox"></div>
                        <div class="ai-input-area">
                            <input type="text" class="ai-input" id="aiInput" placeholder="针对本文提问，或问任何问题..." onkeypress="handleEnter(event)">
                            <button class="ai-send-btn" id="aiBtn" onclick="sendToAI()">发送</button>
                        </div>
                    </div>

                    <div class="comment-section">
                        <div class="section-title">💬 讨论</div>
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

            const PAGE_SIZE = 20; 
            window.addEventListener('scroll', () => {{
                if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 500) {{ loadMore(); }}
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
                if (newlyShown === 0) statusDiv.innerText = "No more content";
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
                window.scrollTo({{ top: 0, behavior: 'smooth' }});
            }}

            function openModal(index) {{
                const dataDiv = document.getElementById('data-' + index);
                if(!dataDiv) return;
                
                const title = dataDiv.getAttribute('data-title');
                const enTitle = dataDiv.getAttribute('data-en-title'); 
                const source = dataDiv.getAttribute('data-source');
                const date = dataDiv.getAttribute('data-date');
                const link = dataDiv.getAttribute('data-link');
                const content = dataDiv.innerText.trim(); 
                const zhContent = dataDiv.getAttribute('data-zh-content'); 

                document.getElementById('mTitle').innerText = title;
                document.getElementById('mEnTitle').innerText = enTitle;
                document.getElementById('mMeta').innerHTML = `${{source}} · ${{date}}`;
                
                // --- 修复点：直接显示已翻译的中文 ---
                // 解码 Unicode 转义 (如果需要) 其实浏览器会自动处理 json.dumps 的转义
                try {{
                    const parsedZh = JSON.parse(zhContent);
                    document.getElementById('mContent').innerHTML = parsedZh && parsedZh.length > 10 ? parsedZh : '<p>内容较短，请查看原文。</p>';
                }} catch(e) {{
                    document.getElementById('mContent').innerHTML = zhContent;
                }}

                document.getElementById('mLink').href = link;
                
                currentArticleContext = `【文章】${{title}}\\n英文原文：${{content.substring(0, 3000)}}`;

                const chatBox = document.getElementById('aiChatBox');
                chatBox.innerHTML = '<div class="ai-msg bot">💡 你好！正文已自动翻译。你可以针对内容继续向我提问。</div>';

                const overlay = document.getElementById('articleModal');
                overlay.style.display = 'block';
                overlay.offsetHeight; 
                overlay.classList.add('open');
                document.body.style.overflow = 'hidden';

                document.getElementById('vcomments').innerHTML = ''; 
                new Valine({{
                    el: '#vcomments',
                    appId: 'DZ02oi5Bbo1wRzqukVZFcSZt-MdYXbMMI',
                    appKey: '7nqxYp6qhm48DoFB7eIgJyBi',
                    placeholder: 'Join the discussion...',
                    avatar: 'monsterid',
                    path: title, 
                    visitor: true
                }});
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
                    const response = await fetch(API_URL, {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json", "Authorization": `Bearer ${{API_KEY}}` }},
                        body: JSON.stringify({{
                            model: "deepseek-chat",
                            messages: [
                                {{role: "system", content: "你是一个智能助手。请根据用户提供的英文文章内容回答问题。如果问题无关，则直接回答。"}},
                                {{role: "user", content: `${{currentArticleContext}}\\n\\n问题：${{question}}`}}
                            ],
                            stream: false
                        }})
                    }});
                    const data = await response.json();
                    const aiResponseText = data.choices[0].message.content;
                    chatBox.innerHTML += `<div class="ai-msg bot">${{aiResponseText}}</div>`;
                }} catch (err) {{
                    chatBox.innerHTML += `<div class="ai-msg bot" style="color:red">Error: ${{err.message}}</div>`;
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
