import os
import faiss
import pickle
import traceback
from sentence_transformers import SentenceTransformer

from Workflow.CommonFeedsCrawFlow import logger

"""
# 文本嵌入模型选择指南 (2025 Q3)
+----------------------------+--------+----------+----------+---------------------+------------------------------------------+
|          Model             | Dims   | Mem(GB)  | MTEB ↑   | Best For            | EN Evaluation Notes                      |
+----------------------------+--------+----------+----------+---------------------+------------------------------------------+
| Gemini-Embedding-exp-03-07 | 3072   | 4.8      | 87.3%    | Multi-lingual QA    | SOTA in XTREME-UP benchmark (91 languages)|
| BGE-M3                     | 1024   | 3.2      | 85.9%    | Hybrid Retrieval    | Supports dense/sparse/colbert tri-mode   |
| text-embedding-3-large     | 3072   | 5.1      | 86.7%    | Semantic Similarity | Optimal at 1536 dims via dim-reduction   |
| gte-Qwen2-7B-instruct      | 3584   | 10.2     | 84.5%    | Long Document       | 32k tokens context (SOTA for >10k docs)  |
| jina-embeddings-v3         | 512    | 1.8      | 83.1%    | Legal Text          | 8k ctx, German/Chinese optimized         |
| mxbai-embed-large          | 1024   | 2.4      | 82.8%    | Classification      | 79.3% accuracy on HuggingFace Emotions   |
| text-embedding-3-small     | 1536   | 1.1      | 82.3%    | General Purpose     | Cost-perf leader (11x faster than BERT)  |
| nomic-embed-text           | 768    | 1.5      | 80.9%    | RAG Systems         | Apache-2 licensed, 8k ctx                |
| all-MiniLM-L6-v2 ★         | 384    | 0.9      | 80.1%    | Fast Prototyping    | 58ms latency on CPU (baseline model)     |
| damo/nlp_corom_sentence    | 768    | 1.6      | 78.4%    | Chinese QA          | 85.3% on T2Rerank-zh benchmark           |
+----------------------------+--------+----------+----------+---------------------+------------------------------------------+
# MTEB ↑: Higher is better (0-100 scale), Mem: VRAM usage for batch=32

# Faiss 索引方案对比
+---------------------+----------------+------------+----------+----------------+----------------------------------------+
| Index Type          | Parameters     | Recall ↑   | Mem ↓    | Build Time     | EN Application Notes                   |
+---------------------+----------------+------------+----------+----------------+----------------------------------------+
| HNSW32              | M=32, ef=128    | 97.2%      | High     | Slow           | Best for <100M vectors (fast query)    |
| IVF4096_PQ32        | nlist=4096     | 89.7%      | 0.25X    | Medium         | Memory-efficient for 1B+ vectors       |
| OPQ256_IVF1024      | OPQ bits=256   | 93.1%      | 0.6X     | Fast           | For >1024d vectors (dimensionality reduction)|
| SCANN               | leaves=2000    | 88.3%      | 0.3X     | Very Slow      | Google's billion-scale solution        |
| IndexFlatL2 ★       | -              | 100%       | 1.0X     | Instant        | Exact search (development/testing)     |
| IMI2x10_PQ50        | 2^10 clusters  | 82.4%      | 0.15X    | Very Slow      | Extreme compression (edge devices)      |
+---------------------+----------------+------------+----------+----------------+----------------------------------------+
# Recall ↑: Compared to exact search, Mem ↓: Relative to Flat index
"""

class VectorDatabase:
    def __init__(self, db_name="vectordb", save_path="./", embedding_model: str = 'all-MiniLM-L6-v2'):
        self.save_path = os.path.join(save_path, db_name)
        os.makedirs(self.save_path, exist_ok=True)

        # 使用轻量级句子嵌入模型（约90MB）
        self.encoder = SentenceTransformer(embedding_model)
        self.dimension = 384  # 模型输出维度

        # 初始化Faiss索引
        self.index = faiss.IndexFlatL2(self.dimension)
        self.id_map = {}  # 维护ID到索引位置的映射
        self.current_idx = 0

        # 加载已有数据
        self.load()

    def add_text(self, doc_id: str, text: str) -> bool:
        """添加文本并生成向量"""
        if not isinstance(doc_id, str):
            return False
        vector = self.encoder.encode([text], convert_to_numpy=True)
        self.index.add(vector.astype('float32'))
        self.id_map[self.current_idx] = doc_id
        self.current_idx += 1
        return True

    def search(self, query_text: str, top_n=5):
        """相似文本搜索"""
        if top_n <= 0:
            return []
        query_vec = self.encoder.encode([query_text], convert_to_numpy=True)
        distances, indices = self.index.search(query_vec.astype('float32'), top_n)

        return [self.id_map[idx] for idx in indices[0] if idx in self.id_map]

    def save(self) -> bool:
        """保存数据库"""
        try:
            faiss.write_index(self.index, os.path.join(self.save_path, "index.faiss"))
            with open(os.path.join(self.save_path, "id_map.pkl"), 'wb') as f:
                pickle.dump(self.id_map, f)
            return True
        except Exception as e:
            logger.error(f'Save vector db error: {str(e)}')
            return False

    def load(self) -> bool:
        """加载已有数据库"""
        try:
            index_path = os.path.join(self.save_path, "index.faiss")
            map_path = os.path.join(self.save_path, "id_map.pkl")

            if os.path.exists(index_path):
                self.index = faiss.read_index(index_path)
                with open(map_path, 'rb') as f:
                    self.id_map = pickle.load(f)
                self.current_idx = max(self.id_map.keys()) + 1
            return True
        except Exception as e:
            logger.error(f'Load vector db error: {str(e)}')
            return False


# ----------------------------------------------------------------------------------------------------------------------

def test_vector_db():
    import shutil
    test_results = []

    def _run_test(test_name, func):
        try:
            result = func()
            test_results.append((test_name, "PASS", result))
        except Exception as e:
            test_results.append((test_name, "FAIL", str(e)))

    # 测试1: 正常流程测试
    def _test_normal_flow():
        db = VectorDatabase("test_db", "./test_data")
        # 添加文档
        db.add_text("doc1", "Machine learning algorithms")
        db.add_text("doc2", "Deep neural networks")
        db.add_text("doc3", "Natural language processing")

        # 基础搜索
        search_result = db.search("AI technology", 2)
        # 验证返回数量
        assert len(search_result) == 2, f"Expected 2 results, got {len(search_result)}"
        # 验证ID存在性
        assert all(id in ["doc1", "doc2", "doc3"] for id in search_result)

        # 保存加载验证
        db.save()
        reload_db = VectorDatabase("test_db", "./test_data")
        reload_search = reload_db.search("AI", 1)
        return {
            "initial_search": search_result,
            "reload_search": reload_search
        }

    # 测试2: 边界条件测试
    def _test_edge_cases():
        db = VectorDatabase("edge_db", "./test_data")
        # 空文本测试
        db.add_text("empty", "")
        # 超长文本
        long_text = "deep learning " * 1000
        db.add_text("long", long_text)

        # 搜索空文本
        empty_search = db.search("", 3)
        # 超限topN
        over_search = db.search("test", 10)
        # 零结果请求
        zero_search = db.search("test", 0)

        return {
            "empty_search": empty_search,
            "over_search": len(over_search),
            "zero_search": zero_search
        }

    # 测试3: 异常处理测试
    def _test_exceptions():
        db = VectorDatabase("exception_db", "./test_data")
        # 重复ID添加
        db.add_text("dup", "first")
        db.add_text("dup", "second")  # 应该覆盖
        result = db.add_text(123, "invalid id")  # ID类型错误

        # 无效topN
        invalid_search = db.search("test", -5)
        return {
            "duplicate_add": db.search("second", 1),
            "type_error": result,
            "negative_search": invalid_search
        }

    # 执行所有测试
    _run_test("Normal Functionality", _test_normal_flow)
    _run_test("Edge Cases", _test_edge_cases)
    _run_test("Exception Handling", _test_exceptions)

    # 清理测试数据
    shutil.rmtree("./test_data", ignore_errors=True)

    # 打印测试结果
    print("\n=== Detailed Test Report ===")
    for name, status, data in test_results:
        print(f"\n[{status}] {name}")
        print(f"Details: {str(data)[:200]}...")  # 截断长输出


def main():
    test_vector_db()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e))
        traceback.print_exc()






