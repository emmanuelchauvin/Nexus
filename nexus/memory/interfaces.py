from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class EntityNode(BaseModel):
    id: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class RelationEdge(BaseModel):
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class VectorDocument(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None

class GraphStore(ABC):
    @abstractmethod
    def add_node(self, node: EntityNode) -> None:
        """Add or update a node in the graph."""
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[EntityNode]:
        """Retrieve a specific node by its ID."""
        pass

    @abstractmethod
    def add_edge(self, edge: RelationEdge) -> None:
        """Add or update an edge between two nodes."""
        pass

    @abstractmethod
    def get_edges(self, node_id: str) -> List[RelationEdge]:
        """Get all edges connected to a node (incoming and/or outgoing)."""
        pass

    @abstractmethod
    def delete_node(self, node_id: str) -> None:
        """Delete a node and its associated edges."""
        pass

    @abstractmethod
    def list_nodes(self) -> List[EntityNode]:
        """List all nodes in the store."""
        pass

    @abstractmethod
    def list_edges(self) -> List[RelationEdge]:
        """List all edges in the store."""
        pass

class VectorStore(ABC):
    @abstractmethod
    def upsert(self, document: VectorDocument) -> None:
        """Upsert a document text and metadata into the vector database."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> List[VectorDocument]:
        """Perform semantic search and return matched documents."""
        pass

    @abstractmethod
    def delete(self, document_id: str) -> None:
        """Delete a document by its unique ID."""
        pass

    @abstractmethod
    def get_all(self) -> List[VectorDocument]:
        """Retrieve all documents currently stored in the vector database."""
        pass

