"""
OnlineAgentBackend — routes messages to a Foundry-hosted model via the Chat
Completions API with local tool execution.

Switching from responses.create() to chat.completions.create() lets us run
tools (fetch_url_content, generate_quiz, score_quiz, save_progress) locally,
which is required for save_progress to write to the local progress file.
"""
import logging
from typing import Any, Dict, List

from openai import OpenAI, RateLimitError, APIStatusError

from .base import AgentBackend, TransientBackendError

logger = logging.getLogger(__name__)


class OnlineAgentBackend(AgentBackend):
    """Agentic Chat Completions loop against the Foundry endpoint with local tool execution."""

    def __init__(self, client: OpenAI, model: str, registry) -> None:
        self._client = client
        self._model = model
        self._registry = registry

    @property
    def mode(self) -> str:
        return "online"

    def send(self, history: List[Dict[str, Any]]) -> str:
        # Import shared schemas and prompt from offline to avoid duplication.
        from .offline import TOOL_SCHEMAS, _SYSTEM_PROMPT

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT}
        ] + list(history)

        while True:
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                    temperature=0.7,
                )
            except RateLimitError:
                raise TransientBackendError(
                    "⚠️ The model is currently rate-limited (HTTP 429). "
                    "Please wait a moment and try again."
                )
            except APIStatusError as exc:
                logger.error("API error in online backend: %s", exc)
                raise TransientBackendError(
                    f"⚠️ The model returned an error ({exc.status_code}): {exc.message}"
                )

            choice = response.choices[0]

            if choice.finish_reason == "tool_calls":
                messages.append(choice.message)
                for tc in choice.message.tool_calls:
                    result = self._registry.execute(tc.function.name, tc.function.arguments)
                    logger.info("Tool %s → %s", tc.function.name, str(result)[:120])
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                return choice.message.content or ""
