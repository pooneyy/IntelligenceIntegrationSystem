import os
import json
import shutil
import traceback

import hnswlib
import numpy as np
from sentence_transformers import SentenceTransformer


class VectorDatabase:
    def __init__(self, db_name="vectordb", dim=384, max_elements=1000):
        """
        :param db_name: 数据库存储路径/名称
        :param dim: 向量维度（需与模型匹配）
        :param max_elements: 最大存储容量
        """
        self.db_path = f"{db_name}.json"
        self.index_path = f"{db_name}_index.bin"
        self.model = SentenceTransformer('paraphrase-MiniLM-L6-v2')  # 轻量级模型[10](@ref)
        self.dim = dim
        self.max_elements = max_elements

        # 初始化索引
        self.index = hnswlib.Index(space='cosine', dim=dim)
        if os.path.exists(self.index_path):
            self.index.load_index(self.index_path)
        else:
            self.index.init_index(max_elements, ef_construction=200, M=16)

        # 加载已有数据
        self.id_map = {}
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r') as f:
                self.id_map = json.load(f)

    def add(self, doc_id: str, text: str):
        """ 添加文档 """
        vector = self.model.encode(text).tolist()
        print(f"Vector before np.array: {vector}, type: {type(vector)}")
        self.id_map[doc_id] = vector
        np_arr = np.array([vector])
        self.index.add_items(np_arr)
        self._save()

    def search(self, query_text: str, top_n=5) -> list:
        """ 相似度查询 """
        query_vec = self.model.encode(query_text)
        labels, _ = self.index.knn_query(query_vec, k=top_n)
        return [list(self.id_map.keys())[label] for label in labels[0]]

    def _save(self):
        """ 持久化存储 """
        self.index.save_index(self.index_path)
        with open(self.db_path, 'w') as f:
            json.dump(self.id_map, f)


# ----------------------------------------------------------------------------------------------------------------------

def test_vector_database():
    # 初始化测试环境
    test_db_name = "test_db"
    if os.path.exists(f"{test_db_name}.json"):
        shutil.rmtree(f"{test_db_name}.json")
    if os.path.exists(f"{test_db_name}_index.bin"):
        os.remove(f"{test_db_name}_index.bin")

    print("\n=== 测试1：数据库初始化 ===")
    db = VectorDatabase(test_db_name)
    print(f"初始化数据库 {test_db_name}，当前文档数：{len(db.id_map)}")
    assert len(db.id_map) == 0, "初始数据库应为空"

    # 测试数据准备
    test_data = {
        "doc1": "苹果是一种常见的水果",
        "doc2": "量子计算机使用量子比特进行计算",
        "doc3": "Python是一种解释型编程语言",
        "doc4": "深度学习需要大量矩阵运算"
    }

    print("\n=== 测试2：文档添加操作 ===")
    for doc_id, text in test_data.items():
        db.add(doc_id, text)
        print(f"已添加 {doc_id}：{text[:10]}...")
        assert doc_id in db.id_map, f"{doc_id} 应存在于数据库"
        print(f"验证 {doc_id} 向量存储：{len(db.id_map[doc_id])}维向量")
        assert len(db.id_map[doc_id]) == db.dim, "向量维度不匹配"

    print("\n=== 测试3：基础搜索功能 ===")
    test_cases = [
        ("水果", ["doc1"], "应匹配最相关的水果文档"),
        ("编程", ["doc3", "doc2"], "应匹配编程和计算机相关文档"),
        ("计算", ["doc2", "doc4"], "应匹配量子计算和矩阵计算")
    ]

    for query, expected, desc in test_cases:
        results = db.search(query, top_n=2)
        print(f"\n查询『{query}』返回：{results}")
        print(f"验证 {desc}")
        assert any(e in results for e in expected), f"未返回预期结果 {expected}"

    print("\n=== 测试4：边界条件测试 ===")
    # 空数据库测试（使用新实例）
    empty_db = VectorDatabase("empty_db")
    empty_results = empty_db.search("test", 1)
    print(f"空数据库查询结果：{empty_results}")
    assert len(empty_results) == 0, "空数据库应返回空结果"

    # 超量请求测试
    overflow_results = db.search("计算", 10)
    print(f"请求10个结果，实际返回 {len(overflow_results)} 个")
    assert len(overflow_results) == min(10, len(test_data)), "返回数量错误"

    print("\n=== 测试5：持久化验证 ===")
    # 创建新实例验证持久化
    reload_db = VectorDatabase(test_db_name)
    print(f"重新加载数据库，文档数：{len(reload_db.id_map)}")
    assert len(reload_db.id_map) == len(test_data), "持久化数据不完整"

    # 验证向量一致性
    sample_id = "doc1"
    print(f"对比 {sample_id} 的向量一致性：")
    print("原向量：", db.id_map[sample_id][:3], "...")
    print("新向量：", reload_db.id_map[sample_id][:3], "...")
    assert db.id_map[sample_id] == reload_db.id_map[sample_id], "向量数据不一致"

    print("\n=== 测试6：异常情况处理 ===")
    try:
        db.add("doc1", "重复ID测试")
        print("重复ID测试结果：覆盖成功")
        assert "doc1" in db.id_map
    except Exception as e:
        print(f"重复ID处理异常：{str(e)}")
        assert False, "应支持ID覆盖"

    print("\n=== 所有测试完成 ===")
    return True


def main():
    test_result = test_vector_database()
    print("\n测试最终结果：", "通过" if test_result else "未通过")


# 执行测试
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e))
        traceback.print_exc()
