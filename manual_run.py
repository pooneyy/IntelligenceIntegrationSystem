import os
import threading
import traceback

from ServiceEngine import ServiceContext


def drive_module(module):
    stop_event = threading.Event()
    service_context = ServiceContext()

    module.module_init(service_context)
    while not stop_event.is_set():
        module.start_task(stop_event)


def main():
    # from CrawlTasks import task_crawl_chinanews
    # drive_module(task_crawl_chinanews)

    # from CrawlTasks import task_crawl_people
    # drive_module(task_crawl_people)

    # from CrawlTasks import task_crawl_voanews
    # drive_module(task_crawl_voanews)

    from CrawlTasks import task_crawl_cbc
    drive_module(task_crawl_cbc)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
        traceback.print_exc()
