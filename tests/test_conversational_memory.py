import pytest
from datetime import datetime
from nexus.graph import create_nexus_graph
from nexus.state import AgentState

def test_conversational_memory_simple_ingestion(memory, llm_client):
    """
    Test Case: User says a simple fact (e.g. "My favorite color is blue").
    Validation: Fact is silently saved immediately; response is clean.
    """
    # LLM responses:
    # 1. router_node -> QUERY
    # 2. diagnostic_node -> score 1.0 (sufficient)
    # 3. inference_node -> "Nice to know your favorite color is blue!"
    # 4. analyze_interaction_node -> Extracted SIMPLE fact
    mock_simple_extraction = {
        "has_fact": True,
        "classification": "SIMPLE",
        "description": "User's favorite color is blue",
        "updates": [
            {
                "action": "add_fact",
                "node_id": "user_favorite_color",
                "node_type": "Preference",
                "text": "The user's favorite color is blue."
            }
        ]
    }
    
    import json
    llm_client.mock_responses = [
        "QUERY",
        '{"sufficiency_score": 1.0, "reasoning": "Nothing missing.", "missing_knowledge": []}',
        "Nice to know your favorite color is blue!",
        json.dumps(mock_simple_extraction)
    ]
    
    graph = create_nexus_graph(memory, llm_client)
    
    state = {
        "messages": [{"role": "user", "content": "My favorite color is blue."}],
        "current_query": "My favorite color is blue.",
        "retrieved_context": "",
        "sufficiency_score": 1.0,
        "missing_knowledge_log": [],
        "audit_trail": [],
        "response": "",
        "pending_memory_updates": []
    }
    
    res = graph.invoke(state, config={"configurable": {"thread_id": "thread_simple"}})
    
    # Assert fact was saved immediately
    node = memory.graph_store.get_node("user_favorite_color")
    assert node is not None
    assert node.properties["text"] == "The user's favorite color is blue."
    
    # Assert no staging
    assert res.get("pending_memory_updates") == []
    assert "Proposition" not in res["response"]


def test_conversational_memory_structural_staged_and_confirmed(memory, llm_client):
    """
    Test Case: User mentions a structural fact ("Charles is no longer CEO, Donald is CEO").
    Validation: Update is staged in pending_memory_updates, prompt is appended.
    Then user says "Yes" -> staged updates are committed.
    """
    import json
    
    # --- TURN 1: Stage Update ---
    mock_structural_extraction = {
        "has_fact": True,
        "classification": "STRUCTURAL",
        "description": "Change CEO of Acme from Charles to Donald",
        "updates": [
            {
                "action": "add_fact",
                "node_id": "company_ceo",
                "node_type": "Role",
                "text": "The CEO of Acme Corp is Donald."
            }
        ]
    }
    
    llm_client.mock_responses = [
        "QUERY",
        '{"sufficiency_score": 1.0, "reasoning": "Context is fine.", "missing_knowledge": []}',
        "I understand that Donald is the new CEO.",
        json.dumps(mock_structural_extraction)
    ]
    
    graph = create_nexus_graph(memory, llm_client)
    
    state = {
        "messages": [{"role": "user", "content": "Donald is now the CEO instead of Charles."}],
        "current_query": "Donald is now the CEO instead of Charles.",
        "retrieved_context": "",
        "sufficiency_score": 1.0,
        "missing_knowledge_log": [],
        "audit_trail": [],
        "response": "",
        "pending_memory_updates": []
    }
    
    # Run turn 1
    res_1 = graph.invoke(state, config={"configurable": {"thread_id": "thread_struct"}})
    
    # Assert updates were staged
    assert len(res_1.get("pending_memory_updates", [])) == 1
    assert res_1["pending_memory_updates"][0]["node_id"] == "company_ceo"
    
    # Assert proposal was appended to the response
    assert "Proposition de mise à jour mémoire" in res_1["response"]
    
    # Assert it hasn't been written to memory yet
    assert memory.graph_store.get_node("company_ceo") is None
    
    # --- TURN 2: User Confirms "Yes" ---
    llm_client.mock_responses = [
        "YES"  # Classified by verify_confirmation_node
    ]
    
    state_2 = {
        "messages": res_1["messages"] + [{"role": "user", "content": "Yes, please do."}],
        "current_query": "Yes, please do.",
        "retrieved_context": res_1.get("retrieved_context", ""),
        "sufficiency_score": res_1.get("sufficiency_score", 1.0),
        "missing_knowledge_log": res_1.get("missing_knowledge_log", []),
        "audit_trail": res_1.get("audit_trail", []),
        "response": res_1.get("response", ""),
        "pending_memory_updates": res_1.get("pending_memory_updates")
    }
    
    res_2 = graph.invoke(state_2, config={"configurable": {"thread_id": "thread_struct"}})
    
    # Assert committed to memory
    node = memory.graph_store.get_node("company_ceo")
    assert node is not None
    assert node.properties["text"] == "The CEO of Acme Corp is Donald."
    
    # Assert pending updates cleared
    assert res_2.get("pending_memory_updates") == []
    assert "succès" in res_2["response"]


def test_conversational_memory_structural_staged_and_cancelled(memory, llm_client):
    """
    Test Case: Structural update is staged, then user says "No".
    Validation: Staged updates are discarded, no changes are committed.
    """
    import json
    
    # Stage an update in state
    state = {
        "messages": [
            {"role": "user", "content": "Update the server IP to 10.0.0.1"},
            {"role": "assistant", "content": "Staged update. Confirm? (Oui/Non)"},
            {"role": "user", "content": "No, cancel it."}
        ],
        "current_query": "No, cancel it.",
        "retrieved_context": "",
        "sufficiency_score": 1.0,
        "missing_knowledge_log": [],
        "audit_trail": [],
        "response": "",
        "pending_memory_updates": [
            {
                "action": "add_fact",
                "node_id": "server_ip",
                "node_type": "Config",
                "text": "The server IP is 10.0.0.1."
            }
        ]
    }
    
    llm_client.mock_responses = [
        "NO"  # Classified by verify_confirmation_node
    ]
    
    graph = create_nexus_graph(memory, llm_client)
    res = graph.invoke(state, config={"configurable": {"thread_id": "thread_cancel"}})
    
    # Assert NOT committed to memory
    assert memory.graph_store.get_node("server_ip") is None
    
    # Assert pending updates cleared
    assert res.get("pending_memory_updates") == []
    assert "annulé" in res["response"]


def test_conversational_memory_other_query_discards_pending(memory, llm_client):
    """
    Test Case: Structural update is staged, but user ignores it and asks a new query.
    Validation: Pending updates are cleared, and the new query is processed normally.
    """
    import json
    
    # Stage an update in state
    state = {
        "messages": [
            {"role": "user", "content": "Update server IP to 10.0.0.1"},
            {"role": "assistant", "content": "Staged update. Confirm? (Oui/Non)"},
            {"role": "user", "content": "What is the capital of France?"}
        ],
        "current_query": "What is the capital of France?",
        "retrieved_context": "",
        "sufficiency_score": 1.0,
        "missing_knowledge_log": [],
        "audit_trail": [],
        "response": "",
        "pending_memory_updates": [
            {
                "action": "add_fact",
                "node_id": "server_ip",
                "node_type": "Config",
                "text": "The server IP is 10.0.0.1."
            }
        ]
    }
    
    llm_client.mock_responses = [
        "OTHER",  # Consumed by verify_confirmation_node
        '{"sufficiency_score": 1.0, "reasoning": "Capital of France is common knowledge.", "missing_knowledge": []}',  # Consumed by diagnostic_node
        "The capital of France is Paris.",  # Consumed by inference_node
        '{"has_fact": false, "classification": "NONE", "updates": []}'  # Consumed by analyze_interaction_node
    ]
    
    graph = create_nexus_graph(memory, llm_client)
    res = graph.invoke(state, config={"configurable": {"thread_id": "thread_other"}})
    
    # Assert NOT committed
    assert memory.graph_store.get_node("server_ip") is None
    
    # Assert pending updates cleared
    assert res.get("pending_memory_updates") == []
    
    # Assert new query answered
    assert "Paris" in res["response"]
