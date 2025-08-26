import datetime
import threading
from typing import Optional, Callable

from ServiceComponent.IntelligenceHubDefines import APPENDIX_TIME_ARCHIVED
from ServiceComponent.IntelligenceQueryEngine import IntelligenceQueryEngine


class IntelligenceCache:
    def __init__(self, db_archive, cache_period: datetime.timedelta):
        self.db_archive = db_archive
        self.cache_period = cache_period

        self.lock = threading.Lock()
        self.cache = []  # Sorted by data['APPENDIX'][APPENDIX_TIME_ARCHIVED] in descending order

    def encache(self, data: dict) -> bool:
        """
        Insert data into cache in descending order based on APPENDIX_TIME_ARCHIVED.

        Args:
            data: ArchivedData object to be cached

        Returns:
            bool: True if successfully cached else False
        """
        with self.lock:
            # Get the archive time from appendix
            archive_time = data.get('APPENDIX', {}).get(APPENDIX_TIME_ARCHIVED, None)
            if not archive_time:
                return False

            if not self.cache:
                self.cache.insert(0, data)
                return False

            # Find the correct position to insert (maintain descending order)
            for i, cached_item in enumerate(self.cache):
                cached_time = cached_item['APPENDIX'][APPENDIX_TIME_ARCHIVED]

                # 如果新数据时间更晚，插入到当前位置前面
                if archive_time > cached_time:
                    insert_index = i
                    break
            else:
                # 循环正常结束（未break），说明新数据是最早的，插入到末尾
                insert_index = len(self.cache)

            # Insert at the found position
            self.cache.insert(insert_index, data)

            return True

    def load_cache(self) -> bool:
        """
        Load data from database into cache for the specified cache period.

        Returns:
            bool: True if loading was successful, False otherwise
        """
        try:
            # Calculate time range for query
            end_time = datetime.datetime.now()
            start_time = end_time - self.cache_period

            # Create query engine and build query
            query_engine = IntelligenceQueryEngine(self.db_archive)

            # Execute query and process results
            results = query_engine.query_intelligence(archive_period=(start_time, end_time))
            results_sorted = sorted(
                    results,
                    key=lambda item: item['APPENDIX'][APPENDIX_TIME_ARCHIVED],
                    reverse=True
                )

            with self.lock:
                self.cache = results_sorted

                return True

        except Exception as e:
            print(f"Error loading cache: {e}")
            return False

    def get_cached_data(self,
                        filter_func: Optional[Callable[[dict], bool]] = None,
                        map_function: Optional[Callable[[dict], any]] = None) -> list:
        """
        Retrieve data from cache with optional filtering and mapping.

        Args:
            filter_func: Function to filter cached items
            map_function: Function to transform cached items

        Returns:
            list: Processed cached data
        """
        with self.lock:
            # Apply filtering if provided
            if filter_func:
                filtered_data = [item for item in self.cache if filter_func(item)]
            else:
                filtered_data = self.cache

            # Apply mapping if provided
            if map_function:
                result = [map_function(item) for item in filtered_data]
            else:
                result = filtered_data

            return result

    def _check_drop_out_of_period(self):
        """
        Remove expired data from cache based on cache_period.
        """
        current_time = datetime.datetime.now()
        cutoff_time = current_time - self.cache_period

        with self.lock:
            # Remove items from the end until we reach data within the cache period
            while self.cache:
                oldest_item = self.cache[-1]
                oldest_time = oldest_item['APPENDIX'][APPENDIX_TIME_ARCHIVED]

                if oldest_time < cutoff_time:
                    self.cache.pop()
                else:
                    break
