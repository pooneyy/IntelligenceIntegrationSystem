import asyncio
from tortoise.models import Model
from tortoise import Tortoise, fields, run_async
from tortoise.exceptions import IntegrityError, DoesNotExist


# ========================
# 🏗️ 1. 数据模型定义
# ========================
class User(Model):
    """用户模型（对应SQLite中的users表）"""
    id = fields.IntField(pk=True)  # 主键自增
    username = fields.CharField(max_length=50, unique=True)  # 唯一约束用户名
    email = fields.CharField(max_length=100, index=True)  # 建立索引提高查询效率
    created_at = fields.DatetimeField(auto_now_add=True)

    # 定义返回数据的友好格式
    def __str__(self):
        return f"User(id={self.id}, username='{self.username}')"


# ===========================================
# 🔧 2. 核心工具函数 (包含重复创建和存在性检测)
# ===========================================
class UserDAO:
    @staticmethod
    async def create_user(username: str, email: str) -> User:
        """
        安全创建用户（自动处理重复冲突）

        存在以下三种状态处理：
        1. 成功创建新用户 → 返回User实例
        2. 用户名重复 → 自动添加后缀重试
        3. 重试后仍失败 → 抛出IntegrityError
        """
        original_name = username
        attempt = 1

        while attempt <= 3:  # 最大重试3次
            try:
                return await User.create(username=username, email=email)
            except IntegrityError:  # 捕获唯一约束冲突
                print(f"⚠️ 用户名冲突: {username}. 尝试添加后缀重试...")
                username = f"{original_name}_{attempt}"  # 添加数字后缀
                attempt += 1

        raise ValueError(f"无法创建用户，所有尝试的用户名均已被占用: {original_name}")

    @staticmethod
    async def user_exists(username: str) -> bool:
        """检测用户名是否存在 (高效查询，仅返回布尔值)"""
        return await User.filter(username=username).exists()

    @staticmethod
    async def get_user(username: str) -> User | None:
        """获取用户完整对象（不存在时返回None）"""
        try:
            return await User.get(username=username)
        except DoesNotExist:
            return None

    @staticmethod
    async def update_email(username: str, new_email: str) -> bool:
        """
        更新用户邮箱
        返回操作结果：True=更新成功, False=用户不存在
        """
        affected = await User.filter(username=username).update(email=new_email)
        return affected > 0  # 根据受影响行数判断


# ========================
# 🚀 3. 示例执行函数
# ========================
async def main():
    # 初始化数据库连接 (SQLite内存数据库)
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["__main__"]}  # 指向当前模块的模型
    )
    await Tortoise.generate_schemas(safe=True)  # ⚡ 自动建表

    print("=========== 测试场景1: 用户创建 ===========")
    # 首次创建成功
    user1 = await UserDAO.create_user("john_doe", "john@example.com")
    print(f"✅ 创建用户: {user1}")

    # 尝试重复创建（会自动添加后缀）
    user2 = await UserDAO.create_user("john_doe", "another@example.com")
    print(f"✅ 冲突处理创建: {user2}")

    print("\n========= 测试场景2: 存在性检测 =========")
    # 检测存在的用户
    exists = await UserDAO.user_exists("john_doe")
    print(f"用户'john_doe'存在: {exists}")

    # 检测不存在的用户
    exists = await UserDAO.user_exists("non_exist")
    print(f"用户'non_exist'存在: {exists}")

    print("\n=========== 测试场景3: 更新操作 ==========")
    # 获取已有用户
    if (user := await UserDAO.get_user("john_doe")):
        print(f"🔍 找到用户: {user}")

        # 邮箱更新
        success = await UserDAO.update_email("john_doe", "john_new@company.com")
        print(f"📧 邮箱更新结果: {'成功' if success else '失败'}")

        # 验证更新
        updated_user = await UserDAO.get_user("john_doe")
        print(f"🆕 更新后邮箱: {updated_user.email}")

    print("\n======= 测试场景4: 批量查询与统计 ========")
    # 批量插入测试数据
    await User.create(username="user3", email="user3@test.com")
    await User.create(username="user4", email="user4@test.com")

    # 获取所有用户
    all_users = await User.all()
    print(f"📋 总用户数: {len(all_users)}")
    print("用户列表:", [u.username for u in all_users])

    # 关闭数据库连接
    await Tortoise.close_connections()


# 执行入口
if __name__ == "__main__":
    run_async(main())
