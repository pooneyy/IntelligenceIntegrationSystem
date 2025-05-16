import types
import inspect
import asyncio
from functools import partial
from typing import Any
from collections.abc import Iterable, Iterator, Awaitable


def get_full_type(obj: Any) -> str:
    """返回对象的详细类型描述，覆盖所有可能的Python对象类型"""
    # 特殊类型优先判断
    if inspect.ismodule(obj):
        return f"module: {obj.__name__}"
    if inspect.isclass(obj):
        return f"class: {obj.__name__}"
    if inspect.isfunction(obj):
        return f"function: {obj.__name__}"
    if isinstance(obj, partial):
        return "builtins.partial"
    if isinstance(obj, types.BuiltinFunctionType):
        return "builtin_function"
    if inspect.ismethod(obj):
        return f"method: {obj.__func__.__name__}"
    if isinstance(obj, types.ModuleType):
        return "module"
    if isinstance(obj, types.GeneratorType):
        return "generator"
    if isinstance(obj, types.CoroutineType):
        return "coroutine"
    if inspect.isawaitable(obj):
        return "async_generator" if inspect.isasyncgen(obj) else "async_coroutine"
    if isinstance(obj, (list, dict, set, tuple, str)):
        return f"builtin_container: {type(obj).__name__}"
    if isinstance(obj, memoryview):
        return "memoryview"
    if isinstance(obj, slice):
        return "slice"
    # 覆盖所有内置类型
    return f"{type(obj).__module__}.{type(obj).__name__}"


def analyze_properties(obj: Any) -> dict:
    """返回对象的关键属性分析字典"""
    return {
        "callable": callable(obj),
        "iterable": isinstance(obj, Iterable) and not isinstance(obj, (str, bytes)),
        "iterator": isinstance(obj, Iterator),
        "awaitable": isinstance(obj, Awaitable),
        "hashable": hasattr(obj, "__hash__") and type(obj).__hash__ is not None,
        "context_manager": hasattr(obj, "__enter__") and hasattr(obj, "__exit__"),
        "sizeable": hasattr(obj, "__len__"),
        "numeric": isinstance(obj, (int, float, complex)),
        "buffer_protocol": (
            hasattr(obj, "__buffer__")                  # 通用缓冲区协议支持
            or isinstance(obj, memoryview)              # 直接识别 memoryview 对象
            or (isinstance(obj, (bytes, bytearray)))    # 支持缓冲区协议的原始类型
        ),
        "descriptor": hasattr(obj, "__get__") or hasattr(obj, "__set__"),
        "dynamic_attrs": hasattr(obj, "__dict__")
    }


def main():
    import types
    import pytest
    import asyncio
    from functools import partial


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

    print('Done')


if __name__ == "__main__":
    main()
