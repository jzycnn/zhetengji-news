import feedparser
import datetime
import urllib.parse
from bs4 import BeautifulSoup
import ssl
import json
import random
import concurrent.futures
import time
import re

# 1. SSL 证书修复
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# 2. RSS 源配置 (已精选高稳定源)
feeds = [
    # --- 核心科技 ---
    {"id": "ithome", "name": "IT之家", "url": "https://www.ithome.com/rss/", "color": "#d32f2f"},
    {"id": "jiemian", "name": "界面", "url": "https://www.jiemian.com/rss/119.xml", "color": "#f5a623"},
    {"id": "landian", "name": "蓝点网", "url": "https://www.landiannews.com/feed", "color": "#0078d7"},
    {"id": "pingwest", "name": "品玩", "url": "https://www.pingwest.com/feed/all", "color": "#000000"},
    {"id": "leiphone", "name": "雷峰网", "url": "https://www.leiphone.com/feed", "color": "#cf2928"},
    
    # --- 极客/软件 ---
    {"id": "sspai", "name": "少数派", "url": "https://sspai.com/feed", "color": "#da282a"},
    {"id": "appinn", "name": "小众软件", "url": "https://www.appinn.com/feed/", "color": "#33691e"},
    {"id": "solidot", "name": "Solidot", "url": "https://www.solidot.org/index.rss", "color": "#546e7a"},
    {"id": "v2ex", "name": "V2EX", "url": "https://www.v2ex.com/index.xml", "color": "#333333"},
    
    # --- 游戏/影音 ---
    {"id": "gcores", "name": "机核", "url": "https://www.gcores.com/rss", "color": "#bf2228"},
    {"id": "yystv", "name": "游研社", "url": "https://www.yystv.cn/rss/feed", "color": "#ffc107"},
    {"id": "douban", "name": "豆瓣", "url": "https://www.douban.com/feed/movie/review/best", "color": "#007722"},
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
                    # 过滤无效图片
                    if any(x in url for x in ['emoji', '.gif', 'avatar', 'stat', 'icon', 'button', 'share', 'pixel']):
                        continue
                    return url
    except: return None
    return None

def process_image_url(original_url):
    """ 图片代理 """
    if not original_url: return None
    original_url = original_url.strip()
    if not original_url.startswith('http'): return None
    encoded_url = urllib.parse.quote(original_url)
    return f"https://wsrv.nl/?url={encoded_url}&w=280&h=200&fit=cover&output=webp&q=80"

def clean_text(html):
    """ 清洗文本 """
    if not html: return ""
    return BeautifulSoup(html, 'html.parser').get_text().strip()

def fetch_feed(feed):
    feed_articles = []
    try:
        # 增加超时设置
        f = feedparser.parse(feed["url"])
        
        # 即使没有 entries 也不报错，返回空列表
        if not f.entries: return []

        for entry in f.entries[:30]: 
            content_html = ""
            if hasattr(entry, 'content'): content_html = entry.content[0].value
            elif hasattr(entry, 'summary'): content_html = entry.summary
            elif hasattr(entry, 'description'): content_html = entry.description
            
            # 1. 尝试获取图片
            raw_img = get_image_from_html(content_html)
            final_img = process_image_url(raw_img)
            
            # 2. 获取文本
            soup_text = clean_text(content_html)
            summary_short = soup_text[:85] + "..." if soup_text else entry.title
            full_content_for_ai = soup_text[:3500]

            # 3. 时间处理
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
                "source_color": feed.get("color", "#333"),
                "image": final_img, # 可能是 None
                "summary": summary_short,
                "full_content": full_content_for_ai,
                "timestamp": ts
            })
    except Exception as e:
        print(f"Error parsing {feed['name']}: {e}")
        return []
    
    return feed_articles

def generate_html():
    articles = []
    
    # 模拟浏览器 UA
    feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    print(f"开始抓取 {len(feeds)} 个源...")
    
    # 使用线程池并发抓取
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_feed = {executor.submit(fetch_feed, feed): feed for feed in feeds}
        for future in concurrent.futures.as_completed(future_to_feed):
            try:
                data = future.result()
                articles.extend(data)
            except Exception as e:
                print(f"Thread Error: {e}")

    # 排序与去重
    articles.sort(key=lambda x: x["timestamp"], reverse=True)
    unique_articles = []
    seen = set()
    for art in articles:
        if art['title'] not in seen:
            unique_articles.append(art)
            seen.add(art['title'])
    articles = unique_articles

    # 至少保证有数据，否则页面会崩
    if not articles:
        print("警告：没有抓取到任何数据！")

    news_list_html = ""
    for index, art in enumerate(articles):
        hidden_class = "" if index < 20 else "news-item-hidden"
        display_style = "flex" if index < 20 else "none"

        # --- 核心修复：无图时的回退显示 ---
        if art["image"]:
            # 有图：正常显示，onerror 时切换到 fallback 样式
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
            # 无图：直接显示 fallback 样式（渐变色块 + 首字）
            img_html = f'''
            <div class="item-img" data-type="fallback">
                <div class="img-fallback" style="background-color: {art['source_color']}15; color: {art['source_color']};">
                    {art['source'][0]}
                </div>
            </div>
            '''

        # JSON 安全转义
        safe_content = json.dumps(art['full_content']).replace('"', '&quot;')

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
                --bg-body: #f7f9fc; 
                --bg-card: #ffffff; 
                --text-main: #2c3e50; 
                --text-sub: #7f8c8d;
                --radius: 12px;
            }}
            
            * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                background-color: var(--bg-body); margin: 0; color: var(--text-main); 
                display: flex; flex-direction: column; min-height: 100vh;
            }}
            
            /* 导航栏 */
            header {{ 
                background: rgba(255,255,255,0.9); backdrop-filter: blur(10px);
                position: sticky; top: 0; z-index: 100; border-bottom: 1px solid rgba(0,0,0,0.05);
            }}
            .header-inner {{ max-width: 800px; margin: 0 auto; height: 56px; display: flex; align-items: center; padding: 0 16px; }}
            .logo {{ color: var(--primary); font-size: 19px; font-weight: 800; margin-right: 20px; }}
            .nav-scroll {{ flex: 1; overflow-x: auto; white-space: nowrap; scrollbar-width: none; display: flex; }}
            .nav-scroll::-webkit-scrollbar {{ display: none; }}
            .nav-btn {{ 
                background: none; border: none; color: var(--text-sub); 
                font-size: 14px; padding: 0 12px; height: 56px; cursor: pointer; font-weight: 500;
            }}
            .nav-btn.active {{ color: var(--primary); font-weight: 700; border-bottom: 2px solid var(--primary); }}
            
            /* 列表 */
            .container {{ max-width: 800px; margin: 20px auto; padding: 0 16px; width: 100%; flex: 1; }}
            
            .news-item {{ 
                background: var(--bg-card); margin-bottom: 16px; padding: 16px; 
                display: flex; border-radius: var(--radius); 
                box-shadow: 0 2px 8px rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.02);
                cursor: pointer; transition: transform 0.2s;
            }}
            .news-item:active {{ transform: scale(0.98); }}
            
            /* 图片与回退样式 */
            .item-img {{ 
                width: 120px; height: 90px; flex-shrink: 0; margin-right: 16px; 
                border-radius: 8px; overflow: hidden; position: relative; background: #f0f0f0;
            }}
            .item-img img {{ width: 100%; height: 100%; object-fit: cover; }}
            
            /* 默认隐藏 fallback */
            .img-fallback {{ 
                position: absolute; top: 0; left: 0; width: 100%; height: 100%; 
                display: none; align-items: center; justify-content: center; 
                font-size: 32px; font-weight: bold;
            }}
            /* 当 data-type="fallback" 时显示 fallback */
            .item-img[data-type="fallback"] .img-fallback {{ display: flex; }}
            .item-img[data-type="fallback"] img {{ display: none; }}

            .item-content {{ flex: 1; display: flex; flex-direction: column; justify-content: space-between; }}
            .item-title {{ 
                margin: 0 0 6px 0; font-size: 17px; font-weight: 700; line-height: 1.4; color: #222;
                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
            }}
            .item-meta {{ font-size: 12px; color: #999; display: flex; align-items: center; }}
            .source-badge {{ padding: 2px 6px; border-radius: 4px; font-weight: 600; margin-right: 10px; }}
            .item-summary {{ 
                font-size: 13px; color: #666; line-height: 1.5; margin: 6px 0 0 0;
                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
            }}

            .load-more-status {{ text-align: center; color: #aaa; font-size: 13px; padding: 20px; }}

            .main-footer {{ text-align: center; padding: 30px 0; color: #ccc; font-size: 12px; background: #fff; margin-top: 30px; border-top: 1px solid #eee; }}
            .main-footer a {{ color: #ccc; text-decoration: none; }}

            /* 移动端 */
            @media (max-width: 600px) {{
                .item-img {{ width: 100px; height: 75px; margin-right: 12px; }}
                .item-title {{ font-size: 16px; }}
                .item-summary {{ display: none; }}
            }}

            /* 模态框 */
            .modal-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 2000; display: none; opacity: 0; transition: opacity 0.3s; }}
            .modal-overlay.open {{ display: block; opacity: 1; }}
            .modal-card {{ 
                position: fixed; bottom: 0; left: 0; width: 100%; height: 92vh; 
                background: #fff; border-radius: 20px 20px 0 0; 
                transform: translateY(100%); transition: transform 0.3s;
                z-index: 2001; display: flex; flex-direction: column;
            }}
            .modal-overlay.open .modal-card {{ transform: translateY(0); }}
            @media (min-width: 769px) {{
                .modal-card {{ 
                    width: 700px; height: 90vh; left: 50%; top: 50%; bottom: auto;
                    transform: translate(-50%, -45%) scale(0.95); opacity: 0; border-radius: 16px; 
                }}
                .modal-overlay.open .modal-card {{ transform: translate(-50%, -50%) scale(1); opacity: 1; }}
            }}
            
            .modal-header {{ 
                padding: 0 20px; height: 56px; border-bottom: 1px solid #eee; 
                display: flex; justify-content: space-between; align-items: center; 
                background: #fff; border-radius: 20px 20px 0 0; flex-shrink: 0;
            }}
            .close-btn {{ font-size: 26px; color: #999; cursor: pointer; }}
            
            .modal-scroll-area {{ flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; }}
            .modal-body {{ padding: 24px 24px 0 24px; }}

            .article-title {{ font-size: 22px; font-weight: 800; margin-bottom: 10px; color: #222; }}
            .article-meta {{ color: #999; font-size: 13px; margin-bottom: 20px; }}
            .article-content {{ font-size: 16px; line-height: 1.8; color: #333; }}
            .read-more-btn {{ 
                display: block; width: 100%; text-align: center; 
                background: #f0f7ff; color: var(--primary); 
                padding: 12px; margin-top: 30px; border-radius: 10px; 
                text-decoration: none; font-size: 14px; font-weight: 600;
            }}
            
            .ai-section, .comment-section {{ padding: 24px; border-top: 1px solid #f5f5f5; background: #fafafa; }}
            .section-title {{ font-size: 15px; font-weight: 700; color: #333; margin-bottom: 15px; display: flex; align-items: center;
