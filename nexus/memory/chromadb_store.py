import chromadb
from typing import List, Optional
from nexus.memory.interfaces import VectorStore, VectorDocument

class ChromaDBStore(VectorStore):
    def __init__(self, persist_directory: Optional[str] = None):
        """
        Initialize ChromaDBStore.
        If persist_directory is provided, uses a persistent SQLite client.
        Otherwise, uses an ephemeral in-memory client.
        """
        if persist_directory:
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            self.client = chromadb.EphemeralClient()
        
        # Get or create the unified memory collection
        self.collection = self.client.get_or_create_collection(
            name="nexus_memory"
        )

    def upsert(self, document: VectorDocument) -> None:
        """
        Upsert a document into the Chroma collection.
        If embedding is provided, it is stored. Otherwise, Chroma's
        default embedding function will generate it.
        """
        kwargs = {
            "ids": [document.id],
            "documents": [document.text],
            "metadatas": [document.metadata]
        }
        if document.embedding is not None:
            kwargs["embeddings"] = [document.embedding]
            
        self.collection.upsert(**kwargs)

    def search(self, query: str, limit: int = 5) -> List[VectorDocument]:
        """
        Query the collection for similar documents.
        """
        # Protect against empty database or requesting more items than exist
        count = self.collection.count()
        if count == 0:
            return []
        
        n_results = min(limit, count)
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        documents = []
        if results and results.get("ids") and len(results["ids"]) > 0:
            ids = results["ids"][0]
            texts = results["documents"][0]
            metadatas = results["metadatas"][0]
            embeddings = results.get("embeddings")
            embeddings_list = embeddings[0] if embeddings else [None] * len(ids)
            
            for i in range(len(ids)):
                documents.append(VectorDocument(
                    id=ids[i],
                    text=texts[i],
                    metadata=metadatas[i] or {},
                    embedding=embeddings_list[i]
                ))
        return documents

    def delete(self, document_id: str) -> None:
        """
        Delete a document by its ID.
        """
        self.collection.delete(ids=[document_id])

    def get_all(self) -> List[VectorDocument]:
        """
        Retrieve all documents currently stored in the Chroma collection.
        """
        results = self.collection.get(include=["documents", "metadatas", "embeddings"])
        documents = []
        if results and results.get("ids"):
            ids = results["ids"]
            texts = results.get("documents") or [""] * len(ids)
            metadatas = results.get("metadatas") or [{}] * len(ids)
            embeddings = results.get("embeddings")
            embeddings_list = embeddings if embeddings else [None] * len(ids)
            
            for i in range(len(ids)):
                documents.append(VectorDocument(
                     id=ids[i],
                     text=texts[i],
                     metadata=metadatas[i] or {},
                     embedding=embeddings_list[i]
                ))
        return documents

