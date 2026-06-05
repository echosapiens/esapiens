import json
from typing import Optional
from openai import OpenAI
from app.config import settings


class OpenRouterClient:
    """Wrapper around OpenAI client for OpenRouter API calls."""

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = "https://openrouter.ai/api/v1"
        self._client = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def chat_completion(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> dict:
        """Send a chat completion request to OpenRouter."""
        try:
            kwargs = {
                "model": model or settings.DEFAULT_LLM_MODEL,
                "messages": messages,
                "temperature": temperature,
            }

            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content

            return {"content": content, "model": response.model}

        except Exception as e:
            return {"error": str(e)}