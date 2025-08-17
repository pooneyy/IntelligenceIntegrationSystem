import gc
import logging
import random
import unittest
import os
import shutil
import stat
from Tools.CrawlRecord import CrawlRecord, STATUS_SUCCESS, STATUS_ERROR, STATUS_NOT_EXIST, STATUS_IGNORED, \
    STATUS_UNKNOWN


class TestCrawlRecord(unittest.TestCase):
    def setUp(self):
        """初始化测试环境"""
        self.db_dir = 'test_dir'
        self.db_name = "test_db"
        self.db_path = os.path.join(self.db_dir, self.db_name + '.db')      # CrawlRecord should auto add suffix
        self.cleanup_files()
        self.record = CrawlRecord([self.db_dir, self.db_name])
        self.test_url = "https://example.com"
        self.test_url2 = "https://test.org"
        self.assertTrue(len(self.record.memory_cache) == 0)

    def tearDown(self):
        """清理测试环境"""
        if self.record:
            self.record.close()
            self.record = None
        self.cleanup_files()

    def cleanup_files(self):
        """强制删除数据库文件及目录（支持只读文件和目录）"""
        # 删除数据库文件（若为只读文件，先修改权限）
        if os.path.exists(self.db_path):
            try:
                # 解除只读属性
                os.chmod(self.db_path, stat.S_IWRITE)  # Windows/Linux 通用[1,9](@ref)
                os.remove(self.db_path)
            except PermissionError:
                # 若仍失败，尝试强制删除（Windows 特例）
                if os.name == 'nt':  # Windows 系统
                    os.system(f'DEL /F "{self.db_path}"')  # /F 强制删除只读文件[2,5](@ref)
                else:  # Linux/Mac
                    os.system(f'rm -f "{self.db_path}"')  # -f 强制忽略权限[6](@ref)
            except Exception as e:
                logging.error(f"删除文件失败: {self.db_path}, 错误: {str(e)}")

        # 删除目录（递归处理只读内容）
        if os.path.exists(self.db_dir):
            try:
                # 递归删除目录及内容（自动处理只读文件）
                shutil.rmtree(self.db_dir, onerror=self._handle_remove_error)
            except Exception as e:
                logging.error(f"删除目录失败: {self.db_dir}, 错误: {str(e)}")

    def _handle_remove_error(self, func, path, exc_info):
        """shutil.rmtree 的错误回调函数，用于处理只读文件"""
        # 若因权限问题失败，修改权限后重试[7,9](@ref)
        if func in (os.rmdir, os.remove, os.unlink) and exc_info[1].errno == 13:  # Errno 13: Permission denied
            os.chmod(path, stat.S_IWRITE)  # 解除只读属性
            func(path)  # 重试删除操作
        else:
            raise exc_info[1]  # 其他错误直接抛出

    # --- 核心功能测试 ---
    def test_record_new_url(self):
        """测试新URL记录"""
        self.assertTrue(self.record.record_url_status(self.test_url, STATUS_SUCCESS))
        status = self.record.get_url_status(self.test_url)
        self.assertEqual(status, STATUS_SUCCESS)  # 应返回正确状态[7](@ref)

    def test_update_existing_url(self):
        """测试更新已有URL"""
        self.record.record_url_status(self.test_url, STATUS_SUCCESS)
        self.record.record_url_status(self.test_url, STATUS_ERROR)
        self.assertEqual(self.record.get_url_status(self.test_url), STATUS_ERROR)  # 状态应更新[2](@ref)

    def test_error_count_increment(self):
        """测试错误计数增加"""
        self.record.increment_error_count(self.test_url)
        self.assertEqual(self.record.get_error_count(self.test_url), 1)
        self.record.increment_error_count(self.test_url)
        self.assertEqual(self.record.get_error_count(self.test_url), 2)  # 应累加[4](@ref)

    # --- 边界条件测试 ---
    def test_cache_eviction(self):
        """测试缓存淘汰机制"""
        # 填充缓存至上限+1
        for i in range(1001):
            url = f"https://site{i}.com"
            self.record.record_url_status(url, STATUS_SUCCESS)

        # 验证第一条记录被淘汰
        self.assertIsNone(self.record.memory_cache.get("https://site0.com", None))  # 应被移除
        self.assertIsNotNone(self.record.memory_cache.get("https://site1000.com", None))  # 最新记录应保留

    def test_nonexistent_url_status(self):
        """测试不存在的URL"""
        status = self.record.get_url_status("invalid_url")
        self.assertEqual(status, STATUS_NOT_EXIST)  # 应返回不存在状态[2](@ref)

    def test_invalid_status_code(self):
        """测试无效状态码"""
        result = self.record.record_url_status(self.test_url, 5)  # <10的保留状态码
        self.assertFalse(result)  # 应拒绝记录[4](@ref)

    # --- 持久化测试 ---
    def test_persistence_after_reopen(self):
        """测试重启后数据持久化"""
        self.record.record_url_status(self.test_url, STATUS_SUCCESS)
        self.record.close()
        self.record = None

        gc.collect()

        self.record = CrawlRecord([self.db_dir, self.db_name])
        status = self.record.get_url_status(self.test_url, from_db=True)
        self.assertEqual(status, STATUS_SUCCESS)

    # --- 并发安全测试 ---
    def test_concurrent_write(self):
        """测试并发写入（需手动验证日志）"""
        import threading
        def worker(url):
            self.record.record_url_status(url, STATUS_SUCCESS)

        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(f"https://concurrent{i}.com",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    # --- 错误处理测试 ---
    def test_db_write_failure(self):
        """测试数据库写入失败"""
        # 创建只读数据库文件
        with open(self.db_path, 'w') as f:
            f.write("readonly")
        os.chmod(self.db_path, 0o444)  # 只读权限

        record = CrawlRecord(["test_dir", self.db_path])
        result = record.record_url_status(self.test_url, STATUS_SUCCESS)
        self.assertFalse(result)  # 应返回失败

    def test_large_rw_and_reload(self):
        # 构造2000条测试数据并随机更新状态/错误计数
        total_records = 2000
        test_urls = [f"https://example.com/page_{i}" for i in range(total_records)]

        for url in test_urls:
            # 随机生成状态（从预定义状态码中选择）
            status = random.choice([
                STATUS_SUCCESS,
                STATUS_ERROR,
                STATUS_IGNORED
            ])
            # 随机错误计数（0-5次）
            error_count = random.randint(0, 5)

            # 记录状态
            self.record.record_url_status(url, status)
            # 更新错误计数
            for _ in range(error_count):
                self.record.increment_error_count(url)

        # 释放资源并强制垃圾回收
        self.record.close()
        self.record = None
        gc.collect()

        # 重新初始化CrawlRecord（应加载最后1000条）
        self.record = CrawlRecord([self.db_dir, self.db_name], cache_size=1000)

        # 验证缓存是否包含最后1000条数据
        cached_urls = list(self.record.memory_cache.keys())
        expected_latest_urls = test_urls[-1000:]

        # 检查缓存数量
        self.assertEqual(len(cached_urls), 1000)
        # 检查缓存内容是否为最新数据
        self.assertCountEqual(cached_urls, expected_latest_urls)

        # 重复测试3次以验证稳定性
        for i in range(3):
            # 新增100条数据
            new_urls = [f"https://example.com/new_{j + i * 100}" for j in range(100)]
            for url in new_urls:
                self.record.record_url_status(url, random.choice([
                    STATUS_SUCCESS,
                    STATUS_ERROR,
                    STATUS_IGNORED
                ]))

            # 再次释放并重载
            self.record.close()
            self.record = None
            gc.collect()
            self.record = CrawlRecord([self.db_dir, self.db_name], cache_size=1000)

            # 验证缓存仍为最新1000条
            current_urls = list(self.record.memory_cache.keys())
            test_urls += new_urls
            expected_urls = test_urls[-1000:]
            self.assertCountEqual(current_urls, expected_urls)

        print('test_large_rw_and_reload done.')


if __name__ == '__main__':
    unittest.main()
