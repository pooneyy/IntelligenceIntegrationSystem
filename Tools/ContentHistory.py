import os
import re
import sqlite3
import hashlib
import threading
from pathlib import Path
from datetime import datetime

# Singleton instance and initialization lock
_instance = None
_init_lock = threading.Lock()


class _ContentHistoryManager:
    """Actual implementation class (private)"""

    def __init__(self, base_dir='content_storage', db_name='content_history.db'):
        self.db_path = os.path.join(base_dir, db_name)
        self.base_dir = Path(base_dir)
        self.operation_lock = threading.RLock()
        self.conn = sqlite3.connect(self.db_path, timeout=10)
        self._create_table()
        self._url_map = self._load_records()

    def _create_table(self):
        """Create database table schema"""
        with self.operation_lock:
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

    def _load_records(self):
        """Load existing records from database"""
        with self.operation_lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT url, filepath FROM content_history')
            return {row[0]: row[1] for row in cursor.fetchall()}

    def has_url(self, url):
        """Check URL existence"""
        with self.operation_lock:
            return url in self._url_map

    def save_content(self, url, content, title, category, suffix='.txt'):
        """Save content with thread-safe operation"""
        with self.operation_lock:
            if url in self._url_map:
                return False, self._url_map[url]

            filepath = self.generate_filepath(title, content, category, suffix)

            try:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)

                checksum = hashlib.md5(content.encode()).hexdigest()

                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO content_history (url, filepath, checksum)
                    VALUES (?, ?, ?)
                ''', (url, str(filepath), checksum))
                self.conn.commit()

                self._url_map[url] = str(filepath)
                return True, str(filepath)

            except Exception as e:
                if filepath.exists():
                    filepath.unlink()
                raise RuntimeError(f"Content save failed: {str(e)}") from e

    def generate_filepath(self, title, content, category, suffix):
        """Generate human-readable file path"""
        clean_category = re.sub(r'[\\/*?:"<>|]', '', category.strip())
        clean_title = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5\-_]', '_', title.strip())[:50]
        clean_title = re.sub(r'_+', '_', clean_title)

        content_hash = hashlib.md5(content.encode()).hexdigest()[:6]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_name = f"{clean_title}_{content_hash}_{timestamp}{suffix}"
        base_path = self.base_dir / clean_category / base_name

        if not base_path.exists():
            return base_path

        timestamp_ms = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        return self.base_dir / clean_category / f"{clean_title}_{content_hash}_{timestamp_ms}{suffix}"

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

    def close(self):
        """Close database connection"""
        with self.operation_lock:
            self.conn.close()


def _get_instance():
    """Initialize singleton instance with double-checked locking"""
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                _instance = _ContentHistoryManager()
    return _instance


# Public interface functions

def has_url(url):
    return _get_instance().has_url(url)


def save_content(url, content, title, category, suffix='.txt'):
    return _get_instance().save_content(url, content, title, category, suffix)


def get_filepath(url):
    return _get_instance().get_filepath(url)


def export_mappings(export_path, format='csv'):
    return _get_instance().export_mappings(export_path, format)


def generate_filepath(title, content, category, suffix):
    return _get_instance().generate_filepath(title, content, category, suffix)


def close():
    _get_instance().close()


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
