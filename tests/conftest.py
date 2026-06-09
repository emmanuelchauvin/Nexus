import pytest
from datetime import datetime
from typing import List, Dict, Any, Optional
from nexus.memory.interfaces import VectorStore, VectorDocument
from nexus.memory.networkx_store import NetworkXGraphStore
from nexus.memory.hybrid import HybridMemory
from nexus.llm.client import LLMClient
from nexus.graph import create_nexus_graph

class InMemoryVectorStore(VectorStore):
    """
    A lightweight, deterministic in-memory vector store for unit testing.
    Uses basic keyword overlap to avoid the overhead/latency of local embedding models.
    """
    def __init__(self):
        self.documents = {}

    def upsert(self, document: VectorDocument) -> None:
        self.documents[document.id] = document

    def search(self, query: str, limit: int = 5) -> List[VectorDocument]:
        # Split query into clean words
        query_words = [w.lower() for w in query.replace(".", "").replace(",", "").split() if w]
        
        matches = []
        for doc in self.documents.values():
            doc_text_lower = doc.text.lower()
            # Split document text into clean words for exact boundary matching
            doc_words = [w.strip(".,!?()\"'") for w in doc_text_lower.split() if w]
            score = sum(1 for word in query_words if word in doc_words)
            if score > 0 or not query_words:
                matches.append((score, doc))
        
        # Sort by score descending, then by document id to ensure determinism
        matches.sort(key=lambda x: (-x[0], x[1].id))
        
        # If no query overlap matches, return top documents sorted by ID
        if not matches:
            all_docs = list(self.documents.values())
            all_docs.sort(key=lambda d: d.id)
            return all_docs[:limit]
            
        return [doc for score, doc in matches[:limit]]

    def delete(self, document_id: str) -> None:
        if document_id in self.documents:
            del self.documents[document_id]

    def get_all(self) -> List[VectorDocument]:
        return list(self.documents.values())

@pytest.fixture
def graph_store():
    """Returns an ephemeral, in-memory NetworkX GraphStore."""
    return NetworkXGraphStore(filepath=None)

@pytest.fixture
def vector_store():
    """Returns the custom InMemoryVectorStore fixture."""
    return InMemoryVectorStore()

@pytest.fixture
def memory(graph_store, vector_store, llm_client):
    """Returns a HybridMemory coordinator using in-memory stores."""
    mem = HybridMemory(graph_store=graph_store, vector_store=vector_store)
    mem.llm_client = llm_client
    return mem


@pytest.fixture
def llm_client():
    """Returns a mock LLM client initialized in mock mode."""
    return LLMClient(mock=True)
