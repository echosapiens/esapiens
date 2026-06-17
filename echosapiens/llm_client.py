"""
llm_client.py - Budget-Model OpenAI-Compatible Verification Client

Custom client wrapper for OpenAI-compatible budget model execution.
Features robust structured JSON validation and schema injection.
"""

import json
from typing import TypeVar

import structlog
from openai import OpenAI
from pydantic import BaseModel

from .config import Settings

logger = structlog.get_logger()

# TypeVar bound to BaseModel so call_structured returns the *exact* schema
# subtype it was given, not a bare BaseModel.
T = TypeVar("T", bound=BaseModel)


class BudgetLLMClient:
    """Custom client wrapper for OpenAI-compatible budget model execution.

    Features robust structured JSON validation and schema injection. The
    client injects the Pydantic response schema into the system prompt and
    forces ``response_format=json_object`` so the model returns parseable JSON.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the OpenAI-compatible chat client.

        Args:
            settings: System settings containing LLM API key, base URL, and
                model parameters.
        """
        self.settings = settings
        self.client = OpenAI(
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
        )

    def call_structured(
        self, messages: list[dict[str, str]], response_schema: type[T]
    ) -> T:
        """Enforce structured JSON extraction conforming strictly to validation models.

        Injects the JSON schema derived from ``response_schema`` as a system
        message, requests a ``json_object`` response, then validates and
        marshalls the output directly into the targeted Pydantic model.

        Args:
            messages: Conversation messages (without the schema system prompt;
                the schema instruction is prepended automatically).
            response_schema: Pydantic model class the response must conform to.

        Returns:
            A validated instance of ``response_schema``.

        Raises:
            pydantic.ValidationError: If the model output fails schema validation.
            openai.OpenAIError: On upstream API failures.
        """
        system_instruction = (
            f"You are a scientific computational agent. Return JSON matching this schema: "
            f"{json.dumps(response_schema.model_json_schema())}"
        )

        # Inject validation schema at index 0
        messages_with_schema = [{"role": "system", "content": system_instruction}] + messages

        logger.info("llm_call_initiated", model=self.settings.llm_model)

        response = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=messages_with_schema,
            response_format={"type": "json_object"},
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
        )

        content = response.choices[0].message.content
        logger.debug("llm_call_completed", response_length=len(content or ""))

        # Validates and marshalls output directly into targeted Pydantic Models
        return response_schema.model_validate_json(content)
