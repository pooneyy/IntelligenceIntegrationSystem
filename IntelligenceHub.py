import copy
import json
import uuid
import time
import queue
import logging
import datetime
import traceback
from typing import List, Tuple

import pymongo
import requests
import threading
from flask import Flask, request, jsonify
from werkzeug.serving import make_server
from pymongo.errors import ConnectionFailure
from pydantic import BaseModel, ValidationError
from requests.exceptions import RequestException

from faiss import IndexFlatL2
import numpy as np

from Tools.IntelligenceAnalyzerProxy import analyze_with_ai
from Tools.OpenAIClient import OpenAICompatibleAPI
from prompts import DEFAULT_ANALYSIS_PROMPT


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class VectorIndex:
    def __init__(self, dim=512):
        self.index = IndexFlatL2(dim)
        self.id_map = {}

    def add_vector(self, doc_id, vector):
        idx = len(self.id_map)
        self.id_map[idx] = doc_id
        self.index.add(np.array([vector], dtype='float32'))


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
    TIME: str | None
    LOCATION: str | None
    PEOPLE: str | None
    ORGANIZATION: str | None
    EVENT_BRIEF: str | None
    EVENT_TEXT: str | None
    RATE: str | None
    IMPACT: str | None


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
    validated_data, error_text = check_sanitize_dict(dict(data), CollectedData)
    if error_text:
        return {'status': 'error', 'reason': error_text}
    return common_post(f'{url}/feedback', validated_data, timeout)


APPENDIX_TIME_GOT       = '__TIME_GOT__'            # Timestamp of get from collector
APPENDIX_TIME_POST      = '__TIME_POST__'           # Timestamp of post to processor
APPENDIX_TIME_DONE      = '__TIME_DONE__'           # Timestamp of retrieve from processor
APPENDIX_RETRY_COUNT    = '__RETRY_COUNT__'

APPENDIX_FIELDS = [
    APPENDIX_TIME_GOT,
    APPENDIX_TIME_POST,
    APPENDIX_TIME_DONE,
    APPENDIX_RETRY_COUNT
]


DEFAULT_IHUB_PORT = 5000
DEFAULT_MONGO_DB_URL = "mongodb://localhost:27017/"
DEFAULT_PROCESSOR_URL = "http://localhost:5001/process"

OPEN_AI_API_BASE_URL = "https://api.siliconflow.cn"


class IntelligenceHub:
    def __init__(self, serve_port: int = DEFAULT_IHUB_PORT,
                 mongo_db_uri=DEFAULT_MONGO_DB_URL,
                 intelligence_processor_uri=DEFAULT_PROCESSOR_URL,
                 intelligence_process_timeout: int = 5 * 60,
                 intelligence_process_max_retries=3,
                 request_timeout: int = 2):

        # ---------------- Parameters ----------------

        self.serve_port = serve_port
        self.mongo_db_uri = mongo_db_uri
        self.intelligence_processor_uri = intelligence_processor_uri
        self.intelligence_process_timeout = intelligence_process_timeout
        self.intelligence_process_max_retries = intelligence_process_max_retries
        self.request_timeout = request_timeout

        # -------------- Queues Related --------------

        self.input_queue = queue.Queue()            # 待处理队列
        self.processing_map = {}                    # 正在处理的任务映射 {uuid: data}
        self.output_queue = queue.Queue()           # 完成处理队列
        self.drop_counter = 0
        self.processed_counter = 0

        # ----------------- Mongo DB -----------------

        self.db = None
        self.archive_col = None
        self.mongo_client = None

        # --------------------------------------------

        self.vector_index = VectorIndex()

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
        self.ai_analysis_thread = threading.Thread(target=self._ai_analysis_thread, daemon=True)
        self.archive_thread = threading.Thread(target=self._archive_worker, daemon=True)
        self.timeout_checker_thread = threading.Thread(target=self._check_timeout_worker, daemon=True)

        # worker_count = max(1, os.cpu_count() // 2)
        # self.processor_executor = ThreadPoolExecutor(
        #     max_workers=worker_count,
        #     thread_name_prefix="ProcessorWorker"
        # )

        # self.server_thread.start()
        # self.archive_thread.start()
        # self.processor_thread.start()
        # self.timeout_checker_thread.start()

    # ----------------------------------------------------- Setups -----------------------------------------------------

    def _setup_apis(self):
        @self.app.route('/collect', methods=['POST'])
        def collect_api():
            try:
                data = request.json
                validated_data, error_text = check_sanitize_dict(dict(data), CollectedData)
                if error_text:
                    return jsonify({'status': 'error', 'reason': error_text})

                validated_data[APPENDIX_TIME_GOT] = time.time()
                self.input_queue.put(validated_data)

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

                with self.lock:
                    if uuid_str in self.processing_map:
                        # original_retry_count, original_data = self.processing_map.pop(uuid_str)
                        # combined_data = {**original_data, **processed_data}  # 合并数据

                        del self.processing_map[uuid_str]
                        self.output_queue.put(validated_data)

                return jsonify({"status": "acknowledged", "uuid": uuid_str})
            except Exception as e:
                logger.error(f"Feedback API error: {str(e)}")
                return jsonify({"status": "error", "uuid": ""})

    # ------------------------------------------------ Public Functions ------------------------------------------------

    def startup(self):
        # for _ in range(self.processor_executor._max_workers):
        #     self.processor_executor.submit(self._processing_loop)

        self.server_thread.start()
        self.archive_thread.start()
        self.timeout_checker_thread.start()

    def shutdown(self, timeout=10):
        """优雅关闭系统"""
        logger.info("启动关闭流程...")

        # 1. 设置关闭标志
        self.shutdown_flag.set()

        # 2. 停止WEB服务器
        self.server.shutdown()

        # 3. Clear and persists unprocessed data. Put None to un-block all threads.
        self._clear_queues()
        # for _ in range(self.processor_executor._max_workers * 2):
        #     self.input_queue.put(None)

        # 4. 等待工作线程结束
        self.server_thread.join(timeout=timeout)
        self.archive_thread.join(timeout=timeout)
        self.timeout_checker_thread.join(timeout=timeout)

        # 5.关闭线程池
        # self.processor_executor.shutdown(wait=True)
        # logger.info("线程池已安全关闭")

        # 6. 清理资源
        self._cleanup_resources()
        logger.info("服务已安全停止")

    @property
    def statistics(self):
        return {
            'input': self.input_queue.qsize(),
            'processing': len(self.processing_map),
            'output': self.output_queue.qsize(),
            'dropped': self.drop_counter
        }

    # --------------------------------------------------- Shutdowns ----------------------------------------------------

    def _clear_queues(self):
        unprocessed = []
        with self.lock:
            while not self.input_queue.empty():
                item = self.input_queue.get()
                unprocessed.append(item)
                self.input_queue.task_done()
        # 保存到文件或数据库
        # self._save_to_file(unprocessed, 'pending_tasks.json')

    def _cleanup_resources(self):
        # 关闭数据库连接
        self.mongo_client.close()

        # 保存索引等持久化操作
        if self.vector_index:
            self.vector_index.save('vector_index.ann')

    # ---------------------------------------------------- Workers -----------------------------------------------------

    def _ai_analysis_thread(self):
        while not self.shutdown_flag.is_set():
            try:
                data = self.input_queue.get(block=True)
                self.input_queue.task_done()

                if not data:
                    continue

                result = analyze_with_ai(self.api_client, DEFAULT_ANALYSIS_PROMPT, data)

                uuid_str = result["UUID"]
                result[APPENDIX_TIME_DONE] = time.time()

                with self.lock:
                    if uuid_str in self.processing_map:
                        del self.processing_map[uuid_str]
                        self.output_queue.put(result)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"_processing_loop error: {str(e)}")

    # def _processing_loop(self):
    #     while not self.shutdown_flag.is_set():
    #         try:
    #             data = self.input_queue.get(block=True)
    #
    #             # Shutdown will put None to make thread un-blocking
    #             if not data:
    #                 self.input_queue.task_done()
    #                 continue
    #
    #             self._process_data(data)
    #         except queue.Empty:
    #             continue
    #         except Exception as e:
    #             logger.error(f"_processing_loop error: {str(e)}")
    #         finally:
    #             self.input_queue.task_done()
    #
    # def _process_data(self, data: dict):
    #     try:
    #         if 'prompt' not in data:
    #             data['prompt'] = DEFAULT_ANALYSIS_PROMPT
    #
    #         data['PROMPT'] = data.pop('prompt')
    #         data['TEXT'] = self._format_message_text(data)
    #
    #         uuid_str = data['UUID']
    #         data[APPENDIX_TIME_POST] = time.time()
    #
    #         # Record data first avoiding request gets exception which makes data lost.
    #         self.processing_map[uuid_str] = data
    #
    #         response = post_to_ai_processor(
    #             self.intelligence_processor_uri,
    #             self._data_without_appendix(data)
    #         )
    #         response.raise_for_status()
    #
    #         # TODO: If the request is actively rejected. Just drop this data.
    #
    #     except Exception as e:
    #         logger.error(f"_process_data got error: {str(e)}")

    def _check_timeout_worker(self):
        while not self.shutdown_flag.is_set():
            current_time = time.time()

            with self.lock:
                uuids = list(self.processing_map.keys())
                for _uuid in uuids:
                    data = self.processing_map[_uuid]
                    if APPENDIX_TIME_POST not in data:
                        del self.processing_map[_uuid]
                        self.drop_counter += 1
                        logger.error(f'{data["uuid"]} has no must have fields - drop.')
                        continue

                    if APPENDIX_RETRY_COUNT not in data:
                        data[APPENDIX_RETRY_COUNT] = self.intelligence_process_max_retries
                    else:
                        if data[APPENDIX_RETRY_COUNT] <= 0:
                            del self.processing_map[_uuid]
                            self.drop_counter += 1
                            logger.error(f'{data["UUID"]} has no retry times - drop.')
                            continue

                    if current_time - data[APPENDIX_TIME_POST] > self.intelligence_process_timeout:
                        data[APPENDIX_RETRY_COUNT] -= 1
                        self.input_queue.put(data)

            time.sleep(self.intelligence_process_timeout / 2)

    def _archive_worker(self):
        while not self.shutdown_flag.is_set():
            try:
                data = self.output_queue.get(timeout=1)

                try:
                    if not self.insert_data_into_mongo(data):
                        raise ValueError

                    # doc = self._create_document(data)
                    # doc_id = self.archive_col.insert_one(doc).inserted_id
                    #
                    # if 'embedding' in data:
                    #     self.vector_index.add_vector(doc_id, data['embedding'])

                    self.processed_counter += 1

                    # TODO: Call post processor plugins
                except Exception as e:
                    logger.error(f"归档失败: {str(e)}")
                    self.output_queue.put(data)  # 重新放回队列
                finally:
                    self.output_queue.task_done()
            except queue.Empty:
                continue

    # ---------------------------------------------------- Helpers -----------------------------------------------------

    def _format_message_text(self, data: dict) -> str:
        appendix = []
        if 'title' in data:
            appendix.append(f"Title: {data['title']}")
        if 'authors' in data:
            appendix.append(f"Author: {data['authors']}")
        if 'pub_time' in data:
            appendix.append(f"Publish Time: {data['pub_time']}")
        if 'informant' in data:
            appendix.append(f"Informant: {data['informant']}")
        return '\n'.join(appendix) + data['content']

    def _data_without_appendix(self, data: dict) -> dict:
        return {k: v for k, v in data.items() if k not in APPENDIX_FIELDS}


def main():
    hub = IntelligenceHub(
        intelligence_processor_uri='http://192.168.50.220:5678/webhook-test/intelligence_process')
    hub.startup()
    while True:
        print(f'Hub queue size: {hub.statistics}')
        time.sleep(1)


if __name__ == '__main__':
    main()
