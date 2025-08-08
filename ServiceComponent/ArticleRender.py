from datetime import datetime


def default_article_render(article_dict):
    """
    Renders article dictionary data into a formatted HTML page

    Parameters:
        article_dict (dict): Dictionary containing article data

    Returns:
        str: Formatted HTML string
    """
    # Safely get data that might be empty
    uuid_val = article_dict.get('UUID', '')
    informant = article_dict.get('INFORMANT', '')
    pub_time = article_dict.get('PUB_TIME', 'N/A')
    event_times = article_dict.get('TIME', [])
    locations = article_dict.get('LOCATION', [])
    people = article_dict.get('PEOPLE', [])
    organizations = article_dict.get('ORGANIZATION', [])
    title = article_dict.get('EVENT_TITLE', 'No Title')
    brief = article_dict.get('EVENT_BRIEF', 'No Brief')
    content = article_dict.get('EVENT_TEXT', 'No Content')
    rates = article_dict.get('RATE', {})
    impact = article_dict.get('IMPACT', 'No Impact')
    tips = article_dict.get('TIPS', 'No Tips')

    # Format publication time
    if pub_time and pub_time != 'null':
        try:
            pub_date = datetime.strptime(pub_time, "%Y-%m-%d")
            pub_time_display = pub_date.strftime("%B %d, %Y")
        except:
            pub_time_display = pub_time
    else:
        pub_time_display = "Not available"

    # Format event times
    formatted_times = []
    if event_times and event_times != 'null':
        if not isinstance(event_times, list):
            event_times = [event_times]

        for time_str in event_times:
            try:
                time_obj = datetime.strptime(time_str, "%Y-%m-%d")
                formatted_times.append(time_obj.strftime("%B %d, %Y"))
            except:
                formatted_times.append(time_str)

    # Create rating stars display
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

    # Build rating table
    rating_table = ""
    if rates:
        rating_table = '<div class="mt-4"><h5><i class="bi bi-graph-up"></i> Analysis & Evaluation</h5>'
        rating_table += '<div class="table-responsive"><table class="table table-sm">'
        rating_table += '<thead><tr><th>Dimension</th><th>Rating</th></tr></thead><tbody>'
        for key, score in rates.items():
            if isinstance(score, (int, float)) and 0 <= score <= 10:
                rating_table += f'<tr><td>{key}</td><td>{create_rating_stars(score)}</td></tr>'
        rating_table += '</tbody></table></div></div>'

    # Build HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
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
            <!-- Article header -->
            <div class="article-header text-center">
                <div class="container">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="text-start">
                            <small class="d-block"><i class="bi bi-calendar-event"></i> Published: {pub_time_display}</small>
                            <small class="d-block"><i class="bi bi-upc-scan"></i> {uuid_val}</small>
                        </div>
                        <h1 class="display-5 fw-bold">{title}</h1>
                        <div>
                            {f'<a href="{informant}" class="btn btn-sm btn-light"><i class="bi bi-link-45deg"></i> Source</a>' if informant else ''}
                        </div>
                    </div>
                    <div class="lead">{brief}</div>
                </div>
            </div>

            <!-- Metadata section -->
            <div class="row">
                <div class="col-md-4">
                    <div class="meta-box">
                        <h5><i class="bi bi-geo-alt"></i> Geographic Locations</h5>
                        {', '.join(locations) if locations else "No location data"}
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="meta-box">
                        <h5><i class="bi bi-people"></i> Related People</h5>
                        {', '.join(people) if people else "No associated people"}
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="meta-box">
                        <h5><i class="bi bi-building"></i> Related Organizations</h5>
                        {', '.join(organizations) if organizations else "No related organizations"}
                    </div>
                </div>
            </div>

            <!-- Event time section -->
            <div class="row mt-2">
                <div class="col-12">
                    <div class="meta-box">
                        <h5><i class="bi bi-clock-history"></i> Event Time(s)</h5>
                        {', '.join(formatted_times) if formatted_times else "No specific timing data"}
                    </div>
                </div>
            </div>

            <!-- Main content -->
            <div class="content-section mt-4">
                {content}
            </div>

            <!-- Analysis section -->
            {rating_table}

            <!-- Impact analysis -->
            <div class="impact-card">
                <h5><i class="bi bi-lightning-charge"></i> Potential Impact</h5>
                <p>{impact}</p>
            </div>

            <!-- Tips section -->
            <div class="tip-card">
                <h5><i class="bi bi-lightbulb"></i> Analyst Notes</h5>
                <p>{tips}</p>
            </div>
        </div>

        <footer>
            <div class="container">
                <div class="d-flex justify-content-between">
                    <div>
                        <div class="system-name">
                            <i class="bi bi-cpu"></i> Intelligence Integration System
                        </div>
                        <div class="mt-2 text-muted">© {datetime.now().year} All rights reserved</div>
                    </div>
                    <div class="text-end">
                        <div class="author-brand">SleepySoft</div>
                        <div class="tagline">Turning data into insight</div>
                    </div>
                </div>
                <div class="text-center mt-4 pt-3 border-top border-secondary border-opacity-25">
                    <small class="d-block opacity-75">
                        Report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    </small>
                </div>
            </div>
        </footer>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """

    return html_content


# Test case
if __name__ == "__main__":
    sample_article = {
        "UUID": "a3d8f7c9-4b2e-4567-8c29-1234abcd5678",
        "INFORMANT": "https://news.example.com/article/12345",
        "PUB_TIME": "2023-10-15",
        "TIME": ["2023-10-18", "2023-11-01"],
        "LOCATION": ["China", "Guangdong Province", "Shenzhen"],
        "PEOPLE": ["Zhang San", "Li Si", "Wang Wu"],
        "ORGANIZATION": ["Tencent Inc", "Shenzhen Municipal Government"],
        "EVENT_TITLE": "New Infrastructure Project Launched in Shenzhen Tech Park",
        "EVENT_BRIEF": "Shenzhen Technology Park announces launch of next-gen digital infrastructure project with ¥50B investment",
        "EVENT_TEXT": "<p>The Shenzhen Municipal Government and several tech companies jointly announced the launch of a new digital infrastructure project in Shenzhen Technology Park. The project is expected to involve a total investment of ¥50 billion yuan, with completion planned within three years.</p><p>The project includes construction of 5G base stations, AI computing centers, IoT facilities and other advanced technical infrastructure. Zhang San, member of Shenzhen Municipal Standing Committee stated: 'This project will further solidify Shenzhen's leading position in technological innovation.'</p><p>Li Si, CEO of Tencent Technology commented: 'The new infrastructure construction will provide strong support for Shenzhen tech companies and accelerate digital transformation.'</p>",
        "RATE": {
            "Strategic Relevance": 8,
            "Global Connectivity": 4,
            "Financial Impact": 9,
            "Policy Relevance": 10,
            "Technical Innovation": 8,
            "Investment Value": 9,
            "Accuracy": 7,
        },
        "IMPACT": "This event may increase valuation of technology companies in Shenzhen, especially in 5G and AI sectors, while creating opportunities in infrastructure industry",
        "TIPS": "Investors should watch opportunities in 5G, AI, and IoT companies"
    }

    html_output = default_article_render(sample_article)

    with open('default_article_render.html', 'wt', encoding='utf-8') as f:
        f.write(html_output)
