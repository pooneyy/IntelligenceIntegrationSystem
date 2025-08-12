import threading
from typing import Any, Dict, List, Tuple, Optional


class CrawlStatistics:
    # Singleton implementation with double-checked locking pattern
    _instance: Optional['CrawlStatistics'] = None
    _singleton_lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> 'CrawlStatistics':
        # First check avoids locking overhead after initialization
        if cls._instance is None:
            with cls._singleton_lock:  # Ensure thread-safe creation
                # Second check prevents race condition during lock acquisition
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # Ensure initialization only happens once
        if hasattr(self, '_initialized'):
            return

        # Thread-safe data structures for statistics
        self._counter_log_lock = threading.Lock()
        self._counter_log_record: Dict[Tuple, Dict[str, int]] = {}

        self._sub_item_log_lock = threading.Lock()
        self._sub_item_log_record: Dict[Tuple, Dict[str, List[Any]]] = {}

        self._initialized = True  # Mark initialization complete

    def counter_log(self, leveled_names: List[str], counter_item_name: str, log_text: str) -> None:
        """Increment counter for a specific item in a hierarchical namespace.

        Args:
            leveled_names: Hierarchical namespace path (e.g., ['domain', 'page'])
            counter_item_name: Name of the counter to increment
            log_text: Placeholder for future logging functionality
        """
        key = tuple(leveled_names)  # Convert path to hashable tuple

        with self._counter_log_lock:  # Ensure thread safety
            # Get or create namespace dictionary
            namespace = self._counter_log_record.setdefault(key, {})
            # Increment counter
            namespace[counter_item_name] = namespace.get(counter_item_name, 0) + 1

    def get_classified_counter(self, leveled_names: List[str]) -> Dict[str, int]:
        """Retrieve counters for a hierarchical namespace.

        Args:
            leveled_names: Hierarchical namespace path

        Returns:
            Copy of counter dictionary to prevent external modification
        """
        key = tuple(leveled_names)

        with self._counter_log_lock:  # Ensure thread safety during read
            # Return copy to avoid external modification of internal data
            return self._counter_log_record.get(key, {}).copy()

    def sub_item_log(self, leveled_names: List[str], sub_item: Any, status: str) -> None:
        """Record sub-item status in a hierarchical namespace.

        Args:
            leveled_names: Hierarchical namespace path
            sub_item: Item to track (e.g., URL, resource)
            status: Current status of the item (e.g., 'success', 'failed')
        """
        key = tuple(leveled_names)

        with self._sub_item_log_lock:  # Ensure thread safety
            # Get or create status dictionary
            status_dict = self._sub_item_log_record.setdefault(key, {})
            # Get or create status list
            status_list = status_dict.setdefault(status, [])
            # Add item to status list
            status_list.append(sub_item)

    def get_sub_item_statistics(self, leveled_names: List[str]) -> Dict[str, List[Any]]:
        """Retrieve sub-item statuses for a hierarchical namespace.

        Args:
            leveled_names: Hierarchical namespace path

        Returns:
            Copy of status dictionary with list copies to prevent modification
        """
        key = tuple(leveled_names)

        with self._sub_item_log_lock:  # Ensure thread safety during read
            # Return deep copy to avoid external modification
            status_dict = self._sub_item_log_record.get(key, {})
            return {
                status: items.copy()  # Copy list to prevent external modification
                for status, items in status_dict.items()
            }
