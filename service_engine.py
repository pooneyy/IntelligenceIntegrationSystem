import os
import time
import threading
import traceback
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from plugin_manager import PluginManager, PluginWrapper, logger


class TaskManager:
    THREAD_JOIN_TIMEOUT = 2
    THREAD_JOIN_ATTEMPTS = 10

    def __init__(self, watch_dir: str, security_config=None):
        self.watch_dir = watch_dir
        self.security = security_config     # Reserved for SecurityConfig

        # {plugin_name: (module_ref, thread, stop_event)}
        self.tasks: dict[str, tuple[PluginWrapper, threading.Thread, threading.Event]] = {}
        self.tasks_lock = threading.Lock()

        self.plugin_manager = PluginManager(['start_task'])
        self.scan_existing_files()

    def scan_existing_files(self):
        try:
            if not os.path.exists(self.watch_dir):
                os.makedirs(self.watch_dir, exist_ok=True)
            plugins = self.plugin_manager.scan_path(self.watch_dir)
            for plugin in plugins:
                self.__add_module(plugin)
        except OSError as e:
            logger.error(f"Failed to create directory {self.watch_dir}: {e}")
        except Exception as e:
            logger.error(f"Scan directory {self.watch_dir} crashed: {e}", exc_info=True)

    def add_task(self, file_path: str):
        plugin = None
        try:
            self.__remove_module(file_path)
            plugin = self.plugin_manager.add_plugin(file_path)
            if not plugin:
                raise ValueError('Plugin load None')
            return self.__add_module(plugin)
        except Exception as e:
            logger.error(f"Load plugin {file_path} fail: {e}", exc_info=True)
            if plugin:
                self.plugin_manager.remove_plugin(plugin.plugin_name)
            return False
    
    def remove_task(self, file_path: str):
        self.__remove_module(file_path)

    def shutdown(self):
        with self.tasks_lock:
            tasks = list(self.tasks.keys())
        for plugin_name in tasks:
            self.__remove_module(plugin_name)

    def on_model_enter(self, plugin: PluginWrapper):
        logger.info(f'Plugin {plugin.plugin_name} loaded')

    def on_model_quit(self, plugin: PluginWrapper):
        logger.info(f'Plugin {plugin.plugin_name} unloaded')

    # ---------------------------------------------------------------------------

    def __add_module(self, plugin: PluginWrapper) -> bool:
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self.__run_module,
            name=f"PluginThread-{plugin.plugin_name}",
            args=(plugin, stop_event),
            daemon=True
        )

        try:
            thread.start()
        except RuntimeError as e:
            logger.error(f"Create thread for {plugin.plugin_name} fail: {e}")
            return False

        with self.tasks_lock:
            self.tasks[plugin.plugin_name] = (plugin, thread, stop_event)

        return True

    def __remove_module(self, file_path: str):
        with self.tasks_lock:
            plugin_name = PluginManager.plugin_name(file_path)

            if plugin_name not in self.tasks:
                return

            self.plugin_manager.remove_plugin(plugin_name)
            task_info = self.tasks.pop(plugin_name)
            module, thread, stop_event = task_info
            stop_event.set()

        for _ in range(TaskManager.THREAD_JOIN_ATTEMPTS):
            thread.join(timeout=TaskManager.THREAD_JOIN_TIMEOUT)
            if not thread.is_alive():
                break

        if thread.is_alive():
            logger.warning(f"Plugin {plugin_name} thread (ID: {thread.ident}) "
                           f"still alive after {TaskManager.THREAD_JOIN_ATTEMPTS} attempts.")

    def __run_module(self, plugin: PluginWrapper, stop_event: threading.Event):
        self.on_model_enter(plugin)
        try:
            plugin.start_task(stop_event)
        except Exception as e:
            logger.error(f"Plugin {plugin.plugin_name} crashed: {e}", exc_info=True)
        finally:
            self.on_model_quit(plugin)

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
        if self.__file_accept(event):
            self.task_manager.add_task(event.src_path)
    
    def on_deleted(self, event):
        if self.__file_accept(event):
            self.task_manager.remove_task(event.src_path)

    def on_modified(self, event):
        if self.__file_accept(event):
            self.task_manager.remove_task(event.src_path)
            self.task_manager.add_task(event.src_path)

    @staticmethod
    def __file_accept(event) -> bool:
        return not event.is_directory and \
            not os.path.basename(event.src_path).startswith(('~', '.')) and \
            event.src_path.endswith('.py')

def main():
    # config  = SecurityConfig(
    #     enable_hash=True,
    #     enable_signature=True,
    #     public_key_path="public_key.pem",
    #     whitelist_hashes={
    #         "/path/to/valid.py": "a1b2c3...sha256哈希值"
    #     }
    # )

    task_manager = TaskManager('playground/tasks')
    event_handler = FileHandler(task_manager)

    observer = Observer()
    observer.schedule(event_handler, path="playground/tasks", recursive=False)
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
