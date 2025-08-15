import sqlite3
import os
import time
from datetime import datetime
import logging
from collections import OrderedDict

# 状态常量 (使用整数减少存储)
STATUS_NOT_EXIST = -1
STATUS_UNKNOWN = 0
STATUS_DB_ERROR = 1
STATUS_ERROR = 10
STATUS_SUCCESS = 100
STATUS_IGNORED = 110


class CrawlRecord:
    """Record crawler results with SQLite persistence and in-memory cache"""

    def __init__(self, path_parts, cache_size=1000, db_suffix=".db"):
        """
        Initialize with enhanced path handling:
        - Single string input treated as filename
        - Auto-add suffix if missing
        - Ensure parent directories exist
        """
        self.conn = None

        self.logger = logging.getLogger('CrawlRecord')
        self.logger.addHandler(logging.StreamHandler())
        self.logger.setLevel(logging.ERROR)

        # Handle path input types
        if isinstance(path_parts, str):
            path_parts = [path_parts]  # Convert to list

        # Extract filename and enforce suffix
        db_filename = path_parts[-1]
        if not db_filename.endswith(db_suffix):
            db_filename += db_suffix

        # Build directory path
        base_dirs = path_parts[:-1] if len(path_parts) > 1 else []
        dir_path = os.path.join(*base_dirs) if base_dirs else "."

        # Create parent directories
        os.makedirs(dir_path, exist_ok=True)

        # Final database path
        self.db_path = os.path.join(dir_path, db_filename)

        self._init_db()  # Initialize database
        self.cache_size = cache_size
        self.memory_cache = OrderedDict()
        self._load_initial_cache()

    def _init_db(self):
        """Initialize database schema"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            cursor = self.conn.cursor()

            # Create table with proper schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crawl_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    status INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    extra_info TEXT,
                    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create indexes for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON crawl_records(url)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updated ON crawl_records(updated_time)')
            self.conn.commit()

        except sqlite3.Error as e:
            self.logger.error(f"Database initialization failed: {str(e)}")

    def _load_initial_cache(self):
        """Load top N records into memory cache"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, url, status, error_count, extra_info 
                FROM crawl_records 
                ORDER BY id DESC 
                LIMIT ?
            ''', (self.cache_size,))

            for row in cursor.fetchall():
                url = row[1]
                self.memory_cache[url] = {
                    'id': row[0],
                    'status': row[2],
                    'error_count': row[3],
                    'extra_info': row[4]
                }

        except sqlite3.Error as e:
            self.logger.error(f"Cache loading failed: {str(e)}")

    def record_url_status(self, url, status, extra_info=None) -> bool:
        """
        Record or update URL status

        :param url: Target URL
        :param status: Status code (must be >=10 or 0)
        :param extra_info: Additional metadata (optional)
        """
        # Validate status input
        if status < 10:
            self.logger.error(f"Invalid status {status}: Reserved for system use")
            return False

        try:
            cursor = self.conn.cursor()
            timestamp = datetime.now().isoformat()

            # Try update existing record
            cursor.execute('''
                UPDATE crawl_records 
                SET status = ?, extra_info = ?, updated_time = ?
                WHERE url = ?
            ''', (status, extra_info, timestamp, url))

            # If no record exists, insert new
            if cursor.rowcount == 0:
                cursor.execute('''
                    INSERT INTO crawl_records 
                    (url, status, extra_info, created_time, updated_time) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (url, status, extra_info, timestamp, timestamp))

            self.conn.commit()

            # Update memory cache
            if url in self.memory_cache:
                self.memory_cache[url].update({
                    'status': status,
                    'extra_info': extra_info
                })
            else:
                # Add to cache and enforce size limit
                self.memory_cache[url] = {
                    'id': cursor.lastrowid,
                    'status': status,
                    'error_count': 0,
                    'extra_info': extra_info
                }
                if len(self.memory_cache) > self.cache_size:
                    self.memory_cache.popitem(last=False)
            return True

        except sqlite3.Error as e:
            self.logger.error(f"Status recording failed for {url}: {str(e)}")
            return False

    def get_url_status(self, url, from_db=False):
        """
        Get current URL status

        :param url: Target URL
        :param from_db: Force database lookup
        :return: Status code (STATUS_NOT_EXIST if not found)
        """
        # Try memory cache first
        if not from_db and url in self.memory_cache:
            return self.memory_cache[url]['status']

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT status FROM crawl_records WHERE url = ?
            ''', (url,))

            result = cursor.fetchone()
            if result:
                status = result[0]

                # Update memory cache
                if url not in self.memory_cache:
                    self._add_to_cache(url)

                return status

        except sqlite3.Error as e:
            self.logger.error(f"Status query failed for {url}: {str(e)}")
            return STATUS_DB_ERROR

        return STATUS_NOT_EXIST

    def increment_error_count(self, url):
        """Increment error counter for URL"""
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.now().isoformat()

            # Try update existing record
            cursor.execute('''
                UPDATE crawl_records 
                SET error_count = error_count + 1, 
                    status = ?,
                    updated_time = ?
                WHERE url = ?
            ''', (STATUS_ERROR, timestamp, url))

            # Create new record if not exists
            if cursor.rowcount == 0:
                cursor.execute('''
                    INSERT INTO crawl_records 
                    (url, status, error_count, created_time, updated_time) 
                    VALUES (?, ?, 1, ?, ?)
                ''', (url, STATUS_ERROR, timestamp, timestamp))

            self.conn.commit()

            # Update memory cache
            if url in self.memory_cache:
                self.memory_cache[url]['error_count'] += 1
                self.memory_cache[url]['status'] = STATUS_ERROR
            else:
                self._add_to_cache(url)

        except sqlite3.Error as e:
            self.logger.error(f"Error count increment failed for {url}: {str(e)}")

    def get_error_count(self, url, from_db=False):
        """
        Get current error count for URL

        :param url: Target URL
        :param from_db: Force database lookup
        :return: Error count (0 if not found)
        """
        # Try memory cache first
        if not from_db and url in self.memory_cache:
            return self.memory_cache[url]['error_count']

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT error_count FROM crawl_records WHERE url = ?
            ''', (url,))

            result = cursor.fetchone()
            if result:
                count = result[0]

                # Update memory cache
                if url not in self.memory_cache:
                    self._add_to_cache(url)

                return count

        except sqlite3.Error as e:
            self.logger.error(f"Error count query failed for {url}: {str(e)}")

        return 0

    def clear_error_count(self, url):
        """Reset error counter for URL"""
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.now().isoformat()

            cursor.execute('''
                UPDATE crawl_records 
                SET error_count = 0, updated_time = ?
                WHERE url = ?
            ''', (timestamp, url))

            self.conn.commit()

            # Update memory cache
            if url in self.memory_cache:
                self.memory_cache[url]['error_count'] = 0
            else:
                self._add_to_cache(url)

        except sqlite3.Error as e:
            self.logger.error(f"Error count clear failed for {url}: {str(e)}")

    def _add_to_cache(self, url):
        """Add specific record to memory cache"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, status, error_count, extra_info 
                FROM crawl_records 
                WHERE url = ?
            ''', (url,))

            result = cursor.fetchone()
            if result:
                # Add to cache and enforce size limit
                self.memory_cache[url] = {
                    'id': result[0],
                    'status': result[1],
                    'error_count': result[2],
                    'extra_info': result[3]
                }
                if len(self.memory_cache) > self.cache_size:
                    self.memory_cache.popitem(last=False)

        except sqlite3.Error as e:
            self.logger.error(f"Cache update failed for {url}: {str(e)}")

    def close(self):
        """Clean up resources"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __del__(self):
        self.close()


# import os
# import time
# import sqlite3
# from datetime import datetime
# from CrawlRecord import CrawlRecord, STATUS_UNKNOWN, STATUS_SUCCESS, STATUS_ERROR, STATUS_IGNORED


def test_CrawlRecord():
    """Comprehensive test for CrawlRecord class without testing frameworks"""
    print("\n=== Starting CrawlRecord Test ===")

    # =========================================================================
    # 1. Test Database Initialization
    # =========================================================================
    print("\n[1] Testing database initialization...")
    test_db = ["test_dir", "crawl_data"]  # No suffix
    recorder = CrawlRecord(test_db, cache_size=2)

    # Verify path handling
    assert recorder.db_path.endswith(".db"), "DB should auto-add suffix"
    assert os.path.exists(os.path.dirname(recorder.db_path)), "Directories should be created"
    print(f"✓ Path created: {recorder.db_path}")

    # Check schema
    with sqlite3.connect(recorder.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(crawl_records)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "url" in columns and "status" in columns, "Schema mismatch"
    print("✓ Schema validated")

    # =========================================================================
    # 2. Test URL Status Recording
    # =========================================================================
    print("\n[2] Testing URL status recording...")
    url1 = "https://example.com/page1"
    recorder.record_url_status(url1, STATUS_SUCCESS, "Primary page")

    # Memory cache check
    assert recorder.get_url_status(url1) == STATUS_SUCCESS, "Should get status from cache"
    print("✓ Memory cache status retrieval")

    # Database check
    assert recorder.get_url_status(url1, from_db=True) == STATUS_SUCCESS, "Should get status from DB"

    # Update status
    recorder.record_url_status(url1, STATUS_IGNORED)
    assert recorder.get_url_status(url1) == STATUS_IGNORED, "Status should update"
    print("✓ Status update validated")

    # =========================================================================
    # 3. Test Error Counting
    # =========================================================================
    print("\n[3] Testing error counting...")
    url2 = "https://example.com/page2"
    recorder.record_url_status(url2, STATUS_UNKNOWN)

    # Increment errors
    recorder.increment_error_count(url2)
    recorder.increment_error_count(url2)
    assert recorder.get_error_count(url2) == 2, "Error count should increment"

    # Clear errors
    recorder.clear_error_count(url2)
    assert recorder.get_error_count(url2) == 0, "Error count should reset"
    print("✓ Error count operations")

    # =========================================================================
    # 4. Test Cache Management (LRU Policy)
    # =========================================================================
    print("\n[4] Testing cache eviction...")
    url3 = "https://example.com/page3"
    recorder.record_url_status(url3, STATUS_SUCCESS)

    # Cache should evict oldest entry (url1)
    assert url1 not in recorder.memory_cache, "url1 should be evicted from cache"
    assert url2 in recorder.memory_cache and url3 in recorder.memory_cache, "Newer URLs should remain"
    print("✓ LRU cache eviction")

    # =========================================================================
    # 5. Test Auto-Increment and Timestamps
    # =========================================================================
    print("\n[5] Testing auto-increment and timestamps...")
    url4 = "https://example.com/page4"
    recorder.record_url_status(url4, STATUS_SUCCESS)

    # Get timestamps from DB
    with sqlite3.connect(recorder.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT created_time, updated_time FROM crawl_records WHERE url=?", (url4,))
        created, updated = cursor.fetchone()
        created_dt = datetime.fromisoformat(created)
        updated_dt = datetime.fromisoformat(updated)

        # Verify timestamps
        assert created_dt <= updated_dt, "Created time should be <= updated time"
        # assert (datetime.now() - created_dt).total_seconds() < 10, "Timestamp should be recent"

    print("✓ Timestamps validated")

    # =========================================================================
    # 6. Test Invalid Status Handling
    # =========================================================================
    print("\n[6] Testing invalid status handling...")
    result = recorder.record_url_status("https://invalid.com", 5)  # Reserved status
    assert not result, "Should reject status <10"
    print("✓ Status validation")

    # =========================================================================
    # 7. Test Non-Existent URL Handling
    # =========================================================================
    print("\n[7] Testing non-existent URL handling...")
    assert recorder.get_url_status("https://ghost.com") == -1, "Should return STATUS_NOT_EXIST"
    assert recorder.get_error_count("https://ghost.com") == 0, "Non-existent URL should have 0 errors"
    print("✓ Non-existent URL handling")

    # =========================================================================
    # Cleanup
    # =========================================================================

    db_path = recorder.db_path
    recorder.close()
    recorder = None

    # time.sleep(5)
    # if os.path.exists(db_path):
    #     os.remove(db_path)
    #     os.rmdir(os.path.dirname(db_path))
    print("\n=== All 7 tests passed ===")


if __name__ == "__main__":
    test_CrawlRecord()
