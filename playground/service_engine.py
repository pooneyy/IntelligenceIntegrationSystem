import sys
import time
import threading
import importlib.util
import traceback
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class TaskManager:
    def __init__(self, watch_dir: str, security_config=None):
        self.watch_dir = Path(watch_dir)
        self.security = security_config     # SecurityConfig()
        self.tasks = {}                     # {file_path: (module_ref, thread, stop_event)}
        self.scan_existing_files()

    def scan_existing_files(self):
        for py_file in self.watch_dir.glob("*.py"):
            if py_file.is_file():
                self.add_task(str(py_file))

    def add_task(self, file_path):
        # 动态加载模块
        module_name = f"dynamic_{Path(file_path).stem}_{time.time()}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        # 验证接口函数
        if not (hasattr(module, 'start_task') and callable(module.start_task)):
            return False
        
        # 创建停止事件和线程
        stop_event = threading.Event()
        thread = threading.Thread(
            target=module.start_task, 
            args=(stop_event,),
            daemon=True
        )
        thread.start()
        
        self.tasks[file_path] = (module, thread, stop_event)
        return True
    
    def remove_task(self, file_path):
        if file_path not in self.tasks:
            return
        
        # 发送停止信号
        module, thread, stop_event = self.tasks[file_path]
        stop_event.set()
        
        # 等待任务完成
        thread.join(timeout=30)
        
        # 清理资源
        del sys.modules[module.__name__]
        del self.tasks[file_path]

    # def verify_security(self, file_path):
    #     # 哈希白名单校验
    #     if self.security.enable_hash:
    #         expected_hash = self.security.whitelist.get(file_path)
    #         if not SecurityValidator.verify_hash(file_path, expected_hash):
    #             return False
    #
    #     # 数字签名校验
    #     if self.security.enable_signature and self.security.public_key:
    #         sig_path = f"{file_path}.sig"
    #         if not SecurityValidator.verify_signature(file_path,
    #                                                   self.security.public_key,
    #                                                   sig_path):
    #             return False
    #     return True


class FileHandler(FileSystemEventHandler):
    def __init__(self, task_manager):
        self.task_manager = task_manager
    
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.py'):
            self.task_manager.add_task(event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith('.py'):
            self.task_manager.remove_task(event.src_path)


def main():
    # config  = SecurityConfig(
    #     enable_hash=True,
    #     enable_signature=True,
    #     public_key_path="public_key.pem",
    #     whitelist_hashes={
    #         "/path/to/valid.py": "a1b2c3...sha256哈希值"
    #     }
    # )

    task_manager = TaskManager('tasks')
    event_handler = FileHandler(task_manager)

    observer = Observer()
    observer.schedule(event_handler, path="tasks", recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
        traceback.print_exc()
