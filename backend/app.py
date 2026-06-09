import os
import sys
import io
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import requests
from pypdf import PdfReader


# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nexus.memory.networkx_store import NetworkXGraphStore
from nexus.memory.chromadb_store import ChromaDBStore
from nexus.memory.hybrid import HybridMemory
from nexus.llm.client import LLMClient
from nexus.graph import create_nexus_graph
from nexus.loops.distillation import DistillationLoop
from nexus.loops.oubli import OubliLoop

# Load environment configs
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"), override=True)

def clean_and_parse_json(raw_text: str) -> dict:
    """
    Cleans markdown backticks and parses the JSON output of the LLM.
    """
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```json") or lines[0].startswith("```"):
            lines = lines[1:-1]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)

app = FastAPI(
    title="Nexus API",
    description="Backend services for the Evolutive Persistent Memory (MPE) system",
    version="1.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Workspace directories for database files
storage_dir = os.path.join(os.getcwd(), ".nexus_storage")
os.makedirs(storage_dir, exist_ok=True)

graph_path = os.path.join(storage_dir, "graph.json")
chroma_path = os.path.join(storage_dir, "chromadb")

# Instantiate stores & coordinator
graph_store = NetworkXGraphStore(filepath=graph_path)
vector_store = ChromaDBStore(persist_directory=chroma_path)
memory = HybridMemory(graph_store=graph_store, vector_store=vector_store)

# LLM Client and Graph StateMachine compilation
llm_client = LLMClient()
memory.llm_client = llm_client
graph_flow = create_nexus_graph(memory=memory, llm_client=llm_client)

# Instantiate background worker loops
distill_loop = DistillationLoop(memory=memory, llm_client=llm_client)
oubli_loop = OubliLoop(memory=memory)

# Discover the securecoder API port from sidecar
SECURECODER_PORT = None
try:
    sidecar_path = os.path.join(os.path.expanduser("~"), ".securecoder", "api.json")
    if os.path.exists(sidecar_path):
        import json
        with open(sidecar_path, "r") as f:
            SECURECODER_PORT = json.load(f).get("port")
except Exception:
    pass

from langchain_core.messages import HumanMessage, AIMessage

# Path to session persistence
sessions_path = os.path.join(storage_dir, "sessions.json")

def load_sessions() -> Dict[str, Any]:
    if os.path.exists(sessions_path):
        try:
            with open(sessions_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"sessions": []}

def save_sessions(data: Dict[str, Any]):
    try:
        with open(sessions_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving sessions: {e}")

# --- Pydantic Data Schemas ---

class QueryRequest(BaseModel):
    message: str
    user_id: Optional[str] = "web_user"
    session_id: Optional[str] = None

class CreateSessionRequest(BaseModel):
    title: Optional[str] = "Nouvelle conversation"

class RenameSessionRequest(BaseModel):
    title: str

class FactRequest(BaseModel):
    node_id: str
    node_type: str
    text: str
    properties: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    source: Optional[str] = None

class RelationRequest(BaseModel):
    source_id: str
    target_id: str
    rel_type: str
    properties: Optional[Dict[str, Any]] = None

class LRURequest(BaseModel):
    max_nodes: int

class DecayRequest(BaseModel):
    max_age_days: int

def chunk_text(text: str, chunk_size: int = 5000, overlap: int = 500) -> List[str]:
    """
    Splits text into chunks of chunk_size with overlap.
    """
    chunks = []
    start = 0
    text_len = len(text)
    if text_len == 0:
        return chunks
        
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        if end == text_len:
            break
        start += (chunk_size - overlap)
    return chunks

def llm_chunk_summarize(chunk_content: str, llm_client: LLMClient) -> dict:
    """
    Calls the LLM to generate a clean, dense Markdown summary of the chunk,
    and extract semantic entity-relation triplets.
    """
    prompt = [
        {
            "role": "system",
            "content": (
                "You are an expert in knowledge engineering.\n"
                "Analyze the following raw text chunk from a scientific document and generate a structured JSON object containing:\n"
                "1. A clean, high-density Markdown summary ('summary_markdown') representing this chunk. Use headers (##) and bullet points. Rewrite pronouns to use explicit entity names for better retrieval.\n"
                "2. A list of entities ('entities') to create in the knowledge graph. Each entity must have 'id' (slug), 'type' (e.g. Concept, Architecture, Algorithm, Author, Technology), and 'text' (description/definition).\n"
                "3. A list of relationships ('triplets') connecting these entities. Each relationship must have 'source', 'target', 'type' (in uppercase, e.g., MANAGES, RESOLVES, COMBINES, IMPLEMENTS), and optionally 'properties'.\n\n"
                "JSON format schema:\n"
                "{\n"
                '  "summary_markdown": "Markdown text here",\n'
                '  "entities": [\n'
                '     {"id": "unique_slug", "type": "EntityType", "text": "Definition/description"}\n'
                '  ],\n'
                '  "triplets": [\n'
                '     {"source": "source_id", "target": "target_id", "type": "REL_TYPE", "properties": {}}\n'
                '  ]\n'
                "}"
            )
        },
        {"role": "user", "content": f"Text chunk to process:\n{chunk_content}"}
    ]
    try:
        raw_resp = llm_client.generate(prompt, max_tokens=4000, response_format={"type": "json_object"})
        data = clean_and_parse_json(raw_resp)
        if "summary_markdown" not in data:
            data["summary_markdown"] = chunk_content
        if "entities" not in data:
            data["entities"] = []
        if "triplets" not in data:
            data["triplets"] = []
        return data
    except Exception as e:
        print(f"[WARNING] LLM chunking failed: {e}. Falling back to default raw text.")
        try:
            print(f"[DEBUG] Raw response was (length={len(raw_resp) if 'raw_resp' in locals() else 0}):")
            if 'raw_resp' in locals():
                print(raw_resp)
        except Exception as print_err:
            print(f"[DEBUG] Failed to print raw response: {print_err}")
        return {
            "summary_markdown": chunk_content,
            "entities": [],
            "triplets": []
        }

@app.post("/api/ingest/pdf")
async def ingest_pdf(file: UploadFile = File(...)):
    """
    Uploads and processes a PDF file, chunking its text and ingesting it.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    try:
        content = await file.read()
        pdf_file = io.BytesIO(content)
        reader = PdfReader(pdf_file)
        
        full_text = ""
        total_pages = len(reader.pages)
        
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_text += f"\n--- Page {page_num + 1} ---\n" + text
        
        if not full_text.strip():
            raise HTTPException(status_code=400, detail=f"No text could be extracted from {file.filename}.")
            
        doc_id = f"doc_{file.filename.replace('.', '_').replace(' ', '_')}"
        
        # 1. Add Document Node to the Graph
        memory.add_fact(
            node_id=doc_id,
            node_type="Document",
            text=f"Document PDF: {file.filename}",
            properties={
                "filename": file.filename,
                "total_pages": total_pages,
                "ingested_at": datetime.utcnow().isoformat()
            },
            timestamp=datetime.utcnow(),
            source="pdf_upload_api"
        )
        
        # 2. Chunk text and add Chunk Nodes
        chunks = chunk_text(full_text)
        
        last_chunk_id = None
        for i, raw_chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            
            # Process with LLM to get Markdown summary and Graph entities/triplets
            llm_data = llm_chunk_summarize(raw_chunk, llm_client)
            summary_markdown = llm_data.get("summary_markdown", raw_chunk)
            entities = llm_data.get("entities", [])
            triplets = llm_data.get("triplets", [])
            
            # Add chunk fact to hybrid memory
            memory.add_fact(
                node_id=chunk_id,
                node_type="DocumentChunk",
                text=summary_markdown,
                properties={
                    "parent_document": doc_id,
                    "chunk_index": i,
                    "filename": file.filename
                },
                timestamp=datetime.utcnow(),
                source=f"pdf_upload_api:{file.filename}"
            )
            
            # Create relationship from chunk to document parent
            memory.add_relationship(
                source_id=chunk_id,
                target_id=doc_id,
                rel_type="PART_OF",
                timestamp=datetime.utcnow()
            )
            
            # Create sequential connection to the previous chunk
            if last_chunk_id:
                memory.add_relationship(
                    source_id=last_chunk_id,
                    target_id=chunk_id,
                    rel_type="NEXT",
                    timestamp=datetime.utcnow()
                )
                
            last_chunk_id = chunk_id
            
            # Ingest extracted entities
            for ent in entities:
                ent_id = ent.get("id")
                ent_type = ent.get("type", "Concept")
                ent_text = ent.get("text", "")
                if ent_id and ent_text:
                    memory.add_fact(
                        node_id=ent_id,
                        node_type=ent_type,
                        text=ent_text,
                        properties={"extracted_from": chunk_id},
                        timestamp=datetime.utcnow(),
                        source=f"pdf_llm_extractor:{file.filename}"
                    )
                    # Link entity to the chunk
                    memory.add_relationship(
                        source_id=ent_id,
                        target_id=chunk_id,
                        rel_type="MENTIONED_IN",
                        timestamp=datetime.utcnow()
                    )
            
            # Ingest extracted triplets
            for trip in triplets:
                src = trip.get("source")
                tgt = trip.get("target")
                rtype = trip.get("type", "CONNECTED_TO")
                props = trip.get("properties", {})
                if src and tgt:
                    memory.add_relationship(
                        source_id=src,
                        target_id=tgt,
                        rel_type=rtype,
                        properties=props,
                        timestamp=datetime.utcnow()
                    )
            
        return {
            "success": True, 
            "message": f"Successfully ingested {file.filename} ({len(chunks)} chunks).",
            "document_id": doc_id,
            "chunks_count": len(chunks)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF ingestion failed: {str(e)}")

# --- API Route Endpoints ---

@app.post("/api/query")
def run_query(request: QueryRequest):
    """
    Executes a query through the LangGraph agent state machine.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Query message cannot be empty.")
    
    session_id = request.session_id or "web_chat_session"
    config = {"configurable": {"thread_id": f"session_{session_id}"}}
    
    try:
        # Load sessions database
        sessions_db = load_sessions()
        session_data = next((s for s in sessions_db["sessions"] if s["id"] == session_id), None)
        
        # If the session is stored in JSON but LangGraph checkpointer is empty (e.g. after server restart),
        # rebuild the LangGraph state.
        lg_state = graph_flow.get_state(config)
        existing_wm = lg_state.values.get("working_memory") if lg_state.values else None
        
        if session_data and (not lg_state.values or "messages" not in lg_state.values):
            lg_messages = []
            for msg in session_data.get("messages", []):
                if msg["role"] == "assistant":
                    lg_messages.append(AIMessage(content=msg["content"]))
                else:
                    lg_messages.append(HumanMessage(content=msg["content"]))
            if lg_messages:
                graph_flow.update_state(config, {"messages": lg_messages})

        initial_state = {
            "messages": [{"role": "user", "content": request.message}],
            "current_query": request.message,
            "retrieved_context": "",
            "sufficiency_score": 1.0,
            "missing_knowledge_log": [],
            "audit_trail": [],
            "response": ""
        }
        if existing_wm:
            initial_state["working_memory"] = existing_wm
        
        final_state = graph_flow.invoke(initial_state, config=config)
        response_text = final_state.get("response", "No response generated.")
        
        # Update or create the session in JSON database
        messages_to_save = []
        updated_lg_messages = final_state.get("messages", [])
        for m in updated_lg_messages:
            role = "user"
            if hasattr(m, "type"):
                role = "assistant" if m.type == "ai" else "user"
            elif isinstance(m, dict):
                role = m.get("role", "user")
            
            content = m.content if hasattr(m, "content") else str(m)
            if isinstance(content, dict):
                content = content.get("content", "")
            
            if content.strip():
                messages_to_save.append({"role": role, "content": content})

        if not session_data:
            session_data = {
                "id": session_id,
                "title": request.message[:40] + ("..." if len(request.message) > 40 else ""),
                "created_at": datetime.utcnow().isoformat(),
                "messages": messages_to_save
            }
            sessions_db["sessions"].insert(0, session_data)
        else:
            session_data["messages"] = messages_to_save
            
        save_sessions(sessions_db)

        return {
            "response": response_text,
            "audit_trail": final_state.get("audit_trail", []),
            "working_memory": final_state.get("working_memory", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")


@app.get("/api/sessions")
def get_sessions():
    """
    Returns the list of all chat sessions without full message lists to save bandwidth.
    """
    sessions_db = load_sessions()
    summary = []
    for s in sessions_db.get("sessions", []):
        summary.append({
            "id": s["id"],
            "title": s["title"],
            "created_at": s.get("created_at", datetime.utcnow().isoformat())
        })
    return {"sessions": summary}


@app.post("/api/sessions")
def create_session(request: CreateSessionRequest):
    """
    Creates a new chat session.
    """
    import uuid
    session_id = str(uuid.uuid4())
    sessions_db = load_sessions()
    
    new_sess = {
        "id": session_id,
        "title": request.title or "Nouvelle conversation",
        "created_at": datetime.utcnow().isoformat(),
        "messages": []
    }
    
    sessions_db["sessions"].insert(0, new_sess)
    save_sessions(sessions_db)
    return new_sess


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    """
    Returns a single session with its messages.
    """
    sessions_db = load_sessions()
    session_data = next((s for s in sessions_db["sessions"] if s["id"] == session_id), None)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_data


@app.put("/api/sessions/{session_id}")
def rename_session(session_id: str, request: RenameSessionRequest):
    """
    Renames an existing session.
    """
    sessions_db = load_sessions()
    session_data = next((s for s in sessions_db["sessions"] if s["id"] == session_id), None)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data["title"] = request.title
    save_sessions(sessions_db)
    return {"success": True, "session": session_data}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    """
    Deletes a session from the list.
    """
    sessions_db = load_sessions()
    sessions_db["sessions"] = [s for s in sessions_db["sessions"] if s["id"] != session_id]
    save_sessions(sessions_db)
    return {"success": True}


@app.post("/api/sessions/{session_id}/commit")
def commit_session_to_memory(session_id: str):
    """
    Consolidates and extracts learnings/facts from a conversation and commits them to the MPE.
    """
    sessions_db = load_sessions()
    session_data = next((s for s in sessions_db["sessions"] if s["id"] == session_id), None)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
        
    messages = session_data.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="Cannot commit an empty session")
        
    # Format dialogue
    dialogue_parts = []
    for m in messages:
        role = "User" if m["role"] == "user" else "Assistant"
        dialogue_parts.append(f"{role}: {m['content']}")
    dialogue_text = "\n".join(dialogue_parts)
    
    prompt = [
        {
            "role": "system",
            "content": (
                "You are the Knowledge Consolidation engine for Nexus.\n"
                "Analyze the following conversation history and extract any concrete facts, conceptual definitions, lessons, or rules that should be persisted to long-term memory.\n"
                "Only extract key facts or learnings. Ignore general dialogue, greeting messages, or irrelevant meta-questions.\n"
                "For each extracted fact, define a node_id (slug), node_type (e.g. Concept, Fact, Skill, Lesson), and the text statement.\n"
                "Also extract relationships if relevant.\n\n"
                "Respond ONLY with a JSON object:\n"
                "{\n"
                '  "facts": [\n'
                '     {"node_id": "slug", "node_type": "type", "text": "description", "properties": {}}\n'
                '  ],\n'
                '  "relations": [\n'
                '     {"source": "src_id", "target": "tgt_id", "type": "REL_TYPE"}\n'
                '  ]\n'
                "}"
            )
        },
        {"role": "user", "content": dialogue_text}
    ]
    
    try:
        raw_json = llm_client.generate(prompt, max_tokens=2500, response_format={"type": "json_object"})
        data = clean_and_parse_json(raw_json)
        
        facts = data.get("facts", [])
        relations = data.get("relations", [])
        
        committed_facts = []
        committed_relations = []
        
        # Ingest facts
        for f in facts:
            node_id = f.get("node_id")
            node_type = f.get("node_type", "Fact")
            text = f.get("text", "")
            props = f.get("properties", {})
            if node_id and text:
                res = memory.add_fact(
                    node_id=node_id,
                    node_type=node_type,
                    text=text,
                    properties={**props, "committed_from_session": session_id},
                    timestamp=datetime.utcnow(),
                    source=f"session_commit:{session_id}"
                )
                committed_facts.append(f"{node_id} ({node_type})")
                
        # Ingest relations
        for r in relations:
            src = r.get("source")
            tgt = r.get("target")
            rtype = r.get("type", "CONNECTED_TO")
            if src and tgt:
                memory.add_relationship(
                    source_id=src,
                    target_id=tgt,
                    rel_type=rtype,
                    properties={"committed_from_session": session_id},
                    timestamp=datetime.utcnow()
                )
                committed_relations.append(f"{src} --({rtype})--> {tgt}")
                
        return {
            "success": True,
            "facts_committed": committed_facts,
            "relations_committed": committed_relations,
            "message": f"Successfully committed {len(committed_facts)} facts and {len(committed_relations)} relations to MPE."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to consolidate and commit conversation: {str(e)}")

@app.post("/api/facts")
def add_fact(request: FactRequest):
    """
    Ingests a single fact node, executing temporal arbitration checks.
    """
    try:
        timestamp = datetime.fromisoformat(request.timestamp) if request.timestamp else datetime.utcnow()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp format (ISO-8601 required).")

    try:
        res = memory.add_fact(
            node_id=request.node_id,
            node_type=request.node_type,
            text=request.text,
            properties=request.properties,
            timestamp=timestamp,
            source=request.source or "web_governance"
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fact ingestion failed: {str(e)}")

@app.post("/api/relationships")
def add_relationship(request: RelationRequest):
    """
    Injects a semantic link edge between two nodes.
    """
    try:
        memory.add_relationship(
            source_id=request.source_id,
            target_id=request.target_id,
            rel_type=request.rel_type,
            properties=request.properties,
            timestamp=datetime.utcnow()
        )
        return {"success": True, "message": f"Link '{request.source_id}' --({request.rel_type})--> '{request.target_id}' created."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Relationship creation failed: {str(e)}")

@app.delete("/api/facts/{node_id}")
def delete_fact(node_id: str):
    """
    Forced oubli (deletion) of a specific node.
    """
    try:
        memory.graph_store.delete_node(node_id)
        memory.vector_store.delete(node_id)
        return {"success": True, "message": f"Node '{node_id}' deleted from database stores."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

@app.get("/api/graph")
def get_graph_data():
    """
    Returns the complete list of nodes and edges for UI visualization.
    """
    try:
        nodes = graph_store.list_nodes()
        edges = graph_store.list_edges()
        
        # Serialize objects to dictionaries
        serialized_nodes = [
            {
                "id": n.id,
                "type": n.type,
                "properties": n.properties,
                "timestamp": n.timestamp.isoformat()
            } for n in nodes
        ]
        
        serialized_edges = [
            {
                "source": e.source,
                "target": e.target,
                "type": e.type,
                "properties": e.properties,
                "timestamp": e.timestamp.isoformat()
            } for e in edges
        ]
        
        return {
            "nodes": serialized_nodes,
            "edges": serialized_edges
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch graph data: {str(e)}")

@app.get("/api/deficiencies")
def get_deficiencies():
    """
    Identifies missing nodes (nodes that were referenced in edges but have an 'Unknown' type).
    """
    try:
        nodes = graph_store.list_nodes()
        unknown_ids = [n.id for n in nodes if n.type == "Unknown"]
        return {"deficiencies": unknown_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate deficiencies: {str(e)}")

@app.post("/api/distill")
def run_distillation():
    """
    Triggers the Distillation loop manually.
    """
    try:
        res = distill_loop.run_distillation()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Distillation failed: {str(e)}")

@app.post("/api/oubli/lru")
def enforce_lru(request: LRURequest):
    """
    Triggers LRU forgot cleanup based on capacity limits.
    """
    try:
        res = oubli_loop.enforce_lru(max_nodes=request.max_nodes)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LRU cleanup failed: {str(e)}")

@app.post("/api/oubli/decay")
def enforce_decay(request: DecayRequest):
    """
    Triggers age-based temporal decay cleanup.
    """
    try:
        res = oubli_loop.enforce_temporal_decay(max_age_days=request.max_age_days)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decay cleanup failed: {str(e)}")

@app.get("/api/security/ignored")
def get_ignored_vulnerabilities():
    """
    Fetches the current suppressed findings registry from SecureCoder proxying.
    """
    if not SECURECODER_PORT:
        return {"entries": []}
    
    try:
        # Check API response carefully (CWE-252 validation)
        resp = requests.get(f"http://127.0.0.1:{SECURECODER_PORT}/ignored", timeout=3)
        if resp.status_code == 200:
            return resp.json()
        return {"entries": []}
    except Exception:
        # Fallback in case the local SecureCoder api port is offline
        return {"entries": []}


@app.post("/api/distill/communities")
def run_community_summarization():
    """
    Triggers Louvain community detection and LLM community summarization.
    """
    try:
        res = distill_loop.run_community_summarization()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Community summarization failed: {str(e)}")


@app.get("/api/sessions/{session_id}/working_memory")
def get_session_working_memory(session_id: str):
    """
    Retrieves the current working memory associated with the given session.
    """
    config = {"configurable": {"thread_id": f"session_{session_id}"}}
    try:
        lg_state = graph_flow.get_state(config)
        working_mem = lg_state.values.get("working_memory") if lg_state.values else None
        if not working_mem:
            working_mem = {
                "user_profile": "Unknown user",
                "current_tasks": [],
                "scratchpad": "No active notes."
            }
        return {"working_memory": working_mem}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve working memory: {str(e)}")

