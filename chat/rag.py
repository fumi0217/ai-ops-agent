"""
RAG search interface over indexed runbooks.

Uses ChromaDB (persistent) + sentence-transformers embeddings.
No LLM is involved here — returns raw document chunks for the agent to reason over.
"""

from pathlib import Path

from llama_index.core import VectorStoreIndex
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

CHROMA_PATH = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "runbooks"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 3

_index: VectorStoreIndex | None = None


def _get_index() -> VectorStoreIndex:
    global _index
    if _index is not None:
        return _index

    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
    Settings.llm = None

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    _index = VectorStoreIndex.from_vector_store(vector_store)
    return _index


def search_runbook(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Search runbooks by semantic similarity.
    Returns a list of {title, content, score} dicts.
    """
    index = _get_index()
    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(query)

    results = []
    for node in nodes:
        source = Path(node.metadata.get("file_path", "unknown")).name
        results.append({
            "source": source,
            "score": round(node.score or 0.0, 4),
            "content": node.get_content()[:1000],  # cap at 1000 chars per chunk
        })
    return results
