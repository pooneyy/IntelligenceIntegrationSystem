from functools import partial

import Scraper.RequestsScraper
from GlobalConfig import APPLIED_PROXY, APPLIED_NATIONAL_TIMEOUT_MS
from MyPythonUtility.easy_config import EasyConfig
from ServiceEngine import ServiceContext
from Tools.RSSFetcher import fetch_feed
from Scraper.RequestsScraper import fetch_content
from Scrubber.HTMLConvertor import html_content_converter
from Scrubber.UnicodeSanitizer import sanitize_unicode_string
from Workflow.CommonFeedsCrawFlow import feeds_craw_flow

# https://www.dw.com/

feed_list = {
    # "Top Stories": "https://rss.dw.com/rdf/rss-en-top",
    "Germany": "https://rss.dw.com/rdf/rss-en-ger",
    "World": "https://rss.dw.com/rdf/rss-en-world",
    "Europe": "https://rss.dw.com/rdf/rss-en-eu",
    "Africa": "https://rss.dw.com/rdf/rss-en-africa",
    "Business": "https://rss.dw.com/rdf/rss-en-bus",
    "Science": "https://rss.dw.com/xml/rss_en_science",
    "Asia": "https://rss.dw.com/rdf/rss-en-asia",
}


config: EasyConfig | None = None


def module_init(service_context: ServiceContext):
    global config
    config = service_context.config


def start_task(stop_event):
    feeds_craw_flow('dw',
                    feed_list,
                    stop_event,
                    config,
                    15 * 60,

                    partial(fetch_feed, scraper=Scraper.RequestsScraper, proxy=config.get('collector.global_site_proxy', {})),
                    partial(fetch_content, timeout_ms=APPLIED_NATIONAL_TIMEOUT_MS, proxy=config.get('collector.global_site_proxy', {}), format='lxml'),
                    [
                        partial(html_content_converter, selectors='div.content-area'),
                        partial(sanitize_unicode_string, max_length=10240 * 5)
                    ])

