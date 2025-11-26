import feedparser
import datetime
import re
from bs4 import BeautifulSoup
import ssl

# 1. 解决旧版环境下 SSL 证书验证报错的问题
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# 2. 配置 RSS 新闻源
feeds = [
    {"name": "IT之家", "url": "https://www.ithome.com/rss/"},
    {"name": "36Kr", "url": "https://36kr.com/feed"},
    {"name": "Solidot", "url": "https://www.solidot.org/index.rss"},
    {"name": "少数派", "url": "https://sspai.com/feed"},
    {"name": "爱范儿", "url": "https://www.ifanr.com/feed"},
    {"name": "月光博客", "url": "https://www.williamlong.info/rss.xml"},
]

def get_image_from_html(html_content):
    """从 HTML 文本中提取第一张图片的 src"""
    if not html_content:
        return None
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        img = soup.find('img')
        if img and img.get('src'):
            return img.get('src')
    except:
        return None
    return None

def generate_html():
    articles = []
    
    # 伪装浏览器 User-Agent，防止被拦截
    feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

    print("开始抓取新闻...")
    for feed in feeds:
        try:
            print(f"正在读取: {feed['name']}...")
            # 增加 bozo_exception 容错处理
            f = feedparser.parse(feed["url"])
            
            for entry in f.entries[:8]: # 每个源只取最新的 8 条
                # --- 图片提取逻辑 ---
                content_html = ""
                if hasattr(entry, 'content'):
                    content_html = entry.content[0].value
                elif hasattr(entry, 'summary'):
                    content_html = entry.summary
                elif hasattr(entry, 'description'):
                    content_html = entry.description

                img_url = get_image_from_html(content_html)
                
                # --- 时间处理逻辑 ---
                pub_time = "刚刚"
                if hasattr(entry, 'published'):
                    pub_time = entry.published[:16] 
                elif hasattr(entry, 'updated'):
                    pub_time = entry.updated[:16]

                # --- 存入数据 ---
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "date": pub_time,
                    "source": feed["name"],
                    "image": img_url,
                    # 获取时间戳用于排序，若无则使用当前时间
                    "timestamp": entry.get("published_parsed", datetime.datetime.now().timetuple())
                })
        except Exception as e:
            print(f"Error parsing {feed['name']}: {e}")
            continue

    # 按时间倒序排序（最新的在前）
    articles.sort(key=lambda x: x["timestamp"] if x["timestamp"] else tuple(), reverse=True)

    # 生成卡片 HTML
    cards_html = ""
    for article in articles:
        img_html = ""
        if article["image"]:
            # 有图模式
            img_html = f'<div class="card-img" style="background-image: url(\'{article["image"]}\');"></div>'
        else:
            # 无图模式
            img_html = f'<div class="card-img no-img"><span>{article["source"]}</span></div>'

        cards_html += f"""
        <article class="card">
            <a href="{article["link"]}" target="_blank" class="card-link">
                {img_html}
                <div class="card-content">
                    <div class="card-meta">
                        <span class="source-tag">{article["source"]}</span>
                        <span class="time-tag">{article["date"]}</span>
                    </div>
                    <h3 class="card-title">{article["title"]}</h3>
                </div>
            </a>
        </article>
        """

    update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # --- 完整的 HTML 模板 ---
    template = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <!-- 这里的 no-referrer 是为了让部分防盗链图片能显示 -->
        <meta name="referrer" content="no-referrer">
        <meta name="description" content="折疼记 - 每日自动更新的 IT 科技新闻聚合站">
        <title>折疼记 - 科技早报</title>
        <style>
            :root {{
                --primary: #d32f2f; /* 主色调：深红 */
                --bg: #f5f7fa;
                --card-bg: #ffffff;
                --text: #2c3e50;
            }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: var(--bg); margin: 0; color: var(--text); }}
            
            /* 顶部导航 */
            header {{ background: var(--primary); color: #fff; padding: 1rem 0; box-shadow: 0 4px 6px rgba(0,0,0,0.1); position: sticky; top: 0; z-index: 999; }}
            .header-content {{ max-width: 1200px; margin: 0 auto; padding: 0 20px; display: flex; justify-content: space-between; align-items: center; }}
            .brand {{ font-size: 1.5rem; font-weight: bold; letter-spacing: 1px; }}
            .time {{ font-size: 0.85rem; opacity: 0.8; }}

            /* 主体网格 */
            main {{ max-width: 1200px; margin: 2rem auto; padding: 0 15px; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 20px; }}

            /* 卡片样式 */
            .card {{ background: var(--card-bg); border-radius: 10px; overflow: hidden; transition: all 0.3s ease; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #eaeaea; }}
            .card:hover {{ transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.1); }}
            .card-link {{ text-decoration: none; color: inherit; display: block; height: 100%; }}
            
            /* 图片部分 */
            .card-img {{ height: 150px; background-size: cover; background-position: center; }}
            .no-img {{ display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #f6f7f9 0%, #e3e5e8 100%); color: #999; font-weight: bold; font-size: 1.2rem; }}
            
            /* 文字部分 */
            .card-content {{ padding: 15px; display: flex; flex-direction: column; height: 110px; justify-content: space-between; }}
            .card-meta {{ display: flex; justify-content: space-between; font-size: 0.75rem; color: #888; margin-bottom: 8px; }}
            .source-tag {{ background: #fef2f2; color: var(--primary); padding: 2px 6px; border-radius: 4px; font-weight: 500; }}
            .card-title {{ margin: 0; font-size: 1rem; line-height: 1.5; color: #333; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-weight: 600; }}
            
            /* 底部样式 */
            footer {{ text-align: center; padding: 3rem 0; color: #999; font-size: 0.85rem; line-height: 1.8; }}
            footer a {{ color: #666; text-decoration: none; transition: color 0.2s; }}
            footer a:hover {{ color: var(--primary); }}
            
            /* 移动端适配 */
            @media (max-width: 600px) {{
                main {{ grid-template-columns: 1fr; }}
                .card-img {{ height: 180px; }}
            }}
        </style>
    </head>
    <body>
        <header>
            <div class="header-content">
                <div class="brand">折疼记</div>
                <div class="time">更新: {update_time}</div>
            </div>
        </header>
        
        <main>
            {cards_html}
        </main>

        <footer>
            <p>聚合全网科技热点</p>
            <p>
                <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">浙ICP备2025183710号-1</a>
            </p>
            <p>&copy; {datetime.datetime.now().year} 折疼记. Powered by EdgeOne Pages.</p>
        </footer>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(template)
    
    print("HTML 生成成功！")

if __name__ == "__main__":
    generate_html()
