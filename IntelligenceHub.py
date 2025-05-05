import copy
import uuid
import time
import queue
import logging
import datetime
import traceback

import pymongo
import requests
import threading
from flask import Flask, request, jsonify
from pymongo.errors import ConnectionFailure
from werkzeug.serving import make_server
from requests.exceptions import RequestException
from concurrent.futures import ThreadPoolExecutor
import os

from faiss import IndexFlatL2
import numpy as np


class VectorIndex:
    def __init__(self, dim=512):
        self.index = IndexFlatL2(dim)
        self.id_map = {}

    def add_vector(self, doc_id, vector):
        idx = len(self.id_map)
        self.id_map[idx] = doc_id
        self.index.add(np.array([vector], dtype='float32'))



logging.basicConfig(level=logging.INFO)


def post_collected_intelligence(url: str, data: dict, timeout=10):
    """发送采集数据到收集端点"""
    try:
        if 'UUID' not in data:
            data['UUID'] = str(uuid.uuid4())
            logging.info(f"Generated new UUID: {data['UUID']}")

        response = requests.post(
            f'{url}/collect',
            json=data,
            headers={'X-Request-Source': 'IntelligenceHub'},
            timeout=timeout
        )

        response.raise_for_status()
        logging.info(f"成功发送数据 UUID={data['UUID']}")
        return response.json()

    except RequestException as e:
        logging.error(f"请求失败: {str(e)}")
        return {"status": "error", "uuid": data.get('UUID'), "reason": str(e)}

    except Exception as e:
        logging.error(f"请求失败: {str(e)}")
        return {"status": "error", "uuid": '', "reason": str(e)}


def post_processed_intelligence(url: str, data: dict, timeout=10):
    """发送处理结果到反馈端点"""
    try:
        if 'UUID' not in data:
            error_msg = "Missing UUID in processed data"
            logging.error(error_msg)
            return {"status": "error", "reason": error_msg}

        response = requests.post(
            f'{url}/feedback',
            json=data,
            headers={'X-Request-Source': 'IntelligenceHub'},
            timeout=timeout
        )

        response.raise_for_status()
        logging.info(f"成功反馈处理结果 UUID={data['UUID']}")
        return response.json()

    except RequestException as e:
        logging.error(f"反馈失败: {str(e)}")
        return {"status": "error", "uuid": data['UUID'], "reason": str(e)}

    except Exception as e:
        logging.error(f"反馈失败: {str(e)}")
        return {"status": "error", "uuid": '', "reason": str(e)}


COLLECTOR_DATA_FIELDS = {
    'UUID': 'M',        # [MUST]: The UUID to identify a message.
    'Token': 'M',       # [MUST]: The token to identify the legal end point.
    'source': 'O',      # (Optional): Message source. If it requires reply.
    'target': 'O',      # (Optional): Use for message routing to special module.
    'prompt': 'M',      # [MUST]: The prompt to ask LLM to process this message.
    'content': 'M',     # [MUST]: The content to be processed.
}


PROCESSED_DATA_FIELDS = {
    'UUID': 'M',        # [MUST]: The UUID to identify a message.
}


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


class IntelligenceHub:
    def __init__(self, serve_port: int = 5000,
                 mongo_db_uri="mongodb://localhost:27017/",
                 intelligence_processor_uri="http://localhost:5001/process",
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

        # ----------------- Mongo DB -----------------

        self.db = None
        self.archive_col = None
        self.mongo_client = None

        # --------------------------------------------

        self.vector_index = VectorIndex()

        # ---------------- Web Service----------------

        self.app = Flask(__name__)
        self._setup_apis()
        self.server = make_server('0.0.0.0', self.serve_port, self.app)

        # ----------------- Threads -----------------

        self.lock = threading.Lock()
        self.shutdown_flag = threading.Event()

        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.archive_thread = threading.Thread(target=self._archive_worker, daemon=True)
        self.timeout_checker_thread = threading.Thread(target=self._check_timeout_worker, daemon=True)

        worker_count = max(1, os.cpu_count() // 2)
        self.processor_executor = ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="ProcessorWorker"
        )

        # self.server_thread.start()
        # self.archive_thread.start()
        # self.processor_thread.start()
        # self.timeout_checker_thread.start()

    # ----------------------------------------------------- Setups -----------------------------------------------------

    def _setup_mongo_db(self) -> bool:
        """初始化MongoDB连接并创建必要索引"""
        try:
            # 连接配置
            self.mongo_client = pymongo.MongoClient(
                self.mongo_db_uri,
                maxPoolSize=100,
                serverSelectionTimeoutMS=5000
            )

            # 验证连接
            self.mongo_client.admin.command('ping')
            self.db = self.mongo_client["intelligence_db"]
            self.archive_col = self.db["processed_data"]

            # 定义索引规范（名称、字段、选项）
            index_specs = [
                {
                    "name": "created_at_idx",
                    "keys": [("metadata.created_at", pymongo.ASCENDING)],
                    "description": "基于创建时间的时间范围查询加速"
                },
                {
                    "name": "vector_dim_idx",
                    "keys": [("vector.dim", pymongo.ASCENDING)],
                    "options": {
                        "partialFilterExpression": {"vector": {"$exists": True}},
                        "background": True  # 后台创建避免阻塞
                    },
                    "description": "向量维度查询优化（仅当存在vector字段时建立）"
                },
                {
                    "name": "content_text_idx",
                    "keys": [("raw_data.value", "text")],
                    "options": {
                        "weights": {"raw_data.value": 5},
                        "default_language": "english",
                        "language_override": "language"
                    },
                    "description": "全文检索索引（字段权重优化）"
                }
            ]

            # 检查并创建索引
            existing_indexes = {idx["name"]: idx for idx in self.archive_col.list_indexes()}

            for spec in index_specs:
                index_name = spec["name"]
                index_model = pymongo.IndexModel(spec["keys"], **spec.get("options", {}))

                # 索引存在性检查
                if index_name in existing_indexes:
                    existing = existing_indexes[index_name]
                    # 检查索引定义是否一致
                    if (existing["key"] == index_model.document['key'] and
                            existing.get("partialFilterExpression") == spec.get("options", {}).get(
                                "partialFilterExpression")):
                        logging.info(f"索引 {index_name} 已存在，跳过创建")
                        continue

                    # 删除不一致的旧索引
                    logging.warning(f"检测到不一致索引 {index_name}，重新创建...")
                    self.archive_col.drop_index(index_name)

                # 创建新索引
                logging.info(f"创建索引 {index_name}：{spec['description']}")
                self.archive_col.create_indexes([index_model])

            return True
        except pymongo.errors.OperationFailure as e:
            logging.critical(f"MongoDB索引操作失败: {str(e)}")
            return False
        except Exception as e:
            logging.critical(f"MongoDB连接失败: {str(e)}")
            return False

    def _setup_apis(self):
        @self.app.route('/collect', methods=['POST'])
        def collect_api():
            try:
                data = request.json
                if 'UUID' not in data:
                    return jsonify({"status": "error", "msg": "UUID required"}), 400

                data[APPENDIX_TIME_GOT] = time.time()
                if APPENDIX_RETRY_COUNT in data:
                    logging.warning('Input data has appendix fields')
                    del data[APPENDIX_RETRY_COUNT]

                self.input_queue.put(data)

                return jsonify({"status": "queued", "uuid": data["UUID"]})
            except Exception as e:
                logging.error(f"Collection API fail: {str(e)}")
                return jsonify({"status": "error", "uuid": ""})

        @self.app.route('/feedback', methods=['POST'])
        def feedback_api():
            try:
                processed_data = request.json
                if 'UUID' not in processed_data:
                    return jsonify({"status": "error"}), 400

                uuid_str = processed_data["UUID"]
                processed_data[APPENDIX_TIME_DONE] = time.time()

                with self.lock:
                    if uuid_str in self.processing_map:
                        # original_retry_count, original_data = self.processing_map.pop(uuid_str)
                        # combined_data = {**original_data, **processed_data}  # 合并数据

                        del self.processing_map[uuid_str]
                        self.output_queue.put(processed_data)

                return jsonify({"status": "acknowledged", "uuid": uuid_str})
            except Exception as e:
                logging.error(f"Feedback API error: {str(e)}")
                return jsonify({"status": "error", "uuid": ""})

    # ------------------------------------------------ Public Functions ------------------------------------------------

    def startup(self):
        self._setup_mongo_db()

        for _ in range(self.processor_executor._max_workers):
            self.processor_executor.submit(self._processing_loop)

        self.server_thread.start()
        self.archive_thread.start()
        self.timeout_checker_thread.start()

    def shutdown(self, timeout=10):
        """优雅关闭系统"""
        logging.info("启动关闭流程...")

        # 1. 设置关闭标志
        self.shutdown_flag.set()

        # 2. 停止WEB服务器
        self.server.shutdown()

        # 3. Clear and persists unprocessed data. Put None to un-block all threads.
        self._clear_queues()
        for _ in range(self.processor_executor._max_workers * 2):
            self.input_queue.put(None)

        # 4. 等待工作线程结束
        self.server_thread.join(timeout=timeout)
        self.archive_thread.join(timeout=timeout)
        self.timeout_checker_thread.join(timeout=timeout)

        # 5.关闭线程池
        self.processor_executor.shutdown(wait=True)
        logging.info("线程池已安全关闭")

        # 6. 清理资源
        self._cleanup_resources()
        logging.info("服务已安全停止")

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
        """资源清理"""
        # 关闭数据库连接
        self.mongo_client.close()

        # 保存索引等持久化操作
        if self.vector_index:
            self.vector_index.save('vector_index.ann')

    # ---------------------------------------------------- Workers -----------------------------------------------------

    def _processing_loop(self):
        while not self.shutdown_flag.is_set():
            try:
                data = self.input_queue.get(block=True)

                # Shutdown will put None to make thread un-blocking
                if not data:
                    self.input_queue.task_done()
                    continue

                self._process_data(data)
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"_processing_loop error: {str(e)}")
            finally:
                self.input_queue.task_done()

    def _process_data(self, data: dict):
        try:
            uuid_str = data['UUID']
            data[APPENDIX_TIME_POST] = time.time()

            # Record data first avoiding request gets exception which makes data lost.
            self.processing_map[uuid_str] = data

            response = requests.post(
                self.intelligence_processor_uri,
                json=self._data_without_appendix(data),
                timeout=self.request_timeout
            )
            response.raise_for_status()

            # TODO: If the request is actively rejected. Just drop this data.

        except Exception as e:
            logging.error(f"_process_data got error: {str(e)}")

    def _check_timeout_worker(self):
        while not self.shutdown_flag.is_set():
            current_time = time.time()

            with self.lock:
                for _uuid, data in self.processing_map.items():
                    if APPENDIX_TIME_POST not in data not in data:
                        del self.processing_map[_uuid]
                        self.drop_counter += 1
                        logging.error(f'{data["uuid"]} has no must have fields - drop.')
                        continue

                    if APPENDIX_RETRY_COUNT not in data:
                        data[APPENDIX_RETRY_COUNT] = self.intelligence_process_max_retries
                    else:
                        if data[APPENDIX_RETRY_COUNT] <= 0:
                            del self.processing_map[_uuid]
                            self.drop_counter += 1
                            logging.error(f'{data["uuid"]} has no retry times - drop.')
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
                    doc = self._create_document(data)
                    doc_id = self.archive_col.insert_one(doc).inserted_id
                    # 生成向量并创建索引（示例）
                    if 'embedding' in data:
                        self.vector_index.add_vector(doc_id, data['embedding'])

                    # TODO: Call post processor plugins
                except Exception as e:
                    logging.error(f"归档失败: {str(e)}")
                    self.output_queue.put(data)  # 重新放回队列
                finally:
                    self.output_queue.task_done()
            except queue.Empty:
                continue

    # ---------------------------------------------------- Helpers -----------------------------------------------------

    def _data_without_appendix(self, data: dict) -> dict:
        return {k: v for k, v in data.items() if k not in APPENDIX_FIELDS}

    def _mongo_db_valid(self) -> bool:
        return self.mongo_client and self.db and self.archive_col

    def _create_document(self, raw_data: dict) -> dict:
        """构建符合MongoDB存储规范的文档结构"""
        try:
            # 1. 基础字段校验
            if 'UUID' not in raw_data:
                raise ValueError("文档必须包含UUID字段")

            # 2. 构建标准文档结构
            doc = {
                '_id': raw_data['UUID'],  # 使用UUID作为主键
                'metadata': {
                    'created_at': datetime.datetime.utcnow(),
                    'source_system': 'IntelligenceHub',
                    'version': '1.0'
                },
                'raw_data': copy.deepcopy(raw_data)
            }

            # 3. 处理特殊字段
            if 'processed' in raw_data:
                doc['processed'] = {
                    'timestamp': raw_data.get('processed_time', datetime.datetime.utcnow()),
                    'result': raw_data['processed']
                }
                del doc['raw_data']['processed']

            # 4. 向量数据提取
            if 'embedding' in raw_data:
                doc['vector'] = {
                    'values': raw_data['embedding'],
                    'dim': len(raw_data['embedding']),
                    'model_version': 'text-embedding-3-small'
                }
                del doc['raw_data']['embedding']

            # 5. 数据清洗（示例）
            self._sanitize_data(doc)

            return doc
        except Exception as e:
            logging.error(f"文档创建失败: {str(e)}")
            # 保存原始数据用于调试
            self._save_error_data(raw_data)
            return None

    def _save_error_data(self, data: dict):
        """保存格式错误的数据"""
        error_col = self.db["error_data"]
        try:
            error_col.insert_one({
                "raw": data,
                "error_time": datetime.datetime.utcnow(),
                "error_reason": traceback.format_exc()
            })
        except Exception as e:
            logging.critical(f"连错误数据都无法保存: {str(e)}")

    def _sanitize_data(self, doc: dict):
        """数据清洗和标准化"""
        # 时间格式标准化
        if 'timestamp' in doc['raw_data']:
            try:
                doc['raw_data']['timestamp'] = datetime.datetime.fromisoformat(
                    doc['raw_data']['timestamp']
                )
            except (TypeError, ValueError):
                doc['raw_data']['timestamp'] = datetime.datetime.utcnow()

        # 敏感信息过滤
        sensitive_fields = ['password', 'token', 'credit_card']
        for field in sensitive_fields:
            if field in doc['raw_data']:
                del doc['raw_data'][field]
                logging.warning(f"已过滤敏感字段 {field}")

        # 字段长度限制（防止文档过大）
        max_length = 1000
        for key in list(doc['raw_data'].keys()):
            if isinstance(doc['raw_data'][key], str) and len(doc['raw_data'][key]) > max_length:
                doc['raw_data'][key] = doc['raw_data'][key][:max_length] + '...'


def main():
    hub = IntelligenceHub()
    hub.startup()
    while True:
        print(f'Hub queue size: {hub.statistics}')
        time.sleep(1)


if __name__ == '__main__':
    main()
