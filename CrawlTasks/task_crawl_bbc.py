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

# https://www.bbc.com/

feed_list = {
    "Top Stories": "http://feeds.bbci.co.uk/news/rss.xml",

    "Africa": "http://feeds.bbci.co.uk/news/world/africa/rss.xml",
    "Asia": "http://feeds.bbci.co.uk/news/world/asia/rss.xml",
    "Europe": "http://feeds.bbci.co.uk/news/world/europe/rss.xml",
    "Latin America": "http://feeds.bbci.co.uk/news/world/latin_america/rss.xml",
    "Middle East": "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    "US & Canada": "http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
    "England": "http://feeds.bbci.co.uk/news/england/rss.xml",
    "Northern Ireland": "http://feeds.bbci.co.uk/news/northern_ireland/rss.xml",
    "Scotland": "http://feeds.bbci.co.uk/news/scotland/rss.xml",
    "Wales": "http://feeds.bbci.co.uk/news/wales/rss.xml",
}


config: EasyConfig | None = None


def module_init(service_context: ServiceContext):
    global config
    config = service_context.config


def start_task(stop_event):
    feeds_craw_flow('bbc',
                    feed_list,
                    stop_event,
                    config,
                    15 * 60,

                    partial(fetch_feed, scraper=Scraper.RequestsScraper, proxy=config.get('collector.global_site_proxy', {})),
                    partial(fetch_content, timeout_ms=APPLIED_NATIONAL_TIMEOUT_MS, proxy=config.get('collector.global_site_proxy', {}), format='lxml'),
                    [
                        partial(html_content_converter, selector='main[id="main-content"]'),
                        partial(sanitize_unicode_string, max_length=10240 * 5)
                    ])

