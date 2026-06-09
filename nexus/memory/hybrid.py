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
                metadata = {
                    "type": node_type,
                    "timestamp": timestamp.isoformat(),
                    "source": source or "unknown"
                }
                for field in ("source_doc", "section_hierarchy", "effective_date", "expiration_date", "confidence_score", "last_accessed"):
                    if properties and field in properties:
                        metadata[field] = properties[field]

                doc = VectorDocument(
                    id=node_id,
                    text=text,
                    metadata=metadata
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
            metadata = {
                "type": node_type,
                "timestamp": timestamp.isoformat(),
                "source": source or "unknown"
            }
            for field in ("source_doc", "section_hierarchy", "effective_date", "expiration_date", "confidence_score", "last_accessed"):
                if properties and field in properties:
                    metadata[field] = properties[field]

            doc = VectorDocument(
                id=node_id,
                text=text,
                metadata=metadata
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
        1. Find similar documents using Hybrid Search (ChromaDB + BM25) and RRF fusion.
        2. Rerank candidates using LLM client.
        3. Expand them to a local subgraph in Graph Store (direct relations).
        4. Formulate a clean textual context, listing of retrieved items, and an audit trail.
        """
        # Step 1: Hybrid Search (Dense + BM25)
        # Fetch dense candidates
        dense_results = self.vector_store.search(query, limit=limit * 2)
        dense_ranking = [doc.id for doc in dense_results]

        # Fetch all docs to run BM25
        sparse_ranking = []
        try:
            all_docs = self.vector_store.get_all()
        except Exception:
            all_docs = []
            
        doc_map = {doc.id: doc for doc in all_docs}
        
        # Backpopulate doc_map with dense results if get_all didn't return them for some reason
        for doc in dense_results:
            if doc.id not in doc_map:
                doc_map[doc.id] = doc

        if all_docs:
            try:
                from rank_bm25 import BM25Okapi
                def clean_tokenize(t: str) -> List[str]:
                    lowered = t.lower()
                    for p in ".,!?()\"';:-":
                        lowered = lowered.replace(p, " ")
                    return [w for w in lowered.split() if w]
                    
                tokenized_corpus = [clean_tokenize(doc.text) for doc in all_docs]
                bm25 = BM25Okapi(tokenized_corpus)
                tokenized_query = clean_tokenize(query)
                scores = bm25.get_scores(tokenized_query)
                
                scored_docs = []
                for doc, score in zip(all_docs, scores):
                    if score > 0:
                        scored_docs.append((score, doc.id))
                scored_docs.sort(key=lambda x: -x[0])
                sparse_ranking = [doc_id for _, doc_id in scored_docs]
            except Exception as e:
                # Fallback if BM25 setup fails
                sparse_ranking = []

        # Reciprocal Rank Fusion (RRF)
        rrf_scores = {}
        for rank, doc_id in enumerate(dense_ranking):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (60.0 + (rank + 1))
        for rank, doc_id in enumerate(sparse_ranking):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (60.0 + (rank + 1))

        # Sort candidate doc IDs by RRF score descending
        sorted_doc_ids = sorted(rrf_scores.keys(), key=lambda x: -rrf_scores[x])
        candidate_docs = [doc_map[doc_id] for doc_id in sorted_doc_ids if doc_id in doc_map]

        # Step 2: LLM Reranking (if llm_client is available)
        reranked_docs = candidate_docs
        used_llm_rerank = False
        if hasattr(self, "llm_client") and self.llm_client and len(candidate_docs) > 1:
            candidates_str = ""
            for idx, doc in enumerate(candidate_docs[:limit * 2]):
                candidates_str += f"[{idx}] (ID: {doc.id})\nContent: {doc.text}\n---\n"
            
            prompt = [
                {
                    "role": "system",
                    "content": (
                        "You are an advanced retrieval reranker.\n"
                        "Given a user query and a list of candidate documents, select and rank the most relevant documents "
                        "that directly help answer the query. Return ONLY a JSON object containing the ranked indices in order of relevance.\n"
                        "Ensure the most relevant documents are at the front of the list.\n\n"
                        "JSON format schema:\n"
                        "{\n"
                        '  "ranked_indices": [integer, integer, ...]\n'
                        "}"
                    )
                },
                {
                    "role": "user",
                    "content": f"User Query: {query}\n\nCandidate Documents:\n{candidates_str}"
                }
            ]
            try:
                raw_resp = self.llm_client.generate(prompt, max_tokens=1000, response_format={"type": "json_object"})
                import json
                data = json.loads(raw_resp)
                ranked_indices = data.get("ranked_indices", [])
                
                ordered_docs = []
                seen_indices = set()
                for idx in ranked_indices:
                    if isinstance(idx, int) and 0 <= idx < len(candidate_docs) and idx not in seen_indices:
                        ordered_docs.append(candidate_docs[idx])
                        seen_indices.add(idx)
                
                # Append any remaining candidates that were not ranked by LLM
                for idx, doc in enumerate(candidate_docs):
                    if idx not in seen_indices:
                        ordered_docs.append(doc)
                        
                reranked_docs = ordered_docs
                used_llm_rerank = True
            except Exception:
                pass

        matched_docs = reranked_docs[:limit]
        
        retrieved_nodes: Dict[str, EntityNode] = {}
        retrieved_edges: List[RelationEdge] = []
        audit_trail: List[str] = []

        # Step 3: Fetch nodes from matched results
        for doc in matched_docs:
            node = self.graph_store.get_node(doc.id)
            if node:
                # Update access count and timestamp for LRU policy
                node.properties["access_count"] = node.properties.get("access_count", 0) + 1
                node.properties["last_accessed"] = datetime.utcnow().isoformat()
                self.graph_store.add_node(node)
                
                retrieved_nodes[node.id] = node
                rerank_prefix = "LLM Reranked " if used_llm_rerank else ""
                audit_trail.append(
                    f"[Provenance] Semantic match: Node '{node.id}' retrieved via {rerank_prefix}Hybrid Search. "
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
