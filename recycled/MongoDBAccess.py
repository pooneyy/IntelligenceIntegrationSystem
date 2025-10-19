import logging
from bson import ObjectId
from typing import Dict, Optional, List, Any, Sequence, Union, Tuple
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
                 db_name: str = 'IntelligenceIntegrationSystem',
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
            tz_aware=True,
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

    def find_one(self, query_dict: Dict[str, Any], **kwargs) -> Optional[Dict]:
        """
        Retrieve a single document matching AND conditions of field-value pairs.
        Automatically converts MongoDB ObjectId to string in returned document.

        Args:
            query_dict: Dictionary of field-value equality matches
            **kwargs: Additional find parameters (projection, sort, etc.)

        Returns:
            dict: First matching document with stringified _id, or None

        Raises:
            MongoDBOperationError: If query execution fails
        """
        try:
            document = self.collection.find_one(query_dict, **kwargs)
            if document and '_id' in document:
                document['_id'] = str(document['_id'])
            return document
        except PyMongoError as e:
            self._handle_error(e)

    def find_many(self, query_dict: Dict[str, Any], **kwargs) -> List[Dict]:
        """
        Retrieve all documents matching AND conditions of field-value pairs.
        Converts MongoDB ObjectIds to strings in returned documents.

        Args:
            query_dict: Dictionary of field-value equality matches
            **kwargs: Additional find parameters (projection, sort, limit, etc.)

        Returns:
            List[dict]: All matching documents with stringified _ids

        Raises:
            MongoDBOperationError: If query execution fails
        """
        try:
            cursor = self.collection.find(query_dict, **kwargs)
            return [{**doc, '_id': str(doc['_id'])} if '_id' in doc
                    else doc for doc in cursor]
        except PyMongoError as e:
            self._handle_error(e)

    def update(self, filter_query: Dict[str, Any], update_data: Dict[str, Any], operation: str = '$set', **kwargs) -> Tuple[int, int]:
        """
        Update documents matching the query criteria with specified fields.

        Args:
            filter_query (Dict[str, Any]): Query criteria for document selection
            update_data (Dict[str, Any]): Fields to update or add with new values
            operation (str): MongoDB operator, can be $set, $push, etc...
            **kwargs: Additional parameters for update_many operation

        Returns:
            Tuple[int, int]: (matched_count, modified_count) indicating number of
            documents matched and modified

        Raises:
            MongoDBOperationError: If update operation fails
        """
        try:
            result = self.collection.update_many(
                filter_query,
                {operation: update_data},
                **kwargs
            )
            return result.matched_count, result.modified_count
        except PyMongoError as e:
            self._handle_error(e)
            return -1, -1

    def _handle_error(self, error: PyMongoError) -> None:
        """Centralized error handling with resource cleanup."""
        logger.error(f"MongoDB operation failed: {error}")
        raise MongoDBOperationError from error

    def close(self) -> None:
        """Close all network connections and terminate background tasks."""
        self.client.close()


# ----------------------------------------------------------------------------------------------------------------------

from bson import ObjectId
from typing import Dict, List


def test_mongodb_storage(storage) -> None:
    """Main test entry point for MongoDBStorage functionality"""
    print("\n=== Starting MongoDBStorage Test Suite ===")

    try:
        # Clear existing test data
        storage.collection.delete_many({})
        print("Test collection cleared")

        _test_insert_operations(storage)
        _test_bulk_insert(storage)
        _test_update_operations(storage)
        _test_find_operations(storage)
        _test_find_many_conversion(storage)

    except Exception as e:
        print(f"Test failed: {str(e)}")
        raise
    finally:
        print("\n=== Test Completed ===")


def _test_insert_operations(storage) -> None:
    """Test single document insertion"""
    print("\n-- Testing Insert Operations --")

    # Test basic insertion
    doc1 = {"name": "TestDoc", "value": 42}
    inserted_id = storage.insert(doc1)
    print(f"Insert Result (Single): {inserted_id}")
    assert isinstance(inserted_id, str) and len(inserted_id) == 24
    assert storage.collection.count_documents({}) == 1


def _test_bulk_insert(storage) -> None:
    """Test bulk document insertion"""
    print("\n-- Testing Bulk Insert --")

    docs = [
        {"type": "A", "count": 5},
        {"type": "B", "count": 10},
        {"type": "C", "count": 15}
    ]
    inserted_ids = storage.bulk_insert(docs)
    print(f"Bulk Insert IDs: {inserted_ids}")
    assert len(inserted_ids) == 3
    assert all(isinstance(id_, str) for id_ in inserted_ids)
    assert storage.collection.count_documents({}) == 4  # 3 new + 1 previous


def _test_update_operations(storage) -> None:
    """Test document update functionality"""
    print("\n-- Testing Update Operations --")

    # Prepare test document
    target_doc = {"category": "test", "status": "active"}
    doc_id = storage.insert(target_doc)
    print(f"Update Test Doc ID: {doc_id}")

    # Test basic update
    update_result = storage.update(
        filter_query={"_id": ObjectId(doc_id)},
        update_data={"status": "inactive", "modified": True}
    )
    print(f"Update Result: {update_result}")
    assert update_result == (1, 1)

    # Verify update
    updated_doc = storage.collection.find_one({"_id": ObjectId(doc_id)})
    print(f"Updated Document: {updated_doc}")
    assert updated_doc["status"] == "inactive"
    assert updated_doc["modified"] is True


def _test_find_operations(storage) -> None:
    """Test various find operations"""
    print("\n-- Testing Find Operations --")

    # Test find_one
    single_result = storage.find_one({"type": "B"})
    print(f"Find One Result: {single_result}")
    assert single_result is not None
    assert single_result["count"] == 10

    # Test find_many
    multi_result = storage.find_many({"count": {"$gt": 7}})
    print(f"Find Many Results: {len(multi_result)} documents")
    assert len(multi_result) >= 2  # Expect B(10) and C(15)


def _test_find_many_conversion(storage) -> None:
    """Test _id string conversion in find_many"""
    print("\n-- Testing Dict Conversion --")

    results = storage.find_many({"count": {"$exists": True}})
    print(f"Converted Documents Sample: {results[:1]}")
    assert isinstance(results, list)
    assert all(isinstance(doc["_id"], str) for doc in results)
    assert any(doc["count"] == 15 for doc in results)


def main():
    # Initialize with custom configuration [9](@ref)
    storage = MongoDBStorage(
        host="localhost",
        port=27017,
        db_name="my_app_db",
        collection_name="user_data",
        max_pool_size=50
    )

    test_mongodb_storage(storage)

    # # Insert sample data
    # doc_id = storage.insert({"key": "value", "nested": {"data": 123}})
    # print(f"Inserted ID type: {type(doc_id)}")  # 验证类型
    #
    # # Query data
    # result = storage.find_one({"_id": ObjectId(doc_id)})
    # print(f"Found document: {result}")
    #
    # # Close connections
    # storage.close()

# Example usage
if __name__ == "__main__":
    main()
