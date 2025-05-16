import logging
import traceback
import Scraper.RequestsScraper
from Tools.RSSFetcher import fetch_feed


logger = logging.getLogger(__name__)


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
        try:
            print(f'Process feed: {feed_name} : {feed_url}')
            result = fetch_feed(feed_url, Scraper.RequestsScraper, {})

            for article in result['entries']:
                article_link = article['link']
        except Exception as e:
            print(f"Process feed fail: {feed_url} - {str(e)}")
            print(traceback.format_exc())
