"""
OnlineAgentBackend — routes messages to a Foundry-hosted agent via the
OpenAI Responses API, authenticated with DefaultAzureCredential.

Single Responsibility: only handles Foundry API communication.
"""
import logging
from typing import Any, Dict, List

from openai import OpenAI

from .base import AgentBackend

logger = logging.getLogger(__name__)


class OnlineAgentBackend(AgentBackend):
    """Sends conversation history to a Foundry-hosted agent and returns its reply."""

    def __init__(self, client: OpenAI) -> None:
        self._client = client

    @property
    def mode(self) -> str:
        return "online"

    def send(self, history: List[Dict[str, Any]]) -> str:
        response = self._client.responses.create(input=history)
        return response.output_text
