from functools import partial

import Scraper.PlaywrightRawScraper
from GlobalConfig import APPLIED_PROXY, APPLIED_NATIONAL_TIMEOUT_MS
from MyPythonUtility.easy_config import EasyConfig
from ServiceEngine import ServiceContext
from Tools.RSSFetcher import fetch_feed
from Scraper.PlaywrightRenderedScraper import fetch_content
from Scrubber.HTMLConvertor import html_content_converter
from Scrubber.UnicodeSanitizer import sanitize_unicode_string
from Workflow.CommonFeedsCrawFlow import feeds_craw_flow

# https://www.rfi.fr/

feed_list = {
    "Message": "https://www.rfi.fr/fr/contenu/general/rss",
    "Africa": "https://www.rfi.fr/afrique/rss",
    "Americas": "https://www.rfi.fr/ameriques/rss",
    "Asia Pacific": "https://www.rfi.fr/asie-pacifique/rss",
    "Europe": "https://www.rfi.fr/europe/rss",
    "France": "https://www.rfi.fr/france/rss",
    "Middle East": "https://www.rfi.fr/moyen-orient/rss",
    "Economy": "https://www.rfi.fr/economie/rss",
    "Science": "https://www.rfi.fr/science/rss",
}


config: EasyConfig | None = None


def module_init(service_context: ServiceContext):
    global config
    config = service_context.config


def start_task(stop_event):
    feeds_craw_flow('rfi',
                    feed_list,
                    stop_event,
                    config,
                    15 * 60,

                    partial(fetch_feed, scraper=Scraper.PlaywrightRawScraper, proxy=config.get('collector.global_site_proxy', {})),
                    partial(fetch_content, timeout_ms=APPLIED_NATIONAL_TIMEOUT_MS, proxy=config.get('collector.global_site_proxy', {}), format='lxml'),
                    [
                        partial(html_content_converter, selectors='article.t-content__article-wrapper'),
                        partial(sanitize_unicode_string, max_length=10240 * 5)
                    ])

