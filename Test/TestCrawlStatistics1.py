import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor
from typing import List
import psutil

from Tools.CrawlStatistics import CrawlStatistics

# 预定义测试数据，避免随机性
FIXED_COUNTER_ITEMS = ["success", "timeout", "error"]  # 固定计数器类型
FIXED_SUB_ITEMS = [f"item_{i}" for i in range(1, 1001)]  # 固定1000个子项
FIXED_STATUSES = ["queued", "processing", "completed", "failed"]  # 固定状态类型
FIXED_PATHS = [["root", f"path_{i}"] for i in range(1, 6)]  # 固定5级路径


def create_new_stats_instance():
    """创建新的统计实例，确保测试隔离"""
    CrawlStatistics._instance = None  # 重置单例
    return CrawlStatistics()


# ==========================================================
# 基础功能测试
# ==========================================================

def test_single_thread_basic():
    """单线程基础功能测试"""
    print("\n" + "=" * 50)
    print("单线程基础功能测试")
    print("=" * 50)

    stats = create_new_stats_instance()

    # 测试计数器功能
    stats.counter_log(["test", "counter"], "success", "Test log")
    stats.counter_log(["test", "counter"], "success", "Test log")
    stats.counter_log(["test", "counter"], "error", "Test log")

    # 测试子项状态功能
    stats.sub_item_log(["test", "subitem"], "item1", "processing")
    stats.sub_item_log(["test", "subitem"], "item1", "completed")
    stats.sub_item_log(["test", "subitem"], "item2", "failed")

    # 验证结果
    counter_results = stats.get_classified_counter(["test", "counter"])
    subitem_results = stats.get_sub_item_statistics(["test", "subitem"])

    print("计数器结果:", counter_results)
    print("子项状态结果:", subitem_results)

    # 断言验证
    assert counter_results.get("success", 0) == 2, "计数器success值应为2"
    assert counter_results.get("error", 0) == 1, "计数器error值应为1"
    assert "item1" in subitem_results.get("completed", []), "item1应标记为completed"
    assert "item2" in subitem_results.get("failed", []), "item2应标记为failed"

    print("✅ 单线程基础功能测试通过")


def test_hierarchical_data():
    """分级数据结构测试"""
    print("\n" + "=" * 50)
    print("分级数据结构测试")
    print("=" * 50)

    stats = create_new_stats_instance()

    # 创建分级数据
    stats.counter_log(["level1", "level2A"], "counter1", "Log")
    stats.counter_log(["level1", "level2A"], "counter1", "Log")
    stats.counter_log(["level1", "level2B"], "counter2", "Log")
    stats.sub_item_log(["level1", "level2A"], "itemA", "status1")
    stats.sub_item_log(["level1", "level2B"], "itemB", "status2")

    # 检索不同层级数据
    level2A_counters = stats.get_classified_counter(["level1", "level2A"])
    level2B_counters = stats.get_classified_counter(["level1", "level2B"])
    level1_counters = stats.get_classified_counter(["level1"])

    # 验证结果
    print("level2A 计数器:", level2A_counters)
    print("level2B 计数器:", level2B_counters)
    print("level1 计数器:", level1_counters)

    assert level2A_counters == {"counter1": 2}, "level2A 计数器错误"
    assert level2B_counters == {"counter2": 1}, "level2B 计数器错误"
    assert level1_counters == {}, "level1 应无计数器数据"

    print("✅ 分级数据结构测试通过")


# ==========================================================
# 并发安全测试
# ==========================================================

def test_counter_accuracy():
    """计数器准确性并发测试"""
    print("\n" + "=" * 50)
    print("计数器准确性并发测试")
    print("=" * 50)

    stats = create_new_stats_instance()

    # 使用单一固定路径确保准确性
    FIXED_PATH = ["counter_accuracy_test"]
    expected_counts = {"success": 300, "timeout": 200, "error": 100}

    # 多线程写入固定计数器
    def worker(counter_type, count):
        for _ in range(count):
            stats.counter_log(FIXED_PATH, counter_type, "log")

    threads = []
    for item, count in expected_counts.items():
        t = threading.Thread(target=worker, args=(item, count))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 验证结果
    result = stats.get_classified_counter(FIXED_PATH)
    for item, count in expected_counts.items():
        actual = result.get(item, 0)
        assert actual == count, f"{item}计数应为{count}, 实际{actual}"

    print("✅ 计数器准确性测试通过")


def test_subitem_integrity():
    """子项状态一致性测试"""
    print("\n" + "=" * 50)
    print("子项状态一致性测试")
    print("=" * 50)

    stats = create_new_stats_instance()
    stats.set_sub_items_limit(2000)

    # 使用单一固定路径确保完整性
    FIXED_PATH = ["subitem_integrity_test"]
    target_status = "completed"

    # 所有线程将固定子项标记为同一状态
    def worker(sub_item):
        stats.sub_item_log(FIXED_PATH, sub_item, target_status)

    with ThreadPoolExecutor(max_workers=50) as executor:
        executor.map(worker, FIXED_SUB_ITEMS)

    # 验证所有子项状态一致
    result = stats.get_sub_item_statistics(FIXED_PATH)
    status_items = result.get(target_status, [])

    # 验证两个方向：所有项目都存在，列表中没有额外项
    for item in FIXED_SUB_ITEMS:
        assert item in status_items, f"子项{item}缺失"

    assert len(status_items) == len(FIXED_SUB_ITEMS), "子项数量不正确"

    print("✅ 子项状态一致性测试通过")


# ==========================================================
# 性能与压力测试
# ==========================================================

def test_mixed_operations():
    """混合操作压力测试"""
    print("\n" + "=" * 50)
    print("混合操作压力测试 (100线程 × 5000次操作)")
    print("=" * 50)

    stats = create_new_stats_instance()
    stats.set_sub_items_limit(500000)
    operation_count = 5000  # 每个线程操作次数

    def worker():
        for _ in range(operation_count):
            path = random.choice(FIXED_PATHS)
            if random.random() > 0.5:  # 50%概率执行计数器操作
                stats.counter_log(path, random.choice(FIXED_COUNTER_ITEMS), "log")
            else:  # 50%概率执行子项操作
                stats.sub_item_log(path, random.choice(FIXED_SUB_ITEMS), random.choice(FIXED_STATUSES))

    # 启动100线程
    start_time = time.time()
    threads = [threading.Thread(target=worker) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    duration = time.time() - start_time

    # 验证总量一致性
    total_ops = operation_count * 100
    total_counters = sum(
        sum(stats.get_classified_counter(path).values())
        for path in FIXED_PATHS
    )
    total_subitems = sum(
        len(items)
        for path in FIXED_PATHS
        for items in stats.get_sub_item_statistics(path).values()
    )

    actual_total = total_counters + total_subitems
    print(f"总操作数: {total_ops}, 记录总数: {actual_total}")
    print(f"测试耗时: {duration:.2f}秒, 速率: {total_ops / duration:.2f} ops/sec")

    # 允许少量差异（10%以内）
    assert abs(actual_total - total_ops) / total_ops <= 0.1, "操作总数差异超过10%"

    print("✅ 混合操作压力测试通过")


def test_memory_stability():
    """内存稳定性测试"""
    print("\n" + "=" * 50)
    print("内存稳定性测试 (50线程 × 60秒)")
    print("=" * 50)

    stats = create_new_stats_instance()
    start_mem = psutil.Process().memory_info().rss
    stop_event = threading.Event()

    def worker():
        while not stop_event.is_set():
            path = random.choice(FIXED_PATHS)
            stats.counter_log(path, random.choice(FIXED_COUNTER_ITEMS), "log")
            stats.sub_item_log(path, random.choice(FIXED_SUB_ITEMS), random.choice(FIXED_STATUSES))

    # 启动工作线程
    start_time = time.time()
    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()

    # 运行60秒
    time.sleep(60)
    stop_event.set()

    for t in threads:
        t.join()

    # 检查内存增长
    end_mem = psutil.Process().memory_info().rss
    mem_growth = (end_mem - start_mem) / start_mem
    print(f"初始内存: {start_mem / (1024 * 1024):.2f}MB, 结束内存: {end_mem / (1024 * 1024):.2f}MB")
    print(f"内存增长: {mem_growth * 100:.2f}%")

    assert mem_growth < 0.2, "内存增长超过20%，可能存在泄漏"
    print("✅ 内存稳定性测试通过")


# ==========================================================
# 测试主程序
# ==========================================================

def run_basic_tests():
    """运行基础功能测试"""
    print("\n" + "=" * 60)
    print("执行基础功能测试")
    print("=" * 60)
    test_single_thread_basic()
    test_hierarchical_data()


def run_concurrency_tests():
    """运行并发安全测试"""
    print("\n" + "=" * 60)
    print("执行并发安全测试")
    print("=" * 60)
    test_counter_accuracy()
    test_subitem_integrity()


def run_performance_tests():
    """运行性能与压力测试"""
    print("\n" + "=" * 60)
    print("执行性能与压力测试")
    print("=" * 60)
    test_mixed_operations()
    test_memory_stability()


def main():
    """主测试函数"""
    print("=" * 60)
    print("CrawlStatistics 测试套件")
    print("=" * 60)

    try:
        run_basic_tests()
        run_concurrency_tests()
        run_performance_tests()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过!")
        print("=" * 60)
    except AssertionError as e:
        print("\n" + "!" * 60)
        print(f"测试失败: {e}")
        print("!" * 60)
    except Exception as e:
        print("\n" + "!" * 60)
        print(f"未预期的错误: {e}")
        print("!" * 60)


if __name__ == "__main__":
    main()
