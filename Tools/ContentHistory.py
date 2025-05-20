import os
import re
import hashlib
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
import tldextract
import threading
from typing import Tuple, Optional

from CrawlTasks.task_example import logger


class ContentDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.db_path, timeout=10)
        self._create_table()

    def _create_table(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS content_history (
                    url TEXT PRIMARY KEY,
                    filepath TEXT NOT NULL,
                    checksum TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()

    def load_records(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT url, filepath FROM content_history')
            return {row[0]: row[1] for row in cursor.fetchall()}

    def insert_record(self, url, filepath, checksum):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO content_history (url, filepath, checksum)
                VALUES (?, ?, ?)
            ''', (url, filepath, checksum))
            self.conn.commit()

    def close(self):
        with self.lock:
            self.conn.close()


class _ContentHistoryManager:
    """Actual implementation class (private)"""

    def __init__(self, base_dir='content_storage', db: Optional[ContentDB]=None):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.operation_lock = threading.RLock()  # 实例级操作锁
        self._url_map = {}
        if db is not None:
            self._url_map = db.load_records()
            db.close()

    def has_url(self, url):
        """Check URL existence"""
        with self.operation_lock:
            return url in self._url_map

    def save_content(self, url, content, title, category,
                     suffix='.txt', db: Optional[ContentDB]=None) -> Tuple[bool, str]:
        """Save content with thread-safe operation"""
        with self.operation_lock:
            if url in self._url_map:
                return False, self._url_map[url]

            filepath = self.generate_filepath(title, content, url, category, suffix)

            try:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)

                checksum = hashlib.md5(content.encode()).hexdigest()

                # 如果存在数据库实例，则记录到数据库
                if db is not None:
                    db.insert_record(url, str(filepath), checksum)

                self._url_map[url] = str(filepath)
                return True, str(filepath)

            except Exception as e:
                if filepath.exists():
                    filepath.unlink()
                logging.error(f"Content save failed: {str(e)}")
                return False, str(filepath)

    def generate_filepath(self, title, content, url, category, suffix):
        """生成包含URL域名层级的文件路径"""
        extracted = tldextract.extract(url)
        domain_parts = []
        if extracted.subdomain:
            domain_parts.extend(extracted.subdomain.split('.'))
        domain_parts.append(extracted.domain)
        combined = '.'.join(domain_parts)
        combined = re.sub(r'^www\d*\.', '', combined)
        category_part = re.sub(r'[\\/*?:"<>|]', '', combined.replace('.', '_'))

        clean_category = re.sub(r'[\\/*?:"<>|]', '', category.strip())
        clean_title = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5\-_]', '_', title.strip())[:50]
        clean_title = re.sub(r'_+', '_', clean_title)

        content_hash = hashlib.md5(content.encode()).hexdigest()[:6]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_name = f"{clean_title}_{content_hash}_{timestamp}{suffix}"

        base_path = self.base_dir / category_part / clean_category / base_name

        if not base_path.exists():
            return base_path

        timestamp_ms = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        return self.base_dir / category_part / clean_category / f"{clean_title}_{content_hash}_{timestamp_ms}{suffix}"

    def get_filepath(self, url):
        """Get stored file path"""
        with self.operation_lock:
            return self._url_map.get(url)

    def export_mappings(self, export_path, format='csv'):
        """Export URL-file mappings"""
        with self.operation_lock:
            items = list(self._url_map.items())

            if format == 'csv':
                import csv
                with open(export_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['URL', 'Filepath'])
                    writer.writerows(items)
            elif format == 'json':
                import json
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(dict(items), f, indent=2)
            else:
                raise ValueError("Unsupported format")


_instance: Optional[_ContentHistoryManager] = None
_init_lock = threading.Lock()


def _get_instance():
    """Initialize singleton instance with double-checked locking"""
    if _instance is None:
        logger.error('You must init ContentHistoryManager first.')
    return _instance


def init(base_dir='content_storage', init_db=None):
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                _instance = _ContentHistoryManager(base_dir, init_db)
    return _instance


# Public interface functions

def has_url(url):
    return _get_instance().has_url(url)


def get_base_dir() -> Path:
    return _get_instance().base_dir


def save_content(url, content, title, category,
                 suffix='.txt', db: Optional[ContentDB]=None) -> Tuple[bool, str]:
    return _get_instance().save_content(url, content, title, category, suffix, db)


def get_filepath(url):
    return _get_instance().get_filepath(url)


def export_mappings(export_path, format='csv'):
    return _get_instance().export_mappings(export_path, format)


def generate_filepath(title, content, url, category, suffix):
    return _get_instance().generate_filepath(title, content, url, category, suffix)


# Example usage
if __name__ == "__main__":
    # # First call will automatically initialize with default settings
    # saved, path = save_content(
    #     url="https://example.com/article1",
    #     content="Sample content",
    #     title="Example Article",
    #     category="News"
    # )

    print(f"File exists at: {get_filepath('https://example.com/article1')}")
    print(f"URL exists check: {has_url('https://example.com/article1')}")
