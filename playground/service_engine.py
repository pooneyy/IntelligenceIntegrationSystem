import time
import threading
import traceback
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from plugin_manager import PluginManager, PluginWrapper, logger


class TaskManager:
    def __init__(self, watch_dir: str, security_config=None):
        self.watch_dir = watch_dir
        self.security = security_config     # SecurityConfig()
        self.tasks = {}                     # {file_path: (module_ref, thread, stop_event)}
        self.plugin_manager = PluginManager(['start_task'])
        self.scan_existing_files()

    def scan_existing_files(self):
        plugins = self.plugin_manager.scan_path(self.watch_dir)
        for plugin in plugins:
            self.__add_module(plugin)

    def add_task(self, file_path: str):
        plugin = self.plugin_manager.add_plugin(file_path)

        if not plugin or not plugin.has_function('start_task'):
            logger.error('Load plugin {file_path} fail.')
            return False

        return self.__add_module(plugin)
    
    def remove_task(self, file_path):
        plugin_name = PluginManager.plugin_name(file_path)
        if plugin_name not in self.tasks:
            return

        module, thread, stop_event = self.tasks[file_path]
        stop_event.set()

        thread.join(timeout=30)

        del self.tasks[file_path]
        self.plugin_manager.remove_plugin(plugin_name)

    def __add_module(self, plugin: PluginWrapper) -> bool:
        # module_name = f"dynamic_{Path(file_path).stem}_{time.time()}"
        # spec = importlib.util.spec_from_file_location(module_name, file_path)
        # module = importlib.util.module_from_spec(spec)
        # sys.modules[module_name] = module
        # spec.loader.exec_module(module)

        if not plugin.has_function('start_task'):
            return False

        stop_event = threading.Event()
        thread = threading.Thread(
            target=plugin.start_task,
            args=(stop_event,),
            daemon=True
        )
        thread.start()

        self.tasks[plugin.plugin_name] = (plugin, thread, stop_event)
        return True

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
