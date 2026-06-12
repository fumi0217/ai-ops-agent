"""
Index runbooks into ChromaDB for RAG search.

Run once (or re-run to rebuild):
    python -m scripts.index_runbooks
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Settings
import chromadb

load_dotenv()

RUNBOOKS_DIR = Path(__file__).parent.parent / "runbooks"
CHROMA_PATH = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "runbooks"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def build_index() -> None:
    print(f"Loading runbooks from {RUNBOOKS_DIR} ...")
    docs = SimpleDirectoryReader(str(RUNBOOKS_DIR)).load_data()
    print(f"  {len(docs)} documents loaded")

    print(f"Setting up embedding model: {EMBED_MODEL}")
    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
    Settings.llm = None  # RAG only — no LLM needed here

    print(f"Setting up ChromaDB at {CHROMA_PATH} ...")
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    # Drop and recreate to ensure a clean index
    client.delete_collection(COLLECTION_NAME) if COLLECTION_NAME in [c.name for c in client.list_collections()] else None
    collection = client.get_or_create_collection(COLLECTION_NAME)

    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    print("Building vector index ...")
    VectorStoreIndex.from_documents(docs, storage_context=storage_context)
    print(f"Done. {len(docs)} runbooks indexed into ChromaDB.")


if __name__ == "__main__":
    build_index()
