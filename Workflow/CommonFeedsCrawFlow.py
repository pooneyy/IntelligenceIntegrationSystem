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
from Tools.CrawlRecord import CrawlRecord, STATUS_ERROR, STATUS_SUCCESS, STATUS_DB_ERROR, STATUS_UNKNOWN
from Tools.CrawlStatistics import CrawlStatistics
from Tools.ProcessCotrolException import ProcessSkip, ProcessError, ProcessTerminate, ProcessProblem, ProcessIgnore
from Tools.RSSFetcher import FeedData

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CRAWL_ERROR_THRESHOLD = 3

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


# ------------------------------- Cache management -------------------------------

_lock = threading.Lock()
_uncommit_content_cache = { }


def cache_content(url: str, content: any):
    with _lock:
        _uncommit_content_cache[url] = content


def get_cached_content(url: str) -> any:
    with _lock:
        return _uncommit_content_cache.get(url, None)


def drop_cached_content(url: str):
    with _lock:
        if url in _uncommit_content_cache:
            del _uncommit_content_cache[url]


# --------------------------------- Helper Functions ---------------------------------

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


# ---------------------------------- Main process ----------------------------------

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
    print(f'{prefix} submit to URL: {submit_ihub_url}.')

    crawl_record = CrawlRecord(
        ['crawl_record', 'flow_name'])
    crawl_statistics = CrawlStatistics()

    # ------------------------------------------------------------------------------------------------------------------

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
            # ----------------------------------- Fetch and Parse feeds -----------------------------------

            print()
            print('=' * 100)
            print(f'{prefix} Process feed: {feed_name} : {feed_url}')

            result = fetch_feed(feed_url)
            if result.fatal:
                crawl_record.increment_error_count(feed_url)
                crawl_statistics.counter_log(stat_name, 'fail', '\n'.join(result.errors))
                continue
            else:
                crawl_statistics.counter_log(stat_name, 'success')

            feed_statistics['total'] = len(result.entries)

            # ----------------------------------- Process Articles in Feed ----------------------------------

            for article in result.entries:
                feed_statistics['index'] += 1
                article_link = article.link

                # ----------------------------------- Check Duplication ----------------------------------

                url_status = crawl_record.get_url_status(article_link, from_db=False)
                if url_status >= STATUS_SUCCESS:
                    raise ProcessSkip('already exists', article_link)
                elif url_status <= STATUS_UNKNOWN:
                    pass        # <- Can continue running here
                elif url_status == STATUS_ERROR:
                    url_error_count = crawl_record.get_error_count(article_link, from_db=False)
                    if url_error_count < 0:
                        raise ProcessProblem('db_error', article_link)
                    if url_error_count >= CRAWL_ERROR_THRESHOLD:
                        raise ProcessSkip('max retry exceed', article_link)
                    else:
                        pass    # <- Can continue running here
                else:
                    raise ProcessProblem('db_error', article_link)

                # Also keep this check to make it compatible
                if has_url(article_link):
                    raise ProcessSkip('already exists', article_link)

                # ------------------------------- Fetch and Parse articles ------------------------------

                cached_data = get_cached_content(article_link)
                if cached_data:
                    collected_data = cached_data
                else:
                    text, error_place = fetch_process_article(article_link, fetch_content, scrubbers)

                    if error_place == 'fetch':
                        pass

                    if not text:
                        # logger.error(f'{prefix}   |--Got empty content when applying scrubber {str(scrubber)}.')
                        crawl_statistics.sub_item_log(stat_name, article_link, error_place + ' emtpy')
                        raise ProcessIgnore('fetch content empty')

                    # --------------------------------- Record and Persists ---------------------------------

                    success, file_path = to_file_and_history(
                        article_link, text, article.title, feed_name, '.md')
                    # Actually, with CrawlRecord, we don't need this.
                    if not success:
                        # logger.error(f'{prefix}   |--Save content {file_path} fail.')
                        print('x', end='', flush=True)
                        crawl_statistics.sub_item_log(stat_name, article_link, 'persists fail')
                        raise ProcessProblem('persists_error')

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
                    result = _intelligence_sink(submit_ihub_url, collected_data, 10)
                    if result.get('status', 'success') == 'error' and not cached_data:
                        cache_content(article_link, collected_data)
                        raise ProcessProblem('commit_error')
                    else:
                        drop_cached_content(submit_ihub_url)

                feed_statistics['success'] += 1
                crawl_record.record_url_status(article_link, STATUS_SUCCESS)
                crawl_statistics.sub_item_log(stat_name, article_link, 'success')

                print('.', end='', flush=True)

        except ProcessSkip as e:
            feed_statistics['skip'] += 1
            print('*', end='', flush=True)

        except ProcessIgnore as e:
            feed_statistics['skip'] += 1
            print('o', end='', flush=True)

        except ProcessProblem as e:
            if e.problem == 'db_error':
                # DB error, not content error, just ignore and retry at nex loop.
                logger.error('Crawl record DB Error.')

            elif e.problem == 'persists_error':
                # Persists error, actually once we're starting use CrawRecord. We don't need this anymore
                logger.error('Record and persists error.')

            elif e.problem == 'commit_error':
                # Commit error. Maybe the IHub is not ready yet. Data cached, just continue.
                logger.error('Record and persists error.')
            else:
                pass

        except Exception as e:
            print('x', end='', flush=True)
            logger.error(f"{prefix} Process feed fail: {feed_url} - {str(e)}")
            crawl_statistics.counter_log(stat_name, 'exception')

        # ---------------------------------------- Log feed statistics ----------------------------------------

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

    # ----------------------------------------- Log all feeds counter -----------------------------------------

    crawl_statistics.dump_counters(['flow_name'])

    print(f"{prefix} Finished one loop and rest for {update_interval_s} seconds ...")

    # ------------------------------------------ Delay and Wait for Next Loop ------------------------------------------

    # Wait for next loop and check event per 5s.
    # noinspection PyTypeChecker
    for _ in range(update_interval_s // 5):
        if stop_event.is_set():
            break
        time.sleep(5)


