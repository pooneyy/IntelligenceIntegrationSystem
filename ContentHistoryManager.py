import os
import re
import sqlite3
import hashlib
import threading
from datetime import datetime
from pathlib import Path


class ContentHistoryManager:
    """Thread-safe content history manager with SQLite backend and file storage."""

    def __init__(self, db_path='content_history.db', base_dir='content_storage'):
        """Initialize manager with database connection and base storage directory."""
        self.db_path = db_path
        self.base_dir = Path(base_dir)
        self.lock = threading.RLock()  # Use reentrant lock for interface methods
        self.conn = sqlite3.connect(self.db_path, timeout=10)
        self._create_table()
        self._url_map = self._load_records()

    def _create_table(self):
        """Create database table schema if not exists."""
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
        """Load existing records from database into memory."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT url, filepath FROM content_history')
        return {row[0]: row[1] for row in cursor.fetchall()}

    def has_url(self, url):
        """Check if URL exists in history."""
        with self.lock:
            return url in self._url_map

    def save_content(self, url, content, title, category, suffix='.txt'):
        """
        Save content to file system and record in database.
        Returns tuple: (success: bool, filepath: str)
        """
        with self.lock:
            # Check existence within single lock context
            if url in self._url_map:
                return False, self._url_map[url]

            # Generate file path components
            filepath = self._generate_filepath(title, content, category, suffix)

            try:
                # Ensure directory exists
                filepath.parent.mkdir(parents=True, exist_ok=True)

                # Write content to file
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)

                # Calculate content checksum
                checksum = hashlib.md5(content.encode()).hexdigest()

                # Update database
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO content_history (url, filepath, checksum)
                    VALUES (?, ?, ?)
                ''', (url, str(filepath), checksum))
                self.conn.commit()

                # Update in-memory cache
                self._url_map[url] = str(filepath)
                return True, str(filepath)

            except Exception as e:
                # Cleanup failed write operation
                if filepath.exists():
                    filepath.unlink()
                raise RuntimeError(f"Content save failed: {str(e)}") from e

    def _generate_filepath(self, title, content, category, suffix):
        """Generate human-readable file path with conflict resolution."""
        # Sanitize category name
        clean_category = re.sub(r'[\\/*?:"<>|]', '', category.strip())

        # Sanitize title (preserve Unicode characters)
        clean_title = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5\-_]', '_', title.strip())
        clean_title = re.sub(r'_+', '_', clean_title)[:50]

        # Content-based hash
        content_hash = hashlib.md5(content.encode()).hexdigest()[:6]

        # Base filename components
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_name = f"{clean_title}_{content_hash}_{timestamp}{suffix}"
        base_path = self.base_dir / clean_category / base_name

        # Conflict resolution
        if not base_path.exists():
            return base_path

        # Add millisecond timestamp for conflict resolution
        timestamp_ms = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        return self.base_dir / clean_category / f"{clean_title}_{content_hash}_{timestamp_ms}{suffix}"

    def get_filepath(self, url):
        """Get stored file path for given URL."""
        with self.lock:
            return self._url_map.get(url)

    def export_mappings(self, export_path, format='csv'):
        """Export all URL-file mappings to specified format (csv/json)."""
        with self.lock:
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
                raise ValueError("Unsupported format, choose 'csv' or 'json'")

    def close(self):
        """Close database connection and release resources."""
        with self.lock:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Usage Example
if __name__ == "__main__":
    # Initialize content manager
    with ContentHistoryManager(base_dir="content_storage") as manager:
        # Test data
        test_url = "https://example.com/article1"
        test_content = "Sample article content"
        test_title = "Sample Article Title"
        test_category = "News"

        # Save content
        if not manager.has_url(test_url):
            success, path = manager.save_content(
                url=test_url,
                content=test_content,
                title=test_title,
                category=test_category,
                suffix=".txt"
            )
            print(f"Save result: {success}, Path: {path}")

        # Retrieve file path
        print("File path:", manager.get_filepath(test_url))

        # Export mappings
        manager.export_mappings("url_mappings.csv")
        print("Mappings exported")

        # Check URL existence
        print("URL exists:", manager.has_url(test_url))
