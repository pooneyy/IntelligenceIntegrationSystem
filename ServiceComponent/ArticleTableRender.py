import re
import html


article_table_style = """
.article-list { 
    max-width: 1000px; 
    margin: 0 auto; 
    background: white;
    padding: 25px;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}
.article-list h1 {
    color: #343a40;
    border-bottom: 2px solid #e9ecef;
    padding-bottom: 15px;
    margin-bottom: 25px;
}
.article-card {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 25px;
    transition: all 0.3s ease;
    background: white;
}
.article-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 7px 15px rgba(0,0,0,0.1);
    border-color: #c5cae9;
}
.article-title {
    color: #1a73e8;
    text-decoration: none;
    font-weight: 600;
    font-size: 1.4rem;
    display: block;
    margin-bottom: 8px;
}
.article-title:hover { 
    text-decoration: underline; 
    color: #0d47a1;
}
.article-meta {
    color: #5f6368;
    font-size: 0.95em;
    margin: 10px 0;
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
}
.article-time {
    background: #e3f2fd;
    padding: 3px 8px;
    border-radius: 4px;
}
.article-source {
    color: #4a4a4a;
}
.source-link {
    color: #1565c0;
    text-decoration: none;
}
.source-link:hover {
    text-decoration: underline;
}
.article-summary {
    color: #202124;
    line-height: 1.7;
    margin: 15px 0;
    font-size: 1.05rem;
}
.debug-info {
    background-color: #f5f5f5;
    border-left: 3px solid #90a4ae;
    padding: 10px 15px;
    margin-top: 15px;
    font-size: 0.85rem;
    color: #546e7a;
    border-radius: 0 4px 4px 0;
    word-break: break-all;
}
.debug-label {
    font-weight: 600;
    color: #37474f;
    margin-right: 5px;
}
.debug-link {
    color: #0288d1;
    text-decoration: none;
}
.debug-link:hover {
    text-decoration: underline;
}
"""


def generate_articles_table(articles):
    """
    生成文章列表的HTML部分，可以被多个页面复用

    参数:
    articles -- 文章字典列表 [{
        "UUID": str,
        "INFORMANT": str,  # 来源信息（可能是URL或文本）
        "TIME": str (YYYY-MM-DD),
        "EVENT_TITLE": str,
        "EVENT_BRIEF": str
    }]
    """

    # 转义所有文本内容防止XSS攻击
    def escape_text(text):
        return html.escape(str(text)) if text else ""

    # 判断是否为有效URL
    def is_valid_url(url):
        return re.match(r'^https?://', url) if url else False

    # 构建文章列表HTML
    articles_html = ""
    for article in articles:
        uuid = escape_text(article["UUID"])
        informant = escape_text(article.get("INFORMANT", ""))

        # 生成情报详情URL（用于调试）
        intel_url = f"/intelligence/{uuid}"

        # 构建来源信息（可点击的URL或纯文本）
        informant_html = (
            f'<a href="{escape_text(informant)}" target="_blank" class="source-link">{informant}</a>'
            if is_valid_url(informant)
            else informant or 'Unknown Source'
        )

        articles_html += f"""
        <div class="article-card">
            <h3>
                <a href="{intel_url}" target="_blank" class="article-title">
                    {escape_text(article.get("EVENT_TITLE", "No Title"))}
                </a>
            </h3>
            <div class="article-meta">
                <span class="article-time">{escape_text(article.get("TIME") or 'NO Datetime')}</span>
                <span class="article-source">来源: {informant_html}</span>
            </div>
            <p class="article-summary">{escape_text(article.get("EVENT_BRIEF", "No Brief"))}</p>

            <!-- 调试信息区域 -->
            <div class="debug-info">
                <span class="debug-label">UUID:</span> {uuid} </br>
                <span class="debug-label">IIS URL:</span> 
                <a href="{intel_url}" target="_blank" class="debug-link">{intel_url}</a>
            </div>
        </div>
        """

    return articles_html
