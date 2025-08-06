from datetime import datetime


def default_article_render(article_dict):
    """
    将文章字典数据渲染为美观的HTML页面

    参数:
        article_dict (dict): 包含文章数据的字典

    返回:
        str: 格式化的HTML字符串
    """
    # 安全获取可能为空的数据
    uuid_val = article_dict.get('UUID', '')
    informant = article_dict.get('INFORMANT', '')
    time_str = article_dict.get('TIME', '无时间信息')
    locations = article_dict.get('LOCATION', [])
    people = article_dict.get('PEOPLE', [])
    organizations = article_dict.get('ORGANIZATION', [])
    title = article_dict.get('EVENT_TITLE', '无标题')
    brief = article_dict.get('EVENT_BRIEF', '无简介')
    content = article_dict.get('EVENT_TEXT', '无内容')
    rates = article_dict.get('RATE', {})
    impact = article_dict.get('IMPACT', '无明显影响分析')
    tips = article_dict.get('TIPS', '无提示信息')

    # 处理时间显示
    if time_str and time_str != 'null':
        try:
            article_date = datetime.strptime(time_str, "%Y-%m-%d")
            time_display = article_date.strftime("%Y年%m月%d日")
        except:
            time_display = time_str
    else:
        time_display = "时间未指定"

    # 创建评分星星
    def create_rating_stars(score):
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

    # 构建评分表
    rating_table = ""
    if rates:
        rating_table = '<div class="mt-4"><h5><i class="bi bi-graph-up"></i> 分析评估</h5>'
        rating_table += '<div class="table-responsive"><table class="table table-sm">'
        rating_table += '<thead><tr><th>评估维度</th><th>评分</th></tr></thead><tbody>'
        for key, score in rates.items():
            if isinstance(score, (int, float)) and 0 <= score <= 10:
                rating_table += f'<tr><td>{key}</td><td>{create_rating_stars(score)}</td></tr>'
        rating_table += '</tbody></table></div></div>'

    # 构建HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css" rel="stylesheet">
        <style>
            .article-header {{
                background: linear-gradient(to right, #1a2980, #26d0ce);
                color: white;
                padding: 2.5rem 0;
                margin-bottom: 2rem;
                border-radius: 0 0 10px 10px;
            }}
            .meta-box {{
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 15px;
            }}
            .key-points {{
                border-left: 4px solid #0d6efd;
                padding-left: 15px;
                margin: 20px 0;
            }}
            .impact-card {{
                background: linear-gradient(to right, #f8f9fa, #e9ecef);
                border-radius: 10px;
                padding: 20px;
                border-left: 4px solid #dc3545;
                margin: 30px 0;
            }}
            .tip-card {{
                background-color: #d1ecf1;
                border-radius: 10px;
                padding: 15px;
                margin: 20px 0;
                border-left: 4px solid #0dcaf0;
            }}
            .content-section {{
                line-height: 1.8;
                font-size: 1.1rem;
                color: #444;
            }}
            footer {{
                border-top: 1px solid #eee;
                padding: 15px 0;
                margin-top: 30px;
                font-size: 0.9rem;
                color: #6c757d;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- 文章头部信息 -->
            <div class="article-header text-center">
                <div class="container">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="text-start">
                            <small class="d-block"><i class="bi bi-calendar-event"></i> {time_display}</small>
                            <small class="d-block"><i class="bi bi-upc-scan"></i> {uuid_val}</small>
                        </div>
                        <h1 class="display-5 fw-bold">{title}</h1>
                        <div>
                            {f'<a href="{informant}" class="btn btn-sm btn-light"><i class="bi bi-link-45deg"></i> 来源</a>' if informant else ''}
                        </div>
                    </div>
                    <div class="lead">{brief}</div>
                </div>
            </div>

            <!-- 关键元数据 -->
            <div class="row">
                <div class="col-md-6">
                    <div class="meta-box">
                        <h5><i class="bi bi-geo-alt"></i> 地理位置</h5>
                        {', '.join(locations) if locations else "无地理位置信息"}
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="meta-box">
                        <h5><i class="bi bi-people"></i> 涉及人物</h5>
                        {', '.join(people) if people else "无相关人物"}
                    </div>
                </div>
                <div class="col-12">
                    <div class="meta-box">
                        <h5><i class="bi bi-building"></i> 相关组织</h5>
                        {', '.join(organizations) if organizations else "无相关组织"}
                    </div>
                </div>
            </div>

            <!-- 主要内容 -->
            <div class="content-section mt-4">
                {content}
            </div>

            <!-- 分析评估 -->
            {rating_table}

            <!-- 影响分析 -->
            <div class="impact-card">
                <h5><i class="bi bi-lightning-charge"></i> 潜在影响分析</h5>
                <p>{impact}</p>
            </div>

            <!-- 提示信息 -->
            <div class="tip-card">
                <h5><i class="bi bi-lightbulb"></i> 分析师提示</h5>
                <p>{tips}</p>
            </div>
        </div>

        <footer>
            <div class="container">
                <div class="footer-content">
                    <div>
                        <div class="system-name">
                            <i class="bi bi-cpu"></i> Intelligence Integration System
                        </div>
                        <div class="mt-2 text-muted">© {datetime.now().year} All rights reserved</div>
                    </div>
                    <div class="mt-3 mt-md-0 text-end">
                        <div class="author-brand">SleepySoft</div>
                        <div class="tagline">Turning data into insight</div>
                    </div>
                </div>
                <div class="text-center mt-4 pt-3 border-top border-secondary border-opacity-25">
                    <small class="d-block opacity-75">
                        Intelligent report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    </small>
                </div>
            </div>
        </footer>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """

    return html_content


# 测试用例
if __name__ == "__main__":
    sample_article = {
        "UUID": "a3d8f7c9-4b2e-4567-8c29-1234abcd5678",
        "INFORMANT": "https://news.example.com/article/12345",
        "TIME": "2023-10-15",
        "LOCATION": ["中国", "广东省", "深圳市"],
        "PEOPLE": ["张三", "李四", "王五"],
        "ORGANIZATION": ["腾讯科技有限公司", "深圳市政府"],
        "EVENT_TITLE": "深圳科技园区启动新基建项目",
        "EVENT_BRIEF": "深圳科技园区宣布启动新一代数字基础设施建设项目，预计投资500亿元",
        "EVENT_TEXT": "<p>深圳市政府与多家科技企业联合宣布，将在深圳科技园区启动新一代数字基础设施建设项目。该项目预计总投资500亿元人民币，计划在三年内完成。</p><p>项目建设包括5G基站、人工智能计算中心、物联网设施等先进技术基础设施。深圳市委常委张三在发布会上表示："
        "该项目将进一步巩固深圳在科技创新领域的领先地位。</p><p>腾讯科技CEO李四表示："
        "新一代基础设施建设将为深圳科技企业提供强大支撑，加速产业数字化升级。</p>",
    "RATE": {
        "战略相关性": 8,
        "国际关联度": 4,
        "金融影响力": 9,
        "政策关联度": 10,
        "科技前瞻性": 8,
        "投资价值": 9,
        "内容准确率": 7,
    },
    "IMPACT": "该事件可能提升深圳地区科技类上市公司估值，特别是5G和人工智能相关企业，同时为基建行业带来增长机会",
    "TIPS": "建议投资者关注5G、人工智能、物联网相关企业的投资机会"
    }

    html_output = default_article_render(sample_article)

    with open('default_article_render.html', 'wt', encoding='utf-8') as f:
        f.write(html_output)
