from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from nexus.memory.interfaces import GraphStore, VectorStore, EntityNode, RelationEdge, VectorDocument

class HybridMemory:
    def __init__(self, graph_store: GraphStore, vector_store: VectorStore):
        """
        Initialize the HybridMemory coordinator by injecting a GraphStore and a VectorStore.
        """
        self.graph_store = graph_store
        self.vector_store = vector_store

    def add_fact(
        self,
        node_id: str,
        node_type: str,
        text: str,
        properties: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingest a fact. Performs temporal arbitration:
        - If the node doesn't exist, it is created.
        - If it exists, the update is accepted only if the new timestamp >= existing timestamp.
        Returns a dict with 'status' ("created", "updated", or "ignored") and an 'audit' message.
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        if properties is None:
            properties = {}

        # Save metadata fields in node properties
        properties["text"] = text
        if source:
            properties["source"] = source

        existing = self.graph_store.get_node(node_id)

        if existing:
            # Temporal arbitration check
            if timestamp >= existing.timestamp:
                # Prepare updated node
                updated_node = EntityNode(
                    id=node_id,
                    type=node_type,
                    properties=properties,
                    timestamp=timestamp
                )
                self.graph_store.add_node(updated_node)

                # Upsert to Vector Store
                doc = VectorDocument(
                    id=node_id,
                    text=text,
                    metadata={
                        "type": node_type,
                        "timestamp": timestamp.isoformat(),
                        "source": source or "unknown"
                    }
                )
                self.vector_store.upsert(doc)

                audit_msg = (
                    f"Updated node '{node_id}' with newer information "
                    f"(T={timestamp.isoformat()}, previous T={existing.timestamp.isoformat()}). "
                    f"Source: {source or 'unknown'}."
                )
                return {"status": "updated", "audit": audit_msg}
            else:
                audit_msg = (
                    f"Ignored update for node '{node_id}' because incoming information "
                    f"(T={timestamp.isoformat()}) is older than existing information "
                    f"(T={existing.timestamp.isoformat()})."
                )
                return {"status": "ignored", "audit": audit_msg}
        else:
            # Create a brand new node
            new_node = EntityNode(
                id=node_id,
                type=node_type,
                properties=properties,
                timestamp=timestamp
            )
            self.graph_store.add_node(new_node)

            # Insert into Vector Store
            doc = VectorDocument(
                id=node_id,
                text=text,
                metadata={
                    "type": node_type,
                    "timestamp": timestamp.isoformat(),
                    "source": source or "unknown"
                }
            )
            self.vector_store.upsert(doc)

            audit_msg = f"Created new node '{node_id}' (T={timestamp.isoformat()}). Source: {source or 'unknown'}."
            return {"status": "created", "audit": audit_msg}

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Add a relationship edge between two nodes in the graph store.
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        if properties is None:
            properties = {}

        edge = RelationEdge(
            source=source_id,
            target=target_id,
            type=rel_type,
            properties=properties,
            timestamp=timestamp
        )
        self.graph_store.add_edge(edge)

    def retrieve(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """
        Retrieve context hybridly:
        1. Find similar documents in Vector Store.
        2. Expand them to a local subgraph in Graph Store (direct relations).
        3. Formulate a clean textual context, listing of retrieved items, and an audit trail.
        """
        # Vector search
        matched_docs = self.vector_store.search(query, limit=limit)
        
        retrieved_nodes: Dict[str, EntityNode] = {}
        retrieved_edges: List[RelationEdge] = []
        audit_trail: List[str] = []

        # Step 1: Fetch nodes from vector results
        for doc in matched_docs:
            node = self.graph_store.get_node(doc.id)
            if node:
                # Update access count and timestamp for LRU policy
                node.properties["access_count"] = node.properties.get("access_count", 0) + 1
                node.properties["last_accessed"] = datetime.utcnow().isoformat()
                self.graph_store.add_node(node)
                
                retrieved_nodes[node.id] = node
                audit_trail.append(
                    f"[Provenance] Semantic match: Node '{node.id}' retrieved via vector search. "
                    f"Ingested: {node.timestamp.isoformat()} from source '{node.properties.get('source', 'unknown')}'."
                )

        # Step 2: Fetch adjacent edges and endpoints to complete the local subgraph context
        seed_ids = list(retrieved_nodes.keys())
        for seed_id in seed_ids:
            edges = self.graph_store.get_edges(seed_id)
            for edge in edges:
                # Add edge
                retrieved_edges.append(edge)
                audit_trail.append(
                    f"[Provenance] Subgraph expansion: Relationship '{edge.source} --({edge.type})--> {edge.target}' "
                    f"retrieved as context neighbor of '{seed_id}'."
                )
                
                # Fetch missing endpoints
                for endpoint_id in (edge.source, edge.target):
                    if endpoint_id not in retrieved_nodes:
                        node = self.graph_store.get_node(endpoint_id)
                        if node:
                            # Update access count and timestamp for LRU policy
                            node.properties["access_count"] = node.properties.get("access_count", 0) + 1
                            node.properties["last_accessed"] = datetime.utcnow().isoformat()
                            self.graph_store.add_node(node)
                            
                            retrieved_nodes[endpoint_id] = node
                            audit_trail.append(
                                f"[Provenance] Subgraph expansion: Node '{node.id}' retrieved as connected endpoint. "
                                f"Ingested: {node.timestamp.isoformat()}."
                            )

        # Step 3: Format standard textual context
        context_blocks = []
        context_blocks.append("=== RETRIEVED FACTS ===")
        for nid, node in retrieved_nodes.items():
            text_val = node.properties.get("text", "")
            prop_str = ", ".join(f"{k}: {v}" for k, v in node.properties.items() if k not in ("text", "source", "access_count", "last_accessed"))
            prop_part = f" ({prop_str})" if prop_str else ""
            src = node.properties.get("source", "unknown")
            context_blocks.append(
                f"- [{node.type}] {nid}: {text_val}{prop_part} [Source: {src}, Time: {node.timestamp.isoformat()}]"
            )

        if retrieved_edges:
            context_blocks.append("\n=== RETRIEVED CONNECTIONS ===")
            for edge in retrieved_edges:
                prop_str = ", ".join(f"{k}: {v}" for k, v in edge.properties.items())
                prop_part = f" ({prop_str})" if prop_str else ""
                context_blocks.append(
                    f"- {edge.source} --({edge.type})--> {edge.target}{prop_part} [Time: {edge.timestamp.isoformat()}]"
                )

        context_text = "\n".join(context_blocks)

        return {
            "context_text": context_text,
            "nodes": list(retrieved_nodes.values()),
            "edges": retrieved_edges,
            "audit_trail": audit_trail
        }
