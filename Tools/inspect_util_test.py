import types
import pytest
import asyncio
from functools import partial

from Tools.inspect_util import get_full_type, analyze_properties


# pip install pytest-asyncio

# 测试类型检测函数
class TestTypeDetection:
    """测试对象类型检测的边界场景"""

    def test_primitive_types(self):
        assert get_full_type(42) == "builtins.int"
        assert get_full_type("test") == "builtin_container: str"
        assert get_full_type(3.14) == "builtins.float"

    def test_function_types(self):
        def sample_func(): pass

        assert get_full_type(sample_func) == "function: sample_func"
        assert get_full_type(lambda x: x) == "function: <lambda>"
        assert get_full_type(partial(print, end="")) == "builtins.partial"

    def test_class_objects(self):
        class MyClass:
            @staticmethod
            def static_m(): pass

            def method(self): pass

        obj = MyClass()
        assert get_full_type(MyClass) == "class: MyClass"
        assert get_full_type(obj.method) == "method: method"

    def test_special_objects(self):
        gen = (x for x in range(3))
        assert get_full_type(gen) == "generator"
        assert get_full_type(slice(1, 5)) == "slice"

    @pytest.mark.asyncio
    async def test_async_objects(self):
        async def async_gen(): yield 1

        coro = asyncio.sleep(0.1)
        assert get_full_type(async_gen()) == "async_generator"
        assert get_full_type(coro) == "async_coroutine"


# 测试属性分析函数
class TestPropertyAnalysis:
    """测试对象行为属性分析"""

    def test_callable_objects(self):
        assert analyze_properties(print)["callable"] is True
        assert analyze_properties(types.new_class('DynClass')())["callable"] is False

    def test_iterable_objects(self):
        props = analyze_properties({"a": 1}.keys())
        assert props["iterable"] is True and props["iterator"] is False

        props = analyze_properties(iter([1, 2, 3]))
        assert props["iterator"] is True

    def test_context_managers(self):
        class CtxManager:
            def __enter__(self): pass

            def __exit__(self, *args): pass

        assert analyze_properties(CtxManager())["context_manager"] is True

    def test_numeric_types(self):
        assert analyze_properties(10 + 2j)["numeric"] is True
        assert analyze_properties("123")["numeric"] is False

    @pytest.mark.asyncio
    async def test_awaitable_objects(self):
        coro = asyncio.sleep(0.1)
        assert analyze_properties(coro)["awaitable"] is True


# 综合测试数据集
TEST_OBJECTS = [
    (open(__file__), {"context_manager": True, "dynamic_attrs": True}),
    (memoryview(b'bytes'), {"buffer_protocol": True}),
    (asyncio.Lock(), {"awaitable": False, "callable": False}),
    (types.new_class('DynClass')(), {"dynamic_attrs": True})
]


@pytest.mark.parametrize("obj, expected", TEST_OBJECTS)
def test_comprehensive_properties(obj, expected):
    actual = analyze_properties(obj)
    for k, v in expected.items():
        assert actual[k] == v
