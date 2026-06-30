"""
AgentBackend — abstract base for all agent communication backends.

Dependency Inversion: AgentClient depends on this abstraction, not on
concrete OpenAI or Azure clients.

Liskov Substitution: OnlineAgentBackend and OfflineAgentBackend are fully
interchangeable through this interface.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class AgentBackend(ABC):
    """Minimal interface for sending a conversation to an agent backend."""

    @property
    @abstractmethod
    def mode(self) -> str:
        """Return the mode identifier ('online' or 'offline')."""

    @abstractmethod
    def send(self, history: List[Dict[str, Any]]) -> str:
        """
        Send the current conversation history and return the assistant reply.

        Args:
            history: Full conversation as a list of role/content dicts.

        Returns:
            The assistant's response text.
        """
