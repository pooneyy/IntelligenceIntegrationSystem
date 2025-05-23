from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError
from typing import Dict, Optional, List, Any
import threading


class MongoDBStorage:
    """
    A thread-safe MongoDB storage handler for generic dictionary data with configurable connection settings.

    Features:
    - Automatic connection pooling management
    - Index optimization
    - Safe concurrent access
    - Flexible query interface
    - Comprehensive configuration options

    Attributes:
        client (MongoClient): Thread-safe MongoDB client instance
        collection: MongoDB collection reference
        lock (threading.Lock): Resource lock for thread safety
    """

    def __init__(self,
                 host: str = 'localhost',
                 port: int = 27017,
                 db_name: str = 'generic_db',
                 collection_name: str = 'data',
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 auth_source: str = 'admin',
                 max_pool_size: int = 100,
                 indexes: Optional[List[tuple]] = None,
                 **kwargs):
        """
        Initialize MongoDB connection with configurable parameters.

        Args:
            host (str): MongoDB server address [5,9](@ref)
            port (int): MongoDB server port
            db_name (str): Target database name
            collection_name (str): Target collection name
            username (Optional[str]): Authentication username
            password (Optional[str]): Authentication password
            auth_source (str): Authentication database [9](@ref)
            max_pool_size (int): Maximum connection pool size [6,8](@ref)
            indexes
            **kwargs: Additional MongoDB client parameters
        """
        self.lock = threading.Lock()
        connection_uri = f"mongodb://{host}:{port}/"

        # Configure authentication if provided [9](@ref)
        if username and password:
            connection_uri = f"mongodb://{username}:{password}@{host}:{port}/?authSource={auth_source}"

        # Initialize thread-safe client with connection pooling [6,8](@ref)
        self.client = MongoClient(
            connection_uri,
            maxPoolSize=max_pool_size,
            connectTimeoutMS=3000,
            serverSelectionTimeoutMS=5000,
            **kwargs
        )

        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self._create_indexes()

    def _create_indexes(self) -> None:
        """
        Create optimized indexes for common query patterns.
        Creates ascending index on '_id' by default for faster lookups [5](@ref).
        """
        with self.lock:
            self.collection.create_index([("_id", ASCENDING)], background=True)

    def insert(self, data: Dict[str, Any], **kwargs) -> str:
        """
        Insert a single document into the collection.

        Args:
            data (Dict): Dictionary data to store
            **kwargs: Additional insert parameters

        Returns:
            str: Inserted document ID

        Raises:
            PyMongoError: On insertion failure
        """
        with self.lock:
            try:
                result = self.collection.insert_one(data, **kwargs)
                return str(result.inserted_id)
            except PyMongoError as e:
                self._handle_error(e)

    def bulk_insert(self, data_list: List[Dict[str, Any]], **kwargs) -> List[str]:
        """
        Bulk insert multiple documents with optimized batch writing.

        Args:
            data_list (List[Dict]): List of dictionaries to store
            **kwargs: Additional bulk insert parameters

        Returns:
            List[str]: List of inserted document IDs

        Raises:
            PyMongoError: On bulk insertion failure
        """
        with self.lock:
            try:
                result = self.collection.insert_many(
                    data_list,
                    ordered=False,  # Enable parallel document insertion [5](@ref)
                    **kwargs
                )
                return [str(id) for id in result.inserted_ids]
            except PyMongoError as e:
                self._handle_error(e)

    def find(self, query: Dict[str, Any], **kwargs) -> List[Dict]:
        """
        Generic document finder with flexible query support.

        Args:
            query (Dict): MongoDB query dictionary
            **kwargs: Additional find parameters

        Returns:
            List[Dict]: Matching documents

        Raises:
            PyMongoError: On query failure
        """
        with self.lock:
            try:
                return list(self.collection.find(query, **kwargs))
            except PyMongoError as e:
                self._handle_error(e)

    def find_one(self, query: Dict[str, Any], **kwargs) -> Optional[Dict]:
        """
        Find a single document matching the query criteria.

        Args:
            query (Dict): MongoDB query dictionary
            **kwargs: Additional find parameters

        Returns:
            Optional[Dict]: Matching document or None

        Raises:
            PyMongoError: On query failure
        """
        with self.lock:
            try:
                return self.collection.find_one(query, **kwargs)
            except PyMongoError as e:
                self._handle_error(e)

    def _handle_error(self, error: PyMongoError) -> None:
        """Centralized error handling with resource cleanup."""
        # Implement custom error handling/logging here
        raise error

    def close(self) -> None:
        """Properly close all MongoDB connections."""
        with self.lock:
            self.client.close()


# Example usage
if __name__ == "__main__":
    # Initialize with custom configuration [9](@ref)
    storage = MongoDBStorage(
        host="localhost",
        port=27017,
        db_name="my_app_db",
        collection_name="user_data",
        username="",
        password="",
        auth_source="admin",
        max_pool_size=50
    )

    # Insert sample data
    doc_id = storage.insert({"key": "value", "nested": {"data": 123}})

    # Query data
    result = storage.find_one({"_id": doc_id})
    print(f"Found document: {result}")

    # Close connections
    storage.close()
