import json
from typing import Dict, Any, List
from nexus.llm.client import LLMClient

def evaluate_sufficiency(query: str, context: str, llm_client: LLMClient) -> Dict[str, Any]:
    """
    Evaluates whether the retrieved context contains enough facts to resolve the user's query.
    Returns a dictionary containing:
    - 'sufficiency_score': float between 0.0 and 1.0
    - 'reasoning': text explanation
    - 'missing_knowledge': list of missing elements
    """
    prompt = [
        {
            "role": "system",
            "content": (
                "You are the Diagnostic Loop of the Nexus Memory System.\n"
                "Evaluate if the retrieved context contains sufficient, clear, and relevant factual details "
                "to fully and accurately answer the user query.\n"
                "Respond ONLY with a JSON object containing:\n"
                "{\n"
                '  "sufficiency_score": float (between 0.0 and 1.0),\n'
                '  "reasoning": "brief explanation",\n'
                '  "missing_knowledge": ["list of specific details or facts missing in context, or empty list"]\n'
                "}"
            )
        },
        {
            "role": "user",
            "content": f"User Query: {query}\n\nRetrieved Context:\n{context}"
        }
    ]

    try:
        raw_json = llm_client.generate(prompt, max_tokens=1500)
        json_str = raw_json.strip()
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                lines = lines[1:-1]
            json_str = "\n".join(lines).strip()

        data = json.loads(json_str)
        return {
            "sufficiency_score": float(data.get("sufficiency_score", 0.5)),
            "reasoning": data.get("reasoning", ""),
            "missing_knowledge": data.get("missing_knowledge", [])
        }
    except Exception:
        return {
            "sufficiency_score": 0.5,
            "reasoning": "Failed to parse diagnostic output JSON.",
            "missing_knowledge": ["Unknown missing facts"]
        }
