#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Vector Index Rebuild and Search Tool

This script connects to a MongoDB database, fetches data, and builds
two separate vector search indexes using VectorStoreManager:
1. 'intelligence_full_text': Indexes the 'APPENDIX.RAW_DATA' field.
2. 'intelligence_summary': Indexes a combination of 'EVENT_TITLE',
                             'EVENT_BRIEF', and 'EVENT_TEXT'.

It supports two modes:
  - 'rebuild': Deletes old indexes and rebuilds them from MongoDB.
  - 'search':  Provides an interactive CLI to search one or both indexes.

Usage:
  python rebuild_vector_index.py rebuild
  python rebuild_vector_index.py search
  python rebuild_vector_index.py rebuild search  (Rebuild, then start search)
"""

# --- Imports ---
import sys
import time
import argparse
import traceback
from pymongo import MongoClient
from typing import List, Dict, Any, Union, Optional
from Tools.VectorStoreManager import VectorStoreManager, ThreadedVectorStore

# pip install pymongo chromadb sentence-transformers langchain-text-splitters numpy tqdm


# --- Configuration (EDIT THESE VALUES) ---

MONGO_URI = "mongodb://localhost:27017/"  # Your MongoDB connection string
MONGO_DB_NAME = "IntelligenceIntegrationSystem"  # Your database name
MONGO_COLLECTION_NAME = "intelligence_archived"  # Your collection name

VECTOR_DB_PATH = "./vector_stores"  # Directory to store ChromaDB files
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'  # Multi-language model

# Collection names for the two vector stores
COLLECTION_FULL_TEXT = "intelligence_full_text"
COLLECTION_SUMMARY = "intelligence_summary"

# Search configuration
SEARCH_SCORE_THRESHOLD = 0.5  # Default similarity threshold (0.0 to 1.0)
SEARCH_TOP_N = 5


# --- Helper Functions ---

def wait_for_store_ready(store: ThreadedVectorStore, store_name: str) -> bool:
    """Polls the store until it is 'ready' or 'error'."""
    while True:
        status_info = store.get_status()
        if status_info['status'] == "ready":
            print(f"[Main]: Store '{store_name}' is ready.")
            return True

        if status_info['status'] == "error":
            print(f"[Main]: FATAL: Store '{store_name}' failed to load: {status_info['error']}")
            return False

        print(f"[Main]: Waiting for store '{store_name}' to initialize...")
        time.sleep(2)


def connect_to_mongo() -> Optional[MongoClient]:
    """Connects to MongoDB and returns the collection object."""
    try:
        client = MongoClient(MONGO_URI)
        client.server_info()  # Test connection
        db = client[MONGO_DB_NAME]
        collection = db[MONGO_COLLECTION_NAME]
        print(f"Successfully connected to MongoDB: {MONGO_DB_NAME}.{MONGO_COLLECTION_NAME}")
        return collection
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        return None


# --- Core Logic Functions ---

def func_rebuild(store_full_text: VectorStoreManager, store_summary: VectorStoreManager):
    """
    Fetches all data from MongoDB and rebuilds the vector indexes.
    """
    print("\n--- Starting Vector Index Rebuild ---")

    from tqdm import tqdm

    collection = connect_to_mongo()
    if collection is not None:
        return

    # Get total count for progress bar
    try:
        total_docs = collection.count_documents({})
    except Exception as e:
        print(f"Error counting documents: {e}")
        total_docs = 0

    if total_docs == 0:
        print("No documents found in MongoDB collection. Nothing to rebuild.")
        return

    print(f"Found {total_docs} documents to process.")

    # (Requirement) Process all documents with a progress bar
    processed_count = 0
    skipped_count = 0

    # Use tqdm for progress
    with tqdm(total=total_docs, desc="Rebuilding Indexes") as pbar:
        for doc in collection.find():
            try:
                # 1. Get the UUID (Key)
                uuid = doc.get('UUID')
                if not uuid:
                    skipped_count += 1
                    pbar.update(1)
                    continue

                # 2. Process 'intelligence_full_text'
                raw_data = doc.get('APPENDIX', {}).get('RAW_DATA')
                if raw_data:
                    # Robustly handle if RAW_DATA is dict or text
                    text_full = str(raw_data)
                    store_full_text.add_document(text_full, uuid)

                # 3. Process 'intelligence_summary'
                title = doc.get('EVENT_TITLE', '') or ''
                brief = doc.get('EVENT_BRIEF', '') or ''
                text = doc.get('EVENT_TEXT', '') or ''

                text_summary = f"{title}\n{brief}\n{text}".strip()

                if text_summary:
                    store_summary.add_document(text_summary, uuid)

                processed_count += 1

            except Exception as e:
                print(f"\nError processing doc {doc.get('UUID', 'N/A')}: {e}")
                skipped_count += 1

            finally:
                pbar.update(1)

    print("\n--- Rebuild Complete ---")
    print(f"Successfully processed: {processed_count}")
    print(f"Skipped (e.g., no UUID): {skipped_count}")
    print(f"Total chunks in '{COLLECTION_FULL_TEXT}': {store_full_text.count()}")
    print(f"Total chunks in '{COLLECTION_SUMMARY}': {store_summary.count()}")


def func_search(store_full_text: VectorStoreManager, store_summary: VectorStoreManager):
    """
    Starts an interactive search loop.
    """
    print("\n--- Starting Interactive Search (type 'q' to quit) ---")

    while True:
        query_text = input("\nEnter search query: ")
        if query_text.lower() == 'q':
            break

        mode = input("Search [f]ull text, [s]ummary, or [b]oth (intersection)? (f/s/b): ").lower()
        if mode == 'q':
            break

        results_full = []
        results_summary = []

        # Run searches based on mode
        if mode in ['f', 'b']:
            results_full = store_full_text.search(
                query_text,
                top_n=SEARCH_TOP_N,
                score_threshold=SEARCH_SCORE_THRESHOLD
            )

        if mode in ['s', 'b']:
            results_summary = store_summary.search(
                query_text,
                top_n=SEARCH_TOP_N,
                score_threshold=SEARCH_SCORE_THRESHOLD
            )

        # (Requirement) Process and compare UUIDs
        uuids_full = {res['doc_id'] for res in results_full}
        uuids_summary = {res['doc_id'] for res in results_summary}

        print("\n--- Search Results ---")

        if mode == 'f':
            print(f"Found {len(uuids_full)} matching UUIDs in FULL TEXT (threshold > {SEARCH_SCORE_THRESHOLD}):")
            for res in results_full:
                print(f"  - UUID: {res['doc_id']} (Score: {res['score']:.4f})")
                print(f"    Chunk: {res['chunk_text'][:80]}...")

        elif mode == 's':
            print(f"Found {len(uuids_summary)} matching UUIDs in SUMMARY (threshold > {SEARCH_SCORE_THRESHOLD}):")
            for res in results_summary:
                print(f"  - UUID: {res['doc_id']} (Score: {res['score']:.4f})")
                print(f"    Chunk: {res['chunk_text'][:80]}...")

        elif mode == 'b':
            intersection = uuids_full.intersection(uuids_summary)
            print(f"Found {len(intersection)} matching UUIDs in BOTH (Intersection):")
            print(intersection)

            print(f"\nDetails (Full Text Hits): {uuids_full}")
            print(f"Details (Summary Hits):   {uuids_summary}")

        else:
            print("Invalid mode. Please enter 'f', 's', or 'b'.")


# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description="Vector Index Rebuild and Search Tool")
    parser.add_argument(
        'actions',
        nargs='+',
        choices=['rebuild', 'search'],
        help="Action(s) to perform. 'rebuild' deletes and rebuilds the index. 'search' starts interactive search."
    )
    args = parser.parse_args()

    # --- Handle Rebuild Action (Pre-initialization) ---
    if 'rebuild' in args.actions:
        print("--- REBUILD ACTION REQUESTED ---")
        confirm = input(
            "ARE YOU SURE you want to rebuild? This will DELETE all existing data "
            f"in '{COLLECTION_FULL_TEXT}' and '{COLLECTION_SUMMARY}'. (type 'yes' to confirm): "
        )
        if confirm.lower() == 'yes':
            print("Proceeding with deletion...")
            try:
                # Initialize a temporary client just for deletion
                import chromadb
                temp_client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
                temp_client.delete_collection(name=COLLECTION_FULL_TEXT)
                print(f"Deleted old collection: {COLLECTION_FULL_TEXT}")
                temp_client.delete_collection(name=COLLECTION_SUMMARY)
                print(f"Deleted old collection: {COLLECTION_SUMMARY}")
            except Exception as e:
                print(f"Note: Could not delete collections (may not exist): {e}")
            print("Old collections cleared.")
        else:
            print("Rebuild cancelled.")
            # If only 'rebuild' was specified and cancelled, exit.
            if 'search' not in args.actions:
                sys.exit(0)

    # --- Initialize Stores (Non-blocking) ---
    # This happens for BOTH 'rebuild' and 'search'
    print("\nInitializing vector stores (non-blocking)...")
    store_full = ThreadedVectorStore(
        db_path=VECTOR_DB_PATH,
        collection_name=COLLECTION_FULL_TEXT,
        model_name=MODEL_NAME
    )

    store_summary = ThreadedVectorStore(
        db_path=VECTOR_DB_PATH,
        collection_name=COLLECTION_SUMMARY,
        model_name=MODEL_NAME,
        chunk_size=256  # Summaries are shorter, use smaller chunks
    )

    # --- Wait for Stores to be Ready ---
    print("Waiting for stores to finish loading...")
    ready_full = wait_for_store_ready(store_full, COLLECTION_FULL_TEXT)
    ready_summary = wait_for_store_ready(store_summary, COLLECTION_SUMMARY)

    if not (ready_full and ready_summary):
        print("One or more vector stores failed to initialize. Exiting.")
        sys.exit(1)

    print("All vector stores are ready.")

    # --- Route to Core Logic ---
    if 'rebuild' in args.actions:
        func_rebuild(store_full, store_summary)

    if 'search' in args.actions:
        func_search(store_full, store_summary)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e))
        print(traceback.format_exc())
