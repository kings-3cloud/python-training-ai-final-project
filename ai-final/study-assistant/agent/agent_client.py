"""
Agent Client - Handles interaction with the Microsoft Foundry Study Assistant agent.

Connects to the agent published in Microsoft Foundry using the OpenAI Responses API
with DefaultAzureCredential authentication. Maintains multi-turn conversation history
across fetch, quiz, and progress-tracking interactions.
"""

import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)


class AgentClient:
    """Client for interacting with the Foundry-hosted Personal Study Assistant agent."""

    def __init__(self):
        """Initialize the agent client with authentication and endpoint."""
        self.agent_endpoint = os.getenv("AGENT_ENDPOINT", "").replace("/responses", "")
        if not self.agent_endpoint:
            raise ValueError("AGENT_ENDPOINT not found in environment variables")

        # Create OpenAI client authenticated with Azure credentials
        self.client = OpenAI(
            api_key=get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://ai.azure.com/.default",
            ),
            base_url=self.agent_endpoint,
            default_query={"api-version": "v1"},
        )

        # Maintain conversation history (last 5 exchanges)
        self.conversation_history: List[Dict[str, Any]] = []
        self.max_history = 5

    def send_message(self, user_message: str) -> str:
        """
        Send a message to the agent and return the response.

        Args:
            user_message: The text message from the user.

        Returns:
            The agent's response text, or an error string on failure.
        """
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        try:
            assistant_message = ""

            response = self.client.responses.create(
                input=self.conversation_history
            )
            assistant_message = response.output_text

            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message,
            })

            # Trim to max_history exchanges (one exchange = 1 user + 1 assistant)
            user_message_count = sum(
                1 for msg in self.conversation_history
                if isinstance(msg, dict) and msg.get("role") == "user"
            )

            while user_message_count > self.max_history:
                for i, msg in enumerate(self.conversation_history):
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        self.conversation_history.pop(i)
                        if (i < len(self.conversation_history) and
                                self.conversation_history[i].get("role") == "assistant"):
                            self.conversation_history.pop(i)
                        user_message_count -= 1
                        break

            return assistant_message

        except Exception:
            logger.exception("Error communicating with agent")
            return "An internal error occurred while communicating with the agent."

    def reset_session(self):
        """Clear the conversation history to start a fresh study session."""
        self.conversation_history = []
