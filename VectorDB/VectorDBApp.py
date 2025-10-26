# main_app.py
"""
示例 Flask 服务器

演示如何协调 VectorDB 的非阻塞启动
以及 VectorApi 的路由注册。
"""
import os
import sys
import time
import logging
from flask import Flask
from flask_cors import CORS


logger = logging.getLogger(__name__)


try:
    if __name__ == '__main__':
        self_path = os.path.dirname(os.path.abspath(__file__))
        sys.path.append(self_path)

        from VectorDBService import VectorDBService
        from VectorDBBackend import VectorDBBackend
    else:
        from .VectorDBService import VectorDBService
        from .VectorDBBackend import VectorDBBackend
except ImportError as e:
    print(str(e))
    print("错误: 找不到 'VectorDBService.py' 或 'VectorDBBackend.py'。")
    print("请确保这两个文件与 'main_app.py' 在同一目录下。")
    sys.exit(1)

# --- (2) 配置 ---
VECTOR_DB_PATH = "./vector_stores"
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
HOST = "127.0.0.1"
PORT = 5100

# --- (3) 协调启动 ---

print("[Main App] 正在初始化 VectorDB (非阻塞)...")
# 实例化服务。后台线程开始工作。
service = VectorDBService(
    db_path=VECTOR_DB_PATH,
    model_name=MODEL_NAME
)

print("[Main App] 正在等待 VectorDB 准备就绪...")
while True:
    status_info = service.get_status()
    if status_info["status"] == "ready":
        print("[Main App] VectorDB 已准备就绪！")
        break
    if status_info["status"] == "error":
        print(f"[Main App] 致命错误: VectorDB 启动失败: {status_info['error']}")
        sys.exit(1)

    print("[Main App] ...正在等待模型和数据库加载 (在后台)...")
    time.sleep(2)

print("[Main App] 正在初始化 Flask 服务器...")
app = Flask(__name__)
# 为本地开发启用 CORS，允许 8080 端口的前端访问 5100 端口的后端
CORS(app, resources={r"/vector/api/*": {"origins": "http://127.0.0.1:8080"}})

# --- (4) 实例化并注册 API ---
# 关键: 将 *已经就绪* 的 service 实例传递给 VectorApi
print("[Main App] 正在实例化并注册 VectorApi...")
vector_api_component = VectorDBBackend(app, service)

# (需求) 调用 register_routes 方法
# 我们没有登录包装器，所以传入 None
vector_api_component.register_routes(wrapper=None)

print("[Main App] API 路由注册完毕。")


# --- (5) 添加一个根路由用于测试 ---
@app.route('/')
def index():
    return ("VectorDB API 服务器正在运行。请在 8080 端口访问前端应用。")


# --- (6) 运行服务器 ---
if __name__ == '__main__':
    print(f"\nFlask 服务器已启动，运行于 http://{HOST}:{PORT}")
    print(f"请在另一个终端中使用 'python -m http.server 8080' 来运行 index.html")
    app.run(host=HOST, port=PORT, debug=False)
