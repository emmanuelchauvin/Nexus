from typing import Dict, Any, List
from datetime import datetime, timedelta
from nexus.memory.hybrid import HybridMemory

class OubliLoop:
    def __init__(self, memory: HybridMemory):
        """
        Initialize the Oubli (Forgetting) Loop with injected HybridMemory.
        """
        self.memory = memory

    def enforce_lru(self, max_nodes: int) -> Dict[str, Any]:
        """
        Enforce Least Recently Used (LRU) policy.
        If the number of nodes in the graph store exceeds max_nodes,
        deletes the nodes with the lowest access_count and oldest timestamps.
        """
        nodes = self.memory.graph_store.list_nodes()
        if len(nodes) <= max_nodes:
            return {
                "status": "skipped", 
                "message": f"Graph size ({len(nodes)}) is within limit ({max_nodes})."
            }

        # Sort nodes by access_count (ascending), then by timestamp (ascending)
        # to ensure less accessed and older nodes are deleted first.
        sorted_nodes = sorted(
            nodes,
            key=lambda n: (n.properties.get("access_count", 0), n.timestamp)
        )

        num_to_delete = len(nodes) - max_nodes
        deleted_ids = []
        
        for i in range(num_to_delete):
            node_to_delete = sorted_nodes[i]
            self.memory.graph_store.delete_node(node_to_delete.id)
            self.memory.vector_store.delete(node_to_delete.id)
            deleted_ids.append(node_to_delete.id)

        return {
            "status": "success",
            "deleted_nodes": deleted_ids,
            "message": f"Deleted {len(deleted_ids)} nodes to enforce max limit of {max_nodes}."
        }

    def enforce_temporal_decay(self, max_age_days: int) -> Dict[str, Any]:
        """
        Enforce temporal obsolescence.
        Deletes nodes older than max_age_days.
        """
        nodes = self.memory.graph_store.list_nodes()
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        
        deleted_ids = []
        for node in nodes:
            if node.timestamp < cutoff_date:
                self.memory.graph_store.delete_node(node.id)
                self.memory.vector_store.delete(node.id)
                deleted_ids.append(node.id)

        if not deleted_ids:
            return {
                "status": "skipped", 
                "message": "No nodes exceeded maximum age cutoff."
            }

        return {
            "status": "success",
            "deleted_nodes": deleted_ids,
            "message": f"Deleted {len(deleted_ids)} nodes older than {max_age_days} days."
        }
