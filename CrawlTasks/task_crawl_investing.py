from functools import partial

import Scraper.RequestsScraper
from GlobalConfig import APPLIED_NATIONAL_TIMEOUT_MS
from MyPythonUtility.easy_config import EasyConfig
from ServiceEngine import ServiceContext
from Tools.RSSFetcher import fetch_feed
from Scraper.PlaywrightRenderedScraper import fetch_content
from Scrubber.HTMLConvertor import html_content_converter
from Scrubber.UnicodeSanitizer import sanitize_unicode_string
from Workflow.CommonFeedsCrawFlow import feeds_craw_flow

# https://www.investing.com/

feed_list = {
    "Analysis": "https://www.investing.com/rss/121899.rss",
    "Market Overview": "https://www.investing.com/rss/market_overview.rss",

    "SWOT Analysis News": "https://www.investing.com/rss/news_1060.rss",
    "Stock Analyst Ratings": "https://www.investing.com/rss/news_1061.rss",
    "Cryptocurrency News": "https://www.investing.com/rss/news_301.rss",
    "Company News": "https://www.investing.com/rss/news_356.rss",
    "Insider Trading News": "https://www.investing.com/rss/news_357.rss",
    "Forex News": "https://www.investing.com/rss/news_1.rss",
    "Commodities & Futures News": "https://www.investing.com/rss/news_11.rss",
    "Stock Market News": "https://www.investing.com/rss/news_25.rss",
    "Economic Indicators News": "https://www.investing.com/rss/news_95.rss",
    "Economy News": "https://www.investing.com/rss/news_14.rss",
}


config: EasyConfig | None = None


def module_init(service_context: ServiceContext):
    global config
    config = service_context.config


def start_task(stop_event):
    feeds_craw_flow('investing',
                    feed_list,
                    stop_event,
                    config,
                    15 * 60,

                    partial(fetch_feed, scraper=Scraper.RequestsScraper, proxy=config.get('collector.global_site_proxy', {})),
                    partial(fetch_content, timeout_ms=APPLIED_NATIONAL_TIMEOUT_MS, proxy=config.get('collector.global_site_proxy', {}), format='lxml'),
                    [
                        partial(html_content_converter, selector='div[id="article"]'),
                        partial(sanitize_unicode_string, max_length=10240 * 5)
                    ])

