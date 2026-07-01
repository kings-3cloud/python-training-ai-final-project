"""
OfflineAgentBackend — local agentic loop using Chat Completions API with
native tool calling.

Single Responsibility: manages the local model loop and tool dispatch.

Open/Closed: ToolRegistry allows new tools to be registered without
modifying the execution logic.

Supported models: llama3.1, llama3.2, mistral, qwen2.5, gemma3
NOT supported:    llama3 (3.0), phi3-mini  (no tool calling)
"""
import json
import logging
from typing import Any, Callable, Dict, List

from openai import OpenAI, RateLimitError, APIStatusError

from .base import AgentBackend, TransientBackendError

logger = logging.getLogger(__name__)

ToolHandler = Callable[..., str]

_SYSTEM_PROMPT = (
    "You are a Personal Study Assistant. Help the user learn by fetching content, "
    "generating quizzes, and tracking progress. Be concise and encouraging.\n"
    "CRITICAL RULES — follow these without exception:\n"
    "1. NEVER send a plain-text message that only describes what you are about to do. "
    "   If a tool call is needed, make it your FIRST action \u2014 not a text announcement.\n"
    "2. When the user provides a URL, your very first action MUST be a fetch_url_content tool call.\n"
    "3. When the user asks for a quiz, immediately call generate_quiz.\n"
    "4. After the user answers all quiz questions:\n"
    "   a. Call score_quiz(answers=[...]) \u2014 NEVER estimate or guess the score.\n"
    "   b. Then call save_progress(topic, score, total) with the numbers from score_quiz.\n"
    "5. Only respond with text AFTER all required tool calls are complete.\n"
)

# Phrases that indicate the model announced an upcoming tool call instead of making one.
_PENDING_TOOL_PHRASES = frozenset({
    "one moment", "just a moment", "please wait", "stand by",
    "fetching", "let me fetch", "i'll fetch", "i will fetch",
    "gathering", "let me gather", "i'll gather",
    "looking that up", "i'll look", "let me look",
    "pulling up", "retrieving", "i'll retrieve",
})

# Maximum number of times the loop will nudge the model before returning its text as-is.
_MAX_NUDGES = 2


def _looks_like_announcement(text: str) -> bool:
    """Return True when the response is a short preamble announcing an upcoming tool call."""
    if len(text) > 400:  # genuine content is typically longer
        return False
    lower = text.lower()
    return any(phrase in lower for phrase in _PENDING_TOOL_PHRASES)


# OpenAI function-calling schema for all registered tools.
# Add a new entry here when a new tool is added to the registry.
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_url_content",
            "description": "Fetch and return the plain-text content of a web page or PDF URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Fully-qualified URL to fetch"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_quiz",
            "description": "Generate multiple-choice quiz questions on a topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The subject to quiz on"},
                    "num_questions": {"type": "integer", "description": "Number of questions (default 5)"}
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_progress",
            "description": "Save a quiz result to the study progress log.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "score": {"type": "integer", "description": "Number of correct answers"},
                    "total": {"type": "integer", "description": "Total number of questions"}
                },
                "required": ["topic", "score", "total"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "score_quiz",
            "description": (
                "Grade the user's answers for the current quiz. "
                "Returns the exact score as 'X/Y'. "
                "Always call this after the user has answered all questions "
                "\u2014 never guess or calculate the score yourself."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "User's answer letters in question order, e.g. ['A', 'C', 'B', 'D', 'A']"
                    }
                },
                "required": ["answers"]
            }
        }
    }
]


class ToolRegistry:
    """
    Registry of callable tool handlers.

    Open/Closed: new tools are registered via register() without modifying
    the execute() dispatch logic.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        """Register a callable handler under the given tool name."""
        self._handlers[name] = handler

    def execute(self, name: str, arguments_json: str) -> str:
        """Parse JSON arguments and call the named tool. Returns a string result."""
        try:
            args: Dict[str, Any] = json.loads(arguments_json)
        except json.JSONDecodeError:
            return f"Error: invalid JSON arguments for tool '{name}'"

        handler = self._handlers.get(name)
        if handler is None:
            return f"Error: unknown tool '{name}'"

        try:
            return str(handler(**args))
        except Exception as exc:
            logger.error("Tool execution error (%s): %s", name, exc)
            return f"Error executing {name}: {exc}"


class OfflineAgentBackend(AgentBackend):
    """
    Agentic loop over a local OpenAI-compatible model.

    Sends the conversation to the model with tool schemas, executes any
    requested tool calls via the injected ToolRegistry, and loops until
    the model returns a final text response.
    """

    def __init__(self, client: OpenAI, model: str, registry: ToolRegistry) -> None:
        self._client = client
        self._model = model
        self._registry = registry

    @property
    def mode(self) -> str:
        return "offline"

    def send(self, history: List[Dict[str, Any]]) -> str:
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT}
        ] + list(history)

        nudge_count = 0
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
                    "⚠️ The local model is rate-limited. "
                    "Please wait a moment and try again."
                )
            except APIStatusError as exc:
                logger.error("API error in offline backend: %s", exc)
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
                content = choice.message.content or ""
                if nudge_count < _MAX_NUDGES and _looks_like_announcement(content):
                    nudge_count += 1
                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "system",
                        "content": "Call the appropriate tool now. Do not generate a text response first.",
                    })
                else:
                    return content
