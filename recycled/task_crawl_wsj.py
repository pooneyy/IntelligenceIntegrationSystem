from functools import partial

import Scraper.RequestsScraper
from Tools.RSSFetcher import fetch_feed
from Scraper.PlaywrightRenderedScraper import fetch_content
from Scrubber.HTMLConvertor import html_content_converter
from Scrubber.UnicodeSanitizer import sanitize_unicode_string
from Workflow.CommonFeedsCrawFlow import feeds_craw_flow


feed_list = {
    "Opinion": "https://feeds.content.dowjones.io/public/rss/RSSOpinion",
    "World News": "https://feeds.content.dowjones.io/public/rss/RSSWorldNews",
    "U.S. Business": "https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness",
    "Markets News": "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    "Technology: What's News": "https://feeds.content.dowjones.io/public/rss/RSSWSJD",
    "U.S.": "https://feeds.content.dowjones.io/public/rss/RSSUSnews",
    "Politics": "https://feeds.content.dowjones.io/public/rss/socialpoliticsfeed",
    "Economy": "https://feeds.content.dowjones.io/public/rss/socialeconomyfeed",
    "Real Estate": "https://feeds.content.dowjones.io/public/rss/latestnewsrealestate",
    "Personal Finance": "https://feeds.content.dowjones.io/public/rss/RSSPersonalFinance"
}

# 要付费
