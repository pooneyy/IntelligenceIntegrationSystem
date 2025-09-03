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

# https://sputniknews.cn/

feed_list = {
    "All": "https://sputniknews.cn/export/rss2/archive/index.xml",
}


config: EasyConfig | None = None


def module_init(service_context: ServiceContext):
    global config
    config = service_context.config


def start_task(stop_event):
    feeds_craw_flow('sputniknews',
                    feed_list,
                    stop_event,
                    config,
                    15 * 60,

                    partial(fetch_feed, scraper=Scraper.RequestsScraper, proxy=config.get('collector.cn_site_proxy', {})),
                    partial(fetch_content, timeout_ms=APPLIED_NATIONAL_TIMEOUT_MS, proxy=config.get('collector.cn_site_proxy', {}), format='lxml'),
                    [
                        partial(html_content_converter, selectors=['.article__title', 'div.article__body']),
                        partial(sanitize_unicode_string, max_length=10240 * 5)
                    ])

