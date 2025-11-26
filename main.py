import feedparser
import datetime
import urllib.parse
from bs4 import BeautifulSoup
import ssl
import random

# 1. SSL 证书修复
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# 2. 配置 RSS 源
feeds = [
    {"id": "all", "name": "全部", "url": ""},
    {"id": "ithome", "name": "IT之家", "url": "https://www.ithome.com/rss/"},
    {"id": "36kr", "name": "36Kr", "url": "https://36kr.com/feed"},
    {"id": "solidot", "name": "Solidot", "url": "https://www.solidot.org/index.rss"},
    {"id": "sspai", "name": "少数派", "url": "https://sspai.com/feed"},
    {"id": "ifanr", "name": "爱范儿", "url": "https://www.ifanr.com/feed"},
    {"id": "huxiu", "name": "虎嗅", "url": "https://www.huxiu.com/rss/0.xml"},
    {"id": "coolapk", "name": "酷安", "url": "https://www.coolapk.com/feed/feed"},
]

def get_image_from_html(html_content):
    """ 智能提取图片：优先查找懒加载属性 """
    if not html_content: return None
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        img = soup.find('img')
        if img:
            candidates = ['data-original', 'data-src', 'data-url', 'src']
            for attr in candidates:
                url = img.get(attr)
                if url and url.startswith('http'):
                    if 'emoji' in url or '.gif' in url: continue
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

def generate_html():
    articles = []
    feedparser.USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"

    print("开始抓取...")
    
    for feed in feeds[1:]:
        try:
            print(f"正在读取: {feed['name']}...")
            f = feedparser.parse(feed["url"])
            for entry in f.entries[:12]: 
                content_html = ""
                if hasattr(entry, 'content'): content_html = entry.content[0].value
                elif hasattr(entry, 'summary'): content_html = entry.summary
                elif hasattr(entry, 'description'): content_html = entry.description
                
                raw_img = get_image_from_html(content_html)
                final_img = process_image_url(raw_img)
                
                soup_text = BeautifulSoup(content_html, 'html.parser').get_text()
                summary_text = soup_text.strip()[:90] + "..." if soup_text else entry.title

                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        dt = datetime.datetime(*entry.published_parsed[:6])
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
                    "summary": summary_text,
                    "timestamp": entry.get("published_parsed", datetime.datetime.now().timetuple())
                })
        except Exception as e:
            print(f"Error: {e}")
            continue

    articles.sort(key=lambda x: x["timestamp"] if x["timestamp"] else tuple(), reverse=True)

    news_list_html = ""
    for art in articles:
        img_html = ""
        if art["image"]:
            img_html = f'''
            <div class="item-img">
                <img src="{art["image"]}" loading="lazy" alt="封面" onerror="this.onerror=null;this.parentNode.classList.add('no-img-fallback');this.style.display='none';">
                <div class="fallback-text">{art["source"][0]}</div>
            </div>
            '''
        else:
            img_html = f'<div class="item-img no-img-fallback"><div class="fallback-text">{art["source"][0]}</div></div>'

        news_list_html += f"""
        <article class="news-item" data-source="{art['source_id']}">
            {img_html}
            <div class="item-content">
                <h2 class="item-title"><a href="{art['link']}" target="_blank">{art['title']}</a></h2>
                <div class="item-meta">
                    <span class="meta-tag tag-blue">{art['source']}</span>
                    <span class="meta-date">{art['date']}</span>
                </div>
                <p class="item-summary">{art['summary']}</p>
            </div>
        </article>
        """
    
    headline_articles = articles[:10]
    sidebar_html = ""
    for art in headline_articles:
        sidebar_html += f'<li><a href="{art["link"]}" target="_blank">{art["title"]}</a></li>'

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
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        <meta name="referrer" content="no-referrer">
        <meta name="description" content="折疼记 - IT资讯聚合">
        <title>折疼记 - 科技资讯</title>
        <style>
            :root {{
                --cb-blue: #0b63b6;
                --cb-dark: #1f2937;
                --cb-gray: #f2f2f2;
                --text-main: #333;
                --text-sub: #666;
                --white: #fff;
            }}
            * {{ box-sizing: border-box; }}
            body {{ font-family: "Microsoft YaHei", -apple-system, BlinkMacSystemFont, sans-serif; background: var(--cb-gray); margin: 0; color: var(--text-main); display: flex; flex-direction: column; min-height: 100vh; }}
            
            header {{ background: var(--cb-blue); box-shadow: 0 2px 4px rgba(0,0,0,0.1); position: sticky; top: 0; z-index: 1000; }}
            .header-inner {{ max-width: 1100px; margin: 0 auto; padding: 0 15px; height: 60px; display: flex; align-items: center; justify-content: space-between; }}
            .logo {{ color: #fff; font-size: 20px; font-weight: bold; text-decoration: none; margin-right: 30px; }}
            .nav-scroll {{ flex: 1; overflow-x: auto; white-space: nowrap; scrollbar-width: none; -ms-overflow-style: none; }}
            .nav-scroll::-webkit-scrollbar {{ display: none; }}
            .nav-btn {{ background: none; border: none; color: rgba(255,255,255,0.7); font-size: 15px; padding: 0 15px; cursor: pointer; height: 60px; line-height: 60px; transition: color 0.2s; }}
            .nav-btn.active {{ color: #fff; font-weight: bold; border-bottom: 3px solid #fff; }}
            
            .container {{ max-width: 1100px; margin: 20px auto; padding: 0 15px; display: grid; grid-template-columns: 1fr 300px; gap: 20px; align-items: start; flex: 1; width: 100%; }}

            .news-list {{ background: transparent; }}
            .news-item {{ background: var(--white); margin-bottom: 15px; padding: 15px; display: flex; border: 1px solid #e0e0e0; border-radius: 4px; transition: box-shadow 0.2s; }}
            .news-item:hover {{ box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-color: #ccc; }}
            
            .item-img {{ width: 160px; height: 120px; flex-shrink: 0; margin-right: 20px; background: #f0f2f5; overflow: hidden; border-radius: 2px; position: relative; }}
            .item-img img {{ width: 100%; height: 100%; object-fit: cover; transition: transform 0.3s; display: block; }}
            .news-item:hover .item-img img {{ transform: scale(1.05); }}
            .fallback-text {{ display: none; }}
            .no-img-fallback {{ display: flex; align-items: center; justify-content: center; background: #eef4fa; }}
            .no-img-fallback .fallback-text {{ display: block; color: var(--cb-blue); font-size: 2rem; font-weight: bold; }}

            .item-content {{ flex: 1; display: flex; flex-direction: column; justify-content: space-between; }}
            .item-title {{ margin: 0 0 8px 0; font-size: 18px; line-height: 1.4; }}
            .item-title a {{ color: var(--text-main); text-decoration: none; }}
            .item-title a:hover {{ color: var(--cb-blue); text-decoration: underline; }}
            .item-summary {{ font-size: 13px; color: #888; margin: 0 0 10px 0; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; height: 38px; }}
            .item-meta {{ font-size: 12px; color: #999; display: flex; align-items: center; }}
            .meta-tag {{ margin-right: 10px; padding: 2px 6px; border-radius: 2px; }}
            .tag-blue {{ background: #e6f0fa; color: var(--cb-blue); }}
            
            aside {{ background: var(--white); padding: 20px; border: 1px solid #e0e0e0; border-radius: 4px; position: sticky; top: 80px; }}
            .sidebar-title {{ font-size: 16px; border-left: 4px solid var(--cb-blue); padding-left: 10px; margin: 0 0 15px 0; color: #333; font-weight: bold; }}
            .sidebar-list {{ list-style: none; padding: 0; margin: 0; counter-reset: sidebar-counter; }}
            .sidebar-list li {{ margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px dashed #eee; position: relative; padding-left: 28px; }}
            .sidebar-list li:last-child {{ border: none; }}
            .sidebar-list li::before {{ counter-increment: sidebar-counter; content: counter(sidebar-counter); position: absolute; left: 0; top: 2px; width: 20px; height: 20px; line-height: 20px; background: #ddd; color: #fff; text-align: center; border-radius: 4px; font-size: 12px; font-weight: bold; }}
            .sidebar-list li:nth-child(-n+3)::before {{ background: var(--cb-blue); }}
            .sidebar-list a {{ text-decoration: none; color: #555; font-size: 14px; line-height: 1.4; display: block; }}
            .sidebar-list a:hover {{ color: var(--cb-blue); }}

            /* 底部样式 (Footer) */
            .main-footer {{ background: #fff; border-top: 1px solid #e0e0e0; padding: 30px 0; margin-top: 40px; text-align: center; color: #999; font-size: 13px; width: 100%; }}
            .main-footer p {{ margin: 8px 0; }}
            .main-footer a {{ color: #999; text-decoration: none; transition: color 0.2s; }}
            .main-footer a:hover {{ color: var(--cb-blue); }}

            @media (max-width: 768px) {{
                .container {{ grid-template-columns: 1fr; }}
                aside {{ display: none; }}
                .item-img {{ width: 100px; height: 75px; margin-right: 15px; }}
                .item-title {{ font-size: 16px; }}
                .item-summary {{ display: none; }}
                .header-inner {{ padding: 0 10px; }}
                .main-footer {{ padding: 20px 0; margin-top: 20px; }}
            }}
        </style>
    </head>
    <body>
        <header>
            <div class="header-inner">
                <a href="#" class="logo">折疼记</a>
                <div class="nav-scroll" id="navBar">
                    {tabs_html}
                </div>
            </div>
        </header>

        <div class="container">
            <main class="news-list" id="newsContainer">
                {news_list_html}
            </main>

            <aside>
                <h3 class="sidebar-title">今日头条</h3>
                <ul class="sidebar-list">
                    {sidebar_html}
                </ul>
            </aside>
        </div>

        <footer class="main-footer">
            <p>更新于: {update_time} (北京时间)</p>
            <p><a href="https://beian.miit.gov.cn/" target="_blank">浙ICP备2025183710号-1</a></p>
            <p>&copy; 折疼记</p>
        </footer>

        <script>
            function filterNews(sourceId, btn) {{
                document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const items = document.querySelectorAll('.news-item');
                items.forEach(item => {{
                    if (sourceId === 'all' || item.getAttribute('data-source') === sourceId) {{
                        item.style.display = 'flex';
                    }} else {{
                        item.style.display = 'none';
                    }}
                }});
                window.scrollTo({{ top: 0, behavior: 'smooth' }});
            }}
        </script>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(template)

if __name__ == "__main__":
    generate_html()
