"""
Use the methods in this document to organize the process of
    check history -> crawling -> cleaning -> recording history -> submitting results
"""
import html2text
from bs4 import BeautifulSoup

from Streamer.ToFileAndHistory import to_file_and_history
from Tools import ContentHistory
from Scraper.PlaywrightRenderedScraper import fetch_content


def html_content_converter(html_content, selector, output_format='markdown'):
    """
    提取指定HTML元素内容并转换为目标格式

    :param html_content: 原始HTML字符串
    :param selector: CSS选择器字符串，如'div.left_zw'
    :param output_format: 输出格式，可选'markdown'或'text'
    :return: 转换后的文本内容
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    target_element = soup.select_one(selector)

    if not target_element:
        return ""

    if output_format == 'text':
        return target_element.get_text(separator='\n', strip=True)
    elif output_format == 'markdown':
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = True
        return converter.handle(target_element.decode_contents()).strip()
    else:
        raise ValueError("不支持的输出格式，请选择'markdown'或'text'")


def crawl_article(url: str):
    if ContentHistory.has_url(url):
        return

    raw_html = fetch_content(url, 20)
    markdown = html_content_converter(raw_html, 'div.left_zw')
    to_file_and_history(url, markdown, '', 'abc', '.md')




