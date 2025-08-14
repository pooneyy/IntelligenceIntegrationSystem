import re
import html
from typing import List

from IntelligenceHub import APPENDIX_TIME_ARCHIVED, APPENDIX_MAX_RATE_CLASS, APPENDIX_MAX_RATE_SCORE

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
    background: #e3f2fd;
    padding: 3px 8px;
    border-radius: 4px;
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
    padding: 10px 10px;
    margin-top: 5px;
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


def generate_articles_table(articles: List[dict]):
    """
    Generate HTML for articles list that can be reused across pages

    Parameters:
    articles -- List of article dictionaries [{
        "UUID": str,
        "INFORMANT": str,  # Source information (could be URL or text)
        "TIME": str (YYYY-MM-DD),
        "EVENT_TITLE": str,
        "EVENT_BRIEF": str
    }]
    """

    # Escape all text content to prevent XSS attacks
    def escape_text(text):
        return html.escape(str(text)) if text else ""

    # Check if valid URL
    def is_valid_url(url):
        return re.match(r'^https?://', url) if url else False

    # Generate rating stars display
    def create_rating_stars(score):
        """Convert numeric score to star rating display"""
        if not isinstance(score, (int, float)) or score < 0 or score > 10:
            return ""

        stars = ""
        full_stars = int(score) // 2
        half_star = (int(score) % 2 == 1)
        empty_stars = 5 - full_stars - (1 if half_star else 0)

        stars += ''.join(['<i class="bi bi-star-fill text-warning"></i> ' for _ in range(full_stars)])
        if half_star:
            stars += '<i class="bi bi-star-half text-warning"></i> '
        stars += ''.join(['<i class="bi bi-star text-warning"></i> ' for _ in range(empty_stars)])
        stars += f' <span class="ms-2 text-muted">{score}/10</span>'
        return stars

    # Build articles HTML
    articles_html = ""
    for article in articles:
        uuid = escape_text(article["UUID"])
        informant = escape_text(article.get("INFORMANT", ""))

        # Generate intelligence detail URL (for debugging)
        intel_url = f"/intelligence/{uuid}"

        # Build source information (clickable URL or plain text)
        informant_html = (
            f'<a href="{escape_text(informant)}" target="_blank" class="source-link">{informant}</a>'
            if is_valid_url(informant)
            else informant or 'Unknown Source'
        )

        # Safely get archived time from nested structure
        appendix = article.get('APPENDIX', {})
        archived_time = escape_text(appendix.get(APPENDIX_TIME_ARCHIVED, ''))

        # Safely get max rating information
        max_rate_class = escape_text(appendix.get(APPENDIX_MAX_RATE_CLASS, ''))
        max_rate_score = appendix.get(APPENDIX_MAX_RATE_SCORE)
        max_rate_display = ""

        # Generate rating display if valid data exists
        if max_rate_class and max_rate_score is not None:
            max_rate_display = f"""
            <div class="article-rating mt-2">
                {max_rate_class}：
                {create_rating_stars(max_rate_score)}
            </div>
            """

        articles_html += f"""
        <div class="article-card">
            <h3>
                <a href="{intel_url}" target="_blank" class="article-title">
                    {escape_text(article.get("EVENT_TITLE", "No Title"))}
                </a>
            </h3>
            <div class="article-meta">
                {f'<span class="article-time">Archived: {archived_time}</span>' if archived_time else ''}
                <span class="article-time">Publish: {escape_text(article.get("PUB_TIME") or 'No Datetime')}</span>
                <span class="article-source">Source: {informant_html}</span>
            </div>
            <p class="article-summary">{escape_text(article.get("EVENT_BRIEF", "No Brief"))}</p>

            <!-- Debug information section -->
            <div class="debug-info">
                {max_rate_display}
                <span class="debug-label">UUID:</span> {uuid}
            </div>
        </div>
        """

    return articles_html


# ----------------------------------------------------------------------------------------------------------------------

def main():
    articles = [
        # 完整特性：含归档时间、最高评分、有效URL来源
        {
            "UUID": "a1b2c3d4-5678-90ef-ghij-klmnopqrstuv",
            "INFORMANT": "https://news.example.com/article/123",
            "PUB_TIME": "2025-08-10",
            "EVENT_TITLE": "全球人工智能大会发布伦理新框架",
            "EVENT_BRIEF": "国际组织联合提出AI治理原则，强调透明性与问责机制。",
            "APPENDIX": {
                APPENDIX_TIME_ARCHIVED: "2025-08-12 14:30:00",
                APPENDIX_MAX_RATE_CLASS: "技术可行性",
                APPENDIX_MAX_RATE_SCORE: 8.5
            }
        },

        # 部分特性：含最高评分但无归档时间，纯文本来源
        {
            "UUID": "b2c3d4e5-6789-01fg-hijk-lmnopqrstuvw",
            "INFORMANT": "内部调研报告",
            "PUB_TIME": "2025-08-11",
            "EVENT_TITLE": "量子计算突破：新型超导材料稳定性提升200%",
            "EVENT_BRIEF": "实验室成功验证新型材料在极端环境下的量子比特保持能力。",
            "APPENDIX": {
                APPENDIX_MAX_RATE_CLASS: "创新性",
                APPENDIX_MAX_RATE_SCORE: 9.0
            }
        },

        # 边界情况：无APPENDIX字段，来源为无效URL（视为纯文本）
        {
            "UUID": "c3d4e5f6-7890-12gh-ijkl-mnopqrstuvwx",
            "INFORMANT": "ftp://invalid-url.example.org",
            "PUB_TIME": "2025-08-13",
            "EVENT_TITLE": "可再生能源补贴政策调整解读",
            "EVENT_BRIEF": "财政部宣布2026年起逐步取消光伏发电补贴，转向市场化机制。"
        },

        # 特殊特性：含归档时间但无评分，来源为有效URL
        {
            "UUID": "d4e5f6g7-8901-23hi-jklm-nopqrstuvxyz",
            "INFORMANT": "https://finance.example.com/policy/456",
            "PUB_TIME": "2025-08-14",
            "EVENT_TITLE": "央行数字货币试点扩展至跨境贸易",
            "EVENT_BRIEF": "首批试点银行完成多边央行数字货币桥接测试。",
            "APPENDIX": {
                APPENDIX_TIME_ARCHIVED: "2025-08-14 09:15:00"
            }
        }
    ]

    html_text = generate_articles_table(articles)
    html_page = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css" rel="stylesheet">
            
            <meta charset="UTF-8">
            <title>Intelligence Integration System (IIS)</title>
            <style>
                body {{ 
                    font-family: 'Segoe UI', system-ui, sans-serif; 
                    padding: 20px; 
                    background-color: #f8f9fa;
                }}
                
                {article_table_style}
            
                .pagination {{
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    margin-top: 10px;
                    margin-bottom: 40px;
                    gap: 15px;
                }}
                .page-btn {{
                    padding: 8px 25px;
                    background-color: #e3f2fd;
                    border: 1px solid #bbdefb;
                    border-radius: 6px;
                    text-decoration: none;
                    color: #0d47a1;
                    transition: all 0.3s;
                    font-weight: 500;
                }}
                .page-btn:hover {{
                    background-color: #bbdefb;
                    transform: translateY(-2px);
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                }}
                .page-info {{
                    color: #546e7a;
                    font-size: 0.95rem;
                }}
            </style>
        </head>
        <body>
            <div class="article-list">
                <h1>Intelligences</h1>
                <div class="articles-container">
                    {html_text}
                </div>
            </div>
        </body>
        </html>
    """

    with open('ArticleTableRender.html', 'w', encoding='utf-8') as f:
        f.write(html_page)


if __name__ == "__main__":
    main()
