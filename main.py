import feedparser
import datetime
import urllib.parse
from bs4 import BeautifulSoup
import ssl
import json
import random
import concurrent.futures # 引入多线程库，加速抓取
import time

# 1. SSL 证书修复
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# 2. 配置 RSS 源 (扩容至 20+ 个高质量源)
feeds = [
    # --- 综合科技 ---
    {"id": "ithome", "name": "IT之家", "url": "https://www.ithome.com/rss/"},
    {"id": "landian", "name": "蓝点网", "url": "https://www.landiannews.com/feed"},
    {"id": "cnbeta", "name": "cnBeta", "url": "https://www.cnbeta.com.tw/backend.php"},
    {"id": "solidot", "name": "Solidot", "url": "https://www.solidot.org/index.rss"},
    {"id": "ifanr", "name": "爱范儿", "url": "https://www.ifanr.com/feed"},
    
    # --- 深度与商业 ---
    {"id": "36kr", "name": "36Kr", "url": "https://36kr.com/feed"},
    {"id": "huxiu", "name": "虎嗅", "url": "https://www.huxiu.com/rss/0.xml"},
    {"id": "pingwest", "name": "品玩", "url": "https://www.pingwest.com/feed/all"},
    {"id": "jiemian", "name": "界面新闻", "url": "https://www.jiemian.com/rss/119.xml"},
    {"id": "leiphone", "name": "雷峰网", "url": "https://www.leiphone.com/feed"},
    
    # --- 软件与极客 ---
    {"id": "appinn", "name": "小众软件", "url": "https://www.appinn.com/feed/"},
    {"id": "sspai", "name": "少数派", "url": "https://sspai.com/feed"},
    {"id": "v2ex", "name": "V2EX", "url": "https://www.v2ex.com/index.xml"},
    {"id": "william", "name": "月光博客", "url": "https://www.williamlong.info/rss.xml"},
    {"id": "oschina", "name": "开源中国", "url": "https://www.oschina.net/news/rss"},

    # --- 游戏与生活 ---
    {"id": "gcores", "name": "机核网", "url": "https://www.gcores.com/rss"},
    {"id": "yystv", "name": "游研社", "url": "https://www.yystv.cn/rss/feed"},
    {"id": "vgtime", "name": "VGtime", "url": "https://www.vgtime.com/topic/index/load.xml"},
    {"id": "douban_movie", "name": "豆瓣电影", "url": "https://www.douban.com/feed/movie/review/best"},
    
    # --- 开发者 ---
    {"id": "ruanyifeng", "name": "阮一峰", "url": "http://www.ruanyifeng.com/blog/atom.xml"},
    {"id": "infoq", "name": "InfoQ", "url": "https://www.infoq.cn/feed"},
    {"id": "coolapk", "name": "酷安", "url": "https://www.coolapk.com/feed/feed"},
]

def get_image_from_html(html_content):
    """ 智能提取图片 """
    if not html_content: return None
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        imgs = soup.find_all('img')
        for img in imgs:
            candidates = ['data-original', 'data-src', 'data-url', 'src']
            for attr in candidates:
                url = img.get(attr)
                if url and url.startswith('http'):
                    if any(x in url for x in ['emoji', '.gif', 'avatar', 'stat', 'icon', 'button', 'share']):
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
    return f"https://wsrv.nl/?url={encoded_url}&w=240&h=180&fit=cover&output=webp&q=80"

def clean_text(html):
    """ 清洗 HTML 获取纯文本 """
    if not html: return ""
    return BeautifulSoup(html, 'html.parser').get_text().strip()

# 单个 Feed 抓取函数 (用于多线程)
def fetch_feed(feed):
    feed_articles = []
    try:
        # print(f"正在读取: {feed['name']}...") # 多线程下print会乱，注释掉
        f = feedparser.parse(feed["url"])
        
        if not f.entries: return []

        # 抓取量提升到 30 条/每源
        for entry in f.entries[:30]: 
            content_html = ""
            if hasattr(entry, 'content'): content_html = entry.content[0].value
            elif hasattr(entry, 'summary'): content_html = entry.summary
            elif hasattr(entry, 'description'): content_html = entry.description
            
            raw_img = get_image_from_html(content_html)
            final_img = process_image_url(raw_img)
            
            # 强过滤：无图不要
            if not final_img: continue

            soup_text = clean_text(content_html)
            summary_short = soup_text[:80] + "..." if soup_text else entry.title
            full_content_for_ai = soup_text[:3000]

            try:
                # 统一时间处理
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    dt = datetime.datetime(*entry.published_parsed[:6])
                    pub_time = (dt + datetime.timedelta(hours=8)).strftime("%m-%d %H:%M")
                    # 生成用于排序的时间戳
                    ts = datetime.datetime(*entry.published_parsed[:6]).timestamp()
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    dt = datetime.datetime(*entry.updated_parsed[:6])
                    pub_time = (dt + datetime.timedelta(hours=8)).strftime("%m-%d %H:%M")
                    ts = datetime.datetime(*entry.updated_parsed[:6]).timestamp()
                else:
                    pub_time = "最新"
                    ts = datetime.datetime.now().timestamp()
            except:
                pub_time = "最新"
                ts = datetime.datetime.now().timestamp()

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
    feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    print(f"开始并行抓取 {len(feeds)} 个源...")
    start_time = time.time()

    # 使用多线程并行抓取，最大 10 个线程
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 提交所有任务
        future_to_feed = {executor.submit(fetch_feed, feed): feed for feed in feeds}
        
        for future in concurrent.futures.as_completed(future_to_feed):
            feed = future_to_feed[future]
            try:
                data = future.result()
                articles.extend(data)
                print(f"  - {feed['name']} 抓取完成，获 {len(data)} 条")
            except Exception as exc:
                print(f"  - {feed['name']} 生成异常: {exc}")

    print(f"抓取耗时: {time.time() - start_time:.2f} 秒")
    
    # 全局按时间倒序
    articles.sort(key=lambda x: x["timestamp"], reverse=True)
    
    print(f"去重前文章数: {len(articles)}")
    # 简单去重 (按标题)
    unique_articles = []
    seen_titles = set()
    for art in articles:
        if art['title'] not in seen_titles:
            unique_articles.append(art)
            seen_titles.add(art['title'])
    articles = unique_articles
    print(f"最终有效文章数: {len(articles)}")

    news_list_html = ""
    for index, art in enumerate(articles):
        safe_content = json.dumps(art['full_content']).replace('"', '&quot;')
        
        img_html = f'''
        <div class="item-img">
            <img src="{art["image"]}" loading="lazy" alt="封面" 
                 onerror="this.closest('.news-item').remove()">
        </div>
        '''

        # 注意：这里增加了一个 class 'news-item-hidden' 用于前端分页
        # 默认前 20 条显示，后面的加上 hidden class
        hidden_class = "" if index < 20 else "news-item-hidden"
        display_style = "flex" if index < 20 else "none"

        news_list_html += f"""
        <article class="news-item {hidden_class}" style="display:{display_style};" data-source="{art['source_id']}" onclick="openModal({index})">
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
    
    # 生成 Tabs (包含全部)
    tabs_html = '<button class="nav-btn active" onclick="filterNews(\'all\', this)">全部</button>'
    # 提取所有不重复的 source_id 和 name
    seen_sources = set()
    for feed in feeds:
        if feed['id'] not in seen_sources:
            tabs_html += f'<button class="nav-btn" onclick="filterNews(\'{feed["id"]}\', this)">{feed["name"]}</button>'
            seen_sources.add(feed['id'])

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
            :root {{ --cb-blue: #0b63b6; --bg-gray: #f2f2f2; --white: #fff; --text: #333; }}
            * {{ box-sizing: border-box; outline: none; -webkit-tap-highlight-color: transparent; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; background: var(--bg-gray); margin: 0; color: var(--text); display: flex; flex-direction: column; min-height: 100vh; }}
            
            header {{ background: var(--cb-blue); position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            .header-inner {{ max-width: 800px; margin: 0 auto; height: 56px; display: flex; align-items: center; padding: 0 15px; }}
            .logo {{ color: #fff; font-size: 18px; font-weight: 800; margin-right: 20px; white-space: nowrap; }}
            .nav-scroll {{ flex: 1; overflow-x: auto; white-space: nowrap; display: flex; scrollbar-width: none; }}
            .nav-btn {{ background: none; border: none; color: rgba(255,255,255,0.7); font-size: 14px; padding: 0 12px; height: 56px; transition: color 0.2s; cursor: pointer; }}
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

            /* 加载更多提示 */
            .load-more-status {{ text-align: center; color: #999; font-size: 13px; padding: 20px; }}

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
            
            .modal-header {{ padding: 15px 20px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; background: #fff; border-radius: 16px 16px 0 0; flex-shrink: 0; }}
            .close-btn {{ font-size: 28px; color: #999; cursor: pointer; line-height: 1; }}
            .modal-scroll-area {{ flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; padding: 0; }}
            .modal-body {{ padding: 20px; }}

            .article-title {{ font-size: 22px; font-weight: bold; margin-bottom: 10px; color: #222; }}
            .article-meta {{ color: #999; font-size: 13px; margin-bottom: 20px; }}
            .article-content {{ font-size: 16px; line-height: 1.8; color: #333; }}
            .read-more-btn {{ display: block; width: 100%; text-align: center; background: #f5f5f5; color: #666; padding: 12px; margin-top: 30px; border-radius: 8px; text-decoration: none; font-size: 14px; }}
            
            .ai-section {{ border-top: 10px solid #f2f2f2; background: #fff; padding: 20px; }}
            .ai-title {{ font-size: 14px; font-weight: bold; color: var(--cb-blue); margin-bottom: 10px; display: flex; align-items: center; }}
            .ai-title span {{ margin-left: 5px; color: #666; font-weight: normal; font-size: 12px; }}
            .ai-chat-box {{ height: 160px; overflow-y: auto; background: #f9f9f9; border: 1px solid #eee; border-radius: 8px; padding: 12px; margin-bottom: 10px; font-size: 14px; }}
            .ai-msg {{ margin-bottom: 10px; line-height: 1.5; word-wrap: break-word; }}
            .ai-msg.user {{ color: #fff; background: var(--cb-blue); padding: 8px 12px; border-radius: 12px 12px 0 12px; float: right; clear: both; max-width: 85%; }}
            .ai-msg.bot {{ color: #333; background: #fff; border: 1px solid #eee; padding: 8px 12px; border-radius: 12px 12px 12px 0; float: left; clear: both; max-width: 90%; }}
            .ai-msg::after {{ content: ""; display: table; clear: both; }}
            .ai-input-area {{ display: flex; position: relative; }}
            .ai-input {{ flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 20px; font-size: 14px; padding-right: 70px; outline: none; transition: border 0.3s; }}
            .ai-input:focus {{ border-color: var(--cb-blue); }}
            .ai-send-btn {{ position: absolute; right: 4px; top: 4px; bottom: 4px; background: var(--cb-blue); color: #fff; border: none; padding: 0 15px; border-radius: 16px; cursor: pointer; font-size: 13px; }}
            .ai-send-btn:disabled {{ background: #ccc; }}

            .comment-section {{ border-top: 10px solid #f2f2f2; background: #fff; padding: 20px; }}
            .comment-title {{ font-size: 16px; font-weight: bold; color: #333; margin-bottom: 15px; border-left: 4px solid var(--cb-blue); padding-left: 10px; }}
            #vcomments .vwrap {{ border: 1px solid #eee; border-radius: 8px; }}
            #vcomments .vbtn {{ color: #fff; background: var(--cb-blue); border-color: var(--cb-blue); }}
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
            <p>文章总数: {len(articles)} | 更新于: {update_time} (北京时间)</p>
            <p><a href="https://beian.miit.gov.cn/" target="_blank">浙ICP备2025183710号-1</a></p>
            <p>© 折疼记</p>
        </footer>

        <div class="modal-overlay" id="articleModal" onclick="closeModal(event)">
            <div class="modal-card" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <span style="font-weight:bold; color:#0b63b6;">✨ 资讯详情</span>
                    <span class="close-btn" onclick="closeModal()">×</span>
                </div>
                <div class="modal-scroll-area">
                    <div class="modal-body">
                        <h1 class="article-title" id="mTitle"></h1>
                        <div class="article-meta" id="mMeta"></div>
                        <div class="article-content" id="mContent"></div>
                        <a href="" target="_blank" id="mLink" class="read-more-btn">🔗 跳转至源网站查看全文</a>
                    </div>
                    <div class="ai-section">
                        <div class="ai-title">🤖 AI 助手 <span>(已联网)</span></div>
                        <div class="ai-chat-box" id="aiChatBox"></div>
                        <div class="ai-input-area">
                            <input type="text" class="ai-input" id="aiInput" placeholder="输入问题..." onkeypress="handleEnter(event)">
                            <button class="ai-send-btn" id="aiBtn" onclick="sendToAI()">发送</button>
                        </div>
                    </div>
                    <div class="comment-section">
                        <div class="comment-title">💬 网友留言</div>
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
            const PAGE_SIZE = 20; // 每次加载20条
            let visibleCount = 20; // 当前显示数量

            // 监听滚动
            window.addEventListener('scroll', () => {{
                // 如果滚动到距离底部 300px 以内
                if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 300) {{
                    loadMore();
                }}
            }});

            function loadMore() {{
                const allItems = document.querySelectorAll('.news-item');
                let newlyShown = 0;
                
                for (let i = 0; i < allItems.length; i++) {{
                    const item = allItems[i];
                    // 只处理当前筛选下的、且当前是隐藏状态的元素
                    if (item.classList.contains('news-item-hidden')) {{
                        // 如果在当前筛选范围内
                        if (currentFilter === 'all' || item.getAttribute('data-source') === currentFilter) {{
                            item.style.display = 'flex';
                            item.classList.remove('news-item-hidden');
                            newlyShown++;
                            if (newlyShown >= PAGE_SIZE) break; // 每次只多放出来 PAGE_SIZE 条
                        }}
                    }}
                }}

                const statusDiv = document.getElementById('loadStatus');
                if (newlyShown === 0) {{
                    statusDiv.innerText = "--- 我是有底线的 (内容已全部加载) ---";
                }} else {{
                    statusDiv.innerText = "下拉加载更多...";
                }}
            }}

            function filterNews(sourceId, btn) {{
                currentFilter = sourceId;
                document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                // 重置可见性
                const items = document.querySelectorAll('.news-item');
                let shownCount = 0;
                
                items.forEach(item => {{
                    const match = (sourceId === 'all' || item.getAttribute('data-source') === sourceId);
                    if (match) {{
                        // 重新应用分页逻辑：前20条显示，后面的隐藏
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
                        // 不符合条件的也标记为 hidden，以防逻辑混乱
                        item.classList.add('news-item-hidden');
                    }}
                }});
                
                // 重置加载提示
                document.getElementById('loadStatus').innerText = "下拉加载更多...";
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
                
                currentArticleContext = `【当前阅读文章】\\n标题：${{title}}\\n内容摘要：${{content.substring(0, 2000)}}`;

                const chatBox = document.getElementById('aiChatBox');
                chatBox.innerHTML = '<div class="ai-msg bot">💡 你好！我是 AI 助手，有什么可以帮你的？</div>';

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
