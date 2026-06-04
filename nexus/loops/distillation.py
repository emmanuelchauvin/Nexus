from typing import List, Dict, Any
import json
from datetime import datetime
from nexus.memory.hybrid import HybridMemory
from nexus.llm.client import LLMClient
from nexus.memory.interfaces import EntityNode, RelationEdge, VectorDocument

class DistillationLoop:
    def __init__(self, memory: HybridMemory, llm_client: LLMClient):
        """
        Initialize the Distillation Loop with injected HybridMemory and LLMClient.
        """
        self.memory = memory
        self.llm_client = llm_client

    def run_distillation(self) -> Dict[str, Any]:
        """
        Runs a distillation cycle:
        1. Lists all facts (nodes and relationships) in the memory.
        2. Prompts the LLM to identify redundancies, connections, duplicates, or general invariants.
        3. Applies the merges/links back to HybridMemory.
        """
        nodes = self.memory.graph_store.list_nodes()
        edges = self.memory.graph_store.list_edges()
        
        if not nodes:
            return {"status": "skipped", "message": "No memory nodes to distill."}

        # Format graph data for LLM ingestion
        nodes_info = "\n".join([
            f"- Node ID: {n.id} ({n.type}) | Fact: {n.properties.get('text', '')}" 
            for n in nodes
        ])
        edges_info = "\n".join([
            f"- {e.source} --({e.type})--> {e.target}" 
            for e in edges
        ])
        
        prompt = [
            {
                "role": "system",
                "content": (
                    "You are the Distillation Loop of the Nexus Memory System.\n"
                    "Your role is cognitive hygiene. Analyze the current knowledge graph, and look for:\n"
                    "1. Entity Resolution (Synonyms): Identify distinct nodes that refer to the same physical entity or concept (e.g., 'Acme Inc' and 'Société Acme', or 'john_d' and 'john_doe') and recommend merging them.\n"
                    "2. Redundancies: Similar facts or duplicated details that should be consolidated.\n"
                    "3. Semantic Connections: New relation links that should connect existing facts.\n"
                    "4. Invariants/Summaries: Condensing complex multiple facts into a single consolidated node.\n\n"
                    "Respond strictly with a JSON object format:\n"
                    "{\n"
                    '  "merges": [\n'
                    '     {"source_id": "node_to_delete", "target_id": "node_to_keep", "reason": "why they are merged"}\n'
                    '  ],\n'
                    '  "new_edges": [\n'
                    '     {"source": "node_a", "target": "node_b", "type": "REL_TYPE", "properties": {}}\n'
                    '  ]\n'
                    "}"
                )
            },
            {
                "role": "user",
                "content": f"Current Graph Nodes:\n{nodes_info}\n\nCurrent Connections:\n{edges_info}"
            }
        ]

        try:
            raw_json = self.llm_client.generate(prompt, max_tokens=3000)
            json_str = raw_json.strip()
            if json_str.startswith("```"):
                lines = json_str.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    lines = lines[1:-1]
                json_str = "\n".join(lines).strip()

            data = json.loads(json_str)
            merges = data.get("merges", [])
            new_edges = data.get("new_edges", [])
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Failed to parse distillation recommendations JSON: {str(e)}"
            }

        audit_log = []
        
        # Apply Node Merges
        for m in merges:
            src = m.get("source_id")
            tgt = m.get("target_id")
            reason = m.get("reason", "No reason provided")
            
            src_node = self.memory.graph_store.get_node(src)
            tgt_node = self.memory.graph_store.get_node(tgt)
            
            if src_node and tgt_node:
                # Merge texts to maintain facts
                merged_text = tgt_node.properties.get("text", "")
                src_text = src_node.properties.get("text", "")
                if src_text and src_text not in merged_text:
                    merged_text += " " + src_text
                
                # Merge properties dictionaries
                for k, v in src_node.properties.items():
                    if k == "text":
                        continue
                    if k not in tgt_node.properties:
                        tgt_node.properties[k] = v
                
                tgt_node.properties["text"] = merged_text
                
                # Adopt the most recent timestamp
                new_timestamp = max(tgt_node.timestamp, src_node.timestamp)
                tgt_node.timestamp = new_timestamp
                
                # Update target node in stores
                self.memory.graph_store.add_node(tgt_node)
                
                # Re-route edges connected to src
                src_edges = self.memory.graph_store.get_edges(src)
                for edge in src_edges:
                    # Skip edges that would become self-loops on the target node
                    if (edge.source == src and edge.target == tgt) or (edge.source == tgt and edge.target == src):
                        continue
                    
                    if edge.source == src:
                        self.memory.add_relationship(
                            tgt, edge.target, edge.type, edge.properties, edge.timestamp
                        )
                    if edge.target == src:
                        self.memory.add_relationship(
                            edge.source, tgt, edge.type, edge.properties, edge.timestamp
                        )
                
                # Delete source node
                self.memory.graph_store.delete_node(src)
                self.memory.vector_store.delete(src)
                
                # Re-index target node in vector db
                tgt_doc = VectorDocument(
                    id=tgt,
                    text=merged_text,
                    metadata=tgt_node.properties
                )
                self.memory.vector_store.upsert(tgt_doc)
                
                audit_log.append(f"Merged node '{src}' into '{tgt}' (Reason: {reason})")

        # Apply New Edges
        for edge_data in new_edges:
            src = edge_data.get("source")
            tgt = edge_data.get("target")
            etype = edge_data.get("type", "CONNECTED_TO")
            props = edge_data.get("properties", {})
            
            if self.memory.graph_store.get_node(src) and self.memory.graph_store.get_node(tgt):
                self.memory.add_relationship(src, tgt, etype, props)
                audit_log.append(
                    f"Created semantic link '{src}' --({etype})--> '{tgt}' during distillation."
                )

        return {
            "status": "success",
            "merges_executed": len(merges),
            "edges_added": len(new_edges),
            "audit_log": audit_log
        }
