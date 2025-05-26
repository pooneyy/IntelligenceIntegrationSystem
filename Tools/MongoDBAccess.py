import logging
import threading
from typing import Dict, Optional, List, Any, Sequence, Union
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from pymongo import MongoClient, ASCENDING


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


IndexSpec = Sequence[tuple[str, Union[int, str]]]


class MongoDBError(Exception):
    """Base exception for MongoDB operations"""

class MongoDBConnectionError(MongoDBError):
    """Error establishing database connection"""

class MongoDBOperationError(MongoDBError):
    """Error executing database operation"""


class MongoDBStorage:
    """
    Thread-safe MongoDB storage handler implementing best practices.

    Implements PyMongo's recommended thread-safe pattern:
    - Client instance is thread-safe when properly configured
    - Connection pooling managed by PyMongo driver
    - Server selection timeout built-in

    Typical usage:
        >> storage = MongoDBStorage()
        >> storage.insert({"data": "value"})

    Note: Client instance should be long-lived. Avoid frequent create/close.

    Raises:
        MongoDBConnectionError: On initial connection failure
        MongoDBOperationError: On subsequent operation failures
    """

    # Rest of implementation...

    def __init__(self,
                 host: str = 'localhost',
                 port: int = 27017,
                 db_name: str = 'generic_db',
                 collection_name: str = 'data',
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 auth_source: str = 'admin',
                 max_pool_size: int = 100,
                 indexes: Optional[List[IndexSpec]] = None,
                 **kwargs):
        """
        Initialize MongoDB connection with configurable parameters.

        Args:
            host (str): MongoDB server hostname or IP
            port (int): MongoDB server port
            db_name (str): Target database name
            collection_name (str): Target collection name
            username (Optional[str]): Authentication username
            password (Optional[str]): Authentication password
            auth_source (str): Authentication database [9](@ref)
            max_pool_size (int): Maximum connection pool size [6,8](@ref)
            indexes: List of tuples specifying indexes, e.g. [("created_at", pymongo.ASCENDING)]
            **kwargs: Additional MongoDB client parameters
        """
        self.connection_uri = f"mongodb://{username}:{password}@{host}:{port}/?authSource={auth_source}" \
            if username and password else f"mongodb://{host}:{port}/"

        self.client = MongoClient(
            self.connection_uri,
            maxPoolSize=max_pool_size,
            connectTimeoutMS=3000,
            serverSelectionTimeoutMS=5000,
            **kwargs
        )

        self.db: Database = self.client[db_name]
        self.collection: Collection = self.db[collection_name]

        try:
            self.client.server_info()  # Force connection attempt
        except PyMongoError as e:
            logger.critical("Connection verification failed")
            self.client.close()
            raise MongoDBConnectionError(f"Connection failed: {e}") from e

        self.indexes = indexes
        if self.indexes:
            self._create_indexes()

    def _create_indexes(self) -> None:
        """
        Create optimized indexes for common query patterns.
        """
        if self.indexes:
            for index in self.indexes:
                self.collection.create_index(index, background=True)

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
        try:
            result = self.collection.insert_many(
                data_list,
                ordered=False,
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
        try:
            return self.collection.find_one(query, **kwargs)
        except PyMongoError as e:
            self._handle_error(e)

    def _handle_error(self, error: PyMongoError) -> None:
        """Centralized error handling with resource cleanup."""
        logger.error(f"MongoDB operation failed: {error}")
        raise MongoDBOperationError from error

    def close(self) -> None:
        """Close all network connections and terminate background tasks."""
        self.client.close()


# Example usage
if __name__ == "__main__":
    # Initialize with custom configuration [9](@ref)
    storage = MongoDBStorage(
        host="localhost",
        port=27017,
        db_name="my_app_db",
        collection_name="user_data",
        max_pool_size=50
    )

    from bson import ObjectId

    # Insert sample data
    doc_id = storage.insert({"key": "value", "nested": {"data": 123}})
    print(f"Inserted ID type: {type(doc_id)}")  # 验证类型

    # Query data
    result = storage.find_one({"_id": ObjectId(doc_id)})
    print(f"Found document: {result}")

    # Close connections
    storage.close()
