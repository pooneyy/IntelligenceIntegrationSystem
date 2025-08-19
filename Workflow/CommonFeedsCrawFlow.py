import time
import logging
import urllib3
import threading
from uuid import uuid4
from typing import Callable, TypedDict, Dict, List, Tuple

from GlobalConfig import DEFAULT_COLLECTOR_TOKEN
from IntelligenceHub import CollectedData
from MyPythonUtility.easy_config import EasyConfig
from Tools.ContentHistory import has_url
from IntelligenceHubWebService import post_collected_intelligence, DEFAULT_IHUB_PORT
from Streamer.ToFileAndHistory import to_file_and_history
from Tools.CrawlRecord import CrawlRecord
from Tools.CrawlStatistics import CrawlStatistics
from Tools.RSSFetcher import FeedData

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


CRAWL_ERROR_FEED_FETCH = 'Feed fetch error'
CRAWL_ERROR_FEED_PARSE = 'Feed parse error'
CRAWL_ERROR_ARTICLE_FETCH = 'Article fetch error'


class FetchContentResult(TypedDict):
    content: str


# Re-assign this function pointer to re-direct output for debug.
_intelligence_sink: Callable[[str, CollectedData, int], dict] | None = post_collected_intelligence


def set_intelligence_sink(func: Callable[[str, dict, int], dict] | None):
    global _intelligence_sink
    _intelligence_sink = func


def fetch_process_article(article_link: str,
                          fetch_content: Callable[[str], FetchContentResult],
                          scrubbers: List[Callable[[str], str]]) -> Tuple[str, str]:
    content = fetch_content(article_link)

    raw_html = content['content']
    if not raw_html:
        # logger.error(f'{prefix}   |--Got empty HTML content.')
        # craw_statistics.sub_item_log(stat_name, article_link, 'fetch emtpy')
        return '', 'fetch'

    # TODO: If an article always convert fail. Need a special treatment.

    text = raw_html
    for scrubber in scrubbers:
        text = scrubber(text)
        if not text:
            break
    if not text:
        # logger.error(f'{prefix}   |--Got empty content when applying scrubber {str(scrubber)}.')
        # craw_statistics.sub_item_log(stat_name, article_link, 'scrub emtpy')
        return '', 'scrub'

    return text, ''


def feeds_craw_flow(flow_name: str,
                    feeds: Dict[str, str],
                    stop_event: threading.Event,
                    config: EasyConfig,
                    update_interval_s: int,

                    fetch_feed: Callable[[str], FeedData],
                    fetch_content: Callable[[str], FetchContentResult],
                    scrubbers: List[Callable[[str], str]]):
    """
    A common feeds and their articles craw workflow. This workflow works in this sequence:
        fetch_feed -> for each feed: fetch_content -> apply scrubbers

    :param flow_name: The workflow name for logging and tracing.
    :param feeds: The feeds dict like:
                {
                    'feed name': 'feed link'
                }
    :param stop_event: The stop event to quit loop.
    :param config: The easy config. This function will get token from it.
    :param update_interval_s: The polling update interval in second.

    :param fetch_feed: The function to fetch feed. Function declaration:
                        fetch_feed(feed_url: str) -> dict
    :param fetch_content: The function to fetch web content by url. Function declaration:
                        fetch_content(article_link: str) -> dict
    :param scrubbers: The functions to process scrubbed text. Function declaration:
                        scrubber(text: str) -> str

    :return: None
    """
    prefix = f'[{flow_name}]:'
    print(f'{prefix} starts work.')

    submit_ihub_url = config.get('collector.submit_ihub_url', f'http://127.0.0.1:{DEFAULT_IHUB_PORT}')
    collector_tokens = config.get('intelligence_hub_web_service.collector.tokens')
    token = collector_tokens[0] if collector_tokens else DEFAULT_COLLECTOR_TOKEN

    print(f'{prefix} submit token: {token}.')
    print(f'{prefix} submit URL: {submit_ihub_url}.')

    # Use both for compatibility.
    # crawl_record = CrawlRecord(['crawl_record', 'flow_name'])
    crawl_statistics = CrawlStatistics()

    for feed_name, feed_url in feeds.items():
        if stop_event.is_set():
            break
        stat_name = [flow_name, feed_url]

        feed_statistics = {
            'total': 0,
            'index': 0,
            'success': 0,
            'skip': 0,
        }

        try:
            # -------------------------------- Fetch and Parse feeds --------------------------------
            print()
            print('=' * 100)
            print(f'{prefix} Process feed: {feed_name} : {feed_url}')

            result = fetch_feed(feed_url)
            if result.fatal:
                crawl_statistics.counter_log(stat_name, 'fail', '\n'.join(result.errors))
                continue
            else:
                crawl_statistics.counter_log(stat_name, 'success')

            feed_statistics['total'] = len(result.entries)

            # ------------------------------- Fetch and Parse articles ------------------------------

            for article in result.entries:
                feed_statistics['index'] += 1
                article_link = article.link

                if has_url(article_link):
                    feed_statistics['skip'] += 1
                    print('*', end='', flush=True)
                    continue

                text, error_place = fetch_process_article(article_link, fetch_content, scrubbers)

                # print(f"{prefix} --Fetch article ({feed_statistics['index']}/{feed_statistics['total']}): {article_link}")

                # content = fetch_content(article_link)
                #
                # raw_html = content['content']
                # if not raw_html:
                #     # logger.error(f'{prefix}   |--Got empty HTML content.')
                #     crawl_statistics.sub_item_log(stat_name, article_link, 'fetch emtpy')
                #     continue
                #
                # # TODO: If an article always convert fail. Need a special treatment.
                #
                # text = raw_html
                # for scrubber in scrubbers:
                #     text = scrubber(text)
                #     if not text:
                #         break

                if not text:
                    # logger.error(f'{prefix}   |--Got empty content when applying scrubber {str(scrubber)}.')
                    print('o', end='', flush=True)
                    crawl_statistics.sub_item_log(stat_name, article_link, error_place + ' emtpy')
                    continue

                success, file_path = to_file_and_history(
                    article_link, text, article.title, feed_name, '.md')
                if not success:
                    print('x', end='', flush=True)
                    # logger.error(f'{prefix}   |--Save content {file_path} fail.')
                    crawl_statistics.sub_item_log(stat_name, article_link, 'persists fail')
                    continue

                # Post to IHub
                collected_data = CollectedData(
                    UUID=str(uuid4()),
                    token=token,

                    title=article.title,
                    authors=article.authors,
                    content=text,
                    pub_time=article.published,
                    informant=article.link
                )

                if _intelligence_sink:
                    # TODO: Cache submit fail items in memory.
                    _intelligence_sink(submit_ihub_url, collected_data, 10)

                feed_statistics['success'] += 1
                crawl_statistics.sub_item_log(stat_name, article_link, 'success')

                print('.', end='', flush=True)

        except Exception as e:
            print('x', end='', flush=True)
            logger.error(f"{prefix} Process feed fail: {feed_url} - {str(e)}")
            crawl_statistics.counter_log(stat_name, 'exception')

        print(f"{prefix} Feed: {feed_name} finished.\n"
                    f"     Total: {feed_statistics['total']}\n"
                    f"     Success: {feed_statistics['success']}\n"
                    f"     Skip: {feed_statistics['skip']}\n"
                    f"     Fail: {feed_statistics['total'] - feed_statistics['success'] - feed_statistics['skip']}\n")

        print('-' * 80)
        print(crawl_statistics.dump_sub_items(stat_name, statuses=[
            'fetch emtpy', 'scrub emtpy', 'persists fail', 'exception']))
        print()
        print('=' * 100)
        print()

    crawl_statistics.dump_counters(['flow_name'])

    print(f"{prefix} Finished one loop and rest for {update_interval_s} seconds ...")

    # Wait for next loop and check event per 5s.
    # noinspection PyTypeChecker
    for _ in range(update_interval_s // 5):
        if stop_event.is_set():
            break
        time.sleep(5)


