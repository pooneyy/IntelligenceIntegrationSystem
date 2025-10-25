import traceback

import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Dict, Any, Union, Optional


# pip install chromadb sentence-transformers langchain


class VectorStoreManager:
    """
    A manager class for handling text vectorization, storage, and search
    using ChromaDB and SentenceTransformers.

    This class is designed to be decoupled. It accepts instances of
    the ChromaDB client and the embedding model via its constructor.
    """

    def __init__(
            self,
            chroma_client: chromadb.Client,
            collection_name: str,
            embedding_model: SentenceTransformer,
            chunk_size: int = 512,
            chunk_overlap: int = 50
    ):
        """
        Initializes the VectorStoreManager.

        Args:
            chroma_client (chromadb.Client): An initialized ChromaDB client
                                             (e.g., PersistentClient).
            collection_name (str): The name of the collection to use.
            embedding_model (SentenceTransformer): An initialized
                                                  SentenceTransformer model.
            chunk_size (int): The target size for text chunks (in characters).
            chunk_overlap (int): The overlap between consecutive chunks.
        """
        self.client = chroma_client
        self.model = embedding_model

        # Get or create the collection with cosine similarity,
        # which is standard for sentence-transformers.
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )

        # (Requirement 3) Initialize the text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""]  # Good for multi-language
        )

        print(f"VectorStoreManager initialized for collection: '{collection_name}'")

    # --- Requirement 2: Independent Vectorization ---
    def vectorize_text(self, text: Union[str, List[str]]) -> np.ndarray:
        """
        Vectorizes a single text or a list of texts without saving to the DB.

        Args:
            text (Union[str, List[str]]): The text or texts to vectorize.

        Returns:
            np.ndarray: The resulting embedding(s).
        """
        return self.model.encode(text)

    # --- Requirement 1 & 3: Add Document with Chunking ---
    def add_document(self, text: str, doc_id: str) -> List[str]:
        """
        Adds a document to the vector store.
        Handles chunking for long text and maintains a mapping
        from the original doc_id to its chunks.

        Args:
            text (str): The full text of the document.
            doc_id (str): The unique identifier for the original document.

        Returns:
            List[str]: A list of the vector database index IDs (chunk_ids)
                       created for this document.
        """
        # (Requirement 3) Automatically split text into chunks
        chunks = self.text_splitter.split_text(text)

        if not chunks:
            print(f"Warning: Document {doc_id} produced no chunks.")
            return []

        # (Requirement 3) Create unique IDs and metadata for each chunk
        chunk_ids = [f"{doc_id}#chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {"original_doc_id": doc_id, "chunk_index": i, "total_chunks": len(chunks)}
            for i in range(len(chunks))
        ]

        # (Requirement 8) Decoupled vectorization
        embeddings = self.vectorize_text(chunks).tolist()

        # (Requirement 1) Save to vector database
        try:
            self.collection.add(
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas,
                ids=chunk_ids
            )
            return chunk_ids
        except Exception as e:
            print(f"Error adding document {doc_id}: {e}")
            return []

    # --- Requirement 4 & 5: Search with Filtering ---
    def search(
            self,
            query_text: str,
            top_n: int = 5,
            score_threshold: float = None,
            softmax_threshold: float = None,
            where_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Searches the vector store for a query text.
        Returns a de-duplicated list of original document IDs,
        ranked by their best matching chunk.

        Args:
            query_text (str): The text to search for.
            top_n (int): The maximum number of *chunks* to retrieve initially.
            score_threshold (float): A hard cutoff for similarity score (0.0 to 1.0).
                                     Only results with score >= threshold are returned.
            softmax_threshold (float): A cutoff for the softmax-normalized score.
                                       Only results with softmax_score >= threshold.
            where_filter (dict): A ChromaDB 'where' filter to apply to metadata.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, one for each unique
                                  matching *document*. Each dict contains the
                                  doc_id, the best score, and chunk details.
        """
        query_vector = self.vectorize_text(query_text).tolist()

        # (Requirement 4) Query the collection
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_n,
            where=where_filter,
            include=["metadatas", "documents", "distances"]
        )

        chunk_results = []
        if not results['ids'][0]:
            return []

        # Process raw results
        for i in range(len(results['ids'][0])):
            distance = results['distances'][0][i]
            # Convert cosine distance (0 to 2) to similarity score (1.0 to -1.0)
            # Since we set "cosine", distance = 1 - similarity
            similarity_score = 1.0 - distance

            chunk_results.append({
                "chunk_id": results['ids'][0][i],
                "doc_id": results['metadatas'][0][i]['original_doc_id'],
                "score": similarity_score,
                "chunk_text": results['documents'][0][i]
            })

        # --- (Requirement 5) Filtering ---

        # 1. Filter by hard score_threshold
        if score_threshold is not None:
            chunk_results = [r for r in chunk_results if r['score'] >= score_threshold]

        if not chunk_results:
            return []

        # 2. Filter by softmax_threshold
        if softmax_threshold is not None:
            scores = np.array([r['score'] for r in chunk_results])
            softmax_scores = self._softmax(scores)

            filtered_by_softmax = []
            for i, r in enumerate(chunk_results):
                r['softmax_score'] = softmax_scores[i]
                if r['softmax_score'] >= softmax_threshold:
                    filtered_by_softmax.append(r)
            chunk_results = filtered_by_softmax

        if not chunk_results:
            return []

        # --- De-duplicate by doc_id ---
        # Return the *best* chunk for each unique document
        final_doc_results = {}
        for r in chunk_results:
            doc_id = r['doc_id']
            if doc_id not in final_doc_results or r['score'] > final_doc_results[doc_id]['score']:
                final_doc_results[doc_id] = r

        # Sort final list by score, descending
        return sorted(final_doc_results.values(), key=lambda x: x['score'], reverse=True)

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """Helper function to compute softmax."""
        if x.size == 0:
            return np.array([])
        e_x = np.exp(x - np.max(x))  # Subtract max for numerical stability
        return e_x / e_x.sum(axis=0)

    # --- Requirement 6: Get and Delete ---
    def delete(
            self,
            doc_id: Optional[str] = None,
            chunk_id: Optional[str] = None
    ) -> bool:
        """
        Deletes data from the vector store.
        Can delete all chunks for a document OR a single specific chunk.

        Args:
            doc_id (str, optional): The original document ID. Deletes ALL
                                    associated chunks.
            chunk_id (str, optional): A specific chunk ID to delete.

        Returns:
            bool: True if deletion was attempted.
        """
        if not doc_id and not chunk_id:
            raise ValueError("Must provide either 'doc_id' or 'chunk_id'")

        try:
            if doc_id:
                # (Requirement 6) Delete by document_id using the metadata filter
                self.collection.delete(where={"original_doc_id": doc_id})
                print(f"Deleted all chunks for doc_id: {doc_id}")
            elif chunk_id:
                # (Requirement 6) Delete by specific vector index (chunk_id)
                self.collection.delete(ids=[chunk_id])
                print(f"Deleted chunk_id: {chunk_id}")
            return True
        except Exception as e:
            print(f"Error during deletion: {e}")
            return False

    def get_document_chunks(self, doc_id: str) -> Dict[str, Any]:
        """
        Retrieves all data (chunks, metadata) for a specific document ID.

        Args:
            doc_id (str): The original document ID.

        Returns:
            dict: The raw response from ChromaDB 'get' method.
        """
        return self.collection.get(
            where={"original_doc_id": doc_id},
            include=["metadatas", "documents"]
        )

    # --- Requirement 7: Browse Interface ---
    def browse(self, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """
        Provides a paginated interface to browse the database.
        Ideal for a future web UI.

        Args:
            limit (int): Number of items to return.
            offset (int): Item offset for pagination.

        Returns:
            dict: A dictionary containing data and pagination info.
        """
        total_count = self.collection.count()
        results = self.collection.get(
            limit=limit,
            offset=offset,
            include=["metadatas", "documents"]
        )
        return {
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "data": results
        }

    # --- Requirement 7: Other Necessary Interfaces ---
    def update_document(self, text: str, doc_id: str) -> List[str]:
        """
        Updates an existing document by deleting all its old chunks
        and adding the new ones.

        Args:
            text (str): The *new* full text of the document.
            doc_id (str): The unique identifier for the document.

        Returns:
            List[str]: A list of the new chunk_ids.
        """
        print(f"Updating document: {doc_id}...")
        # This is a robust "delete-then-add" strategy
        self.delete(doc_id=doc_id)
        return self.add_document(text, doc_id)

    def get_chunk_count(self) -> int:
        """Returns the total number of chunks in the collection."""
        return self.collection.count()

    def get_document_count(self) -> int:
        """
        Returns the total number of *unique documents* by
        counting unique 'original_doc_id' in metadata.

        Note: This can be slow on very large collections.
        """
        all_metadata = self.collection.get(include=["metadatas"])['metadatas']
        if not all_metadata:
            return 0
        unique_doc_ids = set(meta['original_doc_id'] for meta in all_metadata)
        return len(unique_doc_ids)


# ----------------------------------------------------------------------------------------------------------------------

def main():
    # --- 1. Initialization (Decoupled) ---

    DB_PATH = "./my_vector_db"
    COLLECTION_NAME = "multilingual_docs"
    # (Requirement) Use a multilingual model
    MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'

    print("Initializing components...")
    # Initialize the components to be injected
    client = chromadb.PersistentClient(path=DB_PATH)
    model = SentenceTransformer(MODEL_NAME)

    # Initialize the manager
    store = VectorStoreManager(
        chroma_client=client,
        collection_name=COLLECTION_NAME,
        embedding_model=model,
        chunk_size=200,  # Use small chunks for demo
        chunk_overlap=30
    )

    # --- 2. Define Sample Data ---
    doc_data = {
        "doc1": "Python is a high-level, general-purpose programming language. Its design philosophy emphasizes code readability with the use of significant indentation. It is dynamically-typed and garbage-collected.",
        "doc2": "A vector database is a database designed to store and search vector embeddings. These databases are specialized for performing efficient similarity searches, like k-nearest neighbor (k-NN) queries.",
        "doc3": "LangChain is a framework designed to simplify the creation of applications using large language models (LLMs). It provides modules for managing prompts, memory, and chains of components.",
        "doc4": "你好，世界！这是一个用于测试多语言支持的中文文档。向量数据库可以处理多种语言的文本，只要嵌入模型支持它们。",
        "doc5": "ChromaDB es una base de datos vectorial de código abierto. Facilita la creación de aplicaciones LLM al permitir almacenar y consultar embeddings de forma sencilla."
    }

    # Clear collection for a clean demo
    print(f"Clearing old collection '{COLLECTION_NAME}'...")
    client.delete_collection(name=COLLECTION_NAME)
    store = VectorStoreManager(client, COLLECTION_NAME, model, 200, 30)

    # --- 3. (Req 1 & 3) Add Documents ---
    print("\n--- Adding Documents ---")
    for doc_id, text in doc_data.items():
        chunk_ids = store.add_document(text, doc_id)
        print(f"Added {doc_id} with {len(chunk_ids)} chunks. Chunk IDs: {chunk_ids}")

    print(f"\nTotal Chunks: {store.get_chunk_count()}")
    print(f"Total Documents: {store.get_document_count()}")

    # --- 4. (Req 2) Independent Vectorization ---
    print("\n--- Independent Vectorization ---")
    query_vec = store.vectorize_text("What is Python?")
    print(f"Vector for 'What is Python?': {query_vec.shape} (dim={len(query_vec)})")

    # --- 5. (Req 4 & 5) Search ---
    print("\n--- Search (English Query) ---")
    query_en = "What is a vector database?"
    search_results = store.search(query_en, top_n=3)
    for res in search_results:
        print(f"  Doc ID: {res['doc_id']}, Score: {res['score']:.4f}")
        print(f"  Chunk: {res['chunk_text'][:50]}...")

    print("\n--- Search (Multilingual Query) ---")
    query_multi = "base de datos de vectores"  # Spanish for "vector database"
    search_results = store.search(query_multi, top_n=3)
    for res in search_results:
        print(f"  Doc ID: {res['doc_id']}, Score: {res['score']:.4f} (Matched from Spanish)")
        print(f"  Chunk: {res['chunk_text'][:50]}...")

    print("\n--- Search (Chinese Query) ---")
    query_cn = "什么是LLM？"  # Chinese for "What is LLM?"
    search_results = store.search(query_cn, top_n=3)
    for res in search_results:
        print(f"  Doc ID: {res['doc_id']}, Score: {res['score']:.4f} (Matched from Chinese)")
        print(f"  Chunk: {res['chunk_text'][:50]}...")

    print("\n--- Search with Score Threshold ---")
    search_results = store.search(query_en, top_n=5, score_threshold=0.6)
    print(f"Found {len(search_results)} results with score > 0.6")

    # --- 6. (Req 6) Delete ---
    print("\n--- Deleting Document ---")
    print(f"Chunks before delete: {store.get_chunk_count()}")
    store.delete(doc_id="doc1")  # Delete all of doc1 (Python)
    print(f"Chunks after deleting doc1: {store.get_chunk_count()}")

    # Verify deletion
    search_results = store.search("What is Python?", top_n=3)
    print(f"Search for 'Python' after delete: {search_results}")

    # --- 7. (Req 7) Browse ---
    print("\n--- Browsing Database (Pagination) ---")
    page_1 = store.browse(limit=3, offset=0)
    print(f"Total: {page_1['total_count']}, Limit: {page_1['limit']}, Offset: {page_1['offset']}")
    for i, item_id in enumerate(page_1['data']['ids']):
        print(f"  Item {i}: {item_id}")

    page_2 = store.browse(limit=3, offset=3)
    print(f"\nTotal: {page_2['total_count']}, Limit: {page_2['limit']}, Offset: {page_2['offset']}")
    for i, item_id in enumerate(page_2['data']['ids']):
        print(f"  Item {i + 3}: {item_id}")

    # --- 8. (Req 7) Update ---
    print("\n--- Updating Document ---")
    store.update_document("LangChain is an old framework.", "doc3")
    search_results = store.search("old framework", top_n=1)
    print("Search for 'old framework':")
    for res in search_results:
        print(f"  Doc ID: {res['doc_id']}, Chunk: {res['chunk_text']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e))
        print(traceback.format_exc())






