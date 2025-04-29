import os
import re
import json
import sqlite3
import hashlib
import traceback
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from RSSFetcher import fetch_feed
from typing import Dict, List
from markdownify import markdownify as md

from Scraper.PlaywrightRenderedScraper import fetch_web_content


def html_to_clean_md(html: str) -> str:
    # 预处理清洗
    soup = BeautifulSoup(html, 'lxml')
    for tag in soup(['script', 'style', 'nav', 'footer']):
        tag.decompose()

    # 转换增强配置
    return md(
        str(soup),
        heading_style="ATX",
        strip=['a[href^="#"]', 'img.avatar'],  # 过滤锚点链接和头像图片
        autolinks=False  # 禁用自动链接转换
    )

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

    def __init__(self, proxy=None):
        self.feeds = {}
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

    def read_feeds_from_json(self, filepath: str) -> Dict[str, str]:
        """Read RSS feed URLs from JSON configuration file
        Args:
            filepath (str): Path to JSON config file
        Returns:
            Dict[str, str]: Dictionary of feed names to URLs
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.feeds = config.get('feeds', {})
                return self.feeds
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise ValueError(f"Invalid JSON file: {str(e)}") from e

    def process_all_feeds(self):
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
            result = fetch_feed(url)
            if 'entries' not in result:
                raise ValueError(f"Feed parse error: {result["errors"]}")
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
        html = fetch_web_content(url)
        if not html:
            print(f'  ! Article empty: {article["title"]}')
            return
        markdown = html_to_clean_md(html)

        article['content_html'] = html
        article['content_markdown'] = markdown

        # 生成存储路径
        filepath = _generate_filepath(article)

        # 原子化写入
        with self.conn:
            try:
                # 写入文件
                _write_md_file(filepath, markdown)

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


# ----------------------------------------------------------------------------------------------------------------------

def main():
    proxy_config = {
        "server": "socks5://127.0.0.1:10808",
        "username": "",
        "password": ""
    }
    processor = RSSProcessor(proxy=None)
    try:
        feeds = processor.read_feeds_from_json("feeds_tech.json")
        print(f'Feeds count: {len(feeds)}')

        processor.process_all_feeds()
        print(f"Successfully got {len(processor.articles)} articles.")

    except Exception as e:
        print(f"Process fail: {str(e)}")
        print(traceback.format_exc())


if __name__ == "__main__":
    main()