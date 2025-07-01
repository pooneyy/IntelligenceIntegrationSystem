
import re
import pytz  # 时区处理
import pymongo
from datetime import datetime
from typing import Optional, List, Tuple, Union

from Tools.MongoDBAccess import MongoDBStorage


class IntelligenceQueryEngine:
    def __init__(self, db: MongoDBStorage):
        self.__mongo_db = db

    def get_intelligence(self, _uuid: str) -> Optional[dict]:
        """通过UUID获取单个情报条目

        参数:
            _uuid (str): 要查询的UUID字符串

        返回:
            Optional[dict]: 如果找到匹配文档则返回文档字典，否则返回None
        """
        # 参数验证
        if not _uuid:
            logger.error("UUID参数为空")
            return None

        try:
            # 尝试获取数据库连接
            collection = self.__mongo_db.collection
            if collection is None:
                logger.error("数据库连接未初始化")
                return None

            # 构建精确匹配UUID的查询
            query = {"UUID": str(_uuid).lower()}

            # 执行查询 - 只获取第一个匹配项
            doc = collection.find_one(query)

            if doc is None:
                logger.warning(f"未找到匹配的UUID: {_uuid}")
                return None

            # 处理文档格式
            return self.process_document(doc)

        except pymongo.errors.PyMongoError as e:
            logger.error(f"数据库查询失败: {str(e)}")
            return None
        except Exception as e:
            logger.exception(f"未知错误: {str(e)}")
            return None

    def query_intelligence(
            self,
            *,
            period: Optional[Tuple[datetime, datetime]] = None,
            locations: Optional[Union[str, List[str]]] = None,
            peoples: Optional[Union[str, List[str]]] = None,
            organizations: Optional[Union[str, List[str]]] = None,
            keywords: Optional[str] = None
    ) -> List[dict]:
        """执行智能情报查询

        参数：
        period: UTC时间范围 (起始时间, 结束时间)
        locations: 地点标识 (str或str列表)
        peoples: 人员标识 (str或str列表)
        organizations: 组织机构标识 (str或str列表)
        keywords: 关键词全文检索

        返回：
        符合条件的情报文档列表
        """
        # 获取指定数据库集合
        collection = self.__mongo_db.collection

        try:
            # 构建MongoDB查询
            query = self.build_intelligence_query(
                period=period,
                locations=locations,
                peoples=peoples,
                organizations=organizations,
                keywords=keywords
            )

            # 执行查询并转换结果
            return self.execute_query(collection, query)

        except pymongo.errors.PyMongoError as e:
            logger.error(f"情报查询失败: {str(e)}")
            return []

    def build_intelligence_query(
            self,
            period: Optional[Tuple[datetime, datetime]] = None,
            locations: Optional[Union[str, List[str]]] = None,
            peoples: Optional[Union[str, List[str]]] = None,
            organizations: Optional[Union[str, List[str]]] = None,
            keywords: Optional[str] = None
    ) -> dict:
        """构建MongoDB查询字典"""
        query_conditions = []

        # 1. 时间范围过滤
        if period:
            query_conditions.append(self.build_time_condition(*period))

        # 2. 地点过滤
        if locations:
            query_conditions.append(self.build_list_condition("LOCATION", locations))

        # 3. 人员过滤
        if peoples:
            query_conditions.append(self.build_list_condition("PEOPLE", peoples))

        # 4. 组织过滤
        if organizations:
            query_conditions.append(self.build_list_condition("ORGANIZATION", organizations))

        # 5. 关键词全文检索
        if keywords:
            query_conditions.append(self.build_keyword_condition(keywords))

        # 组合最终查询条件
        return {"$and": query_conditions} if query_conditions else {}

    def process_document(self, doc: dict) -> dict:
        """标准化处理MongoDB文档"""
        # 转换ObjectId为字符串
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])

        # 确保所有字段都有默认值
        fields = {
            'TIME': None,
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

    def build_time_condition(self, start_time: datetime, end_time: datetime) -> dict:
        """构建时间范围查询条件"""
        # 转换为UTC时间并格式化为ISO字符串
        utc_start = start_time.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        utc_end = end_time.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        return {"TIME": {"$gte": utc_start, "$lte": utc_end}}

    def build_list_condition(self, field: str, values: Union[str, List[str]]) -> dict:
        """构建列表字段查询条件"""
        target_list = [values] if isinstance(values, str) else values
        return {field: {"$in": target_list}}

    def build_keyword_condition(self, keywords: str) -> dict:
        """构建全文检索查询条件"""
        # 清洗并分割关键词
        cleaned_keywords = self.sanitize_keywords(keywords)

        # 为关键字段创建正则表达式条件
        regex_conditions = [
            condition
            for kw_pattern in cleaned_keywords
            for condition in [
                {"EVENT_BRIEF": {"$regex": kw_pattern, "$options": "i"}},
                {"EVENT_TEXT": {"$regex": kw_pattern, "$options": "i"}}
            ]
        ]

        # 使用逻辑OR组合所有关键词条件
        return {"$or": [condition for sublist in regex_conditions for condition in sublist]}

    def sanitize_keywords(self, keywords: str) -> List[str]:
        """清洗并优化关键词"""
        # 分割关键词并移除空值
        keywords = [kw.strip() for kw in keywords.split() if kw.strip()]

        # 转义特殊字符并添加边界匹配
        return [r'\b' + re.escape(kw) + r'\b' for kw in keywords]

    def execute_query(self, collection: pymongo.collection.Collection, query: dict) -> List[dict]:
        """执行查询并处理结果"""
        cursor = collection.find(query).sort("TIME", pymongo.DESCENDING)

        return [self.process_document(doc) for doc in cursor]

    def process_document(self, doc: dict) -> dict:
        """处理MongoDB文档"""
        # 转换ObjectId为字符串
        doc['_id'] = str(doc['_id'])

        # 确保关键字段存在
        for field in ['RATE', 'IMPACT', 'TIPS']:
            doc.setdefault(field, None)

        return doc
