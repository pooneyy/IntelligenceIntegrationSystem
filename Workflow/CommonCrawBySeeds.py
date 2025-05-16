import traceback
# from typing import Dict
#
# import Scraper.RequestsScraper
# from Tools.RSSFetcher import fetch_feed
# from Tools import ContentHistory
# from Scraper.PlaywrightRenderedScraper import fetch_content
# from Scrubber.HTMLConvertor import html_content_converter
# from Streamer.ToFileAndHistory import to_file_and_history
#
#
# def craw_by_feeds(feed_list: Dict[str, str], stop_event):
#     for feed_name, feed_url in feed_list.items():
#         if stop_event.is_set():
#             break
#         try:
#             print(f'Process feed: {feed_name} : {feed_url}')
#             result = fetch_feed(feed_url, Scraper.RequestsScraper, {})
#
#             for article in result['entries']:
#                 article_link = article['link']
#
#                 if ContentHistory.has_url(article_link):
#                     return
#
#                 content = fetch_content(article_link, 20 * 1000)
#                 raw_html = content['content']
#
#                 markdown = html_content_converter(raw_html, 'div.left_zw')
#
#                 to_file_and_history(article_link, markdown, '', 'UnicodeSanitizer', '.md')
#
#         except Exception as e:
#             print(f"Process feed fail: {feed_url} - {str(e)}")
#             print(traceback.format_exc())

