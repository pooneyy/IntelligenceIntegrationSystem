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

# https://www.abc.net.au/

feed_list = {
    "Top Stories": "https://www.abc.net.au/news/feed/10719986/rss.xml",
    "World": "https://www.abc.net.au/news/feed/104217382/rss.xml",
    "Business": "https://www.abc.net.au/news/feed/104217374/rss.xml",
    "Politics": "https://www.abc.net.au/news/feed/104217372/rss.xml",
}


config: EasyConfig | None = None


def module_init(service_context: ServiceContext):
    global config
    config = service_context.config


def start_task(stop_event):
    feeds_craw_flow('abc',
                    feed_list,
                    stop_event,
                    config,
                    15 * 60,

                    partial(fetch_feed, scraper=Scraper.RequestsScraper, proxy=config.get('collector.global_site_proxy', {})),
                    partial(fetch_content, timeout_ms=APPLIED_NATIONAL_TIMEOUT_MS, proxy=config.get('collector.global_site_proxy', {}), format='lxml'),
                    [
                        partial(html_content_converter, selectors=['div[class*="ArticleHeadlineTitle_container"]', 'div[class*="ArticleWeb_article"]']),
                        partial(sanitize_unicode_string, max_length=10240 * 5)
                    ])

