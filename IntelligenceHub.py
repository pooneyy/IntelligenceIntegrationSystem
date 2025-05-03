import os
import uuid
import time
import queue
import logging
import requests
import threading
from flask import Flask, request, jsonify
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from werkzeug.serving import make_server
from requests.exceptions import RequestException

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


COLLECTOR_DATA_MUST_FIELD = ['UUID', 'content', 'prompt']
PROCESSED_DATA_MUST_FIELD = ['UUID']


class IntelligenceHub:
    def __init__(self, serve_port: int = 5000,
                 mongo_db_uri="mongodb://localhost:27017/",
                 intelligence_processor_uri="",
                 intelligence_process_timeout: int = 5 * 60,
                 intelligence_process_max_retries=3,
                 request_timeout: int = 5):

        # ---------------- Parameters ----------------

        self.serve_port = serve_port
        self.mongo_db_uri = mongo_db_uri
        self.intelligence_processor_uri = intelligence_processor_uri
        self.intelligence_process_timeout = intelligence_process_timeout
        self.intelligence_process_max_retries = intelligence_process_max_retries
        self.request_timeout = request_timeout

        # -------------- Queues Related --------------

        self.lock = threading.Lock()
        self.input_queue = queue.PriorityQueue()    # 待处理队列 (优先级, timestamp, data)
        self.processing_map = {}                    # 正在处理的任务映射 {uuid: (retry_count, data)}
        self.output_queue = queue.Queue()           # 完成处理队列

        # ----------------- Mongo DB -----------------

        self.db = None
        self.archive_col = None
        self.mongo_client = None
        self._setup_mongo_db()

        # ---------------- Web Service----------------

        self.app = Flask(__name__)
        self._setup_apis()
        self.server = make_server('0.0.0.0', self.serve_port, self.app)

        # ----------------- Threads -----------------

        # processor_thread_count = os.cpu_count() or 4
        # self.processor_threads = [
        #     threading.Thread(target=self._process_data_worker, daemon=True)
        #     for _ in range(processor_thread_count)
        # ]

        self.shutdown_flag = threading.Event()

        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.archive_thread = threading.Thread(target=self._archive_worker, daemon=True)
        self.processor_thread = threading.Thread(target=self._process_data_worker, daemon=True)
        self.timeout_checker_thread = threading.Thread(target=self._check_timeouts, daemon=True)

        self.server_thread.start()
        self.archive_thread.start()
        self.processor_thread.start()
        self.timeout_checker_thread.start()

    @property
    def queue_sizes(self):
        """获取队列状态"""
        return {
            'input': self.input_queue.qsize(),
            'processing': len(self.processing_map),
            'output': self.output_queue.qsize()
        }

    def shutdown(self, timeout=10):
        """优雅关闭系统"""
        logging.info("启动关闭流程...")

        # 1. 设置关闭标志
        self.shutdown_flag.set()

        # 2. 停止WEB服务器
        self.server.shutdown()
        self.server_thread.join(timeout=2)

        # 3. 等待工作线程结束
        self.archive_thread.join(timeout=timeout)
        self.processor_thread.join(timeout=timeout)
        self.timeout_checker_thread.join(timeout=timeout)

        # 4. 清理资源
        self._cleanup_resources()
        logging.info("服务已安全停止")

    def _cleanup_resources(self):
        """资源清理"""
        # 关闭数据库连接
        self.mongo_client.close()

        # 清空队列（根据业务需求选择）
        self._clear_queues()

        # 保存索引等持久化操作
        self._save_vector_index()

    def _clear_queues(self):
        """持久化未处理数据示例"""
        unprocessed = []
        with self.lock:
            while not self.input_queue.empty():
                item = self.input_queue.get()
                unprocessed.append(item)
                self.input_queue.task_done()

        # 保存到文件或数据库
        # self._save_to_file(unprocessed, 'pending_tasks.json')

    def _save_vector_index(self):
        """向量索引持久化示例"""
        if hasattr(self, 'vector_index'):
            self.vector_index.save('vector_index.ann')

    def _setup_mongo_db(self) -> bool:
        # MongoDB连接池
        try:
            self.mongo_client = MongoClient(
                self.mongo_db_uri,
                maxPoolSize=100,
                serverSelectionTimeoutMS=5000
            )
            self.mongo_client.admin.command('ping')  # 验证连接
            self.db = self.mongo_client["intelligence_db"]
            self.archive_col = self.db["processed_data"]
            return True
        except ConnectionFailure as e:
            logging.critical(f"MongoDB连接失败: {str(e)}")
            return False
        except Exception as e:
            logging.critical(f"MongoDB连接失败: {str(e)}")
            return False

    def _setup_apis(self):
        # 信息收集API
        @self.app.route('/collect', methods=['POST'])
        def collect_api():
            try:
                data = request.json
                if 'UUID' not in data:
                    return jsonify({"status": "error", "msg": "UUID required"}), 400

                with self.lock:
                    priority = self._calculate_priority(data.get('retry_count', 0))
                    self.input_queue.put((priority, time.time(), data))

                return jsonify({"status": "queued", "uuid": data["UUID"]})
            except Exception as e:
                logging.error(f"Collection API fail: {str(e)}")
                return jsonify({"status": "error", "uuid": ""})

        # 处理反馈API
        @self.app.route('/feedback', methods=['POST'])
        def feedback_api():
            try:
                processed_data = request.json
                if 'UUID' not in processed_data:
                    return jsonify({"status": "error"}), 400

                uuid_str = processed_data["UUID"]
                with self.lock:
                    if uuid_str in self.processing_map:
                        # original_retry_count, original_data = self.processing_map.pop(uuid_str)
                        # combined_data = {**original_data, **processed_data}  # 合并数据

                        del self.processing_map[uuid_str]
                        self.output_queue.put(processed_data)

                return jsonify({"status": "acknowledged", "uuid": uuid_str})
            except Exception as e:
                print(str(e))
                return jsonify({"status": "error", "uuid": ""})

    def _process_data_worker(self):
        while not self.shutdown_flag.is_set():
            try:
                priority, timestamp, data = self.input_queue.get_nowait()
            except queue.Empty:
                time.sleep(0.1)
                continue

            uuid_str = data['UUID']
            retry_count = data.get('retry_count', 0)

            try:
                # 发送处理请求
                response = requests.post(
                    self.intelligence_processor_uri,
                    json=data,
                    timeout=self.request_timeout
                )
                response.raise_for_status()

                # 记录处理开始时间
                with self.lock:
                    self.processing_map[uuid_str] = (retry_count, data)
                    data['_enqueue_time'] = time.time()

            except Exception as e:
                logging.error(f"处理请求失败 UUID={uuid_str}: {str(e)}")
                new_retry = retry_count + 1
                if new_retry <= self.intelligence_process_max_retries:
                    data['retry_count'] = new_retry
                    priority = self._calculate_priority(new_retry)
                    with self.lock:
                        self.input_queue.put((priority, time.time(), data))
                else:
                    logging.error(f"数据 {uuid_str} 超过最大重试次数，丢弃")

            finally:
                self.input_queue.task_done()

    def _check_timeouts(self):
        while not self.shutdown_flag.is_set():
            current_time = time.time()
            with self.lock:
                timeout_uuids = []
                for uuid_str, (retry_count, data) in self.processing_map.items():
                    if current_time - data['_enqueue_time'] > self.intelligence_process_timeout:
                        timeout_uuids.append(uuid_str)

                for uuid_str in timeout_uuids:
                    retry_count, data = self.processing_map.pop(uuid_str)
                    new_retry = retry_count + 1
                    if new_retry <= self.intelligence_process_max_retries:
                        data['retry_count'] = new_retry
                        data['_enqueue_time'] = current_time
                        priority = self._calculate_priority(new_retry)
                        self.input_queue.put((priority, current_time, data))
                    else:
                        logging.error(f"数据 {uuid_str} 超时且重试次数耗尽")
            time.sleep(self.intelligence_process_timeout / 2)  # 检查频率调整为超时时间的一半

    def _calculate_priority(self, retry_count):
        # 重试次数越多优先级越高（数值越小优先级越高）
        return max(0, self.intelligence_process_max_retries - retry_count)

    # # 归档模块
    # def _archive_worker(self):
    #     while True:
    #         try:
    #             data = self.output_queue.get()
    #             # MongoDB写入
    #             doc_id = self.archive_col.insert_one(data).inserted_id
    #             # TODO: 创建向量索引
    #             self.output_queue.task_done()
    #
    #             # TODO: Call post processor plugins
    #         except queue.Empty:
    #             time.sleep(0.5)


def _archive_worker(self):
    # self.vector_index = VectorIndex()  # 初始化向量索引

    while not self.shutdown_flag.is_set():
        try:
            data = self.output_queue.get(timeout=1)
            # MongoDB写入
            try:
                doc = self._create_document(data)
                doc_id = self.archive_col.insert_one(doc).inserted_id
                # 生成向量并创建索引（示例）
                # if 'embedding' in data:
                #     self.vector_index.add_vector(doc_id, data['embedding'])
            except Exception as e:
                logging.error(f"归档失败: {str(e)}")
                self.output_queue.put(data)  # 重新放回队列
            finally:
                self.output_queue.task_done()
        except queue.Empty:
            continue

