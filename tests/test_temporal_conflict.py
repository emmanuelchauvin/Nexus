from datetime import datetime, timedelta
from nexus.memory.hybrid import HybridMemory

def test_temporal_conflict_resolution(memory):
    """
    Test Case: Ingestion of fact A at T1, then contradictory fact A' at T2 (T2 > T1).
    Validation: Memory must use A', update vector indexing, and record the transition.
    """
    t1 = datetime(2026, 6, 1, 12, 0, 0)
    t2 = t1 + timedelta(hours=1)
    
    # Ingest A at T1
    res1 = memory.add_fact(
        node_id="target_company_president",
        node_type="President",
        text="The president of Company X is Alice.",
        timestamp=t1,
        source="doc_t1"
    )
    assert res1["status"] == "created"
    
    # Verify node creation
    node = memory.graph_store.get_node("target_company_president")
    assert node.properties["text"] == "The president of Company X is Alice."
    
    # Ingest A' (contradictory) at T2
    res2 = memory.add_fact(
        node_id="target_company_president",
        node_type="President",
        text="The president of Company X is Bob.",
        timestamp=t2,
        source="doc_t2"
    )
    assert res2["status"] == "updated"
    assert "updated" in res2["status"]
    
    # Verify node updated in GraphStore
    updated_node = memory.graph_store.get_node("target_company_president")
    assert updated_node.properties["text"] == "The president of Company X is Bob."
    assert updated_node.timestamp == t2
    
    # Verify vector search retrieves only the updated Bob fact
    search_res = memory.vector_store.search("president of Company X")
    assert len(search_res) == 1
    assert search_res[0].text == "The president of Company X is Bob."

def test_temporal_conflict_older_ignored(memory):
    """
    Test Case: Ingestion of fact A at T1, then a write request for contradictory fact A' at T2 (T2 < T1).
    Validation: Memory must ignore A', keeping A, and log the rejection.
    """
    t1 = datetime(2026, 6, 1, 12, 0, 0)
    t2 = t1 - timedelta(hours=1) # T2 is older!
    
    # Ingest newer fact A at T1
    memory.add_fact(
        node_id="target_company_president",
        node_type="President",
        text="The president of Company X is Alice.",
        timestamp=t1,
        source="doc_t1"
    )
    
    # Attempt to ingest older fact A' at T2
    res = memory.add_fact(
        node_id="target_company_president",
        node_type="President",
        text="The president of Company X is Bob.",
        timestamp=t2,
        source="doc_t2"
    )
    
    assert res["status"] == "ignored"
    assert "older" in res["audit"]
    
    # Verify node remains Alice
    node = memory.graph_store.get_node("target_company_president")
    assert node.properties["text"] == "The president of Company X is Alice."
