from datetime import datetime, timedelta
from nexus.loops.oubli import OubliLoop

def test_memory_saturation_and_lru_cleanup(memory):
    """
    Test Case: Saturation of memory by massive document ingestion.
    Validation: Verify that when memory limits are exceeded, the Oubli Loop enforces the LRU policy,
    removing older/unaccessed items from both the GraphStore and VectorStore, preserving
    only the capped maximum nodes.
    """
    oubli = OubliLoop(memory)
    
    # 1. Ingest 20 facts sequentially
    base_time = datetime(2026, 6, 1, 10, 0, 0)
    for i in range(20):
        memory.add_fact(
            node_id=f"fact_{i}",
            node_type="FactualStatement",
            text=f"Factual statement number {i}.",
            timestamp=base_time + timedelta(minutes=i),
            source="resilience_suite"
        )
        
    # Verify we have 20 nodes
    nodes = memory.graph_store.list_nodes()
    assert len(nodes) == 20
    
    # 2. Simulate reading fact_5 and fact_6 to increase their access count
    # retrieve() with limit=1 to only target and increment the specific facts
    memory.retrieve("statement number 5", limit=1)
    memory.retrieve("statement number 6", limit=1)
    
    # 3. Enforce LRU forgetting rule with a limit of 5 nodes
    res = oubli.enforce_lru(max_nodes=5)
    
    assert res["status"] == "success"
    assert len(res["deleted_nodes"]) == 15
    
    # Verify that only 5 nodes remain in GraphStore
    remaining_nodes = memory.graph_store.list_nodes()
    assert len(remaining_nodes) == 5
    
    remaining_ids = [n.id for n in remaining_nodes]
    
    # fact_5 and fact_6 MUST be preserved because of access count > 0
    assert "fact_5" in remaining_ids
    assert "fact_6" in remaining_ids
    
    # 4. Verify that deleted nodes are also removed from ChromaDB VectorStore
    for i in range(20):
        node_id = f"fact_{i}"
        if node_id not in remaining_ids:
            search_res = memory.vector_store.search(f"statement number {i}", limit=1)
            if search_res:
                assert search_res[0].id != node_id
