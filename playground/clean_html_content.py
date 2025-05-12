from bs4 import BeautifulSoup
from readability import Document


# pip install readability-lxml beautifulsoup4


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


# 示例使用
if __name__ == "__main__":
    # 读取 HTML 文件
    with open(r"C:\D\Code\git\IntelligenceIntegrationSystem\output\即时新闻\4月份各种自然灾害共造成610.6万人次不同程度受灾_140d88_20250512-170720..html", "r", encoding="utf-8") as f:
        raw_html = f.read()

    # 清洗内容
    cleaned_content = clean_html_content(raw_html)

    # 保存清洗后的内容到文件
    with open("cleaned_example.html", "w", encoding="utf-8") as f:
        f.write(cleaned_content)

    print("清洗完成！清洗后的内容已保存到 cleaned_example.html")
