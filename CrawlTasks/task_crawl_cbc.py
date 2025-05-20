from functools import partial

import Scraper.RequestsScraper
from GlobalConfig import APPLIED_PROXY, APPLIED_NATIONAL_TIMEOUT_MS
from Tools.RSSFetcher import fetch_feed
from Scraper.PlaywrightRenderedScraper import fetch_content
from Scrubber.HTMLConvertor import html_content_converter
from Scrubber.UnicodeSanitizer import sanitize_unicode_string
from Workflow.CommonFeedsCrawFlow import feeds_craw_flow


# https://www.cbc.ca/rss/

feed_list = {
    "World News": "https://www.cbc.ca/webfeed/rss/rss-world",
    "Canada News": "https://www.cbc.ca/webfeed/rss/rss-canada",
    "Business News": "https://www.cbc.ca/webfeed/rss/rss-business",
    "Technology News": "https://www.cbc.ca/webfeed/rss/rss-technology",
}


def module_init(service_context):
    pass


def start_task(stop_event):
    feeds_craw_flow('cbc', feed_list, stop_event, 15 * 60,
                    partial(fetch_feed, scraper=Scraper.RequestsScraper, proxy=APPLIED_PROXY),
                    partial(fetch_content, timeout_ms=APPLIED_NATIONAL_TIMEOUT_MS, proxy=APPLIED_PROXY),
                    [
                        partial(html_content_converter, selector='div[data-cy="storyWrapper"]'),
                        partial(sanitize_unicode_string, max_length=10240)
                    ])

