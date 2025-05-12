import re
import chardet
import html2text
from readability import Document
from bs4 import BeautifulSoup, Comment
from markdownify import markdownify as md


def html_to_clean_md(html: str) -> str:
    # 输入验证
    if not isinstance(html, (str, bytes)):
        raise ValueError(f"Invalid input type {type(html)}, expected str/bytes")

    # 编码处理
    if isinstance(html, bytes):
        detected_enc = chardet.detect(html)['encoding'] or 'utf-8'
        html = html.decode(detected_enc, errors='replace')

    # 容错解析
    try:
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        soup = BeautifulSoup(html, 'html.parser')

    # 深度清理
    UNWANTED_TAGS = ['script', 'style', 'nav', 'footer', 'form', 'noscript']
    for tag in soup(UNWANTED_TAGS + ['svg', 'iframe']):
        tag.decompose()

    for comment in soup.find_all(text=lambda t: isinstance(t, Comment)):
        comment.extract()

    # 转换配置
    markdown = md(
        html,
        strip=['script', 'style', 'nav', 'footer', 'form', 'noscript'],
        heading_style="ATX"
    )

    # 后处理
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    markdown = re.sub(r'[ \t]{2,}', ' ', markdown)
    return markdown.strip()


def clean_html_content(html_content):
    """
    清洗网页内容，提取主要内容并尽量删除广告、菜单等无用部分。

    参数：
        html_content (str): 原始 HTML 文件内容。

    返回：
        str: 清洗后的主要内容 HTML。
    """
    # 使用 Readability 提取主要内容
    doc = Document(html_content)
    main_content = doc.summary()  # 提取正文内容（HTML 格式）

    # 使用 BeautifulSoup 进一步清洗提取的内容
    soup = BeautifulSoup(main_content, "html.parser")

    # 删除常见的广告和菜单的标签（根据 class 和 id 进行匹配）
    for ad in soup.find_all(attrs={"class": lambda c: c and "ad" in c.lower()}):
        ad.decompose()
    for menu in soup.find_all(attrs={"class": lambda c: c and "menu" in c.lower()}):
        menu.decompose()
    for sidebar in soup.find_all(attrs={"class": lambda c: c and "sidebar" in c.lower()}):
        sidebar.decompose()

    # 删除多余的脚本和样式
    for script in soup(["script", "style"]):
        script.decompose()

    # 返回清洗后的 HTML 内容
    return soup.prettify()


def html_to_clean_text(html: str) -> str:
    h = html2text.HTML2Text()

    # 关键配置项
    h.ignore_links = True  # 过滤超链接标记
    h.ignore_images = True  # 排除图片标签
    h.ignore_tables = True  # 移除复杂表格结构
    h.body_width = 0  # 禁用自动换行
    h.wrap_list_items = False  # 保持列表项原始格式

    # 处理特殊字符
    h.escape_all = True  # 转义特殊符号如<>&

    # 执行转换（网页1基础方法）
    markdown = h.handle(html)
    return markdown.strip()  # 去除首尾空白
