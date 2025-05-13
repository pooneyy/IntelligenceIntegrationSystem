# 示例任务模块 task_example.py
import time

def start_task(stop_event):
    """任务启动函数"""
    while not stop_event.is_set():
        print("Task is running...")
        time.sleep(5)
    print("Task stopped gracefully")

# 可选实现的清理函数
def stop_task():
    """自定义资源回收逻辑"""
    pass
