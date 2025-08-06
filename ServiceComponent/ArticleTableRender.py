import re
import html


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
