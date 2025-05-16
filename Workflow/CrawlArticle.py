"""
Use the methods in this document to organize the process of
    check history -> crawling -> cleaning -> recording history -> submitting results
"""

from Tools import ContentHistory
from Scraper.PlaywrightRenderedScraper import fetch_content
from Scrubber.HTMLConvertor import html_content_converter
from Streamer.ToFileAndHistory import to_file_and_history


def crawl_article(url: str):
    if ContentHistory.has_url(url):
        return

    content = fetch_content(url, 20 * 1000)
    raw_html = content['content']
    markdown = html_content_converter(raw_html, 'div.left_zw')
    to_file_and_history(url, markdown, '', 'UnicodeSanitizer', '.md')




