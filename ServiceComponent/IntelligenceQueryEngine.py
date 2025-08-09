import re
import pytz  # Time zone handling
import logging
import pymongo
import datetime
from typing import Optional, List, Tuple, Union, Dict, Any

from Tools.MongoDBAccess import MongoDBStorage


logger = logging.getLogger(__name__)


class IntelligenceQueryEngine:
    def __init__(self, db: MongoDBStorage):
        self.__mongo_db = db

    def get_intelligence(self, _uuid: str) -> Optional[dict]:
        """Retrieve single intelligence entry by UUID

        Args:
            _uuid (str): UUID string to query

        Returns:
            Optional[dict]: Document dictionary if found, otherwise None
        """
        # Parameter validation
        if not _uuid:
            logger.error("UUID parameter is empty")
            return None

        try:
            # Attempt to get database connection
            collection = self.__mongo_db.collection
            if collection is None:
                logger.error("Database connection not initialized")
                return None

            # Build exact match UUID query
            query = {"UUID": str(_uuid).lower()}

            # Execute query - get first match
            doc = collection.find_one(query)

            if doc is None:
                logger.warning(f"No matching UUID found: {_uuid}")
                return None

            # Process document format
            return self.process_document(doc)

        except pymongo.errors.PyMongoError as e:
            logger.error(f"Database query failed: {str(e)}")
            return None
        except Exception as e:
            logger.exception(f"Unknown error: {str(e)}")
            return None

    def get_intelligence_summary(self) -> Dict[str, Union[int, Optional[str]]]:
        """
        Retrieve total intelligence count and latest document ID as base snapshot

        Returns:
            dict: Dictionary containing:
                - total_count: Total number of intelligence documents
                - base_uuid: UUID of the newest document (as stable pagination base)

        Ensures consistent pagination even when new documents are added.
        """
        collection = self.__mongo_db.collection

        try:
            # Get total document count
            total_count = collection.count_documents({})

            # Find the newest document as base reference
            newest_doc = collection.find_one(
                filter={},
                sort=[("PUB_TIME", pymongo.DESCENDING)]
            )

            base_uuid = newest_doc["UUID"] if newest_doc else None

            return {
                "total_count": total_count,
                "base_uuid": base_uuid
            }

        except pymongo.errors.PyMongoError as e:
            logger.error(f"Intelligence summary retrieval failed: {str(e)}")
            return {"total_count": 0, "base_uuid": None}

    def get_paginated_intelligences(self, base_uuid: str, offset: int, limit: int) -> List[dict]:
        """
        Retrieve paginated intelligence with stable ordering

        Args:
            base_uuid: Reference UUID for stable pagination anchor (None for start)
            offset: Number of documents to skip from the base
            limit: Maximum number of documents to return

        Returns:
            List of processed intelligence documents
        """
        if limit <= 0:
            return []

        collection = self.__mongo_db.collection
        sort_order = [
            ("PUB_TIME", pymongo.DESCENDING),
            ("_id", pymongo.DESCENDING)  # Secondary sort for consistency
        ]

        try:
            if base_uuid:
                base_doc = collection.find_one({"UUID": base_uuid})
                if not base_doc:
                    logger.warning(f"Base UUID not found: {base_uuid}")
                    return []

                cursor = collection.find(
                    filter={"PUB_TIME": {"$lte": base_doc["PUB_TIME"]}}
                ).sort(sort_order).skip(offset).limit(limit)
            else:
                cursor = collection.find().sort(sort_order).skip(offset).limit(limit)

            return [self.process_document(doc) for doc in cursor]

        except pymongo.errors.PyMongoError as e:
            logger.error(f"Pagination query failed: {str(e)}")
            return []

        except Exception as e:
            logger.error(f"Exception on query: {str(e)}")
            return []

    def query_intelligence(
            self,
            *,
            period: Optional[Tuple[datetime.datetime, datetime.datetime]] = None,
            locations: Optional[Union[str, List[str]]] = None,
            peoples: Optional[Union[str, List[str]]] = None,
            organizations: Optional[Union[str, List[str]]] = None,
            keywords: Optional[str] = None,
            skip: Optional[int] = None,
            limit: Optional[int] = None
    ) -> Tuple[List[dict], int]:
        """Execute intelligence query

        Args:
            period: UTC time range (start, end)
            locations: Location ID(s) (str or str list)
            peoples: Person ID(s) (str or str list)
            organizations: Organization ID(s) (str or str list)
            keywords: Full-text keywords
            skip: Number of documents to skip
            limit: Maximum number of results to return

        Returns:
            Tuple of
                List of matching intelligence documents
                All document count without specifying skip and limit.
        """
        # Get specified database collection
        collection = self.__mongo_db.collection

        try:
            # Build MongoDB query
            query = self.build_intelligence_query(
                period=period,
                locations=locations,
                peoples=peoples,
                organizations=organizations,
                keywords=keywords
            )

            # Execute query and return results with limit
            data = self.execute_query(collection, query, skip=skip, limit=limit)
            total = collection.count_documents(query)

            return data, total

        except pymongo.errors.PyMongoError as e:
            logger.error(f"Intelligence query failed: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Intelligence query error: {str(e)}", stack_info=True)
            return []

    def build_intelligence_query(
            self,
            period: Optional[Tuple[datetime.datetime, datetime.datetime]] = None,
            locations: Optional[Union[str, List[str]]] = None,
            peoples: Optional[Union[str, List[str]]] = None,
            organizations: Optional[Union[str, List[str]]] = None,
            keywords: Optional[str] = None
    ) -> dict:
        query_conditions = []

        if period:
            query_conditions.append(self.build_time_condition(*period))

        if locations:
            query_conditions.append(self.build_list_condition("LOCATION", locations))

        if peoples:
            query_conditions.append(self.build_list_condition("PEOPLE", peoples))

        if organizations:
            query_conditions.append(self.build_list_condition("ORGANIZATION", organizations))

        if keywords:
            query_conditions.append(self.build_keyword_or_condition(keywords))

        return {"$and": query_conditions} if query_conditions else {}

    def common_query(
            self,
            *,
            conditions: Dict[str, Any],
            operator: str = "$and",
            skip: Optional[int] = None,
            limit: Optional[int] = None
    ) -> List[dict]:
        """
        Execute a dynamic query on the intelligence collection using flexible field conditions.

        This function constructs and executes a MongoDB query based on arbitrary field specifications,
        supporting nested fields (using dot notation) and multiple logical operators. It handles both
        simple equality checks and complex conditions (e.g., range queries, existence checks) dynamically.

        Args:
            conditions: A dictionary mapping field paths to query conditions.
                - Keys can be top-level fields (e.g., "status") or nested paths (e.g., "meta.author.organization").
                - Values can be direct values (implicit equality check) or operator dictionaries (e.g.,
                  {"$gte": 10}, {"$in": ["A", "B"]}, {"$exists": True}).
            operator: Logical operator to combine conditions ("$and" or "$or"). Defaults to "$and".
            skip: Number of documents to skip (for pagination).
            limit: Maximum number of documents to return.

        Returns:
            List[dict]: Matching documents from the collection. Returns empty list on query errors.

        Example:
            conditions = {
                "status": "active",
                "confidence": {"$gte": 0.7},
                "entities.locations": {"$in": ["Beijing", "Shanghai"]},
                "timestamp": {"$exists": True}
            }
            results = dynamic_query(conditions=conditions, operator="$and", skip=0, limit=10)
        """
        collection = self.__mongo_db.collection

        try:
            query = self.build_common_conditions(conditions, operator)
            return self.execute_query(collection, query, skip=skip, limit=limit)

        except pymongo.errors.PyMongoError as e:
            logger.error(f"Dynamic query failed: {str(e)}")
            return []
        except ValueError as e:
            logger.error(f"Invalid operator: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Dynamic query error: {str(e)}", stack_info=True)
            return []

    @staticmethod
    def build_common_conditions(conditions: Dict[str, Any], operator: str = "$and") -> dict:
        """
        Construct MongoDB query conditions from dynamic field specifications.

        Transforms a dictionary of field-based conditions into a valid MongoDB query. Supports:
        - Nested field resolution using dot notation (e.g., "meta.location.city" → nested document query)
        - Explicit operator syntax (e.g., {"$gt": 100})
        - Logical combination of conditions via "$and" or "$or"

        Args:
            conditions: Dictionary of field paths to conditions.
                Each key-value pair generates a condition clause.
            operator: Logical operator ("$and" or "$or") to combine conditions.
                Raises ValueError for invalid operators.

        Returns:
            dict: Valid MongoDB query document. Returns empty dict if no conditions provided.

        Raises:
            ValueError: If operator is not "$and" or "$or".

        Example output for conditions {"a": 1, "b.c": {"$lt": 5}}:
            {"$and": [{"a": 1}, {"b.c": {"$lt": 5}}]}

        Notes:
            - Single-condition inputs return directly without logical operator wrapping.
            - Dot-notated fields are expanded into nested documents (e.g., "x.y.z" → {"x": {"y": {"z": value}}}).
        """
        if operator not in ["$and", "$or"]:
            raise ValueError("Operator must be '$and' or '$or'")

        # 处理嵌套字段和操作符
        condition_list = []
        for field_path, condition in conditions.items():
            # 处理嵌套字段（使用MongoDB的点表示法）
            if "." in field_path:
                field_parts = field_path.split(".")
                # 构建嵌套查询条件
                nested_cond = {f"{field_parts[-1]}": condition}
                for part in reversed(field_parts[:-1]):
                    nested_cond = {part: nested_cond}
                condition_list.append(nested_cond)
            else:
                # 直接字段查询
                condition_list.append({field_path: condition})

        # 组合所有条件
        if not condition_list:
            return {}  # 无任何条件
        elif len(condition_list) == 1:
            return condition_list[0]  # 单一条件无需运算符
        else:
            return {operator: condition_list}

    def process_document(self, doc: dict) -> dict:
        # 转换ObjectId为字符串
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])

        # 确保所有字段都有默认值
        fields = {
            'TIME': [],
            'LOCATION': [],
            'PEOPLE': [],
            'ORGANIZATION': [],
            'EVENT_BRIEF': "",
            'EVENT_TEXT': "",
            'RATE': {},
            'IMPACT': "",
            'TIPS': ""
        }

        for field, default in fields.items():
            if field not in doc or doc[field] is None:
                doc[field] = default

        return doc

    def build_time_condition(self, start_time: datetime.datetime, end_time: datetime.datetime) -> dict:
        # 转换为UTC时间并格式化为ISO字符串
        utc_start = start_time.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        utc_end = end_time.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        return {"PUB_TIME": {"$gte": utc_start, "$lte": utc_end}}

    def build_list_condition(self, field: str, values: Union[str, List[str]]) -> dict:
        """构建列表字段查询条件"""
        target_list = [values] if isinstance(values, str) else values
        return {field: {"$in": target_list}}

    def build_keyword_or_condition(self, keywords: str) -> dict:
        cleaned_keywords = self.sanitize_keywords(keywords)
        # 平铺所有字段条件（无需二维列表）
        conditions = []
        for kw in cleaned_keywords:
            conditions.append({"EVENT_BRIEF": {"$regex": kw, "$options": "i"}})
            conditions.append({"EVENT_TEXT": {"$regex": kw, "$options": "i"}})
        return {"$or": conditions}  # 匹配任一条件

    def build_keyword_and_condition(self, keywords: str) -> dict:
        """构建全文检索查询条件（同时匹配所有关键词）"""
        cleaned_keywords = self.sanitize_keywords(keywords)
        if not cleaned_keywords:
            return {}

        conditions = []
        for kw in cleaned_keywords:
            # 每个关键词在任意字段出现即可（字段间OR）
            kw_condition = {
                "$or": [
                    {"EVENT_BRIEF": {"$regex": kw, "$options": "i"}},
                    {"EVENT_TEXT": {"$regex": kw, "$options": "i"}}
                ]
            }
            conditions.append(kw_condition)  # 每个关键词独立条件组

        # 用AND组合所有关键词条件
        return {"$and": conditions}

    def sanitize_keywords(self, keywords: str) -> List[str]:
        """清洗并优化关键词"""
        # 分割关键词并移除空值
        keywords = [kw.strip() for kw in keywords.split() if kw.strip()]

        # 转义特殊字符并添加边界匹配
        return [r'\b' + re.escape(kw) + r'\b' for kw in keywords]

    def execute_query(
            self,
            collection: pymongo.collection.Collection,
            query: dict,
            skip: Optional[int] = None,
            limit: Optional[int] = None
    ) -> List[dict]:
        """Execute query and process results with pagination support

        Args:
            collection: MongoDB collection to query
            query: MongoDB query dictionary
            skip: Number of documents to skip (for pagination)
            limit: Maximum number of documents to return

        Returns:
            List of processed documents matching the query
        """
        try:
            # Apply sorting by TIME field in descending order
            cursor = collection.find(query).sort("PUB_TIME", pymongo.DESCENDING)

            # Apply pagination parameters if provided
            if skip is not None and skip > 0:
                cursor = cursor.skip(skip)  # Skip documents for pagination [6,7](@ref)

            if limit is not None and limit > 0:
                cursor = cursor.limit(limit)  # Limit result size [6](@ref)

            # Process and return results
            return [self.process_document(doc) for doc in cursor]

        except pymongo.errors.PyMongoError as e:
            logger.error(f"MongoDB query execution failed: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during query execution: {str(e)}", stack_info=True)
            return []

