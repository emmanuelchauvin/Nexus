import json
from datetime import datetime
from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from nexus.state import AgentState
from nexus.memory.hybrid import HybridMemory
from nexus.llm.client import LLMClient
from nexus.loops.diagnostic import evaluate_sufficiency

class NexusWorkflow:
    def __init__(self, memory: HybridMemory, llm_client: LLMClient):
        """
        Initialize the workflow nodes with injected services.
        """
        self.memory = memory
        self.llm_client = llm_client

    def router_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Classifies whether the user request is an ingestion (STORE) or an interaction (QUERY).
        """
        pending = state.get("pending_memory_updates", [])
        
        init_updates = {}
        if "loop_count" not in state or state.get("loop_count") is None:
            init_updates["loop_count"] = 0

        if pending:
            return {"response": "CONFIRM", **init_updates}

        messages = state.get("messages", [])
        if not messages:
            return {"response": "QUERY", "current_query": "", "original_query": "", **init_updates}
        
        last_msg = messages[-1]
        text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        if isinstance(text, dict):
            text = text.get("content", "")

        # Allow user overrides via prefix keywords
        text_upper = text.strip().upper()
        if text_upper.startswith("STORE:") or text_upper.startswith("INGEST:"):
            query_clean = text.split(":", 1)[1].strip()
            return {"response": "STORE", "current_query": query_clean, "original_query": query_clean, **init_updates}
        if text_upper.startswith("QUERY:") or text_upper.startswith("ASK:"):
            query_clean = text.split(":", 1)[1].strip()
            return {"response": "QUERY", "current_query": query_clean, "original_query": query_clean, **init_updates}

        # Asynchronously classify using the LLM
        prompt = [
            {
                "role": "system",
                "content": (
                    "You are the routing system for Nexus.\n"
                    "Classify if the user input is a statement/fact/document to be saved into memory (STORE) "
                    "or a question/command/conversation query requesting a response (QUERY).\n"
                    "Respond with exactly one word: STORE or QUERY."
                )
            },
            {"role": "user", "content": text}
        ]
        
        try:
            decision = self.llm_client.generate(prompt, max_tokens=1000).strip().upper()
            if "STORE" in decision:
                classification = "STORE"
            else:
                classification = "QUERY"
        except Exception:
            classification = "QUERY"  # Fallback

        return {
            "response": classification,
            "current_query": text,
            "original_query": text,
            **init_updates
        }

    def search_memory_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Searches the HybridMemory for facts similar to the current query.
        """
        query = state.get("current_query", "")
        retrieved = self.memory.retrieve(query)
        
        existing_context = state.get("retrieved_context", "")
        new_context = retrieved["context_text"]
        
        if existing_context:
            existing_lines = existing_context.split("\n")
            new_lines = new_context.split("\n")
            
            merged_lines = []
            seen_lines = set()
            for line in existing_lines + new_lines:
                clean = line.strip()
                if clean and clean not in seen_lines:
                    merged_lines.append(line)
                    seen_lines.add(clean)
            combined_context = "\n".join(merged_lines)
        else:
            combined_context = new_context
            
        return {
            "retrieved_context": combined_context,
            "audit_trail": state.get("audit_trail", []) + retrieved["audit_trail"]
        }


    def diagnostic_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Diagnostic Loop node. Evaluates context sufficiency for answering the query.
        """
        query = state.get("current_query", "")
        context = state.get("retrieved_context", "")

        result = evaluate_sufficiency(query, context, self.llm_client)
        score = result["sufficiency_score"]
        reasoning = result["reasoning"]
        missing = result["missing_knowledge"]

        audit_msg = f"[Diagnostic] Sufficiency Score: {score}. Reasoning: {reasoning}. Missing: {missing}"
        
        return {
            "sufficiency_score": score,
            "missing_knowledge_log": state.get("missing_knowledge_log", []) + missing,
            "audit_trail": state.get("audit_trail", []) + [audit_msg]
        }

    def carence_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Node that triggers when the context sufficiency is low. Appends warning metadata to context.
        """
        score = state.get("sufficiency_score", 0.0)
        missing = state.get("missing_knowledge_log", [])
        
        alert_text = (
            f"\n[System Alert: Low Sufficiency ({score})] "
            f"Context lacks critical information. Identified Gaps: {', '.join(missing)}"
        )
        
        updated_context = state.get("retrieved_context", "") + alert_text
        audit_msg = f"[Diagnostic Router] Directed to carence_node due to low sufficiency score."

        return {
            "retrieved_context": updated_context,
            "audit_trail": state.get("audit_trail", []) + [audit_msg]
        }

    def reformulate_query_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Reformulates the query using the LLM based on the missing knowledge gaps.
        """
        original_query = state.get("original_query") or state.get("current_query") or ""
        gaps = state.get("missing_knowledge_log", [])
        
        prompt = [
            {
                "role": "system",
                "content": (
                    "You are the Query Reformulator for the Nexus Memory System.\n"
                    "Your job is to rewrite the original user query to retrieve missing details from the memory database.\n"
                    "Consider the original query and the list of identified knowledge gaps.\n"
                    "Generate a single query string that combines keyword search, acronym expansion, and relevant contextual terms.\n"
                    "Respond ONLY with the reformulated query text, nothing else."
                )
            },
            {
                "role": "user",
                "content": f"Original Query: {original_query}\nKnowledge Gaps / Missing: {', '.join(gaps)}"
            }
        ]
        
        try:
            reformulated = self.llm_client.generate(prompt, max_tokens=1000).strip()
        except Exception:
            reformulated = original_query  # Fallback
            
        loop_count = state.get("loop_count", 0) + 1
        audit_msg = f"[Adaptive RAG] Loop {loop_count}: Reformulated query to '{reformulated}' based on gaps: {gaps}"
        
        return {
            "current_query": reformulated,
            "loop_count": loop_count,
            "audit_trail": state.get("audit_trail", []) + [audit_msg]
        }


    def inference_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Generates the final user-facing response using the retrieved context.
        """
        query = state.get("current_query", "")
        context = state.get("retrieved_context", "")

        # Format previous messages to include conversation history
        formatted_history = []
        messages = state.get("messages", [])
        for msg in messages[:-1]:
            role = "user"
            if hasattr(msg, "type"):
                role = "assistant" if msg.type == "ai" else "user"
            elif isinstance(msg, dict):
                role = msg.get("role", "user")
            
            content = msg.content if hasattr(msg, "content") else str(msg)
            if isinstance(content, dict):
                content = content.get("content", "")
            
            # Skip empty or system alerts from previous assistant messages
            if content.strip():
                formatted_history.append({"role": role, "content": content})

        prompt = [
            {
                "role": "system",
                "content": (
                    "You are Nexus, an Evolutive Persistent Memory agent.\n"
                    "Use the retrieved context to answer the user's query.\n"
                    "Rules:\n"
                    "1. Rely strictly on the facts, sources, and timestamps in the context.\n"
                    "2. If there are contradictions, resolve them using the most recent timestamp.\n"
                    "3. If the context is marked as insufficient or has System Alerts, acknowledge the lack of "
                    "information honestly and mention what is missing.\n"
                    "4. Do not make up facts."
                )
            },
            *formatted_history,
            {
                "role": "user",
                "content": f"Retrieved Context:\n{context}\n\nUser Query: {query}"
            }
        ]

        response = self.llm_client.generate(prompt, max_tokens=1000)
        audit_msg = "[Inference] Generated final answer using retrieved context."

        return {
            "response": response,
            "audit_trail": state.get("audit_trail", []) + [audit_msg]
        }

    def verify_confirmation_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Processes confirmation of staged memory updates.
        Checks if the user's latest message is YES, NO, or something else.
        """
        pending = state.get("pending_memory_updates", [])
        if not pending:
            return {"response": "", "pending_memory_updates": []}

        # Get latest message
        messages = state.get("messages", [])
        last_msg = messages[-1]
        text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        if isinstance(text, dict):
            text = text.get("content", "")

        # Ask LLM to classify user response
        prompt = [
            {
                "role": "system",
                "content": (
                    "You are a verification system.\n"
                    "The user was previously asked if they want to apply a set of memory updates.\n"
                    "Analyze the user's response and classify it into exactly one of these categories:\n"
                    "1. YES: The user agrees, confirms, or wants to proceed (e.g. 'oui', 'yes', 'ok', 'go', 'fais-le').\n"
                    "2. NO: The user declines, cancels, or refuses (e.g. 'non', 'no', 'annule', 'ne fais rien').\n"
                    "3. OTHER: The user asks a completely new question, ignores the confirmation, or switches the topic.\n\n"
                    "Respond with exactly one word: YES, NO, or OTHER."
                )
            },
            {"role": "user", "content": text}
        ]

        try:
            decision = self.llm_client.generate(prompt, max_tokens=1000).strip().upper()
        except Exception:
            decision = "OTHER"

        audit_trail = state.get("audit_trail", []) + [f"[Verification] User response classified as: {decision}"]

        if "YES" in decision:
            # Commit pending updates!
            applied_logs = []
            for update in pending:
                action = update.get("action")
                if action == "add_fact":
                    res = self.memory.add_fact(
                        node_id=update.get("node_id"),
                        node_type=update.get("node_type", "Fact"),
                        text=update.get("text", ""),
                        properties=update.get("properties", {}),
                        timestamp=datetime.utcnow(),
                        source="user_confirmed_ingestion"
                    )
                    applied_logs.append(res.get("audit", f"Added node {update.get('node_id')}"))
                elif action == "add_relationship":
                    self.memory.add_relationship(
                        source_id=update.get("source_id"),
                        target_id=update.get("target_id"),
                        rel_type=update.get("rel_type", "CONNECTED_TO"),
                        properties=update.get("properties", {}),
                        timestamp=datetime.utcnow()
                    )
                    applied_logs.append(f"Linked '{update.get('source_id')}' --({update.get('rel_type')})--> '{update.get('target_id')}'")
                elif action == "delete_node":
                    self.memory.graph_store.delete_node(update.get("node_id"))
                    self.memory.vector_store.delete(update.get("node_id"))
                    applied_logs.append(f"Deleted node '{update.get('node_id')}'")

            confirm_msg = "Mise à jour de la mémoire effectuée avec succès !"
            return {
                "response": confirm_msg,
                "messages": [{"role": "assistant", "content": confirm_msg}],
                "pending_memory_updates": [],
                "audit_trail": audit_trail + applied_logs
            }

        elif "NO" in decision:
            cancel_msg = "D'accord, j'ai annulé la mise à jour de la mémoire."
            return {
                "response": cancel_msg,
                "messages": [{"role": "assistant", "content": cancel_msg}],
                "pending_memory_updates": [],
                "audit_trail": audit_trail + ["Staged memory updates discarded by user."]
            }

        else:
            # OTHER: discard updates and fall through to QUERY processing
            return {
                "pending_memory_updates": [],
                "response": "ROUTE_TO_QUERY",
                "audit_trail": audit_trail + ["Staged updates discarded because user changed the topic."]
            }

    def analyze_interaction_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Analyzes the conversational exchange to extract new facts or modifications.
        Automatically updates memory for simple facts, or stages them for confirmation.
        """
        query = state.get("current_query", "")
        response = state.get("response", "")

        # Ask LLM to extract any statement that user declared as fact
        prompt = [
            {
                "role": "system",
                "content": (
                    "You are a Memory Analyzer for a persistent semantic memory agent.\n"
                    "Analyze the user's statement and determine if the user has shared a new fact, correction, or update "
                    "that should be saved to the database.\n"
                    "Only extract facts that the user is asserting as true. Do not extract questions or assistant replies.\n\n"
                    "Classification rules:\n"
                    "1. SIMPLE: A new factual detail that does not contradict existing knowledge and does not alter core relations.\n"
                    "2. STRUCTURAL: An update/correction to an existing key fact (e.g. changing someone's role, name, status, or merging entities, or deleting node).\n"
                    "3. NONE: No new factual information was asserted.\n\n"
                    "Respond ONLY with a JSON object:\n"
                    "{\n"
                    '  "has_fact": true/false,\n'
                    '  "classification": "SIMPLE" or "STRUCTURAL" or "NONE",\n'
                    '  "description": "Short human readable summary of the change (e.g. Update Charles\'s role to ex-CEO)",\n'
                    '  "updates": [\n'
                    '     {\n'
                    '       "action": "add_fact" or "add_relationship" or "delete_node",\n'
                    '       "node_id": "slug",\n'
                    '       "node_type": "type",\n'
                    '       "text": "clean fact statement",\n'
                    '       "properties": {}\n'
                    '     },\n'
                    '     {\n'
                    '       "action": "add_relationship",\n'
                    '       "source_id": "src",\n'
                    '       "target_id": "tgt",\n'
                    '       "rel_type": "TYPE"\n'
                    '     }\n'
                    '  ]\n'
                    "}"
                )
            },
            {"role": "user", "content": f"User: {query}\nAssistant: {response}"}
        ]

        try:
            raw_json = self.llm_client.generate(prompt, max_tokens=3000, response_format={"type": "json_object"})
            data = json.loads(raw_json)
        except Exception:
            data = {"has_fact": False, "classification": "NONE", "updates": []}

        if not data.get("has_fact", False) or not data.get("updates"):
            return {
                "messages": [{"role": "assistant", "content": response}]
            }

        classification = data.get("classification", "NONE")
        updates = data.get("updates", [])
        desc = data.get("description", "Mise à jour")

        audit_trail = []
        pending_updates = []

        if classification == "SIMPLE":
            # Apply immediately and silently!
            for update in updates:
                action = update.get("action")
                if action == "add_fact":
                    res = self.memory.add_fact(
                        node_id=update.get("node_id"),
                        node_type=update.get("node_type", "Fact"),
                        text=update.get("text", ""),
                        properties=update.get("properties", {}),
                        timestamp=datetime.utcnow(),
                        source="user_chat_extraction"
                    )
                    audit_trail.append(res.get("audit", f"Silently added node {update.get('node_id')}"))
                elif action == "add_relationship":
                    self.memory.add_relationship(
                        source_id=update.get("source_id"),
                        target_id=update.get("target_id"),
                        rel_type=update.get("rel_type", "CONNECTED_TO"),
                        properties=update.get("properties", {}),
                        timestamp=datetime.utcnow()
                    )
                    audit_trail.append(f"Silently linked '{update.get('source_id')}' --({update.get('rel_type')})--> '{update.get('target_id')}'")
                elif action == "delete_node":
                    self.memory.graph_store.delete_node(update.get("node_id"))
                    self.memory.vector_store.delete(update.get("node_id"))
                    audit_trail.append(f"Silently deleted node '{update.get('node_id')}'")
            
            return {
                "messages": [{"role": "assistant", "content": response}],
                "audit_trail": state.get("audit_trail", []) + audit_trail
            }

        elif classification == "STRUCTURAL":
            # Stage for validation and append proposal to assistant response
            pending_updates = updates
            
            proposal_prompt = (
                f"\n\n👉 *[Proposition de mise à jour mémoire]* : J'ai détecté un changement important : **{desc}**. "
                "Voulez-vous que je valide cette modification dans ma mémoire ? (Oui / Non)"
            )
            
            updated_response = response + proposal_prompt
            audit_msg = f"[Interaction Analyzer] Staged {len(pending_updates)} structural memory updates: {desc}"
            
            return {
                "response": updated_response,
                "messages": [{"role": "assistant", "content": updated_response}],
                "pending_memory_updates": pending_updates,
                "audit_trail": state.get("audit_trail", []) + [audit_msg]
            }

        return {
            "messages": [{"role": "assistant", "content": response}]
        }

    def update_memory_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Parses incoming facts and stores them inside HybridMemory.
        """
        raw_text = state.get("current_query", "")

        prompt = [
            {
                "role": "system",
                "content": (
                    "You are the Ingestion Parser for the Nexus Memory System.\n"
                    "Extract the core facts to store in the hybrid semantic-vector memory.\n"
                    "Ensure you extract the main entity (node_id), its type (node_type), and the clean text statement.\n"
                    "If relations to other nodes are mentioned, list them. Use clean ISO 8601 formatting for timestamps if mentioned, otherwise leave timestamp null.\n"
                    "Respond ONLY with a JSON object:\n"
                    "{\n"
                    '  "node_id": "slug of entity (e.g. john_doe, company_xyz)",\n'
                    '  "node_type": "type of entity (e.g. Person, Company, Policy)",\n'
                    '  "text": "clean fact text to store",\n'
                    '  "properties": {"key": "value"},\n'
                    '  "timestamp": "ISO 8601 string or null",\n'
                    '  "relations": [\n'
                    '     {"target": "target_node_id", "type": "REL_TYPE", "properties": {}}\n'
                    '  ]\n'
                    "}"
                )
            },
            {"role": "user", "content": raw_text}
        ]

        raw_json = self.llm_client.generate(prompt, max_tokens=1500)
        
        json_str = raw_json.strip()
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                lines = lines[1:-1]
            json_str = "\n".join(lines).strip()

        try:
            data = json.loads(json_str)
            node_id = data["node_id"]
            node_type = data["node_type"]
            text = data["text"]
            properties = data.get("properties", {})
            
            ts_str = data.get("timestamp")
            timestamp = datetime.fromisoformat(ts_str) if ts_str else datetime.utcnow()
            
            relations = data.get("relations", [])
        except Exception:
            # Fallback parsing for unstructured inputs
            node_id = f"fact_{int(datetime.utcnow().timestamp())}"
            node_type = "Fact"
            text = raw_text
            properties = {}
            timestamp = datetime.utcnow()
            relations = []

        # Save the primary node fact
        result = self.memory.add_fact(
            node_id=node_id,
            node_type=node_type,
            text=text,
            properties=properties,
            timestamp=timestamp,
            source="user_ingestion"
        )
        
        audit_trail = [result["audit"]]

        # Save any relationship edges
        for rel in relations:
            target = rel.get("target")
            rel_type = rel.get("type", "CONNECTED_TO")
            rel_props = rel.get("properties", {})
            if target:
                self.memory.add_relationship(
                    source_id=node_id,
                    target_id=target,
                    rel_type=rel_type,
                    properties=rel_props,
                    timestamp=timestamp
                )
                audit_trail.append(f"Linked node '{node_id}' --({rel_type})--> '{target}'")

        success_response = (
            f"Fact stored successfully! Node ID: '{node_id}' ({node_type}). "
            f"Status: {result['status']}. Details: {result['audit']}"
        )

        return {
            "response": success_response,
            "messages": [{"role": "assistant", "content": success_response}],
            "audit_trail": state.get("audit_trail", []) + audit_trail
        }

def route_input(state: AgentState) -> str:
    """
    Decides if request goes to query search, ingestion store, or confirmation.
    """
    decision = state.get("response", "QUERY")
    if decision == "CONFIRM":
        return "verify_confirmation"
    elif decision == "STORE":
        return "update_memory"
    return "search_memory"

def route_confirmation(state: AgentState) -> str:
    """
    Routes after confirmation verification.
    """
    if state.get("response") == "ROUTE_TO_QUERY":
        return "search_memory"
    return END

def route_diagnostic(state: AgentState) -> str:
    """
    Routes to carence warning node if sufficiency score is low.
    """
    score = state.get("sufficiency_score", 1.0)
    loop_count = state.get("loop_count", 0)
    
    if score >= 0.7:
        return "inference"
    
    # Adaptive loop: if score is low, try to reformulate and search again (up to 2 times)
    if loop_count < 2:
        return "reformulate_query"
        
    return "carence"

def create_nexus_graph(memory: HybridMemory, llm_client: LLMClient) -> StateGraph:
    """
    Creates, links, and compiles the LangGraph StateMachine.
    """
    workflow = NexusWorkflow(memory, llm_client)
    graph_builder = StateGraph(AgentState)
    
    # Register Nodes
    graph_builder.add_node("router", workflow.router_node)
    graph_builder.add_node("verify_confirmation", workflow.verify_confirmation_node)
    graph_builder.add_node("search_memory", workflow.search_memory_node)
    graph_builder.add_node("diagnostic", workflow.diagnostic_node)
    graph_builder.add_node("carence", workflow.carence_node)
    graph_builder.add_node("reformulate_query", workflow.reformulate_query_node)
    graph_builder.add_node("inference", workflow.inference_node)
    graph_builder.add_node("analyze_interaction", workflow.analyze_interaction_node)
    graph_builder.add_node("update_memory", workflow.update_memory_node)
    
    # Connect Static Edges
    graph_builder.add_edge(START, "router")
    graph_builder.add_edge("search_memory", "diagnostic")
    graph_builder.add_edge("carence", "inference")
    graph_builder.add_edge("reformulate_query", "search_memory")
    graph_builder.add_edge("inference", "analyze_interaction")
    graph_builder.add_edge("analyze_interaction", END)
    graph_builder.add_edge("update_memory", END)
    
    # Connect Conditional Edges
    graph_builder.add_conditional_edges(
        "router",
        route_input,
        {
            "verify_confirmation": "verify_confirmation",
            "update_memory": "update_memory",
            "search_memory": "search_memory"
        }
    )
    
    graph_builder.add_conditional_edges(
        "verify_confirmation",
        route_confirmation,
        {
            "search_memory": "search_memory",
            "__end__": END
        }
    )
    
    graph_builder.add_conditional_edges(
        "diagnostic",
        route_diagnostic,
        {
            "inference": "inference",
            "reformulate_query": "reformulate_query",
            "carence": "carence"
        }
    )
    
    return graph_builder.compile(checkpointer=MemorySaver())

