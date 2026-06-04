import networkx as nx
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os
from nexus.memory.interfaces import GraphStore, EntityNode, RelationEdge

class NetworkXGraphStore(GraphStore):
    def __init__(self, filepath: Optional[str] = None):
        """
        Initialize NetworkXGraphStore.
        If filepath is provided, automatically loads and saves the graph as JSON.
        """
        self.graph = nx.DiGraph()
        self.filepath = filepath
        if filepath and os.path.exists(filepath):
            self.load_from_file(filepath)

    def add_node(self, node: EntityNode) -> None:
        """Add or update a node in the graph, and save state."""
        self.graph.add_node(
            node.id,
            type=node.type,
            properties=node.properties,
            timestamp=node.timestamp.isoformat()
        )
        if self.filepath:
            self.save_to_file(self.filepath)

    def get_node(self, node_id: str) -> Optional[EntityNode]:
        """Retrieve node details if it exists."""
        if not self.graph.has_node(node_id):
            return None
        data = self.graph.nodes[node_id]
        return EntityNode(
            id=node_id,
            type=data.get("type", "Unknown"),
            properties=data.get("properties", {}),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat()))
        )

    def add_edge(self, edge: RelationEdge) -> None:
        """Add or update an edge between two nodes, creating missing nodes as shells."""
        # Ensure endpoints exist
        if not self.graph.has_node(edge.source):
            self.graph.add_node(
                edge.source,
                type="Unknown",
                properties={},
                timestamp=edge.timestamp.isoformat()
            )
        if not self.graph.has_node(edge.target):
            self.graph.add_node(
                edge.target,
                type="Unknown",
                properties={},
                timestamp=edge.timestamp.isoformat()
            )
            
        self.graph.add_edge(
            edge.source,
            edge.target,
            type=edge.type,
            properties=edge.properties,
            timestamp=edge.timestamp.isoformat()
        )
        if self.filepath:
            self.save_to_file(self.filepath)

    def get_edges(self, node_id: str) -> List[RelationEdge]:
        """Get all edges connected to a node (incoming and outgoing)."""
        edges = []
        if not self.graph.has_node(node_id):
            return edges
            
        # Outgoing edges
        for target in self.graph.successors(node_id):
            data = self.graph.edges[node_id, target]
            edges.append(RelationEdge(
                source=node_id,
                target=target,
                type=data.get("type", "Unknown"),
                properties=data.get("properties", {}),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat()))
            ))
            
        # Incoming edges
        for source in self.graph.predecessors(node_id):
            data = self.graph.edges[source, node_id]
            edges.append(RelationEdge(
                source=source,
                target=node_id,
                type=data.get("type", "Unknown"),
                properties=data.get("properties", {}),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat()))
            ))
        return edges

    def delete_node(self, node_id: str) -> None:
        """Delete a node and all incoming/outgoing edges."""
        if self.graph.has_node(node_id):
            self.graph.remove_node(node_id)
            if self.filepath:
                self.save_to_file(self.filepath)

    def list_nodes(self) -> List[EntityNode]:
        """List all nodes currently in the graph."""
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            nodes.append(EntityNode(
                id=node_id,
                type=data.get("type", "Unknown"),
                properties=data.get("properties", {}),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat()))
            ))
        return nodes

    def list_edges(self) -> List[RelationEdge]:
        """List all edges currently in the graph."""
        edges = []
        for source, target, data in self.graph.edges(data=True):
            edges.append(RelationEdge(
                source=source,
                target=target,
                type=data.get("type", "Unknown"),
                properties=data.get("properties", {}),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat()))
            ))
        return edges

    def save_to_file(self, filepath: str) -> None:
        """Serialize the current graph to a JSON file."""
        data = {
            "nodes": [
                {
                    "id": node_id,
                    "type": attrs.get("type"),
                    "properties": attrs.get("properties"),
                    "timestamp": attrs.get("timestamp")
                }
                for node_id, attrs in self.graph.nodes(data=True)
            ],
            "edges": [
                {
                    "source": u,
                    "target": v,
                    "type": attrs.get("type"),
                    "properties": attrs.get("properties"),
                    "timestamp": attrs.get("timestamp")
                }
                for u, v, attrs in self.graph.edges(data=True)
            ]
        }
        # Ensure containing directory exists
        if os.path.dirname(filepath):
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_file(self, filepath: str) -> None:
        """Restore graph state from a JSON file."""
        if not os.path.exists(filepath):
            return
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.graph.clear()
        for node in data.get("nodes", []):
            self.graph.add_node(
                node["id"],
                type=node.get("type", "Unknown"),
                properties=node.get("properties", {}),
                timestamp=node.get("timestamp", datetime.utcnow().isoformat())
            )
        for edge in data.get("edges", []):
            self.graph.add_edge(
                edge["source"],
                edge["target"],
                type=edge.get("type", "Unknown"),
                properties=edge.get("properties", {}),
                timestamp=edge.get("timestamp", datetime.utcnow().isoformat())
            )
