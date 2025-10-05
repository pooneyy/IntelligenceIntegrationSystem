import time
import uuid
import logging
import threading
from flask import Flask, g, request, jsonify


logger = logging.getLogger(__name__)


class RequestTracer:
    """
    一个用于追踪 Flask 请求生命周期、记录慢请求和发现卡死请求的工具。
    """

    def __init__(self, app=None, threshold_s: int=0.5):
        self.app = app
        self.threshold = threshold_s

        # 用于存储正在进行中的请求信息
        # key: request_id (uuid), value: {start_time, path, method, ip, user_agent}
        self._pending_requests = {}
        # 必须使用锁来保证线程安全
        self._lock = threading.Lock()

        if app:
            self.init_app(app)

    def init_app(self, app):
        """将追踪器挂载到 Flask app 上。"""
        # 注册 before_request 和 after_request 钩子
        app.before_request(self._before_request)
        app.after_request(self._after_request)

    def _before_request(self):
        """Requirement 1: 在请求开始时记录信息。"""
        request_id = str(uuid.uuid4())
        g.request_id = request_id

        request_info = {
            'start_time': time.time(),
            'path': request.path,
            'method': request.method,
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'N/A')
        }

        with self._lock:
            self._pending_requests[request_id] = request_info

    def _after_request(self, response):
        """Requirement 2: 在请求结束时处理日志。"""
        request_id = getattr(g, 'request_id', None)
        if not request_id:
            return response

        with self._lock:
            # 使用 pop 可以原子性地获取并移除记录
            request_info = self._pending_requests.pop(request_id, None)

        if request_info:
            duration = time.time() - request_info['start_time']

            log_message = (
                f"Request finished: {duration:.4f}s | {request_info['method']} {request_info['path']} "
                f"| IP: {request_info['ip']}"
            )

            # 如果超过阈值，打印 Warning
            if duration > self.threshold:
                logger.warning(f"SLOW REQUEST! {log_message}")
            else:
                logger.info(log_message)

        return response

    def dump_long_running_requests(self):
        """Requirement 3: 检查并报告卡住或运行时间极长的请求。"""
        now = time.time()

        # 定义极长和超长阈值
        long_threshold = self.threshold * 10
        critical_threshold = self.threshold * 100

        # 创建一个列表来存储需要报告的请求，避免在锁内执行 I/O
        alerts_to_log = []

        with self._lock:
            # 遍历字典的副本，因为我们可能在另一个线程中修改它
            for req_id, info in self._pending_requests.items():
                duration = now - info['start_time']

                log_detail = (
                    f"STUCK REQUEST DETECTED: {duration:.2f}s | {info['method']} {info['path']} "
                    f"| IP: {info['ip']} | ID: {req_id}"
                )

                if duration > critical_threshold:
                    alerts_to_log.append(('error', f"CRITICAL! {log_detail}"))
                elif duration > long_threshold:
                    alerts_to_log.append(('warning', f"VERY LONG! {log_detail}"))

        # 在锁外执行日志记录
        if not alerts_to_log:
            logger.info("Dump check: No long-running requests found.")

        for level, message in alerts_to_log:
            if level == 'error':
                logger.error(message)
            else:
                logger.warning(message)

        return len(alerts_to_log)
