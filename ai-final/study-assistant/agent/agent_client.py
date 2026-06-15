"""
AgentClient — manages conversation history and delegates to an AgentBackend.

Single Responsibility: this class only manages session state (conversation
history trimming and reset). All communication logic lives in the backend.

Dependency Inversion: depends on the AgentBackend abstraction, not on any
concrete OpenAI client or Azure credential.
"""
import logging
from typing import Any, Dict, List

from backends.base import AgentBackend

logger = logging.getLogger(__name__)


class AgentClient:
    """Manages conversation history and delegates message sending to a backend."""

    def __init__(self, backend: AgentBackend, max_history: int = 5) -> None:
        self._backend = backend
        self.max_history = max_history
        self.conversation_history: List[Dict[str, Any]] = []

    @property
    def mode(self) -> str:
        """Return the current backend mode identifier."""
        return self._backend.mode

    def send_message(self, user_message: str) -> str:
        """
        Append the user message to history, send to the backend, return the reply.

        Returns:
            The assistant's response text, or an error string on failure.
        """
        self.conversation_history.append({"role": "user", "content": user_message})

        try:
            reply = self._backend.send(self.conversation_history)
            self.conversation_history.append({"role": "assistant", "content": reply})
            self._trim_history()
            return reply
        except Exception:
            logger.exception("Error communicating with agent backend")
            return "An internal error occurred while communicating with the agent."

    def reset_session(self) -> None:
        """Clear conversation history to start a fresh study session."""
        self.conversation_history = []

    def _trim_history(self) -> None:
        """Remove oldest exchanges when history exceeds max_history."""
        user_count = sum(
            1 for m in self.conversation_history
            if isinstance(m, dict) and m.get("role") == "user"
        )
        while user_count > self.max_history:
            for i, msg in enumerate(self.conversation_history):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    self.conversation_history.pop(i)
                    if (
                        i < len(self.conversation_history)
                        and self.conversation_history[i].get("role") == "assistant"
                    ):
                        self.conversation_history.pop(i)
                    user_count -= 1
                    break

