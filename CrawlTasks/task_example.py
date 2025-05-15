import time


def module_init(service_context):
    if service_context:
        service_context.solve_import_path()


def start_task(stop_event):
    """任务启动函数"""
    while not stop_event.is_set():
        print("Example task is running...")
        time.sleep(5)
    print("Example task stopped gracefully")
