import uuid
import time
import queue
import logging
import datetime
from typing import List, Tuple, Optional

import pymongo
import requests
import threading
from flask import Flask, request, jsonify
from werkzeug.serving import make_server
from pymongo.errors import ConnectionFailure
from pydantic import BaseModel, ValidationError
from requests.exceptions import RequestException

from Tools.IntelligenceAnalyzerProxy import analyze_with_ai
from Tools.MongoDBAccess import MongoDBStorage
from Tools.OpenAIClient import OpenAICompatibleAPI
from Tools.VectorDatabase import VectorDatabase
from prompts import DEFAULT_ANALYSIS_PROMPT


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CollectedData(BaseModel):
    UUID: str                           # [MUST]: The UUID to identify a message.
    token: str                          # [MUST]: The token to identify the legal end point.
    source: str | None = None           # (Optional): Message source. If it requires reply.
    target: str | None = None           # (Optional): Message source. If it requires reply.
    prompt: str | None = None           # (Optional): The prompt to ask LLM to process this message.

    title: str | None = None            # [MUST]: The content to be processed.
    authors: List[str] | None = []      # (Optional): Article authors.
    content: str                        # [MUST]: The content to be processed.
    pub_time: str | None = None         # (Optional): Content publish time.
    informant: str | None = None        # (Optional): The source of message.


class ProcessedData(BaseModel):
    UUID: str
    TIME: str | None = None
    LOCATION: list | None = None
    PEOPLE: list | None = None
    ORGANIZATION: list | None = None
    EVENT_BRIEF: str | None = None
    EVENT_TEXT: str | None = None
    RATE: dict | None = {}
    IMPACT: str | None = None
    TIPS: str | None = None


def check_sanitize_dict(data: dict, verifier: BaseModel) -> Tuple[dict, str]:
    try:
        validated_data = verifier.model_validate(data).model_dump(exclude_unset=True, exclude_none=True)
        return validated_data, ''
    except ValidationError as e:
        logger.error(f'Collected data field missing: {str(e)}')
        return {}, str(e)
    except Exception as e:
        logger.error(f'Validate Collected data fail: {str(e)}')
        return {}, str(e)


def common_post(url: str, data: dict, timeout: int) -> dict:
    try:
        response = requests.post(
            url,
            json=data,
            headers={'X-Request-Source': 'IntelligenceHub'},
            timeout=timeout
        )

        response.raise_for_status()
        logger.info(f"Sent request to {url} successful UUID={data['UUID']}")
        return response.json()

    except RequestException as e:
        logger.error(f"Sent request to {url} fail: {str(e)}")
        return {"status": "error", "uuid": data.get('UUID'), "reason": str(e)}

    except Exception as e:
        logger.error(f"Sent request to {url} fail: {str(e)}")
        return {"status": "error", "uuid": '', "reason": str(e)}


# POST_PROCESS_DATA_FIELDS = {
#     'UUID': 'M',
#     'PROMPT': 'M',
#     'TEXT': 'M',
# }
#
#
# PROCESSED_DATA_FIELDS = {
#     'UUID': 'M',        # [MUST]: The UUID to identify a message.
#     'TIME': 'M',
#     'LOCATION': 'M',
#     'PEOPLE': 'M',
#     'ORGANIZATION': 'M',
#     'EVENT_BRIEF': 'M',
#     'EVENT_TEXT': 'M',
#     'RATE': 'M',
#     'IMPACT': 'O'
# }


def post_collected_intelligence(url: str, data: CollectedData, timeout=10) -> dict:
    """
    Post collected intelligence to IntelligenceHub (/collect).
    :param url: IntelligenceHub url (without '/collect' path).
    :param data: Collector data.
    :param timeout: Timeout in second
    :return: Requests response or {'status': 'error', 'reason': 'error description'}
    """
    if 'UUID' not in data:
        data['UUID'] = str(uuid.uuid4())
        logger.info(f"Generated new UUID: {data['UUID']}")
    validated_data, error_text = check_sanitize_dict(dict(data), CollectedData)
    if error_text:
        return {'status': 'error', 'reason': error_text}
    return common_post(f'{url}/collect', validated_data, timeout)


def post_processed_intelligence(url: str, data: ProcessedData, timeout=10) -> dict:
    """
    Post processed data to IntelligenceHub (/feedback).
    :param url: IntelligenceHub url (without '/feedback' path).
    :param data: Processed data.
    :param timeout: Timeout in second
    :return: Requests response or {'status': 'error', 'reason': 'error description'}
    """
    validated_data, error_text = check_sanitize_dict(dict(data), ProcessedData)
    if error_text:
        return {'status': 'error', 'reason': error_text}
    return common_post(f'{url}/feedback', validated_data, timeout)


APPENDIX_TIME_GOT       = '__TIME_GOT__'            # Timestamp of get from collector
APPENDIX_TIME_POST      = '__TIME_POST__'           # Timestamp of post to processor
APPENDIX_TIME_DONE      = '__TIME_DONE__'           # Timestamp of retrieve from processor
APPENDIX_RETRY_COUNT    = '__RETRY_COUNT__'
APPENDIX_ARCHIVED_FLAG  = '__ARCHIVED__'

APPENDIX_FIELDS = [
    APPENDIX_TIME_GOT,
    APPENDIX_TIME_POST,
    APPENDIX_TIME_DONE,
    APPENDIX_RETRY_COUNT,
    APPENDIX_ARCHIVED_FLAG
]


def data_without_appendix(data: dict) -> dict:
    return {k: v for k, v in data.items() if k not in APPENDIX_FIELDS}


DEFAULT_IHUB_PORT = 5000
DEFAULT_MONGO_DB_URL = "mongodb://localhost:27017/"
DEFAULT_PROCESSOR_URL = "http://localhost:5001/process"

OPEN_AI_API_BASE_URL = "https://api.siliconflow.cn"

import re
from datetime import datetime
from typing import Optional, List, Tuple, Union
import pymongo
import pytz  # 时区处理


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


class IntelligenceHub:
    def __init__(self, serve_port: int = DEFAULT_IHUB_PORT,
                 db_vector: Optional[VectorDatabase] = None,
                 db_cache: Optional[MongoDBStorage] = None,
                 db_archive: Optional[MongoDBStorage] = None,
                 intelligence_processor_uri=DEFAULT_PROCESSOR_URL,
                 intelligence_process_timeout: int = 5 * 60,
                 intelligence_process_max_retries=3,
                 request_timeout: int = 2):

        # ---------------- Parameters ----------------

        self.serve_port = serve_port
        self.vector_db_idx = db_vector
        self.mongo_db_cache = db_cache
        self.mongo_db_archive = db_archive

        self.intelligence_processor_uri = intelligence_processor_uri
        self.intelligence_process_timeout = intelligence_process_timeout
        self.intelligence_process_max_retries = intelligence_process_max_retries

        self.request_timeout = request_timeout

        # -------------- Queues Related --------------

        self.original_queue = queue.Queue()             # Original intelligence queue
        self.processed_queue = queue.Queue()            # Processed intelligence queue
        self.processing_table = {}
        self.archived_counter = 0
        self.drop_counter = 0
        self.error_counter = 0

        # --------------------------------------------

        self._load_vector_db()
        self._load_unarchived_data()

        # ---------------- Web Service ----------------

        self.app = Flask(__name__)
        self._setup_apis()
        self.server = make_server('0.0.0.0', self.serve_port, self.app)

        # ---------------- AI Proxy ----------------

        self.api_client = OpenAICompatibleAPI(
            api_base_url=OPEN_AI_API_BASE_URL,
            token='',
            default_model='Qwen/Qwen3-235B-A22B')

        # ----------------- Threads -----------------

        self.lock = threading.Lock()
        self.shutdown_flag = threading.Event()

        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.analysis_thread = threading.Thread(target=self._ai_analysis_thread, daemon=True)
        self.post_process_thread = threading.Thread(target=self._post_process_worker, daemon=True)

        logger.info('***** IntelligenceHub init complete *****')

    # ----------------------------------------------------- Setups -----------------------------------------------------

    def _setup_apis(self):
        @self.app.route('/collect', methods=['POST'])
        def collect_api():
            try:
                data = request.json
                validated_data, error_text = check_sanitize_dict(dict(data), CollectedData)
                if error_text:
                    return jsonify({'status': 'error', 'reason': error_text})

                self._cache_original_data(validated_data)

                validated_data[APPENDIX_TIME_GOT] = time.time()
                self.original_queue.put(validated_data)

                return jsonify({"status": "queued", "uuid": validated_data["UUID"]})
            except Exception as e:
                logger.error(f"Collection API fail: {str(e)}")
                return jsonify({"status": "error", "uuid": ""})

        @self.app.route('/feedback', methods=['POST'])
        def feedback_api():
            try:
                data = request.json

                validated_data, error_text = check_sanitize_dict(dict(data), ProcessedData)
                if error_text:
                    return jsonify({'status': 'error', 'reason': error_text})

                uuid_str = validated_data["UUID"]
                validated_data[APPENDIX_TIME_DONE] = time.time()

                return jsonify({"status": "acknowledged", "uuid": uuid_str})
            except Exception as e:
                logger.error(f"Feedback API error: {str(e)}")
                return jsonify({"status": "error", "uuid": ""})

    def _load_vector_db(self):
        self.vector_db_idx.load()

    def _load_unarchived_data(self):
        """Load unarchived data into a queue."""
        if not self.mongo_db_cache:
            return

        try:
            # 1. Build query
            query = {APPENDIX_ARCHIVED_FLAG: {"$exists": False}}

            # 2. Stream processing
            cursor = self.mongo_db_cache.collection.find(query)
            for doc in cursor:
                # Convert ObjectId to string
                doc['_id'] = str(doc['_id'])

                # 3. Handle queue with timeout
                try:
                    self.original_queue.put(doc, block=True, timeout=5)
                except queue.Full:
                    logger.error("Queue full, failed to add document")
                    break

            logger.info(f'Previous unprocessed data loaded, item count: {self.original_queue.qsize()}')

        except pymongo.errors.PyMongoError as e:
            logger.error(f"Database operation failed: {str(e)}")

    # ------------------------------------------------ Public Functions ------------------------------------------------

    def startup(self):
        self.server_thread.start()
        self.analysis_thread.start()
        self.post_process_thread.start()

    def shutdown(self, timeout=10):
        """优雅关闭系统"""
        logger.info("启动关闭流程...")

        # 1. 设置关闭标志
        self.shutdown_flag.set()

        # 2. 停止WEB服务器
        self.server.shutdown()

        # 3. Clear and persists unprocessed data. Put None to un-block all threads.
        self._clear_queues()

        # 4. 等待工作线程结束
        self.server_thread.join(timeout=timeout)
        self.post_process_thread.join(timeout=timeout)

        # 6. 清理资源
        self._cleanup_resources()
        logger.info("Service has stopped.")

    def get_intelligence(self, _uuid: str):
        query_engine = IntelligenceQueryEngine(self.mongo_db_archive)
        return query_engine.get_intelligence(_uuid)

    def query_intelligence(self,
                           *,
                           db: str = 'cache',
                           period:      Optional[Tuple[datetime.date, datetime.date]] = None,
                           locations:   Optional[List[str]] = None,
                           peoples:     Optional[List[str]] = None,
                           organizations: Optional[List[str]] = None,
                           keywords: Optional[str] = None
                           ):
        query_engine = IntelligenceQueryEngine(self.mongo_db_archive)
        result = query_engine.query_intelligence(
            period = period, locations = locations, peoples = peoples,
            organizations = organizations, keywords = keywords)
        return result


    @property
    def statistics(self):
        return {
            'original': self.original_queue.qsize(),
            'processing': len(self.processing_table),
            'processed': self.processed_queue.qsize(),
            'archived': self.archived_counter,
            'dropped': self.drop_counter,
            'error': self.error_counter,
        }

    # --------------------------------------------------- Shutdowns ----------------------------------------------------

    def _clear_queues(self):
        unprocessed = []
        with self.lock:
            while not self.original_queue.empty():
                item = self.original_queue.get()
                unprocessed.append(item)
                self.original_queue.task_done()
        # 保存到文件或数据库
        # self._save_to_file(unprocessed, 'pending_tasks.json')

    def _cleanup_resources(self):
        if self.vector_db_idx:
            self.vector_db_idx.save()

        if self.mongo_db_cache:
            self.mongo_db_cache.close()

        if self.mongo_db_archive:
            self.mongo_db_archive.close()

    # ---------------------------------------------------- Workers -----------------------------------------------------

    def _ai_analysis_thread(self):
        while not self.shutdown_flag.is_set():
            try:
                data = self.original_queue.get(block=True)
                if not data:
                    self.original_queue.task_done()
                    continue
            except queue.Empty:
                continue
            try:
                self._notice_data_in_processing(data)
                result = analyze_with_ai(self.api_client, DEFAULT_ANALYSIS_PROMPT, data)
                self.original_queue.task_done()

                validated_data = self._validate_sanitize_processed_data(result)

                if validated_data:
                    validated_data[APPENDIX_TIME_DONE] = time.time()
                    self.processed_queue.put(validated_data)
            except Exception as e:
                logger.error(f"_processing_loop error: {str(e)}")
            finally:
                self._notice_data_quit_processing(data)

    def _post_process_worker(self):
        while not self.shutdown_flag.is_set():
            try:
                data = self.processed_queue.get(timeout=1)

                if 'UUID' not in data:
                    # There's no reason to reach this path.
                    logger.error('NO UUID field. This data is not even error.')
                    self.error_counter += 1
                    self.processed_queue.task_done()
                    continue

                # According to the prompt (DEFAULT_ANALYSIS_PROMPT),
                #   if the article does not have any value, just "UUID" is returned.
                if 'EVENT_TEXT' not in data:
                    logger.info(f"Message {data['UUID']} not archived.")
                    self._mark_cache_data_archived_flag(data['UUID'], 'F')
                    self.drop_counter += 1
                    self.processed_queue.task_done()
                    continue

                validated_data = self._validate_sanitize_processed_data(data)

                if not validated_data:
                    self._mark_cache_data_archived_flag(validated_data['UUID'], 'E')
                    self.error_counter += 1
                    self.processed_queue.task_done()
                    continue

                try:
                    self._archive_processed_data(validated_data)
                    self._index_archived_data(validated_data)
                    self._mark_cache_data_archived_flag(validated_data['UUID'], 'T')
                    self.archived_counter += 1

                    logger.info(f"Message {validated_data['UUID']} archived.")

                    # TODO: Call post processor plugins
                except Exception as e:
                    logger.error(f"Archived fail with exception: {str(e)}")
                    self._mark_cache_data_archived_flag(validated_data['UUID'], 'E')
                finally:
                    self.processed_queue.task_done()
            except queue.Empty:
                continue

    # ------------------------------------------------ Helpers ------------------------------------------------

    def _notice_data_in_processing(self, data: dict):
        with self.lock:
            uuid_str = data['UUID']
            if uuid_str in self.processing_table:
                logger.warning(f'Found existing processing data {uuid_str}, maybe data has duplicated processing.')
            else:
                self.processing_table[uuid_str] = data

    def _notice_data_quit_processing(self, data: dict):
        with self.lock:
            uuid_str = data['UUID']
            if uuid_str not in self.processing_table:
                logger.warning(f'No processing data {uuid_str}, maybe data processing notification missing.')
            else:
                del self.processing_table[uuid_str]

    def _index_archived_data(self, data: dict):
        self.vector_db_idx.add_text(data['UUID'], data['EVENT_TEXT'])
        # TODO: Decrease save frequency.
        self.vector_db_idx.save()

    def _cache_original_data(self, data: dict):
        try:
            if self.mongo_db_cache:
                self.mongo_db_cache.insert(data)
        except Exception as e:
            logger.error(f'Cache original data fail: {str(e)}')

    def _archive_processed_data(self, data: dict):
        try:
            if self.mongo_db_archive:
                self.mongo_db_archive.insert(data)
        except Exception as e:
            logger.error(f'Archive processed data fail: {str(e)}')

    def _mark_cache_data_archived_flag(self, _uuid: str, archived: bool or str):
        """
        20250530: Extend the archived parameter as str. It can be the following values:
            'T' - True. Archived
            'F' - False. Low value data so not archived
            'E' - Error. We should go back and check the error, then analysis again.
        :param _uuid:
        :param archived:
        :return:
        """
        try:
            if isinstance(archived, bool):
                archived = 'T' if archived else 'F'
            if self.mongo_db_cache:
                self.mongo_db_cache.update({'UUID': _uuid}, {APPENDIX_ARCHIVED_FLAG: archived})
        except Exception as e:
            logger.error(f'Cache original data fail: {str(e)}')

    def _validate_sanitize_processed_data(self, data: dict) -> dict or None:
        try:
            validated_data, error_text = check_sanitize_dict(dict(data), ProcessedData)
            if error_text:
                print('Processed data check fail - Drop.')
                print('-------------------------------')
                print(str(data))
                print('-------------------------------')
                with self.lock:
                    self.drop_counter += 1
                return None
            return validated_data
        except Exception as e:
            logger.error(f"Check processed data got exception: {str(e)}")
            with self.lock:
                self.drop_counter += 1
            return None


def main():
    hub = IntelligenceHub(
        intelligence_processor_uri='http://192.168.50.220:5678/webhook-test/intelligence_process',
        db_vector=VectorDatabase('IntelligenceIndex'),
        db_cache=MongoDBStorage(collection_name='intelligence_cached'),
        db_archive=MongoDBStorage(collection_name='intelligence_archived'))
    hub.startup()

    result = hub.get_intelligence('a6a485dd-d843-4acd-b58a-4d516bfb0fa8')
    print(result)

    result = hub.query_intelligence(locations=['美国'])
    print(result)

    while True:
        print(f'Hub queue size: {hub.statistics}')
        time.sleep(2)


if __name__ == '__main__':
    main()
