import time
import logging
import traceback
import threading
from typing import Callable, TypedDict, Dict, List

from Tools.ContentHistory import ContentDB, has_url, get_base_dir
from Streamer.ToFileAndHistory import to_file_and_history


class FetchFeedEntries(TypedDict):
    link: str
    title: str


class FetchFeedResult(TypedDict):
    entries: List[FetchFeedEntries]


class FetchContentResult(TypedDict):
    content: str



def feeds_craw_flow(flow_name: str, feeds: Dict[str, str], stop_event: threading.Event, update_interval_s: int,
                    fetch_feed: Callable[[str], FetchFeedResult],
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
    :param update_interval_s: The polling update interval in second.

    :param fetch_feed: The function to fetch feed. Function declaration:
                        fetch_feed(feed_url: str) -> dict
    :param fetch_content: The function to fetch web content by url. Function declaration:
                        fetch_content(article_link: str) -> dict
    :param scrubbers: The functions to process scrubbed text. Function declaration:
                        scrubber(text: str) -> str

    :return: None
    """
    logging.info(f'[{flow_name}]: starts work.')

    db = ContentDB(get_base_dir())

    for feed_name, feed_url in feeds.items():
        if stop_event.is_set():
            break

        statistics = {
            'total': 0,
            'index': 0,
            'current': 0,
            'success': 0,
            'skip': 0,
        }

        try:
            print(f'Process feed: {feed_name} : {feed_url}')
            result = fetch_feed(feed_url)
            statistics['total'] = len(result['entries'])

            for article in result['entries']:
                statistics['index'] += 1
                article_link = article['link']

                if has_url(article_link):
                    statistics['skip'] += 1
                    # print(f"|__Skip  article ({statistics['index']}/{statistics['total']}): {article_link}")
                    continue

                statistics['current'] += 1
                print(f"|__Fetch article ({statistics['index']}/{statistics['total']}): {article_link}")

                content = fetch_content(article_link)

                raw_html = content['content']
                if not raw_html:
                    logging.error('  |__Got empty HTML content.')
                    continue

                # TODO: If an article always convert fail. Need a special treatment.

                text = raw_html
                for scrubber in scrubbers:
                    text = scrubber(text)
                    if not text:
                        logging.error(f'  |__Got empty content when applying scrubber {str(scrubber)}.')
                        break
                if not text:
                    continue

                success, file_path = to_file_and_history(
                    article_link, text, article['title'], feed_name, '.md', db)
                if not success:
                    logging.error(f'  |__Save content {file_path} fail.')
                    continue

                statistics['success'] += 1

        except Exception as e:
            print(f"Process feed fail: {feed_url} - {str(e)}")
            print(traceback.format_exc())

        logging.info(f"Feed: {feed_name} finished.\n"
                     f"     Total: {statistics['total']}\n"
                     f"     Success: {statistics['success']}\n"
                     f"     Skip: {statistics['skip']}\n"
                     f"     Fail: {statistics['total'] - statistics['success'] - statistics['skip']}\n")

    logging.info(f"[{flow_name}]: Finished one loop and rest for {update_interval_s} seconds ...")
    db.close()

    # Wait for next loop and check event per 5s.
    # noinspection PyTypeChecker
    for _ in range(update_interval_s // 5):
        if stop_event.is_set():
            break
        time.sleep(5)


