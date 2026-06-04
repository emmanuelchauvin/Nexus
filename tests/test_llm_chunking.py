import json
from nexus.llm.client import LLMClient
from scripts.ingest_pdfs import llm_chunk_summarize

def test_llm_chunking_success():
    """
    Test that llm_chunk_summarize correctly parses a valid JSON response from the LLM.
    """
    mock_json = {
        "summary_markdown": "## Dynamic Agent Memory\n\n* Memory should be dynamic.",
        "entities": [
            {"id": "dynamic_memory", "type": "Concept", "text": "Memory that evolves over time."}
        ],
        "triplets": [
            {"source": "dynamic_memory", "target": "agent", "type": "BELONGS_TO"}
        ]
    }
    
    # Initialize a mock LLMClient with the JSON response
    llm_client = LLMClient(mock=True, mock_responses=[json.dumps(mock_json)])
    
    result = llm_chunk_summarize("raw text chunk", llm_client)
    
    assert result["summary_markdown"] == "## Dynamic Agent Memory\n\n* Memory should be dynamic."
    assert len(result["entities"]) == 1
    assert result["entities"][0]["id"] == "dynamic_memory"
    assert len(result["triplets"]) == 1
    assert result["triplets"][0]["type"] == "BELONGS_TO"

def test_llm_chunking_fallback():
    """
    Test that llm_chunk_summarize falls back to raw text if the LLM response is not valid JSON.
    """
    # LLM returns a non-JSON string
    llm_client = LLMClient(mock=True, mock_responses=["This is not JSON"])
    
    raw_text = "This is some raw academic text."
    result = llm_chunk_summarize(raw_text, llm_client)
    
    assert result["summary_markdown"] == raw_text
    assert result["entities"] == []
    assert result["triplets"] == []
