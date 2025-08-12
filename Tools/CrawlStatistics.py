import threading
from typing import Any, Dict, List, Tuple, Optional, Set, Union


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

    def counter_log(self, leveled_names: List[str], counter_item_name: str, log_text: str = '') -> None:
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

    def reset(self, leveled_names: Union[List[str], None] = None) -> None:
        """Reset statistics either completely or for specified namespace(s)

        Args:
            leveled_names:
                - None: Reset all statistics
                - List: Reset specific namespace and its children
        """
        if leveled_names is None:
            # Reset everything
            with self._counter_log_lock, self._sub_item_log_lock:
                self._counter_log_record.clear()
                self._sub_item_log_record.clear()
            return

        # Convert to tuple for matching
        target_key = tuple(leveled_names)

        with self._counter_log_lock:
            # Remove target namespace and any child namespaces
            keys_to_remove = [
                k for k in self._counter_log_record.keys()
                if k[:len(target_key)] == target_key
            ]
            for k in keys_to_remove:
                del self._counter_log_record[k]

        with self._sub_item_log_lock:
            # Repeat for sub-item log
            keys_to_remove = [
                k for k in self._sub_item_log_record.keys()
                if k[:len(target_key)] == target_key
            ]
            for k in keys_to_remove:
                del self._sub_item_log_record[k]

    def dump(self, leveled_names: Union[List[str], None] = None) -> str:
        """Generate formatted statistics report either for all namespaces or specified one

        Args:
            leveled_names:
                - None: Dump all namespaces
                - List: Dump specific namespace and its children

        Returns:
            Formatted multi-line statistics report
        """
        # Handle all-namespace case
        if leveled_names is None:
            return self._dump_all_namespaces()

        # Handle specific namespace case
        target_key = tuple(leveled_names)
        return self._dump_single_namespace(target_key, include_children=True)

    def _get_all_namespaces(self) -> Set[Tuple]:
        """Get combined keys from both log records"""
        with self._counter_log_lock:
            counter_keys = set(self._counter_log_record.keys())
        with self._sub_item_log_lock:
            subitem_keys = set(self._sub_item_log_record.keys())
        return counter_keys | subitem_keys

    def _dump_all_namespaces(self) -> str:
        """Generate report for all namespaces"""
        all_keys = sorted(self._get_all_namespaces(), key=lambda x: (len(x), x))
        return "\n\n".join([self._dump_single_namespace(key) for key in all_keys])

    def _dump_single_namespace(
            self,
            namespace_key: Tuple,
            include_children: bool = False
    ) -> str:
        """Generate report for a single namespace (including children if requested)"""
        # Collect matching keys
        matching_keys = []
        if include_children:
            all_keys = self._get_all_namespaces()
            matching_keys = sorted(
                [k for k in all_keys if k[:len(namespace_key)] == namespace_key],
                key=lambda x: (len(x), x)
            )
        else:
            matching_keys = [namespace_key]

        # Generate report sections
        sections = []
        for key in matching_keys:
            counter_data = self.get_classified_counter(list(key))
            subitem_data = self.get_sub_item_statistics(list(key))

            # Skip empty namespaces
            if not counter_data and not subitem_data:
                continue

            section = [
                f"Namespace: {'.'.join(key)}",
                "\nCounter Statistics:"
            ]

            # Format counters
            for name, count in counter_data.items():
                section.append(f"  {name}: {count}")

            # Format subitems
            if subitem_data:
                section.append("\nSub-item Statistics:")
                for status, items in subitem_data.items():
                    section.append(f"  STATUS: {status} (Count: {len(items)})")
                    for i, item in enumerate(items, 1):
                        section.append(f"    {i}. {str(item)}")

            sections.append("\n".join(section))

        return "\n\n".join(sections) if sections else ""
