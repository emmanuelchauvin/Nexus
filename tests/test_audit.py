from datetime import datetime
from nexus.memory.interfaces import VectorDocument
from nexus.graph import create_nexus_graph

def test_audit_provenance_trail(memory, llm_client):
    """
    Test Case: Execution of a query relying on stored memory.
    Validation: Nexus must generate a clear, uncontradictory audit trail (provenance path)
    linking the decision back to the exact source documents and timestamps.
    """
    t = datetime(2026, 6, 1, 10, 0, 0)
    
    # Ingest fact with a specific PDF source
    memory.add_fact(
        node_id="gdp_growth",
        node_type="EconomicData",
        text="GDP growth is 2.5% in 2026.",
        timestamp=t,
        source="report_2026_q1.pdf"
    )
    
    # Set up mock responses for the LangGraph workflow:
    # 1. router classification -> "QUERY"
    # 2. diagnostic sufficiency -> JSON with score 1.0
    # 3. inference node final answer
    llm_client.mock_responses = [
        "QUERY",
        '{"sufficiency_score": 1.0, "reasoning": "We have exact GDP growth data.", "missing_knowledge": []}',
        "According to report_2026_q1.pdf, the GDP growth is 2.5% in 2026."
    ]
    
    graph = create_nexus_graph(memory, llm_client)
    
    initial_state = {
        "messages": [{"role": "user", "content": "What is the GDP growth for 2026?"}],
        "current_query": "What is the GDP growth for 2026?",
        "retrieved_context": "",
        "sufficiency_score": 1.0,
        "missing_knowledge_log": [],
        "audit_trail": [],
        "response": ""
    }
    
    final_state = graph.invoke(initial_state, config={"configurable": {"thread_id": "audit_thread"}})
    
    # Assert final answer is correct
    assert "2.5%" in final_state["response"]
    
    # Assert that the audit trail is generated
    audit = final_state["audit_trail"]
    assert len(audit) > 0
    
    # Verify that the audit trail details the source document name and node ID
    provenance_found = False
    for step in audit:
        if "report_2026_q1.pdf" in step and "gdp_growth" in step:
            provenance_found = True
            break
            
    assert provenance_found, f"Could not find document provenance in audit trail: {audit}"
