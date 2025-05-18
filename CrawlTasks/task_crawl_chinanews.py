import logging
import time
import traceback
from typing import Dict

import Scraper.RequestsScraper
from Tools.RSSFetcher import fetch_feed
import Scraper.RequestsScraper
from Tools.RSSFetcher import fetch_feed
from Tools import ContentHistory
from Scraper.PlaywrightRenderedScraper import fetch_content
from Scrubber.HTMLConvertor import html_content_converter
from Scrubber.UnicodeSanitizer import sanitize_unicode_string
from Streamer.ToFileAndHistory import to_file_and_history


feed_list = {
    "即时新闻": "https://www.chinanews.com.cn/rss/scroll-news.xml",
    "要闻导读": "https://www.chinanews.com.cn/rss/importnews.xml",
    "时政新闻": "https://www.chinanews.com.cn/rss/china.xml",
    "国际新闻": "https://www.chinanews.com.cn/rss/world.xml",
    "财经新闻": "https://www.chinanews.com.cn/rss/finance.xml"
}


def module_init(service_context):
    pass


def start_task(stop_event):
    for feed_name, feed_url in feed_list.items():
        if stop_event.is_set():
            break
        try:
            print(f'Process feed: {feed_name} : {feed_url}')
            result = fetch_feed(feed_url, Scraper.RequestsScraper, {})

            for article in result['entries']:
                article_link = article['link']

                if ContentHistory.has_url(article_link):
                    continue

                print(f'|__Fetch article: {article_link}')
                content = fetch_content(article_link, 20 * 1000)

                raw_html = content['content']
                if not raw_html:
                    logging.error('  |__Got empty HTML content.')
                    continue

                # TODO: If an article always convert fail. Need a special treatment.

                markdown = html_content_converter(raw_html, 'div.left_zw')
                if not markdown:
                    logging.error('  |__Got empty content when converting to markdown.')
                    continue

                clean_text = sanitize_unicode_string(markdown, max_length = 10000)
                if not clean_text:
                    logging.error('  |__Got empty content when sanitizing unicode string.')
                    continue

                success, file_path = to_file_and_history(article_link, clean_text, article['title'], feed_name, '.md')
                if not success:
                    logging.error(f'  |__Save content {file_path} fail.')
                    continue

        except Exception as e:
            print(f"Process feed fail: {feed_url} - {str(e)}")
            print(traceback.format_exc())

    # Wait 10 minutes for next loop and check event per 5s.
    # noinspection PyTypeChecker
    for _ in range(10 * 60 // 5):
        if stop_event.is_set():
            break
        time.sleep(5)
