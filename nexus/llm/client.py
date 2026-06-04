import os
from typing import List, Dict, Any, Optional
from openai import OpenAI

class LLMClient:
    def __init__(self, mock: bool = False, mock_responses: Optional[List[str]] = None):
        """
        Initialize the LLMClient.
        If mock is True, or if the API keys are missing in the environment,
        falls back to a mock mode utilizing the list of mock_responses.
        """
        self.mock = mock
        self.mock_index = 0
        self._mock_responses = mock_responses or []
        self.client = None

        if not self.mock:
            # Check environment variables
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("MINIMAX_API_KEY") or os.getenv("MINIMAX_KEY")
            if not api_key:
                # Silent fallback to mock to prevent crashes during dry runs
                self.mock = True
                self._mock_responses = ["Mock LLM: API key missing, falling back to static stub response."]
            else:
                # Pick up variables automatically (OPENAI_API_KEY and OPENAI_BASE_URL)
                self.client = OpenAI()

    @property
    def mock_responses(self) -> List[str]:
        return self._mock_responses

    @mock_responses.setter
    def mock_responses(self, val: List[str]):
        self._mock_responses = val
        self.mock_index = 0

    def generate(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        response_format: Optional[Dict[str, Any]] = None,
        user: str = "nexus_system_user"
    ) -> str:
        """
        Generate text completion from messages.
        """
        if model is None:
            model = os.getenv("MINIMAX_MODEL", "MiniMax-M3")

        if self.mock:
            if self.mock_responses:
                response = self.mock_responses[self.mock_index % len(self.mock_responses)]
                self.mock_index += 1
                return response
            return '{"sufficiency_score": 1.0, "reasoning": "Mock: sufficient context."}'

        extra_kwargs = {}
        if response_format:
            extra_kwargs["response_format"] = response_format

        def clean_content(text: str) -> str:
            if not text:
                return text
            import re
            # Remove thinking blocks (<think>...</think>)
            cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
            # If JSON is expected, extract from markdown codeblocks
            is_json = response_format and response_format.get("type") in ("json_object", "json_schema")
            if is_json:
                codeblock_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
                if codeblock_match:
                    cleaned = codeblock_match.group(1)
            return cleaned.strip()

        try:
            resp = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                user=user,
                **extra_kwargs
            )
            message = resp.choices[0].message
            # Check model refusal before accessing content (CWE-252)
            if hasattr(message, "refusal") and message.refusal:
                raise RuntimeError(f"MiniMax request refused by model: {message.refusal}")
            return clean_content(message.content)
        except Exception as e:
            # If response_format was used, fallback to request without it
            if response_format and "response_format" in extra_kwargs:
                try:
                    import sys
                    sys.stderr.write(f"[WARNING] API failed with response_format, retrying without it. Error: {e}\n")
                    del extra_kwargs["response_format"]
                    resp = self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        user=user,
                        **extra_kwargs
                    )
                    message = resp.choices[0].message
                    if hasattr(message, "refusal") and message.refusal:
                        raise RuntimeError(f"MiniMax request refused by model: {message.refusal}")
                    return clean_content(message.content)
                except Exception as retry_err:
                    raise RuntimeError(f"MiniMax API call failed on fallback retry: {str(retry_err)}")
            # In case of API failure, log and raise
            raise RuntimeError(f"MiniMax API call failed: {str(e)}")
