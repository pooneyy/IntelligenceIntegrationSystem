import time
import queue
import logging
import pymongo
import datetime
import threading

from attr import dataclass
from pydantic import BaseModel
from typing import List, Tuple, Optional
from pymongo.errors import ConnectionFailure

from prompts import ANALYSIS_PROMPT
from Tools.IntelligenceAnalyzerProxy import analyze_with_ai
from Tools.MongoDBAccess import MongoDBStorage
from Tools.OpenAIClient import OpenAICompatibleAPI
from Tools.RSSPublisher import RSSPublisher, RssItem
from Tools.VectorDatabase import VectorDatabase
from MyPythonUtility.DictTools import check_sanitize_dict
from ServiceComponent.IntelligenceQueryEngine import IntelligenceQueryEngine


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
    informant: str | None = None        # (Optional): The source of message (like URL).


class ProcessedData(BaseModel):
    UUID: str
    INFORMANT: str | None = None
    TIME: str | None = None
    LOCATION: list | None = None
    PEOPLE: list | None = None
    ORGANIZATION: list | None = None
    EVENT_TITLE: str | None = None
    EVENT_BRIEF: str | None = None
    EVENT_TEXT: str | None = None
    RATE: dict | None = {}
    IMPACT: str | None = None
    TIPS: str | None = None


class ArchivedDataExtraFields(BaseModel):
    RAW_DATA: dict | None
    SUBMITTER: str | None


class ArchivedData(ProcessedData, ArchivedDataExtraFields):
    pass


APPENDIX_TIME_GOT       = '__TIME_GOT__'            # Timestamp of get from collector
APPENDIX_TIME_POST      = '__TIME_POST__'           # Timestamp of post to processor
APPENDIX_TIME_DONE      = '__TIME_DONE__'           # Timestamp of retrieve from processor
APPENDIX_TIME_ARCHIVED  = '__TIME_ARCHIVED__'
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


class IntelligenceHub:
    @dataclass
    class Error:
        success: bool
        exception: Exception = None
        error_list: List[str] = []
        warning_list: List[str] = []

        def __bool__(self):
            return self.success

    def __init__(self, *,
                 ref_url: str = 'http://locohost:8080',
                 db_vector: Optional[VectorDatabase] = None,
                 db_cache: Optional[MongoDBStorage] = None,
                 db_archive: Optional[MongoDBStorage] = None,
                 ai_client: OpenAICompatibleAPI):
        """
        Init IntelligenceHub.
        :param ref_url: The reference url for sub-resource url generation.
        :param db_vector: Vector DB for text RAG indexing.
        :param db_cache: The mongodb for caching collected data.
        :param db_archive: The mongodb for archiving processed data.
        :param ai_client: The openai-like client for data processing.
        """

        # ---------------- Parameters ----------------

        self.reference_url = ref_url
        self.vector_db_idx = db_vector
        self.mongo_db_cache = db_cache
        self.mongo_db_archive = db_archive
        self.open_ai_client = ai_client

        # -------------- Queues Related --------------

        self.original_queue = queue.Queue()             # Original intelligence queue
        self.processed_queue = queue.Queue()            # Processed intelligence queue
        self.processing_table = {}
        self.archived_counter = 0
        self.drop_counter = 0
        self.error_counter = 0

        # --------------- Components ----------------

        self.rss_publisher = RSSPublisher()

        # ----------------- Database -----------------

        self._load_vector_db()
        self._load_unarchived_data()
        self._load_rss_publish_data()

        # ----------------- Threads -----------------

        self.lock = threading.Lock()
        self.shutdown_flag = threading.Event()

        self.analysis_thread = threading.Thread(target=self._ai_analysis_thread, daemon=True)
        self.post_process_thread = threading.Thread(target=self._post_process_worker, daemon=True)

        logger.info('***** IntelligenceHub init complete *****')

    # ----------------------------------------------------- Setups -----------------------------------------------------

    def _load_vector_db(self):
        if self.vector_db_idx:
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

    def _load_rss_publish_data(self):
        try:
            cursor = self.mongo_db_archive.collection.find().limit(50)
            rss_items = []

            for doc in cursor:
                if 'EVENT_BRIEF' in doc and 'UUID' in doc:
                    rss_item = RssItem(
                        title=doc['EVENT_BRIEF'],
                        link=f"{self.reference_url}/intelligence/{doc['UUID']}",
                        description=doc['EVENT_BRIEF'],
                        pub_date=datetime.datetime.now())
                    rss_items.append(rss_item)
                else:
                    logger.warning(f'Warning: archived data field missing.')

            self.rss_publisher.add_items(rss_items)
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Database operation failed: {str(e)}")

    # ----------------------------------------------- Startup / Shutdown -----------------------------------------------

    def startup(self):
        self.analysis_thread.start()
        self.post_process_thread.start()

    def shutdown(self, timeout=10):
        """优雅关闭系统"""
        logger.info("启动关闭流程...")

        # 设置关闭标志
        self.shutdown_flag.set()

        # Clear and persists unprocessed data. Put None to un-block all threads.
        self._clear_queues()

        # 等待工作线程结束
        self.analysis_thread.join(timeout=timeout)
        self.post_process_thread.join(timeout=timeout)

        # 清理资源
        self._cleanup_resources()
        logger.info("Service has stopped.")

    # --------------------------------------- Shutdowns ---------------------------------------

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

    # ---------------------------------------------- Statistics and Debug ----------------------------------------------

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

    # ------------------------------------------------ Public Functions ------------------------------------------------

    # ---------------------------------------- Web API ----------------------------------------

    def submit_collected_data(self, data: dict) -> True or Error:
        try:
            validated_data, error_text = check_sanitize_dict(dict(data), CollectedData)
            if error_text:
                return IntelligenceHub.Error(False, error_list=[error_text])

            self._cache_original_data(validated_data)

            validated_data[APPENDIX_TIME_GOT] = time.time()
            self.original_queue.put(validated_data)

            return True
        except Exception as e:
            logger.error(f"Collection API fail: {str(e)}")
            return IntelligenceHub.Error(False, e, [str(e)])

    def submit_archived_data(self, data: dict) -> True or Error:
        try:
            validated_data, error_text = check_sanitize_dict(dict(data), ArchivedData)
            if error_text:
                return IntelligenceHub.Error(False, error_list=[error_text])

            if validated_data:
                validated_data[APPENDIX_TIME_ARCHIVED] = time.time()
                self.processed_queue.put(validated_data)

            return True
        except Exception as e:
            logger.error(f"Submit archived data API error: {str(e)}")
            return IntelligenceHub.Error(False, e, [str(e)])

    # ------------------------------------------------------------------------------------------

    def get_rssfeed(self) -> str or Error:
        try:
            feed_xml = self.rss_publisher.generate_feed(
                'IIS',
                f'http://sleepysoft.org/intelligence',
                'IIS Processed Intelligence')
            return feed_xml
        except Exception as e:
            logger.error(f"Rss Feed API error: {str(e)}", stack_info=True)
            return IntelligenceHub.Error(False, e, [str(e)])

    def get_intelligence(self, _uuid: str) -> dict:
        query_engine = IntelligenceQueryEngine(self.mongo_db_archive)
        return query_engine.get_intelligence(_uuid)

    def query_intelligence(self,
                           *,
                           db: str = 'cache',
                           period:      Optional[Tuple[datetime.date, datetime.date]] = None,
                           locations:   Optional[List[str]] = None,
                           peoples:     Optional[List[str]] = None,
                           organizations: Optional[List[str]] = None,
                           keywords: Optional[str] = None,
                           skip: Optional[str] = None,
                           limit: int = 100,
                           ) -> List[dict]:
        query_engine = IntelligenceQueryEngine(self.mongo_db_archive)
        result = query_engine.query_intelligence(
            period = period, locations = locations, peoples = peoples,
            organizations = organizations, keywords = keywords, skip=skip, limit=limit)
        return result

    def get_intelligence_summary(self) -> Tuple[int, str]:
        query_engine = IntelligenceQueryEngine(self.mongo_db_archive)
        summary = query_engine.get_intelligence_summary()
        return summary["total_count"], summary["base_uuid"]

    def get_paginated_intelligences(self, base_uuid: Optional[str], offset: int, limit: int) -> List[dict]:
        query_engine = IntelligenceQueryEngine(self.mongo_db_archive)
        result = query_engine.get_paginated_intelligences(base_uuid, offset, limit)
        return result

    # ---------------------------------------------------- Workers -----------------------------------------------------

    def _ai_analysis_thread(self):
        if not self.open_ai_client:
            logger.info('**** NO AI API client - Thread QUIT ****')
            return

        ai_process_max_retry = 3

        while not self.shutdown_flag.is_set():
            try:
                original_data = self.original_queue.get(block=True)
                if not original_data:
                    self.original_queue.task_done()
                    continue
            except queue.Empty:
                continue
            try:
                self._notice_data_in_processing(original_data)

                retry = 0
                result = None
                # Add retry to get correct answer from AI
                while retry < ai_process_max_retry and not self.shutdown_flag.is_set():
                    result = analyze_with_ai(self.open_ai_client, ANALYSIS_PROMPT, original_data)
                    if 'error' not in result:
                        break
                    retry += 1

                self.original_queue.task_done()

                if not result or 'error' in result:
                    # TODO: Mark data as dropped in mongodb to really drop it.
                    logger.error(f"AI process error after {retry} retries.")
                    continue

                if retry:
                    logger.info(f'Got AI correct answer after {retry} retires.')

                validated_data = self._validate_sanitize_processed_data(result)

                validated_data['RAW_DATA'] = original_data
                validated_data['SUBMITTER'] = 'Analysis Thread'

                self.submit_archived_data(validated_data)

            except Exception as e:
                logger.error(f"AI process error: {str(e)}")
            finally:
                self._notice_data_quit_processing(original_data)

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

                # According to the prompt (ANALYSIS_PROMPT),
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
                    self._publish_article_to_rss(validated_data)
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
        if self.vector_db_idx:
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

    def _publish_article_to_rss(self, data: dict):
        self.rss_publisher.add_item(title=data.get('EVENT_TITLE', '') or data.get('EVENT_BRIEF', ''),
                                    link=f"{self.reference_url}/intelligence/{data['UUID']}",
                                    description=data.get('EVENT_BRIEF', ''),
                                    pub_date=datetime.datetime.now())

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
