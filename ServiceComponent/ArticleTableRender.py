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
.article-source {
    /* 使用flex布局，确保 "Source:"、图标、URL能良好对齐 */
    display: flex;
    align-items: baseline; /* 基线对齐，视觉效果更佳 */
    flex-wrap: nowrap; /* 不允许 "Source:" 和图标换行 */
}

.source-link-container {
    /* 这个容器将包裹图标和链接，以便它们能作为一个整体换行 */
    display: inline-flex;
    align-items: baseline;
    flex-wrap: wrap; /* 允许URL过长时换行 */
}

.source-prefix {
    /* 图标的前缀样式 */
    display: inline-block; /* 确保图标能和文字同行 */
    margin-right: 6px; /* 和URL之间增加一点间距 */
    font-size: 1.1em;  /* 让图标稍微大一点，更清晰 */
    vertical-align: middle; /* 垂直居中对齐 */
}

.domain-highlight {
    /* 域名高亮样式 */
    background-color: #FFFF00; /* 亮黄色，类似荧光笔 */
    padding: 1px 2px;
    border-radius: 3px;
}

/* 确保链接本身在容器内可以正常表现 */
.source-link {
    word-break: break-all; /* 允许长URL在任意位置断开换行 */
}
"""


article_table_color_gradient_script = """
<script>
function updateTimeBackgrounds() {
    const now = new Date().getTime();
    const twelveHours = 12 * 60 * 60 * 1000;  // 12小时毫秒数

    document.querySelectorAll('.archived-time').forEach(el => {
        const archivedTime = new Date(el.dataset.archived).getTime();
        const timeDiff = now - archivedTime;

        // 计算颜色比例（0-12小时）
        let ratio = Math.min(1, Math.max(0, timeDiff / twelveHours));

        // 起始色：橙色 (#FFA500)，终止色：浅蓝色 (#E3F2FD)
        const r = Math.round(255 - ratio * (255 - 227));
        const g = Math.round(165 - ratio * (165 - 242));
        const b = Math.round(0 - ratio * (0 - 253));

        el.style.backgroundColor = `rgb(${r}, ${g}, ${b})`;
    });
}

document.addEventListener('DOMContentLoaded', updateTimeBackgrounds);
setInterval(updateTimeBackgrounds, 60000);
</script>
"""


article_source_enhancer_script = """
<script>
document.addEventListener('DOMContentLoaded', () => {
    // 媒体来源数据库
    // domain: 用于匹配的关键域名
    // country: 所属国家/地区
    // flag: 对应的 Emoji 国旗
    // accessibleInChina: 在中国大陆是否可直接访问 (true: 是, false: 否)
    const mediaSources = [
        // 美国
        { domain: "wsj.com", country: "USA", flag: "🇺🇸", accessibleInChina: false },
        { domain: "nytimes.com", country: "USA", flag: "🇺🇸", accessibleInChina: false },
        { domain: "voanews.com", country: "USA", flag: "🇺🇸", accessibleInChina: false },
        // 英国
        { domain: "bbc.com", country: "UK", flag: "🇬🇧", accessibleInChina: false },
        // 加拿大
        { domain: "rcinet.ca", country: "Canada", flag: "🇨🇦", accessibleInChina: false },
        // 法国
        { domain: "rfi.fr", country: "France", flag: "🇫🇷", accessibleInChina: false },
        // 德国
        { domain: "dw.com", country: "Germany", flag: "🇩🇪", accessibleInChina: false },
        // 澳大利亚
        { domain: "abc.net.au", country: "Australia", flag: "🇦🇺", accessibleInChina: false },
        // 卡塔尔
        { domain: "aljazeera.com", country: "Qatar", flag: "🇶🇦", accessibleInChina: true },
        // 俄罗斯
        { domain: "sputniknews.com", country: "Russia", flag: "🇷🇺", accessibleInChina: true },
        { domain: "rt.com", country: "Russia", flag: "🇷🇺", accessibleInChina: true },
        // 日本
        { domain: "nhk.or.jp", country: "Japan", flag: "🇯🇵", accessibleInChina: true },
        { domain: "kyodonews.net", country: "Japan", flag: "🇯🇵", accessibleInChina: true },
        { domain: "nikkei.com", country: "Japan", flag: "🇯🇵", accessibleInChina: true },
        // 新加坡
        { domain: "zaobao.com", country: "Singapore", flag: "🇸🇬", accessibleInChina: true },
        // 韩国
        { domain: "chosun.com", country: "South Korea", flag: "🇰🇷", accessibleInChina: true },
        { domain: "joongang.co.kr", country: "South Korea", flag: "🇰🇷", accessibleInChina: true },
        // 国际
        { domain: "investing.com", country: "International", flag: "🌍", accessibleInChina: true },
        { domain: "reuters.com", country: "International", flag: "🌍", accessibleInChina: false },
        { domain: "apnews.com", country: "International", flag: "🌍", accessibleInChina: false },
        // 中国大陆
        { domain: "jiemian.com", country: "China", flag: "🇨🇳", accessibleInChina: true },
        { domain: "thepaper.cn", country: "China", flag: "🇨🇳", accessibleInChina: true },
        { domain: "infzm.com", country: "China", flag: "🇨🇳", accessibleInChina: true },
        { domain: "people.com.cn", country: "China", flag: "🇨🇳", accessibleInChina: true },
        { domain: "gmw.cn", country: "China", flag: "🇨🇳", accessibleInChina: true },
        { domain: "ce.cn", country: "China", flag: "🇨🇳", accessibleInChina: true },
        { domain: "81.cn", country: "China", flag: "🇨🇳", accessibleInChina: true },
        { domain: "qstheory.cn", country: "China", flag: "🇨🇳", accessibleInChina: true },
        { domain: "xinhuanet.com", country: "China", flag: "🇨🇳", accessibleInChina: true },
        { domain: "bjnews.com.cn", country: "China", flag: "🇨🇳", accessibleInChina: true },
        { domain: "chinanews.com", country: "China", flag: "🇨🇳", accessibleInChina: true },
        // 中国台湾
        { domain: "cna.com.tw", country: "Taiwan", flag: "🇹🇼", accessibleInChina: true },
    ];

    /**
     * 根据主机名在媒体库中查找匹配项
     * @param {string} hostname - 链接的主机名 (e.g., "www.wsj.com")
     * @returns {object|null} - 匹配到的媒体对象或null
     */
    function findSourceInfo(hostname) {
        // 先完全匹配
        let source = mediaSources.find(s => s.domain === hostname);
        if (source) return source;
        // 再匹配子域名
        source = mediaSources.find(s => hostname.endsWith('.' + s.domain));
        return source || null;
    }

    /**
     * 提取顶级域名部分用于高亮
     * @param {string} hostname - 链接的主机名
     * @returns {string|null} - 顶级域名 (e.g., "wsj.com", "bbc.co.uk")
     */
    function getHighlightDomain(hostname) {
        // 匹配常见的二级域名后缀，如 .co.uk, .com.cn
        const complexTldMatch = hostname.match(/[^.]+\.(?:co|com|net|org|gov|edu)\.[^.]+$/);
        if (complexTldMatch) {
            return complexTldMatch[0];
        }
        // 匹配标准的顶级域名
        const simpleTldMatch = hostname.match(/[^.]+\.[^.]+$/);
        return simpleTldMatch ? simpleTldMatch[0] : hostname;
    }

    // 遍历页面上所有的 .article-source 元素
    document.querySelectorAll('.article-source').forEach(sourceElement => {
        const link = sourceElement.querySelector('a.source-link');
        if (!link || !link.href) return;

        try {
            const url = new URL(link.href);
            const hostname = url.hostname;
            const sourceInfo = findSourceInfo(hostname);

            // 创建一个容器来包裹图标和链接，以便统一处理换行
            const container = document.createElement('div');
            container.className = 'source-link-container';

            // 1. 创建图标前缀
            const prefixSpan = document.createElement('span');
            prefixSpan.className = 'source-prefix';

            if (sourceInfo) {
                const accessibilityIcon = sourceInfo.accessibleInChina ? '✅' : '🚫';
                prefixSpan.textContent = ` ${accessibilityIcon} ${sourceInfo.flag}`;
            } else {
                prefixSpan.textContent = ' ❔  🌍'; // 默认地球图标
            }

            // 2. 高亮域名
            const highlightPart = getHighlightDomain(hostname);
            const originalText = link.textContent;

            if (originalText.includes(highlightPart)) {
                const highlightedHTML = originalText.replace(
                    highlightPart,
                    `<span class="domain-highlight">${highlightPart}</span>`
                );
                link.innerHTML = highlightedHTML;
            }

            // 3. 更新DOM结构
            // 将图标和链接移入新容器
            container.appendChild(prefixSpan);
            container.appendChild(link);

            // 将原来的 "Source: " 文本节点和新容器一起放回
            const sourceTextNode = sourceElement.firstChild;
            sourceElement.innerHTML = ''; // 清空原有内容
            sourceElement.appendChild(sourceTextNode);
            sourceElement.appendChild(container);

        } catch (e) {
            console.error('Error processing source link:', e);
        }
    });
});
</script>
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

        archived_html = ""
        if archived_time:
            archived_html = f"""
            <span class="article-time archived-time" data-archived="{archived_time}">
                Archived: {archived_time}
            </span>
            """

        articles_html += f"""
        <div class="article-card">
            <h3>
                <a href="{intel_url}" target="_blank" class="article-title">
                    {escape_text(article.get("EVENT_TITLE", "No Title"))}
                </a>
            </h3>
            <div class="article-meta">
                {archived_html}
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

