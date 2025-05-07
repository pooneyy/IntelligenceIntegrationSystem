import os
import re
import json
import threading
import time

import chardet
import sqlite3
import hashlib
import traceback
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Comment
from datetime import datetime

from pydantic.class_validators import partial

from IntelligenceHub import DEFAULT_IHUB_PORT, post_collected_intelligence
from RSSFetcher import fetch_feed
from typing import Dict, List, Any, Optional
from markdownify import markdownify as md

from Scraper.PlaywrightRenderedScraper import fetch_content
from utility.DictPrinter import DictPrinter


def html_to_clean_md(html: str) -> str:
    # 输入验证
    if not isinstance(html, (str, bytes)):
        raise ValueError(f"Invalid input type {type(html)}, expected str/bytes")

    # 编码处理
    if isinstance(html, bytes):
        detected_enc = chardet.detect(html)['encoding'] or 'utf-8'
        html = html.decode(detected_enc, errors='replace')

    # 容错解析
    try:
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        soup = BeautifulSoup(html, 'html.parser')

    # 深度清理
    UNWANTED_TAGS = ['script', 'style', 'nav', 'footer', 'form', 'noscript']
    for tag in soup(UNWANTED_TAGS + ['svg', 'iframe']):
        tag.decompose()

    for comment in soup.find_all(text=lambda t: isinstance(t, Comment)):
        comment.extract()

    # 转换配置
    markdown = md(
        html,
        strip=['script', 'style', 'nav', 'footer', 'form', 'noscript'],
        heading_style="ATX"
    )

    # 后处理
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    markdown = re.sub(r'[ \t]{2,}', ' ', markdown)
    return markdown.strip()


def _generate_filepath(article: dict, base_dir: str = "output") -> Path:
    """生成带校验的文件存储路径

    Args:
        article: 包含标题、URL等元数据的字典
        base_dir: 基础存储目录

    Returns:
        Path: 最终文件路径对象
    """
    # 1. 创建分类目录（参考网页1的目录结构设计）
    feed_dir = _create_feed_dir(base_dir, article['feed_name'])

    # 2. 文件名清洗（结合网页2的文件名处理规则）
    clean_title = re.sub(r'[\\/*?:"<>|]', '_', article['title'].strip())
    clean_title = re.sub(r'\s+', ' ', clean_title)[:100]  # 限制长度

    # 3. 内容哈希生成（参考网页5的校验机制）
    content_hash = hashlib.md5(article['content_markdown'].encode()).hexdigest()[:6]

    # 4. 构建完整文件名（参考网页7的时间戳策略）
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{clean_title}_{content_hash}_{timestamp}.md"

    # 5. 路径冲突检测（参考网页2的防重复机制）
    final_path = Path(feed_dir) / filename
    if final_path.exists():
        # 添加毫秒级时间戳避免冲突
        timestamp_ms = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        filename = f"{clean_title}_{content_hash}_{timestamp_ms}.md"
        final_path = Path(feed_dir) / filename

    return final_path

def _create_feed_dir(base_dir: str, feed_name: str) -> str:
    """创建分类目录（参考网页1的目录结构）"""
    # 清洗目录名中的特殊字符
    clean_feed = re.sub(r'[\\/*?:"<>|]', '', feed_name.strip())
    feed_dir = os.path.join(base_dir, clean_feed)

    # 原子化目录创建（参考网页5的容错机制）
    os.makedirs(feed_dir, exist_ok=True)
    return feed_dir

def _get_content_checksum(content: str) -> str:
    """生成内容摘要"""
    return hashlib.md5(content.encode()).hexdigest()

def _write_md_file(filepath: Path, content: str):
    """带校验的写入"""
    checksum = _get_content_checksum(content)

    # 校验现有文件
    if filepath.exists():
        with open(filepath, 'r') as f:
            existing = _get_content_checksum(f.read())
            if existing == checksum:
                return

    # 写入新文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def _parse_pub_date(entry) -> str:
    """Standardize publication date format"""
    if hasattr(entry, 'published_parsed'):
        return datetime(*entry.published_parsed[:6]).isoformat()
    if hasattr(entry, 'updated_parsed'):
        return datetime(*entry.updated_parsed[:6]).isoformat()
    return 'Unknown'


class RSSProcessor:
    """RSS feed processor with modular functions for JSON reading, feed parsing and content downloading"""

    def __init__(self, article_handlers=None, proxy=None):
        self.feeds = {}
        self.article_handlers = article_handlers \
            if article_handlers else (
            self.article_default_handlers())
        self.proxy = proxy
        self.articles = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) RSSProcessor/1.0'
        })
        self.url_map = {}  # 内存缓存
        self._init_storage()

    # ----------------------------- Storage -----------------------------

    def _init_storage(self):
        """初始化持久化存储表"""
        self.conn = sqlite3.connect('rss_records.db', timeout=10)
        self._create_table()
        self._load_records()
        self.conn.execute('PRAGMA journal_mode=WAL')

    def _create_table(self):
        """创建存储表结构"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feed_history (
                url TEXT PRIMARY KEY,
                filepath TEXT NOT NULL,
                checksum TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def _load_records(self):
        """加载历史记录到内存"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT url, filepath FROM feed_history')
        self.url_map = {row[0]: row[1] for row in cursor.fetchall()}

    # ---------------------------------------------------------------------

    def process_all_feeds(self, feeds: dict):
        self.feeds = feeds
        for feed_name, feed_url in self.feeds.items():
            try:
                print(f'Process feed: {feed_name} : {feed_url}')

                result = self.parse_feed(feed_url)
                for article in result['entries']:
                    article['feed_name'] = feed_name
                    article['feed_url'] = feed_url
                    self._process_article(article)
            except Exception as e:
                print(f"Process feed fail: {feed_url} - {str(e)}")
                print(traceback.format_exc())

    def parse_feed(self, url: str) -> Dict:
        """Parse a single RSS feed and extract article metadata
        Args:
            url (str): RSS feed URL
        Returns:
            List[Dict]: List of articles with metadata
        """
        try:
            result = fetch_feed(url, self.proxy)
            if 'entries' not in result:
                raise ValueError(f'Feed parse error: {result["errors"]}')
            return result
        except Exception as e:
            print(f"Error parsing {url}: {str(e)}")
            return {'entries': [], 'errors': str(e)}

    def _process_article(self, article):
        url = article['link']

        # 去重检查
        if url in self.url_map:
            print(f'  - Skip processed article: {article["title"]}')
            return

        print(f'  - Fetching article: {article["title"]}')
        result = fetch_content(url, 25000)

        html = result['content']
        if not html:
            print(f'  ! Article empty: {article["title"]}')
            return
        markdown = html_to_clean_md(html)

        article['content_html'] = html
        article['content_markdown'] = markdown

        if isinstance(self.article_handlers, list):
            for handler in self.article_handlers:
                try:
                    handler(article)
                except Exception as e:
                    print(f'Article handler error: {str(e)}')

    def set_article_handlers(self, article_handlers: list):
        self.article_handlers = article_handlers

    def article_default_handlers(self) -> List:
        return [
            self.article_handler_append,
            self.article_handler_to_file,
            self.article_handler_log_history
        ]

    def article_handler_append(self, article: dict):
        self.articles.append(article)

    def article_handler_to_file(self, article: dict):
        markdown = article['content_markdown']
        filepath = _generate_filepath(article)
        article['filepath'] = filepath

        _write_md_file(filepath, markdown)

    def article_handler_log_history(self, article: dict):
        with self.conn:
            try:
                url = article['link']
                filepath = article.get('filepath', '')

                # 更新记录
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO feed_history (url, filepath)
                    VALUES (?, ?)
                ''', (url, str(filepath)))

                # 更新内存缓存
                self.url_map[url] = str(filepath)
            except sqlite3.IntegrityError:
                print(f"Conflict detect: {url} is handling by other process.")


CONFIG_DEFAULT_VALUE = {
    'feeds': {},
    'proxy': {},
    'polling_interval_s': 10 * 60,
    'intelligence_hub_url': f'http://localhost:{DEFAULT_IHUB_PORT}'
}


def load_json_config(rss_cfg_file: str, default_config: Optional[Dict]):
    try:
        default_config = default_config or { }
        with open(rss_cfg_file, 'r', encoding='utf-8') as f:
            json_config = json.load(f)
            return {
                k: json_config.get(k, default_config.get(k, v))
                for k, v in CONFIG_DEFAULT_VALUE.items()
            }
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise ValueError(f"Invalid JSON file: {str(e)}") from e


class FeedProcessorManager:
    def __init__(self):
        self.threads: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def start_processing_task(self,
                              rss_cfg_file: str,
                              default_config: Optional[Dict] = None,
                              force: bool = False) -> bool:
        try:
            config = load_json_config(rss_cfg_file, default_config)
        except ValueError as e:
            print(f"Config file f{rss_cfg_file} load failed: {str(e)}")
            return False

        if not config['feeds']:
            print(f"Config file f{rss_cfg_file} has no feeds - ignore.")
            return False

        with self.lock:
            if rss_cfg_file in self.threads:
                if not force:
                    return False
                self._stop_thread(rss_cfg_file)

            stop_event = threading.Event()
            thread = threading.Thread(
                target=self._process_loop,
                args=(rss_cfg_file, config, stop_event),
                daemon=True
            )
            thread.start()

            self.threads[rss_cfg_file] = {
                "thread": thread,
                "stop_event": stop_event,
                "stats": {
                    "executions": 0,
                    "successes": 0,
                    "failures": 0,
                    "total_articles": 0,
                    "last_execution": None
                }
            }
            return True

    def _process_loop(self, filename: str, config: dict, stop_event: threading.Event):
        feeds = config['feeds']
        proxy = config['proxy']
        interval = config['polling_interval_s']
        post_url = config['intelligence_hub_url']

        print(f'Start task for: {filename}')

        while not stop_event.is_set():
            start_time = time.time()
            try:
                processor = RSSProcessor(proxy=proxy)

                article_handlers = processor.article_default_handlers()
                article_handlers.insert(1, partial(self._article_handler_post_to_hub, post_url))
                processor.set_article_handlers(article_handlers)

                processor.process_all_feeds(feeds)

                with self.lock:
                    self.threads[filename]['stats']['executions'] += 1
                    self.threads[filename]['stats']['successes'] += 1
                    # self.threads[filename]['stats']['total_articles'] += len(articles)
                    self.threads[filename]['stats']['last_execution'] = start_time
            except Exception as e:
                with self.lock:
                    self.threads[filename]['stats']['executions'] += 1
                    self.threads[filename]['stats']['failures'] += 1
                print(f"Processing failed [{filename}]: {str(e)}")
                traceback.print_exc()

            elapsed = time.time() - start_time
            sleep_time = max(0, int(interval - elapsed))
            stop_event.wait(sleep_time)

    def _article_handler_post_to_hub(self, post_url: str, article: dict):
        try:
            print(DictPrinter.pretty_print(
                article,
                indent=2,
                sort_keys=True,
                colorize=True,
                max_depth=4
            ))
            # post_collected_intelligence(post_url, article)
        except Exception as e:
            print(f'Post to hub fail: {str(e)}')

    def get_task_stats(self) -> Dict[str, Dict]:
        """获取当前所有任务的统计信息"""
        with self.lock:
            return {
                filename: info['stats'].copy()
                for filename, info in self.threads.items()
            }

    def stop_task(self, filename: str) -> bool:
        with self.lock:
            if filename not in self.threads:
                return False
            self._stop_thread(filename)
            return True

    def _stop_thread(self, filename: str):
        self.threads[filename]['stop_event'].set()
        self.threads[filename]['thread'].join()
        del self.threads[filename]

    def stop_all_tasks(self):
        with self.lock:
            for filename in list(self.threads.keys()):
                self._stop_thread(filename)


def collect(feeds: dict, proxy: dict) -> List:
    try:
        processor = RSSProcessor(proxy=proxy)
        processor.process_all_feeds(feeds)
        return processor.articles
    except Exception as e:
        print(f"Feed collect fail: {str(e)}")
        print(traceback.format_exc())
        return []


def collect_by_json_configs(feed_configs: List[str], default_config: dict):
    for feed_cfg in feed_configs:
        try:
            config = load_json_config(feed_cfg, default_config)
            print(f'{config['config_file']}: Feeds count: {len(config['feeds'])}')

            articles = collect(config['feeds'], config['proxy'])
            print(f"{config['config_file']}: Got {len(articles)} articles.")
        except Exception as e:
            print(f'Collect config {feed_cfg} Error: str(e)')


# ----------------------------------------------------------------------------------------------------------------------

def main():
    proxy_config = {
        "http": "socks5://127.0.0.1:10808",
        "https": "socks5://127.0.0.1:10808"
    }

    # feed_configs = ['feeds_test.json']
    feed_configs = ['feeds_tech.json', 'feeds_ai.json']
    # collect_by_json_configs(feed_configs, {'proxy': {}})

    fpm = FeedProcessorManager()
    for json_file in feed_configs:
        fpm.start_processing_task(json_file)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()