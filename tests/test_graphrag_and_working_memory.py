import pytest
import json
from datetime import datetime
from nexus.loops.distillation import DistillationLoop
from nexus.graph import create_nexus_graph

def test_louvain_communities_summarization(memory, llm_client):
    """
    Test Case: Verify Louvain community detection and summarization.
    """
    # Create two disjoint communities in the graph
    # Community A (Acme Corp CEO)
    memory.add_fact(
        node_id="charles",
        node_type="Person",
        text="Charles is the CEO of Acme Corp.",
        source="doc_1"
    )
    memory.add_fact(
        node_id="acme",
        node_type="Company",
        text="Acme Corp is a widget manufacturer.",
        source="doc_1"
    )
    memory.add_relationship("charles", "acme", "CEO_OF")

    # Community B (Project Omega)
    memory.add_fact(
        node_id="project_omega",
        node_type="Project",
        text="Project Omega is a secret space program.",
        source="doc_2"
    )
    memory.add_fact(
        node_id="nasa",
        node_type="Agency",
        text="NASA sponsors secret space programs.",
        source="doc_2"
    )
    memory.add_relationship("project_omega", "nasa", "SPONSORED_BY")

    # Mock response for the community summarization LLM calls
    # One call per community detected (2 communities expected)
    llm_client.mock_responses = [
        "This community is about Acme Corp and its CEO Charles.",
        "This community is about Project Omega and NASA sponsoring space programs."
    ]

    distillation = DistillationLoop(memory=memory, llm_client=llm_client)
    res = distillation.run_community_summarization()

    assert res["status"] == "success"
    assert res["communities_detected"] == 2
    assert res["summaries_generated"] == 2

    # Verify that summaries are retrieved via HybridMemory
    # Query for Acme Corp
    retrieved = memory.retrieve("Acme Corp")
    context_text = retrieved["context_text"]
    
    assert "COMMUNITY SUMMARIES" in context_text
    assert "CEO Charles" in context_text


def test_working_memory_update_and_persistence(memory, llm_client):
    """
    Test Case: Verify Working Memory updates during conversational turns.
    """
    graph = create_nexus_graph(memory, llm_client)
    config = {"configurable": {"thread_id": "test_session_123"}}

    # Mock responses for the nodes:
    # 1. router -> QUERY
    # 2. diagnostic -> score 0.9
    # 3. inference -> "Hello Emmanuel, how can I help you today?"
    # 4. analyze_interaction -> returns working memory update in JSON
    mock_wm_update = {
        "has_fact": False,
        "classification": "NONE",
        "updates": [],
        "working_memory_update": {
            "user_profile": "User name is Emmanuel",
            "current_tasks": ["Help Emmanuel with his queries"],
            "scratchpad": "Emmanuel introduced himself."
        }
    }
    
    llm_client.mock_responses = [
        "QUERY",
        '{"sufficiency_score": 0.9, "reasoning": "Simple greeting.", "missing_knowledge": []}',
        "Hello Emmanuel, how can I help you today?",
        json.dumps(mock_wm_update)
    ]

    initial_state = {
        "messages": [{"role": "user", "content": "Hello, I am Emmanuel."}],
        "current_query": "Hello, I am Emmanuel.",
        "retrieved_context": "",
        "sufficiency_score": 1.0,
        "missing_knowledge_log": [],
        "audit_trail": [],
        "response": ""
    }

    final_state = graph.invoke(initial_state, config=config)

    # Assert Working Memory was populated correctly
    wm = final_state.get("working_memory")
    assert wm is not None
    assert wm["user_profile"] == "User name is Emmanuel"
    assert wm["current_tasks"] == ["Help Emmanuel with his queries"]
    assert wm["scratchpad"] == "Emmanuel introduced himself."

    # Assert audit trail logged the working memory update
    audit_str = "".join(final_state["audit_trail"])
    assert "[Working Memory]" in audit_str
