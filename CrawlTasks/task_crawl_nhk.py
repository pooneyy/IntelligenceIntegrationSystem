from functools import partial

import Scraper.RequestsScraper
from GlobalConfig import APPLIED_NATIONAL_TIMEOUT_MS
from MyPythonUtility.easy_config import EasyConfig
from ServiceEngine import ServiceContext
from Tools.RSSFetcher import fetch_feed
from Scraper.RequestsScraper import fetch_content
from Scrubber.HTMLConvertor import html_content_converter
from Scrubber.UnicodeSanitizer import sanitize_unicode_string
from Workflow.CommonFeedsCrawFlow import feeds_craw_flow

# https://www.nhk.or.jp/

feed_list = {
    "Main news": "https://www.nhk.or.jp/rss/news/cat0.xml",
    "Social": "https://www.nhk.or.jp/rss/news/cat1.xml",
    "Politics": "https://www.nhk.or.jp/rss/news/cat4.xml",
    "Economic": "https://www.nhk.or.jp/rss/news/cat5.xml",
    "International": "https://www.nhk.or.jp/rss/news/cat6.xml",
}


config: EasyConfig | None = None


def module_init(service_context: ServiceContext):
    global config
    config = service_context.config


def start_task(stop_event):
    feeds_craw_flow('nhk',
                    feed_list,
                    stop_event,
                    config,
                    15 * 60,

                    partial(fetch_feed, scraper=Scraper.RequestsScraper, proxy=config.get('collector.global_site_proxy', {})),
                    partial(fetch_content, timeout_ms=APPLIED_NATIONAL_TIMEOUT_MS, proxy=config.get('collector.global_site_proxy', {}), format='lxml'),
                    [
                        partial(html_content_converter, selectors=['.module--detail-content']),
                        partial(sanitize_unicode_string, max_length=10240 * 5)
                    ])

