from nexus.graph import create_nexus_graph

def test_diagnostic_loop_and_autocorrection(memory, llm_client):
    """
    Test Case: Ask a query about absent information, log deficiency, warning routing,
    then ingest the missing information and re-query.
    Validation: Check that the deficiency is logged in the state, routed through carence_node,
    and then auto-corrected after ingestion (resulting in high sufficiency score and correct answer).
    """
    # Query 1: Fact is missing.
    # LLM responses:
    # 1. router -> QUERY
    # 2. diagnostic -> score 0.2, missing_knowledge = ["budget of project X"]
    # 3. inference -> Acknowledge the carence
    llm_client.mock_responses = [
        "QUERY",
        '{"sufficiency_score": 0.2, "reasoning": "Budget details are not in context.", "missing_knowledge": ["budget of project X"]}',
        "What is the budget of project X?",
        '{"sufficiency_score": 0.2, "reasoning": "Budget details are not in context.", "missing_knowledge": ["budget of project X"]}',
        "What is the budget of project X?",
        '{"sufficiency_score": 0.2, "reasoning": "Budget details are not in context.", "missing_knowledge": ["budget of project X"]}',
        "I don't know the budget of project X."
    ]

    
    graph = create_nexus_graph(memory, llm_client)
    
    initial_state = {
        "messages": [{"role": "user", "content": "What is the budget of project X?"}],
        "current_query": "What is the budget of project X?",
        "retrieved_context": "",
        "sufficiency_score": 1.0,
        "missing_knowledge_log": [],
        "audit_trail": [],
        "response": ""
    }
    
    final_state_1 = graph.invoke(initial_state, config={"configurable": {"thread_id": "thread_q1"}})
    
    # Assert carence was detected
    assert final_state_1["sufficiency_score"] < 0.7
    assert "budget of project X" in final_state_1["missing_knowledge_log"]
    
    # Assert routing through carence warning node is logged in audit trail
    audit_str = "".join(final_state_1["audit_trail"])
    assert "carence_node" in audit_str
    assert "I don't know" in final_state_1["response"]
    
    # Now, ingest the missing information
    memory.add_fact(
        node_id="project_x_budget",
        node_type="ProjectBudget",
        text="The budget of project X is $1.2 million.",
        source="financial_ledger"
    )
    
    # Query 2: Fact is now present!
    # LLM responses:
    # 1. router -> QUERY
    # 2. diagnostic -> score 0.9
    # 3. inference -> Retrieve and formulate answer
    llm_client.mock_responses = [
        "QUERY",
        '{"sufficiency_score": 0.9, "reasoning": "We have the budget in the financial ledger.", "missing_knowledge": []}',
        "The budget of project X is $1.2 million."
    ]
    
    final_state_2 = graph.invoke(initial_state, config={"configurable": {"thread_id": "thread_q2"}})
    
    # Assert sufficiency is now high
    assert final_state_2["sufficiency_score"] >= 0.7
    
    # Assert routing skipped carence_node
    audit_str_2 = "".join(final_state_2["audit_trail"])
    assert "carence_node" not in audit_str_2
    assert "$1.2 million" in final_state_2["response"]
