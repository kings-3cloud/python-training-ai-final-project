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
    "generating quizzes, and tracking progress. Be concise and encouraging. "
    "IMPORTANT: You have tools available — you MUST call them, never just describe calling them. "
    "Rules:\n"
    "- When the user asks for a quiz, call generate_quiz to get the questions.\n"
    "- After the user has answered all quiz questions you MUST:\n"
    "  1. Call score_quiz(answers=[...]) with their answers to get the exact score.\n"
    "     NEVER calculate or guess the score yourself.\n"
    "  2. Call save_progress(topic, score, total) using the integer numbers from score_quiz.\n"
    "- When the user asks to fetch a URL, call fetch_url_content.\n"
    "- Do NOT write 'I will call ...' \u2014 call the tool immediately.\n"
)

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
                return choice.message.content or ""
