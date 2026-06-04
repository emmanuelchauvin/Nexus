import os
import sys
import glob
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pypdf import PdfReader
from nexus.memory.networkx_store import NetworkXGraphStore
from nexus.memory.chromadb_store import ChromaDBStore
from nexus.memory.hybrid import HybridMemory
from nexus.llm.client import LLMClient

# Load env variables (required if we use LLM-based features)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"), override=True)

# Workspace directories for database files
storage_dir = os.path.join(os.getcwd(), ".nexus_storage")
os.makedirs(storage_dir, exist_ok=True)

graph_path = os.path.join(storage_dir, "graph.json")
chroma_path = os.path.join(storage_dir, "chromadb")

# Instantiate stores & coordinator
graph_store = NetworkXGraphStore(filepath=graph_path)
vector_store = ChromaDBStore(persist_directory=chroma_path)
memory = HybridMemory(graph_store=graph_store, vector_store=vector_store)

def chunk_text(text: str, chunk_size: int = 5000, overlap: int = 500):
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
        # If we reached the end of the text, stop
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
        data = json.loads(raw_resp)
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

def ingest_pdf(pdf_path: str) -> bool:
    """
    Extracts text from a single PDF file, chunks it, and ingests it into Nexus.
    """
    filename = os.path.basename(pdf_path)
    print(f"\nIngesting file: {filename}...")
    
    try:
        reader = PdfReader(pdf_path)
        full_text = ""
        total_pages = len(reader.pages)
        
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_text += f"\n--- Page {page_num + 1} ---\n" + text
        
        if not full_text.strip():
            print(f"[WARNING] No text could be extracted from {filename}. (It might be scanned or empty)")
            return False
            
        doc_id = f"doc_{filename.replace('.', '_').replace(' ', '_')}"
        
        # 1. Add Document Node to the Graph
        memory.add_fact(
            node_id=doc_id,
            node_type="Document",
            text=f"Document PDF: {filename}",
            properties={
                "filename": filename,
                "total_pages": total_pages,
                "path": pdf_path,
                "ingested_at": datetime.utcnow().isoformat()
            },
            timestamp=datetime.utcnow(),
            source="pdf_ingestion_script"
        )
        
        # 2. Chunk text and add Chunk Nodes
        chunks = chunk_text(full_text)
        print(f"-> Extracted {len(chunks)} raw windows from {total_pages} pages. Processing with LLM...")
        
        llm_client = LLMClient()
        
        last_chunk_id = None
        for i, raw_chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            
            # Process with LLM to get Markdown summary and Graph entities/triplets
            llm_data = llm_chunk_summarize(raw_chunk, llm_client)
            summary_markdown = llm_data.get("summary_markdown", raw_chunk)
            entities = llm_data.get("entities", [])
            triplets = llm_data.get("triplets", [])
            
            # Add chunk fact to hybrid memory (stores in VectorStore and GraphStore)
            memory.add_fact(
                node_id=chunk_id,
                node_type="DocumentChunk",
                text=summary_markdown,
                properties={
                    "parent_document": doc_id,
                    "chunk_index": i,
                    "filename": filename
                },
                timestamp=datetime.utcnow(),
                source=f"pdf_ingestion_script:{filename}"
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
                        source=f"pdf_llm_extractor:{filename}"
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
            
        print(f"[SUCCESS] Successfully ingested {filename} ({len(chunks)} chunks).")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error ingesting {filename}: {str(e)}")
        return False

def main():
    # Target directory for PDF files
    pdf_dir = os.path.join(os.getcwd(), "data", "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    
    pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
    # Exclude test.pdf
    pdf_files = [f for f in pdf_files if os.path.basename(f) != "test.pdf"]
    
    if not pdf_files:
        print(f"\nNo PDF files found in: {pdf_dir}")
        print("Please place your PDF documents in that folder and run this script again.")
        return
        
    print(f"Found {len(pdf_files)} PDF(s) to process (excluding 'test.pdf').")
    success_count = 0
    for pdf_file in pdf_files:
        if ingest_pdf(pdf_file):
            success_count += 1
            
    print(f"\nDone! Ingested {success_count}/{len(pdf_files)} PDF documents successfully.")

if __name__ == "__main__":
    main()
