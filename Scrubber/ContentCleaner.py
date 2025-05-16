import re
import chardet
import html2text
from readability import Document
from bs4 import BeautifulSoup, Comment
from markdownify import markdownify as md


# def html_to_clean_md(html: str) -> str:
#     # 输入验证
#     if not isinstance(html, (str, bytes)):
#         raise ValueError(f"Invalid input type {type(html)}, expected str/bytes")
#
#     # 编码处理
#     if isinstance(html, bytes):
#         detected_enc = chardet.detect(html)['encoding'] or 'utf-8'
#         html = html.decode(detected_enc, errors='replace')
#
#     # 容错解析
#     try:
#         soup = BeautifulSoup(html, 'lxml')
#     except Exception:
#         soup = BeautifulSoup(html, 'html.parser')
#
#     # 深度清理
#     UNWANTED_TAGS = ['script', 'style', 'nav', 'footer', 'form', 'noscript']
#     for tag in soup(UNWANTED_TAGS + ['svg', 'iframe']):
#         tag.decompose()
#
#     for comment in soup.find_all(text=lambda t: isinstance(t, Comment)):
#         comment.extract()
#
#     # 转换配置
#     markdown = md(
#         html,
#         strip=['script', 'style', 'nav', 'footer', 'form', 'noscript'],
#         heading_style="ATX"
#     )
#
#     # 后处理
#     markdown = re.sub(r'\n{3,}', '\n\n', markdown)
#     markdown = re.sub(r'[ \t]{2,}', ' ', markdown)
#     return markdown.strip()
#
#
# def clean_html_content(html_content):
#     """
#     清洗网页内容，提取主要内容并尽量删除广告、菜单等无用部分。
#
#     参数：
#         html_content (str): 原始 HTML 文件内容。
#
#     返回：
#         str: 清洗后的主要内容 HTML。
#     """
#     # 使用 Readability 提取主要内容
#     doc = Document(html_content)
#     main_content = doc.summary()  # 提取正文内容（HTML 格式）
#
#     # 使用 BeautifulSoup 进一步清洗提取的内容
#     soup = BeautifulSoup(main_content, "html.parser")
#
#     # 删除常见的广告和菜单的标签（根据 class 和 id 进行匹配）
#     for ad in soup.find_all(attrs={"class": lambda c: c and "ad" in c.lower()}):
#         ad.decompose()
#     for menu in soup.find_all(attrs={"class": lambda c: c and "menu" in c.lower()}):
#         menu.decompose()
#     for sidebar in soup.find_all(attrs={"class": lambda c: c and "sidebar" in c.lower()}):
#         sidebar.decompose()
#
#     # 删除多余的脚本和样式
#     for script in soup(["script", "style"]):
#         script.decompose()
#
#     # 返回清洗后的 HTML 内容
#     return soup.prettify()


# def clean_html_content(html_content):
#     """
#     清洗网页内容，提取主要内容并尽量删除广告、菜单等无用部分。
#
#     参数：
#         html_content (str): 原始 HTML 文件内容。
#
#     返回：
#         str: 清洗后的主要内容 HTML。
#     """
#     # 使用 Readability 提取主要内容
#     doc = Document(html_content)
#     main_content = doc.summary()  # 提取正文内容（HTML 格式）
#
#     # 使用 BeautifulSoup 解析提取的正文
#     soup = BeautifulSoup(main_content, "html.parser")
#
#     # 如果提取的正文内容太短，尝试通过自定义规则补充正文
#     if len(soup.get_text(strip=True)) < 200:  # 自定义阈值，判断正文是否过短
#         soup = BeautifulSoup(html_content, "html.parser")
#
#         # 尝试提取常见的正文区域标签
#         article = soup.find("article")  # 优先寻找 <article> 标签
#         if not article:
#             # 如果没有找到 <article>，尝试寻找可能的内容区域
#             content_div = soup.find("div", class_="content") or soup.find("div", id="content")
#             if content_div:
#                 article = content_div
#
#         if not article:
#             # 如果仍然没有找到，尝试提取文本密度最高的区块
#             max_text_block = max(soup.find_all("div"), key=lambda d: len(d.get_text(strip=True)), default=None)
#             if max_text_block and len(max_text_block.get_text(strip=True)) > 100:  # 阈值可调整
#                 article = max_text_block
#
#         # 如果找到合适的内容区域，替换 soup
#         if article:
#             soup = BeautifulSoup(str(article), "html.parser")
#
#     # 删除常见的广告和菜单的标签
#     for ad in soup.find_all(attrs={"class": lambda c: c and "ad" in c.lower()}):
#         ad.decompose()
#     for menu in soup.find_all(attrs={"class": lambda c: c and "menu" in c.lower()}):
#         menu.decompose()
#     for sidebar in soup.find_all(attrs={"class": lambda c: c and "sidebar" in c.lower()}):
#         sidebar.decompose()
#
#     # 删除多余的脚本和样式
#     for script in soup(["script", "style"]):
#         script.decompose()
#
#     # 返回清洗后的 HTML 内容
#     return soup.prettify()
#
#
# def html_to_clean_text(html: str) -> str:
#     h = html2text.HTML2Text()
#
#     # 关键配置项
#     h.ignore_links = True  # 过滤超链接标记
#     h.ignore_images = True  # 排除图片标签
#     h.ignore_tables = True  # 移除复杂表格结构
#     h.body_width = 0  # 禁用自动换行
#     h.wrap_list_items = False  # 保持列表项原始格式
#
#     # 处理特殊字符
#     h.escape_all = True  # 转义特殊符号如<>&
#
#     # 执行转换（网页1基础方法）
#     markdown = h.handle(html)
#     return markdown.strip()  # 去除首尾空白


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

    # 使用 BeautifulSoup 解析提取的正文
    soup = BeautifulSoup(main_content, "html.parser")

    # 如果提取的正文内容太短，尝试通过自定义规则补充正文
    if len(soup.get_text(strip=True)) < 200:  # 自定义阈值，判断正文是否过短
        soup = BeautifulSoup(html_content, "html.parser")

        # 尝试提取常见的正文区域标签
        article = soup.find("article")  # 优先寻找 <article> 标签
        if not article:
            # 如果没有找到 <article>，尝试寻找可能的内容区域
            content_div = soup.find("div", class_="content") or soup.find("div", id="content")
            if content_div:
                article = content_div

        if not article:
            # 如果仍然没有找到，尝试提取文本密度最高的区块
            max_text_block = max(soup.find_all("div"), key=lambda d: len(d.get_text(strip=True)), default=None)
            if max_text_block and len(max_text_block.get_text(strip=True)) > 100:  # 阈值可调整
                article = max_text_block

        # 如果找到合适的内容区域，替换 soup
        if article:
            soup = BeautifulSoup(str(article), "html.parser")

    # 删除常见的广告、菜单、推荐内容和脚注
    for tag in soup.find_all(attrs={"class": lambda c: c and any(
            keyword in c.lower() for keyword in ["ad", "menu", "footer", "recommend", "related", "sidebar"])}):
        tag.decompose()
    for tag in soup.find_all(attrs={"id": lambda i: i and any(
            keyword in i.lower() for keyword in ["ad", "menu", "footer", "recommend", "related", "sidebar"])}):
        tag.decompose()

    # 删除长度过短的段落
    for p in soup.find_all("p"):
        if len(p.get_text(strip=True)) < 50:  # 删除小于 50 字符的段落
            p.decompose()

    # 删除包含特定关键词的段落（脚注、版权声明等）
    for p in soup.find_all("p"):
        if any(keyword in p.get_text(strip=True).lower() for keyword in
               ["声明", "版权", "免责声明", "推荐阅读", "相关文章"]):
            p.decompose()

    # 删除多余的脚本和样式
    for script in soup(["script", "style"]):
        script.decompose()

    # 返回清洗后的 HTML 内容
    return soup.prettify()


# 示例使用
if __name__ == "__main__":
    # 读取 HTML 文件
    with open(r"/output/要闻导读/俄媒：观看二战电影，普京眼含热泪_d00d20_20250512-172515.origin.html", "r", encoding="utf-8") as f:
        raw_html = f.read()

    # 清洗内容
    cleaned_content = clean_html_content(raw_html)

    # 保存清洗后的内容到文件
    with open("cleaned_example.html", "w", encoding="utf-8") as f:
        f.write(cleaned_content)

    print("清洗完成！清洗后的内容已保存到 cleaned_example.html")
