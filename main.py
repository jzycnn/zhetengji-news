import feedparser
import datetime
import urllib.parse
from bs4 import BeautifulSoup
import ssl
import json
import random

# 1. SSL 证书修复
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# 2. 配置 RSS 源 (精选高可用源)
feeds = [
    {"id": "all", "name": "全部", "url": ""},
    {"id": "ithome", "name": "IT之家", "url": "https://www.ithome.com/rss/"},
    {"id": "landian", "name": "蓝点网", "url": "https://www.landiannews.com/feed"},
    {"id": "william", "name": "月光博客", "url": "https://www.williamlong.info/rss.xml"},
    {"id": "appinn", "name": "小众软件", "url": "https://www.appinn.com/feed/"},
    {"id": "pingwest", "name": "品玩", "url": "https://www.pingwest.com/feed/all"},
    {"id": "sspai", "name": "少数派", "url": "https://sspai.com/feed"},
    {"id": "solidot", "name": "Solidot", "url": "https://www.solidot.org/index.rss"},
    {"id": "v2ex", "name": "V2EX", "url": "https://www.v2ex.com/index.xml"},
]

def get_image_from_html(html_content):
    """ 智能提取图片 """
    if not html_content: return None
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        imgs = soup.find_all('img')
        for img in imgs:
            # 增加对 src 属性的清理，有些网站会有相对路径
            candidates = ['data-original', 'data-src', 'data-url', 'src']
            for attr in candidates:
                url = img.get(attr)
                if url and url.startswith('http'):
                    # 过滤掉表情包、小图标、头像、统计像素
                    if any(x in url for x in ['emoji', '.gif', 'avatar', 'stat', 'icon', 'button']):
                        continue
                    return url
    except: return None
    return None

def process_image_url(original_url):
    """ 图片代理与压缩 """
    if not original_url: return None
    original_url = original_url.strip()
    if not original_url.startswith('http'): return None
    encoded_url = urllib.parse.quote(original_url)
    # 使用 wsrv.nl 代理，强制 WebP
    return f"https://wsrv.nl/?url={encoded_url}&w=240&h=180&fit=cover&output=webp&q=80"

def clean_text(html):
    """ 清洗 HTML 获取纯文本 """
    if not html: return ""
    return BeautifulSoup(html, 'html.parser').get_text().strip()

def generate_html():
    articles = []
    # 使用更像真人的 User-Agent，增加抓取成功率
    feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    print("开始抓取...")
    
    for feed in feeds[1:]:
        try:
            print(f"正在读取: {feed['name']}...")
            # 增加 etag/modified 处理，虽然 feedparser 会自动处理，但显式调用更安全
            f = feedparser.parse(feed["url"])
            
            # 检查是否有 bozo 异常 (XML解析错误)
            if f.bozo:
                print(f"  - XML 解析可能有问题，尝试继续: {f.bozo_exception}")

            if not f.entries:
                print(f"  - 警告: {feed['name']} 没有抓取到内容，可能是被反爬了。")
                continue

            # 抓取前15条
            for entry in f.entries[:15]: 
                content_html = ""
                # 尝试获取全文或摘要
                if hasattr(entry, 'content'): 
                    content_html = entry.content[0].value
                elif hasattr(entry, 'summary'): 
                    content_html = entry.summary
                elif hasattr(entry, 'description'): 
                    content_html = entry.description
                
                raw_img = get_image_from_html(content_html)
                final_img = process_image_url(raw_img)
                
                # 强过滤：无图不要 (为了保持版面整洁)
                if not final_img: continue

                soup_text = clean_text(content_html)
                summary_short = soup_text[:80] + "..." if soup_text else entry.title
                full_content_for_ai = soup_text[:3000]

                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        dt = datetime.datetime(*entry.published_parsed[:6])
                        pub_time = (dt + datetime.timedelta(hours=8)).strftime("%m-%d %H:%M")
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        dt = datetime.datetime(*entry.updated_parsed[:6])
                        pub_time = (dt + datetime.timedelta(hours=8)).strftime("%m-%d %H:%M")
                    else:
                        pub_time = "最新"
                except:
                    pub_time = "最新"

                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "date": pub_time,
                    "source": feed["name"],
                    "source_id": feed["id"],
                    "image": final_img,
                    "summary": summary_short,
                    "full_content": full_content_for_ai,
                    "timestamp": entry.get("published_parsed", datetime.datetime.now().timetuple())
                })
        except Exception as e:
            print(f"Error fetching {feed['name']}: {e}")
            continue

    # 按时间倒序
    articles.sort(key=lambda x: x["timestamp"] if x["timestamp"] else tuple(), reverse=True)
    
    print(f"共生成 {len(articles)} 篇文章。")

    news_list_html = ""
    for index, art in enumerate(articles):
        # JSON 安全处理
        safe_content = json.dumps(art['full_content']).replace('"', '&quot;')
        
        # 即使后端过滤了，前端也加上 onerror 移除，双重保险
        img_html = f'''
        <div class="item-img">
            <img src="{art["image"]}" loading="lazy" alt="封面" 
                 onerror="this.closest('.news-item').remove()">
        </div>
        '''

        news_list_html += f"""
        <article class="news-item" data-source="{art['source_id']}" onclick="openModal({index})">
            {img_html}
            <div class="item-content">
                <h2 class="item-title">{art['title']}</h2>
                <div class="item-meta">
                    <span class="meta-tag tag-blue">{art['source']}</span>
                    <span class="meta-date">{art['date']}</span>
                </div>
                <p class="item-summary">{art['summary']}</p>
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
    for feed in feeds[1:]:
        tabs_html += f'<button class="nav-btn" onclick="filterNews(\'{feed["id"]}\', this)">{feed["name"]}</button>'

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
        <title>折疼记 - AI 资讯站</title>
        <style>
            :root {{ --cb-blue: #0b63b6; --bg-gray: #f2f2f2; --white: #fff; --text: #333; }}
            * {{ box-sizing: border-box; outline: none; -webkit-tap-highlight-color: transparent; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; background: var(--bg-gray); margin: 0; color: var(--text); display: flex; flex-direction: column; min-height: 100vh; }}
            
            header {{ background: var(--cb-blue); position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            .header-inner {{ max-width: 800px; margin: 0 auto; height: 56px; display: flex; align-items: center; padding: 0 15px; }}
            .logo {{ color: #fff; font-size: 18px; font-weight: 800; margin-right: 20px; white-space: nowrap; }}
            .nav-scroll {{ flex: 1; overflow-x: auto; white-space: nowrap; display: flex; scrollbar-width: none; }}
            .nav-scroll::-webkit-scrollbar {{ display: none; }}
            .nav-btn {{ background: none; border: none; color: rgba(255,255,255,0.7); font-size: 14px; padding: 0 12px; height: 56px; transition: color 0.2s; }}
            .nav-btn.active {{ color: #fff; font-weight: bold; border-bottom: 3px solid #fff; }}
            
            .container {{ max-width: 800px; margin: 20px auto; padding: 0 15px; width: 100%; flex: 1; }}
            .news-item {{ background: var(--white); margin-bottom: 15px; padding: 15px; display: flex; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); cursor: pointer; transition: background 0.2s; }}
            .news-item:active {{ background: #f9f9f9; }}
            
            .item-img {{ width: 110px; height: 80px; flex-shrink: 0; margin-right: 15px; background: #eee; border-radius: 4px; overflow: hidden; }}
            .item-img img {{ width: 100%; height: 100%; object-fit: cover; }}
            
            .item-content {{ flex: 1; display: flex; flex-direction: column; justify-content: space-between; }}
            .item-title {{ margin: 0 0 6px 0; font-size: 16px; font-weight: bold; line-height: 1.4; color: #222; }}
            .item-meta {{ font-size: 12px; color: #999; display: flex; align-items: center; margin-bottom: 6px; }}
            .tag-blue {{ color: var(--cb-blue); margin-right: 10px; background: rgba(11,99,182,0.1); padding: 1px 4px; border-radius: 2px; }}
            .item-summary {{ font-size: 13px; color: #666; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}

            .main-footer {{ text-align: center; padding: 30px 0; color: #ccc; font-size: 12px; background: #fff; margin-top: 20px; }}
            .main-footer a {{ color: #ccc; text-decoration: none; }}

            /* 模态框 */
            .modal-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 2000; display: none; opacity: 0; transition: opacity 0.3s; }}
            .modal-overlay.open {{ display: block; opacity: 1; }}
            .modal-card {{ 
                position: fixed; bottom: 0; left: 0; width: 100%; height: 92vh; 
                background: #fff; border-radius: 16px 16px 0 0; 
                transform: translateY(100%); transition: transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
                z-index: 2001; display: flex; flex-direction: column;
                box-shadow: 0 -4px 20px rgba(0,0,0,0.15);
            }}
            .modal-overlay.open .modal-card {{ transform: translateY(0); }}
            @media (min-width: 769px) {{
                .modal-card {{ 
                    width: 700px; height: 85vh; left: 50%; top: 50%; bottom: auto;
                    transform: translate(-50%, -40%) scale(0.95); opacity: 0; border-radius: 12px; 
                }}
                .modal-overlay.open .modal-card {{ transform: translate(-50%, -50%) scale(1); opacity: 1; }}
            }}
            
            .modal-header {{ padding: 15px 20px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; background: #fff; border-radius: 16px 16px 0 0; }}
            .close-btn {{ font-size: 28px; color: #999; cursor: pointer; line-height: 1; }}
            
            .modal-body {{ flex: 1; overflow-y: auto; padding: 20px; -webkit-overflow-scrolling: touch; }}
            .article-title {{ font-size: 22px; font-weight: bold; margin-bottom: 10px; color: #222; }}
            .article-meta {{ color: #999; font-size: 13px; margin-bottom: 20px; }}
            .article-content {{ font-size: 16px; line-height: 1.8; color: #333; }}
            .read-more-btn {{ display: block; width: 100%; text-align: center; background: #f5f5f5; color: #666; padding: 12px; margin-top: 30px; border-radius: 8px; text-decoration: none; font-size: 14px; }}
            
            /* AI 区域 */
            .ai-section {{ border-top: 1px solid #eee; background: #fcfcfc; padding: 15px; display: flex; flex-direction: column; }}
            .ai-title {{ font-size: 14px; font-weight: bold; color: var(--cb-blue); margin-bottom: 10px; display: flex; align-items: center; }}
            .ai-title span {{ margin-left: 5px; color: #666; font-weight: normal; font-size: 12px; }}
            .ai-chat-box {{ height: 160px; overflow-y: auto; background: #fff; border: 1px solid #eee; border-radius: 8px; padding: 12px; margin-bottom: 10px; font-size: 14px; }}
            .ai-msg {{ margin-bottom: 10px; line-height: 1.5; word-wrap: break-word; }}
            .ai-msg.user {{ color: #fff; background: var(--cb-blue); padding: 8px 12px; border-radius: 12px 12px 0 12px; float: right; clear: both; max-width: 85%; }}
            .ai-msg.bot {{ color: #333; background: #f2f2f2; padding: 8px 12px; border-radius: 12px 12px 12px 0; float: left; clear: both; max-width: 90%; }}
            .ai-msg::after {{ content: ""; display: table; clear: both; }}

            .ai-input-area {{ display: flex; position: relative; }}
            .ai-input {{ flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 20px; font-size: 14px; padding-right: 70px; outline: none; transition: border 0.3s; }}
            .ai-input:focus {{ border-color: var(--cb-blue); }}
            .ai-send-btn {{ position: absolute; right: 4px; top: 4px; bottom: 4px; background: var(--cb-blue); color: #fff; border: none; padding: 0 15px; border-radius: 16px; cursor: pointer; font-size: 13px; }}
            .ai-send-btn:disabled {{ background: #ccc; }}
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
        </div>

        <footer class="main-footer">
            <p>更新于: {update_time} (北京时间)</p>
            <p><a href="https://beian.miit.gov.cn/" target="_blank">浙ICP备2025183710号-1</a></p>
            <p>© 折疼记</p>
        </footer>

        <div class="modal-overlay" id="articleModal" onclick="closeModal(event)">
            <div class="modal-card" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <span style="font-weight:bold; color:#0b63b6;">✨ 站内智能阅读</span>
                    <span class="close-btn" onclick="closeModal()">×</span>
                </div>
                <div class="modal-body">
                    <h1 class="article-title" id="mTitle"></h1>
                    <div class="article-meta" id="mMeta"></div>
                    <div class="article-content" id="mContent"></div>
                    <a href="" target="_blank" id="mLink" class="read-more-btn">🔗 跳转至源网站查看全文</a>
                </div>
                
                <div class="ai-section">
                    <div class="ai-title">🤖 AI 助手 <span>(已联网全库模式)</span></div>
                    <div class="ai-chat-box" id="aiChatBox">
                        <div class="ai-msg bot">你好！我是你的智能助手。<br>你可以针对这篇文章提问，也可以问我任何互联网知识（如代码、历史、百科）。</div>
                    </div>
                    <div class="ai-input-area">
                        <input type="text" class="ai-input" id="aiInput" placeholder="输入问题，搜索全网知识..." onkeypress="handleEnter(event)">
                        <button class="ai-send-btn" id="aiBtn" onclick="sendToAI()">发送</button>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let currentArticleContext = "";
            const API_KEY = "sk-bcc4ef2185e24dce86a028982862a81e"; 
            const API_URL = "https://api.deepseek.com/chat/completions";

            function filterNews(sourceId, btn) {{
                document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                document.querySelectorAll('.news-item').forEach(item => {{
                    item.style.display = (sourceId === 'all' || item.getAttribute('data-source') === sourceId) ? 'flex' : 'none';
                }});
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
                document.getElementById('mMeta').innerText = `${{source}} · ${{date}}`;
                document.getElementById('mContent').innerHTML = content.length > 5 ? content : '<p>暂无详细摘要，请让 AI 进行分析。</p>';
                document.getElementById('mLink').href = link;
                
                currentArticleContext = `【当前阅读的文章参考】\\n标题：${{title}}\\n内容摘要：${{content.substring(0, 2000)}}`;

                const chatBox = document.getElementById('aiChatBox');
                chatBox.innerHTML = '<div class="ai-msg bot">💡 你好！无论是关于这篇文章，还是关于世界上的任何问题，都可以问我。</div>';

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
                    const systemPrompt = "你是一个功能强大的 AI 搜索助手。用户正在阅读一篇新闻，并可能会根据新闻提问，或者问完全无关的问题。\\n\\n你的任务是：\\n1. 如果用户的问题与【当前阅读的文章参考】相关，请结合文章内容深入解答。\\n2. 如果用户的问题与文章无关，请**忽略参考文章**，直接调用你的互联网知识储备回答。\\n3. 回答风格要像搜索引擎一样客观、精准。";

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
                        const errData = await response.json();
                        throw new Error(errData.error?.message || "API 请求失败");
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
