import html


# def default_article_list_render(articles, offset, count, total_count):
#     """
#     渲染文章列表为带分页功能的HTML页面
#
#     参数:
#     articles -- 文章字典列表 [{
#         "UUID": str,
#         "INFORMANT": str,
#         "TIME": str (YYYY-MM-DD),
#         "EVENT_TITLE": str,
#         "EVENT_BRIEF": str
#     }]
#     offset -- 当前偏移量
#     count -- 每页显示数量
#     total_count -- 文章总数
#     """
#     # 计算分页参数
#     prev_offset = max(0, offset - count)
#     next_offset = offset + count
#     has_prev = offset > 0
#     has_next = offset + count < total_count
#
#     # 转义所有文本内容防止XSS攻击
#     def escape_text(text):
#         return html.escape(str(text)) if text else ""
#
#     # 构建文章列表HTML
#     articles_html = ""
#     for article in articles:
#         uuid = escape_text(article["UUID"])
#         articles_html += f"""
#         <div class="article-card">
#             <h3>
#                 <a href="/intelligence/{uuid}" target="_blank" class="article-title">
#                     {escape_text(article["EVENT_TITLE"])}
#                 </a>
#             </h3>
#             <div class="article-meta">
#                 <span class="article-time">{escape_text(article["TIME"] or '无日期')}</span>
#                 <span class="article-source">{escape_text(article["INFORMANT"] or '未知来源')}</span>
#             </div>
#             <p class="article-summary">{escape_text(article["EVENT_BRIEF"])}</p>
#         </div>
#         """
#
#     # 构建分页控件HTML
#     pagination_html = ""
#     if has_prev or has_next:
#         pagination_html = f"""
#         <div class="pagination">
#             {f'<a href="/intelligences?offset={prev_offset}&count={count}" class="page-btn prev">上一页</a>' if has_prev else ''}
#             <span class="page-info">第 {offset // count + 1} 页/共 {(total_count + count - 1) // count} 页</span>
#             {f'<a href="/intelligences?offset={next_offset}&count={count}" class="page-btn next">下一页</a>' if has_next else ''}
#         </div>
#         """
#
#     # 完整HTML结构 [6,7,10](@ref)
#     return f"""
#     <!DOCTYPE html>
#     <html>
#     <head>
#         <meta charset="UTF-8">
#         <title>情报列表</title>
#         <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
#         <style>
#             body {{ font-family: 'Segoe UI', system-ui, sans-serif; padding: 20px; }}
#             .article-list {{ max-width: 800px; margin: 0 auto; }}
#             .article-card {{
#                 border: 1px solid #e0e0e0;
#                 border-radius: 8px;
#                 padding: 20px;
#                 margin-bottom: 20px;
#                 transition: box-shadow 0.3s;
#             }}
#             .article-card:hover {{
#                 box-shadow: 0 5px 15px rgba(0,0,0,0.1);
#             }}
#             .article-title {{
#                 color: #1a73e8;
#                 text-decoration: none;
#                 font-weight: 600;
#             }}
#             .article-title:hover {{ text-decoration: underline; }}
#             .article-meta {{
#                 color: #5f6368;
#                 font-size: 0.9em;
#                 margin: 8px 0;
#                 display: flex;
#                 gap: 15px;
#             }}
#             .article-summary {{
#                 color: #202124;
#                 line-height: 1.6;
#                 margin-top: 10px;
#             }}
#             .pagination {{
#                 display: flex;
#                 justify-content: center;
#                 align-items: center;
#                 margin-top: 30px;
#                 gap: 20px;
#             }}
#             .page-btn {{
#                 padding: 8px 20px;
#                 background-color: #f1f3f4;
#                 border: 1px solid #dadce0;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 color: #1a73e8;
#                 transition: background-color 0.2s;
#             }}
#             .page-btn:hover {{
#                 background-color: #e8f0fe;
#             }}
#             .page-info {{
#                 color: #5f6368;
#             }}
#         </style>
#     </head>
#     <body>
#         <div class="article-list">
#             <h1 class="mb-4">情报列表</h1>
#             <div class="articles-container">
#                 {articles_html}
#             </div>
#             {pagination_html}
#         </div>
#     </body>
#     </html>
#     """

import html
import re


def default_article_list_render(articles, offset, count, total_count):
    """
    渲染文章列表为带分页功能的HTML页面

    参数:
    articles -- 文章字典列表 [{
        "UUID": str,
        "INFORMANT": str,  # 来源信息（可能是URL或文本）
        "TIME": str (YYYY-MM-DD),
        "EVENT_TITLE": str,
        "EVENT_BRIEF": str
    }]
    offset -- 当前偏移量
    count -- 每页显示数量
    total_count -- 文章总数
    """
    # 计算分页参数
    prev_offset = max(0, offset - count)
    next_offset = offset + count
    has_prev = offset > 0
    has_next = offset + count < total_count

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

    # 构建分页控件HTML
    pagination_html = ""
    if has_prev or has_next:
        pagination_html = f"""
        <div class="pagination">
            {f'<a href="/intelligences?offset={prev_offset}&count={count}" class="page-btn prev">Prev</a>' if has_prev else ''}
            <span class="page-info">{offset // count + 1} / {(total_count + count - 1) // count}</span>
            {f'<a href="/intelligences?offset={next_offset}&count={count}" class="page-btn next">Next</a>' if has_next else ''}
        </div>
        """

    # 完整HTML结构
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Intelligence Integration System (IIS)</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ 
                font-family: 'Segoe UI', system-ui, sans-serif; 
                padding: 20px; 
                background-color: #f8f9fa;
            }}
            .article-list {{ 
                max-width: 1000px; 
                margin: 0 auto; 
                background: white;
                padding: 25px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }}
            .article-list h1 {{
                color: #343a40;
                border-bottom: 2px solid #e9ecef;
                padding-bottom: 15px;
                margin-bottom: 25px;
            }}
            .article-card {{
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 25px;
                transition: all 0.3s ease;
                background: white;
            }}
            .article-card:hover {{
                transform: translateY(-3px);
                box-shadow: 0 7px 15px rgba(0,0,0,0.1);
                border-color: #c5cae9;
            }}
            .article-title {{
                color: #1a73e8;
                text-decoration: none;
                font-weight: 600;
                font-size: 1.4rem;
                display: block;
                margin-bottom: 8px;
            }}
            .article-title:hover {{ 
                text-decoration: underline; 
                color: #0d47a1;
            }}
            .article-meta {{
                color: #5f6368;
                font-size: 0.95em;
                margin: 10px 0;
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
            }}
            .article-time {{
                background: #e3f2fd;
                padding: 3px 8px;
                border-radius: 4px;
            }}
            .article-source {{
                color: #4a4a4a;
            }}
            .source-link {{
                color: #1565c0;
                text-decoration: none;
            }}
            .source-link:hover {{
                text-decoration: underline;
            }}
            .article-summary {{
                color: #202124;
                line-height: 1.7;
                margin: 15px 0;
                font-size: 1.05rem;
            }}
            .debug-info {{
                background-color: #f5f5f5;
                border-left: 3px solid #90a4ae;
                padding: 10px 15px;
                margin-top: 15px;
                font-size: 0.85rem;
                color: #546e7a;
                border-radius: 0 4px 4px 0;
                word-break: break-all;
            }}
            .debug-label {{
                font-weight: 600;
                color: #37474f;
                margin-right: 5px;
            }}
            .debug-link {{
                color: #0288d1;
                text-decoration: none;
            }}
            .debug-link:hover {{
                text-decoration: underline;
            }}
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
            {pagination_html}
            <div class="articles-container">
                {articles_html if articles else '<p class="text-center py-5">NO Intelligence</p>'}
            </div>
        </div>
    </body>
    </html>
    """


# 示例数据
articles = [
    {
        "UUID": "123e4567-e89b-12d3-a456-426614174000",
        "INFORMANT": "情报来源A",
        "TIME": "2023-08-15",
        "EVENT_TITLE": "重要市场趋势分析",
        "EVENT_BRIEF": "近期市场出现明显波动，建议投资者保持谨慎..."
    },
    {
        "UUID": "223e4567-e89b-12d3-a456-426614174001",
        "INFORMANT": "情报来源B",
        "TIME": "2023-08-14",
        "EVENT_TITLE": "新技术突破报告",
        "EVENT_BRIEF": "研究团队宣布在量子计算领域取得重大进展..."
    }
]

# 渲染HTML页面
html_output = default_article_list_render(
    articles=articles,
    offset=100,
    count=20,
    total_count=500
)

# 输出或保存HTML
with open("intelligence_list.html", "w", encoding="utf-8") as f:
    f.write(html_output)

