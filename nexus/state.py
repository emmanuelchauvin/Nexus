from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    State representing the agent's mental state during a single invocation.
    Persisted via LangGraph checkpointer across runs.
    """
    # Messages list using add_messages reducer for convenient conversational tracking
    messages: Annotated[list, add_messages]
    
    # The current active user question
    current_query: str
    
    # The compiled context text from HybridMemory
    retrieved_context: str
    
    # Sufficiency score (0.0 to 1.0) evaluated by the Diagnostic node
    sufficiency_score: float
    
    # Log of identified memory gaps
    missing_knowledge_log: List[str]
    
    # Step-by-step provenance and arbitration tracking
    audit_trail: List[str]
    
    # The final completion response to the user
    response: str
    
    # Staged memory updates pending conversational validation
    pending_memory_updates: List[Dict[str, Any]]

    # Adaptive loop counter for self-RAG query expansion
    loop_count: int

    # The user's original query (saved before any reformulations)
    original_query: str

