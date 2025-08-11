from functools import partial

import Scraper.RequestsScraper
from GlobalConfig import APPLIED_PROXY, APPLIED_NATIONAL_TIMEOUT_MS
from MyPythonUtility.easy_config import EasyConfig
from ServiceEngine import ServiceContext
from Tools.RSSFetcher import fetch_feed
from Scraper.PlaywrightRenderedScraper import fetch_content
from Scrubber.HTMLConvertor import html_content_converter
from Scrubber.UnicodeSanitizer import sanitize_unicode_string
from Workflow.CommonFeedsCrawFlow import feeds_craw_flow

# https://www.voanews.com/rssfeeds
# Too much video content.

feed_list = {
    "USA": "https://www.voanews.com/api/zqboml-vomx-tpeivmy",
    "All About America": "https://www.voanews.com/api/zb__qtl-vomx-tpeqrtqq",
    "Immigration": "https://www.voanews.com/api/zgvmqyl-vomx-tpe-qvqv",

    "Africa": "https://www.voanews.com/api/z-botl-vomx-tpertmq",
    "East Asia": "https://www.voanews.com/api/zobo_l-vomx-tpepvmv",
    "China News": "https://www.voanews.com/api/zmjuqtl-vomx-tpey_jqq",

    "South & Central Asia": "https://www.voanews.com/api/z_-mqyl-vomx-tpevyvqv",
    "Middle East": "https://www.voanews.com/api/zrbopl-vomx-tpeovm_",
    "Iran": "https://www.voanews.com/api/zvgmqil-vomx-tpeumvqm",

    "Europe": "https://www.voanews.com/api/zjbovl-vomx-tpebvmr",
    "Ukraine": "https://www.voanews.com/api/zt_rqyl-vomx-tpekboq_",
    "Americas": "https://www.voanews.com/api/zoripl-vomx-tpeptmm",

    "Technology": "https://www.voanews.com/api/zyritl-vomx-tpettmq",
    "Economy": "https://www.voanews.com/api/zyboql-vomx-tpetvmi",
}


config: EasyConfig | None = None


def module_init(service_context: ServiceContext):
    global config
    config = service_context.config


def start_task(stop_event):
    feeds_craw_flow('voanews',
                    feed_list,
                    stop_event,
                    config,
                    15 * 60,

                    partial(fetch_feed, scraper=Scraper.RequestsScraper, proxy=config.get('collector.global_site_proxy', {})),
                    partial(fetch_content, timeout_ms=APPLIED_NATIONAL_TIMEOUT_MS, proxy=config.get('collector.global_site_proxy', {})),
                    [
                        partial(html_content_converter, selector='div.wsw, div.m-t-md'),
                        partial(sanitize_unicode_string, max_length=10240)
                    ])

