import os
import time
import random
import threading
from collections import defaultdict
from Tools.CrawlRecord import CrawlRecord, STATUS_SUCCESS, STATUS_ERROR, STATUS_IGNORED


class PerformanceTester:
    def __init__(self, db_path, thread_counts=(5, 10, 20), data_scales=(1000, 5000, 10000)):
        self.db_path = db_path
        self.thread_counts = thread_counts
        self.data_scales = data_scales
        self.results = []

    def _generate_urls(self, count):
        return [f"https://site.com/item_{i}_{random.randint(1000, 9999)}" for i in range(count)]

    def _worker_write(self, record, urls, stats):
        for url in urls:
            start = time.perf_counter()
            status = random.choice([STATUS_SUCCESS, STATUS_ERROR, STATUS_IGNORED])
            extra = f"worker_{threading.get_ident()}"
            record.record_url_status(url, status, extra)
            stats['write_times'].append(time.perf_counter() - start)

    def _worker_read(self, record, urls, stats):
        for url in urls:
            start = time.perf_counter()
            record.get_url_status(url)
            stats['read_times'].append(time.perf_counter() - start)

    def _worker_mixed(self, record, urls, stats):
        for url in urls:
            if random.random() > 0.3:  # 70%读操作
                start = time.perf_counter()
                record.get_url_status(url)
                stats['read_times'].append(time.perf_counter() - start)
            else:  # 30%写操作
                start = time.perf_counter()
                status = random.choice([STATUS_SUCCESS, STATUS_ERROR])
                record.record_url_status(url, status)
                stats['write_times'].append(time.perf_counter() - start)

    def _run_test(self, worker_type, thread_count, data_scale):
        # 初始化数据库
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        record = CrawlRecord(self.db_path, cache_size=1000)

        # 预生成测试URL
        all_urls = self._generate_urls(data_scale)
        chunk_size = data_scale // thread_count
        url_chunks = [all_urls[i:i + chunk_size] for i in range(0, data_scale, chunk_size)]

        # 准备统计容器
        stats = defaultdict(list)
        threads = []
        start_time = time.perf_counter()

        # 创建并启动工作线程
        for i in range(thread_count):
            worker_func = {
                'write': self._worker_write,
                'read': self._worker_read,
                'mixed': self._worker_mixed
            }[worker_type]

            t = threading.Thread(
                target=worker_func,
                args=(record, url_chunks[i], stats)
            )
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 计算性能指标
        total_time = time.perf_counter() - start_time
        total_ops = len(stats['read_times']) + len(stats['write_times'])

        # 保存结果
        result = {
            'worker_type': worker_type,
            'thread_count': thread_count,
            'data_scale': data_scale,
            'total_time': total_time,
            'total_ops': total_ops,
            'ops_per_sec': total_ops / total_time,
            'avg_write_time': sum(stats['write_times']) / len(stats['write_times']) if stats['write_times'] else 0,
            'avg_read_time': sum(stats['read_times']) / len(stats['read_times']) if stats['read_times'] else 0,
            'max_write_time': max(stats['write_times']) if stats['write_times'] else 0,
            'max_read_time': max(stats['read_times']) if stats['read_times'] else 0
        }

        record.close()
        return result

    def execute_all_tests(self):
        test_cases = [
                         ('write', t, d) for t in self.thread_counts for d in self.data_scales
                     ] + [
                         ('read', t, d) for t in self.thread_counts for d in self.data_scales
                     ] + [
                         ('mixed', t, d) for t in self.thread_counts for d in self.data_scales
                     ]

        for worker_type, thread_count, data_scale in test_cases:
            print(f"正在测试: {worker_type}模式, {thread_count}线程, {data_scale}数据量")
            result = self._run_test(worker_type, thread_count, data_scale)
            self.results.append(result)
            self.print_result(result)

    def print_result(self, result):
        print(f"\n=== {result['worker_type'].upper()}模式测试结果 ===")
        print(f"线程数: {result['thread_count']} | 数据量: {result['data_scale']}")
        print(f"总耗时: {result['total_time']:.2f}s | 总操作: {result['total_ops']}")
        print(f"操作/秒: {result['ops_per_sec']:.2f} ops/s")
        print(f"平均写耗时: {result['avg_write_time'] * 1000:.2f}ms")
        print(f"平均读耗时: {result['avg_read_time'] * 1000:.2f}ms")
        print(f"最大写耗时: {result['max_write_time'] * 1000:.2f}ms")
        print(f"最大读耗时: {result['max_read_time'] * 1000:.2f}ms")
        print("=" * 50)

    def visualize_results(self):
        try:
            import matplotlib.pyplot as plt
        except Exception as e:
            print('No matplotlib, ignore.')
            return
        # 准备可视化数据
        metrics = {
            'write': {'ops': [], 'write_time': []},
            'read': {'ops': [], 'read_time': []},
            'mixed': {'ops': [], 'write_time': [], 'read_time': []}
        }

        for res in self.results:
            t = res['worker_type']
            metrics[t]['ops'].append(res['ops_per_sec'])

            if t in ['write', 'mixed']:
                metrics[t]['write_time'].append(res['avg_write_time'] * 1000)

            if t in ['read', 'mixed']:
                metrics[t]['read_time'].append(res['avg_read_time'] * 1000)

        # 创建可视化图表
        plt.figure(figsize=(15, 10))

        # 吞吐量图表
        plt.subplot(2, 1, 1)
        for t in metrics:
            if metrics[t]['ops']:
                plt.plot(self.thread_counts * len(self.data_scales),
                         metrics[t]['ops'], 'o-', label=f"{t}模式")
        plt.title('不同模式下的操作吞吐量')
        plt.xlabel('线程数量')
        plt.ylabel('操作/秒 (ops/s)')
        plt.legend()
        plt.grid(True)

        # 延迟图表
        plt.subplot(2, 1, 2)
        for t in ['write', 'read', 'mixed']:
            if t == 'write' and metrics[t]['write_time']:
                plt.plot(self.thread_counts * len(self.data_scales),
                         metrics[t]['write_time'], 's--', label=f"{t}写延迟")
            if t == 'read' and metrics[t]['read_time']:
                plt.plot(self.thread_counts * len(self.data_scales),
                         metrics[t]['read_time'], '^--', label=f"{t}读延迟")
        plt.title('操作延迟对比 (ms)')
        plt.xlabel('线程数量')
        plt.ylabel('延迟 (毫秒)')
        plt.legend()
        plt.grid(True)

        plt.tight_layout()
        plt.savefig('performance_results.png')
        print("性能图表已保存为 performance_results.png")


# ====================== 执行测试 ======================
if __name__ == "__main__":
    tester = PerformanceTester(
        db_path="performance_test.db",
        thread_counts=[1, 5, 10, 20, 30],  # 测试不同线程数
        data_scales=[5000, 10000, 20000]  # 测试不同数据量
    )

    print("=" * 60)
    print("开始执行多线程性能测试...")
    print("=" * 60)

    tester.execute_all_tests()
    tester.visualize_results()

    print("\n测试完成！结果摘要：")
    for res in tester.results:
        print(f"{res['worker_type']}-{res['thread_count']}线程-{res['data_scale']}数据: "
              f"{res['ops_per_sec']:.0f} ops/s")
