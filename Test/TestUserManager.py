
import os
import time
import hashlib
import tempfile
import unittest
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from ServiceComponent.UserManager import UserManager


class TestUserManager(unittest.TestCase):
    def setUp(self):
        # 使用临时数据库文件
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.manager = UserManager(self.db_path)

        # 初始化测试数据
        self._create_test_data()

    def _create_test_data(self):
        # 创建基础权限
        self.manager.create_permission("read_data")
        self.manager.create_permission("write_data")
        self.manager.create_permission("delete_data")

        # 创建角色及其权限
        self.manager.add_role("admin", ["read_data", "write_data", "delete_data"])
        self.manager.add_role("editor", ["read_data", "write_data"])
        self.manager.add_role("viewer", ["read_data"])

        # 创建测试用户
        self.manager.create_user("admin_user", "AdminPass123!", ["admin"])
        self.manager.create_user("editor_user", "EditPass456@", ["editor"])
        self.manager.create_user("viewer_user", "ViewPass789#", ["viewer"])

    def tearDown(self):
        self.manager = None
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_user_authentication_success(self):
        # 测试有效认证
        result, message = self.manager.authenticate("admin_user", "AdminPass123!", "127.0.0.1")
        self.assertTrue(result)
        self.assertEqual(message, "Login successful")

    def test_user_authentication_wrong_password(self):
        # 测试错误密码
        result, message = self.manager.authenticate("admin_user", "wrongpassword", "127.0.0.1")
        self.assertFalse(result)
        self.assertEqual(message, "Invalid credentials")

    def test_user_authentication_invalid_user(self):
        # 测试无效用户
        result, message = self.manager.authenticate("non_existent", "anypassword", "127.0.0.1")
        self.assertFalse(result)
        self.assertEqual(message, "Invalid credentials")

    def test_user_authentication_disabled_account(self):
        # 测试禁用账户
        self.manager.update_user(self._get_user_id("admin_user"), is_active=False)
        result, message = self.manager.authenticate("admin_user", "AdminPass123!", "127.0.0.1")
        self.assertFalse(result)
        self.assertEqual(message, "Account disabled")

    def test_user_creation_success(self):
        # 测试用户创建
        success, message = self.manager.create_user("new_user", "NewPass123!", ["editor"])
        self.assertTrue(success)
        self.assertEqual(message, "User new_user created with 1 roles")

        # 验证用户是否创建成功
        user_id = self._get_user_id("new_user")
        self.assertIsNotNone(user_id)
        self.assertTrue(self.manager.check_permission(user_id, "read_data"))

    def test_user_creation_duplicate_username(self):
        # 测试重复用户名
        id, message = self.manager.create_user("admin_user", "anypassword", [])
        self.assertEqual(id, -1)
        self.assertEqual(message, "Username already exists")

    def test_user_update_username(self):
        # 测试更新用户名
        user_id = self._get_user_id("admin_user")
        success, message = self.manager.update_user(user_id, new_username="new_admin")
        self.assertTrue(success)

        # 验证用户名更新
        conn = self.manager._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM user_account WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        self.assertEqual(result[0], "new_admin")

    def test_user_update_password(self):
        # 测试更新密码
        user_id = self._get_user_id("admin_user")
        success, message = self.manager.update_user(user_id, new_password="NewStrongPass!123")
        self.assertTrue(success)

        # 验证新密码是否有效
        result, _ = self.manager.authenticate("admin_user", "NewStrongPass!123", "127.0.0.1")
        self.assertTrue(result)

    def test_user_update_status(self):
        # 测试更新账户状态
        user_id = self._get_user_id("admin_user")
        success, message = self.manager.update_user(user_id, is_active=False)
        self.assertTrue(success)

        # 验证账户状态
        conn = self.manager._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT is_active FROM user_account WHERE id = ?", (user_id,))
        self.assertEqual(cursor.fetchone()[0], 0)

    def test_user_update_no_changes(self):
        # 测试无更新操作
        user_id = self._get_user_id("admin_user")
        success, message = self.manager.update_user(user_id)
        self.assertFalse(success)
        self.assertEqual(message, "No updates provided")

    def test_user_deletion(self):
        # 测试用户删除
        user_id = self._get_user_id("editor_user")
        success, message = self.manager.delete_user(user_id)
        self.assertTrue(success)

        # 验证用户已删除
        conn = self.manager._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM user_account WHERE id = ?", (user_id,))
        self.assertIsNone(cursor.fetchone())

        # 验证角色关联已级联删除
        cursor.execute("SELECT 1 FROM user_role WHERE user_id = ?", (user_id,))
        self.assertIsNone(cursor.fetchone())

    def test_role_creation_success(self):
        # 测试角色创建
        success, message = self.manager.add_role("moderator", ["read_data", "delete_data"])
        self.assertTrue(success)
        self.assertEqual(message, "Role 'moderator' created with 2 permissions")

        # 验证权限分配
        role_id = self._get_role_id("moderator")
        self.assertTrue(role_id > 0)
        self.assertTrue(self._role_has_permission(role_id, "read_data"))
        self.assertTrue(self._role_has_permission(role_id, "delete_data"))

    def test_role_creation_duplicate(self):
        # 测试重复角色
        success, message = self.manager.add_role("admin", [])
        self.assertFalse(success)
        self.assertEqual(message, "Role already exists")

    def test_role_creation_auto_permission(self):
        # 测试自动创建权限
        success, message = self.manager.add_role("special", ["new_permission", "other_permission"])
        self.assertTrue(success)
        self.manager.create_user('special_user', '1234567890', ["special"])
        self.assertTrue(self.manager.check_permission(self._get_user_id("special_user"), "new_permission"))
        self.assertTrue(self.manager.check_permission(self._get_user_id("special_user"), "other_permission"))

    def test_permission_creation(self):
        # 测试权限创建
        success, message = self.manager.create_permission("execute_tasks")
        self.assertTrue(success)

        # 验证权限存在
        perm_id = self._get_perm_id("execute_tasks")
        self.assertIsNotNone(perm_id)

    def test_permission_creation_duplicate(self):
        # 测试重复权限
        success, _ = self.manager.create_permission("read_data")
        self.assertFalse(success)

    def test_permission_deletion(self):
        # 测试权限删除
        success, message = self.manager.delete_permission("write_data")
        self.assertTrue(success)

        # 验证权限已被删除
        self.assertIsNone(self._get_perm_id("write_data"))

        # 验证角色权限映射已级联删除
        role_id = self._get_role_id("editor")
        self.assertFalse(self._role_has_permission(role_id, "write_data"))

    def test_role_assignment(self):
        # 测试角色分配
        user_id = self._get_user_id("viewer_user")
        success, message = self.manager.assign_roles(user_id, ["editor", "viewer"])
        self.assertTrue(success)
        self.assertEqual(message, "Assigned 2 roles to user")

        # 验证角色分配
        self.assertTrue(self.manager.check_permission(user_id, "write_data"))
        self.assertTrue(self.manager.check_permission(user_id, "read_data"))

        # 验证旧角色是否已移除
        conn = self.manager._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_role WHERE user_id = ?", (user_id,))
        self.assertEqual(cursor.fetchone()[0], 2)

    def test_permission_checking(self):
        # 测试权限检查
        admin_id = self._get_user_id("admin_user")
        editor_id = self._get_user_id("editor_user")
        viewer_id = self._get_user_id("viewer_user")

        # 管理员应有所有权限
        self.assertTrue(self.manager.check_permission(admin_id, "read_data"))
        self.assertTrue(self.manager.check_permission(admin_id, "write_data"))
        self.assertTrue(self.manager.check_permission(admin_id, "delete_data"))

        # 编辑应有读写权限
        self.assertTrue(self.manager.check_permission(editor_id, "read_data"))
        self.assertTrue(self.manager.check_permission(editor_id, "write_data"))
        self.assertFalse(self.manager.check_permission(editor_id, "delete_data"))

        # 查看者只有读权限
        self.assertTrue(self.manager.check_permission(viewer_id, "read_data"))
        self.assertFalse(self.manager.check_permission(viewer_id, "write_data"))
        self.assertFalse(self.manager.check_permission(viewer_id, "delete_data"))

        # 无效权限检查
        self.assertFalse(self.manager.check_permission(admin_id, "non_existent_permission"))

    def test_login_logging(self):
        # 测试登录日志记录
        # 执行登录尝试
        self.manager.authenticate("admin_user", "AdminPass123!", "192.168.1.10")
        self.manager.authenticate("admin_user", "wrongpass", "192.168.1.20")

        # 检查日志记录
        conn = self.manager._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT result, attempted_password_hash FROM login_log ORDER BY id DESC")
        results = cursor.fetchall()

        # 验证最近的两次尝试
        self.assertEqual(len(results), 2)

        # 失败尝试
        self.assertEqual(results[0][0], "FAILURE")
        self.assertEqual(
            results[0][1],
            hashlib.sha256("wrongpass".encode()).hexdigest()
        )

        # 成功尝试
        self.assertEqual(results[1][0], "SUCCESS")
        self.assertIsNone(results[1][1])

    def test_data_integrity(self):
        # 测试外键约束和级联删除
        user_id = self._get_user_id("editor_user")

        # 删除用户
        self.manager.delete_user(user_id)

        # 检查角色映射是否已删除
        conn = self.manager._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM user_role WHERE user_id = ?", (user_id,))
        self.assertIsNone(cursor.fetchone())

        # 检查登录日志是否保留但用户设置为空
        cursor.execute("SELECT user_id FROM login_log WHERE username = 'editor_user'")
        for row in cursor.fetchall():
            self.assertIsNone(row[0])

    # def test_concurrent_access(self):
    #     # 并发性能测试
    #     start_time = time.time()
    #     success_count = 0
    #     total_ops = 500
    #
    #     def worker():
    #         nonlocal success_count
    #         # 在认证、创建用户、权限检查间轮换
    #         try:
    #             if threading.get_ident() % 3 == 0:
    #                 result, _ = self.manager.authenticate("admin_user", "AdminPass123!", "127.0.0.1")
    #                 if result:
    #                     success_count += 1
    #             elif threading.get_ident() % 3 == 1:
    #                 username = f"temp_user_{threading.get_ident()}"
    #                 success, _ = self.manager.create_user(username, "TempPass123", ["viewer"])
    #                 if success:
    #                     success_count += 1
    #                     self.manager.delete_user(self._get_user_id(username))
    #             else:
    #                 if self.manager.check_permission(self._get_user_id("viewer_user"), "read_data"):
    #                     success_count += 1
    #         except Exception:
    #             pass
    #
    #     with ThreadPoolExecutor(max_workers=20) as executor:
    #         for _ in range(total_ops):
    #             executor.submit(worker)
    #
    #     # 等待所有任务完成
    #     executor.shutdown(wait=True)
    #
    #     duration = time.time() - start_time
    #     print(f"\n并发测试完成: {total_ops} 次操作, 成功率: "
    #           f"{(success_count / total_ops) * 100:.2f}%, 耗时: {duration:.2f}秒")
    #
    #     self.assertGreater(success_count / total_ops, 0.95)  # 95%成功率

    # def test_high_volume_create_users(self):
    #     # 高负载用户创建测试
    #     start_time = time.time()
    #     num_users = 100
    #
    #     with ThreadPoolExecutor(max_workers=10) as executor:
    #         futures = [
    #             executor.submit(
    #                 self.manager.create_user,
    #                 f"stress_user_{i}",
    #                 f"Pass_{i}",
    #                 ["viewer"]
    #             )
    #             for i in range(num_users)
    #         ]
    #
    #         success_count = sum(f.result()[0] for f in futures)
    #
    #     duration = time.time() - start_time
    #     print(f"\n高负载用户创建测试: 创建 {success_count}/{num_users} 个用户, "
    #           f"耗时: {duration:.2f}秒, {num_users / duration:.2f} OP/S")
    #
    #     # 验证创建的用户
    #     conn = self.manager._get_conn()
    #     cursor = conn.cursor()
    #     cursor.execute("SELECT COUNT(*) FROM user_account WHERE username LIKE 'stress_user_%'")
    #     self.assertEqual(cursor.fetchone()[0], num_users)

    def test_role_permission_concurrent_update(self):
        # 并发角色更新测试
        role_name = "test_concurrent_role"
        self.manager.add_role(role_name, [])

        # 定义添加和删除权限的worker
        def add_permission():
            try:
                self.manager.add_role(role_name, ["new_permission"])
            except Exception:
                pass

        def remove_permission():
            try:
                self.manager.delete_permission("new_permission")
            except Exception:
                pass

        def check_permission():
            try:
                self.manager.check_permission(self._get_user_id("admin_user"), "new_permission")
            except Exception:
                pass

        # 并行操作
        with ThreadPoolExecutor(max_workers=15) as executor:
            for _ in range(50):
                executor.submit(add_permission)
                executor.submit(remove_permission)
                executor.submit(check_permission)

        # 检查最终状态
        role_id = self._get_role_id(role_name)
        perm_id = self._get_perm_id("new_permission")
        if perm_id:
            self.assertTrue(self._role_has_permission(role_id, "new_permission"))
        else:
            self.assertFalse(self._role_has_permission(role_id, "new_permission"))

    def test_integrity_after_failures(self):
        # 失败后数据完整性测试
        user_id = self._get_user_id("admin_user")

        # 制造一个有缺陷的更新尝试
        try:
            self.manager.update_user(user_id, new_username="admin_user" * 100)  # 故意过长会导致异常
        except:
            pass

        # 检查用户数据是否依然有效
        conn = self.manager._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM user_account WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        self.assertEqual(result[0], "admin_user")

        # 尝试正常操作
        success, message = self.manager.update_user(user_id, is_active=False)
        self.assertTrue(success)

        # 验证更新成功
        cursor.execute("SELECT is_active FROM user_account WHERE id = ?", (user_id,))
        self.assertEqual(cursor.fetchone()[0], 0)

        conn.close()

    def test_username_length_constraints(self):
        # 测试短用户名
        _id, message = self.manager.create_user("ab", "Pass123!", [])
        self.assertEqual(_id, -1)
        self.assertEqual(message, "invalid length")

        # 测试超长用户名
        long_name = "a" * 51
        _id, message = self.manager.create_user(long_name, "Pass123!", [])
        self.assertEqual(_id, -1)
        self.assertEqual(message, "invalid length")

        # 测试非法字符
        _id, message = self.manager.create_user("user@name", "Pass123!", [])
        self.assertEqual(_id, -1)
        self.assertEqual(message, "invalid char")

    # ------------- 辅助方法 --------------

    def _get_user_id(self, username):
        conn = self.manager._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM user_account WHERE username = ?", (username,))
        result = cursor.fetchone()
        return result[0] if result else None

    def _get_role_id(self, role_name):
        conn = self.manager._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM role WHERE role_name = ?", (role_name,))
        result = cursor.fetchone()
        return result[0] if result else None

    def _get_perm_id(self, perm_name):
        conn = self.manager._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM permission WHERE perm_name = ?", (perm_name,))
        result = cursor.fetchone()
        return result[0] if result else None

    def _role_has_permission(self, role_id, perm_name):
        conn = self.manager._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM role_permission rp
            JOIN permission p ON rp.perm_id = p.id
            WHERE rp.role_id = ? AND p.perm_name = ?
        """, (role_id, perm_name))
        return cursor.fetchone() is not None


if __name__ == "__main__":
    # 详细测试输出
    unittest.main(verbosity=2)
