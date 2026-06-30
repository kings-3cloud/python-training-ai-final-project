"""
factories.py — constructs fully-wired AgentClient instances.

Single Responsibility: all object construction and dependency wiring lives
here, keeping app.py and agent_client.py free of configuration logic.

Dependency Inversion: app.py calls create_agent_client() and receives an
AgentClient — it never touches OpenAI, Azure, or tool imports directly.

Open/Closed: adding a new mode means adding a new _build_*_backend()
function and a branch in create_agent_client(), without touching
AgentClient, app.py, or the backends themselves.
"""
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Ensure study-assistant/ is on sys.path so mcp_server.* imports resolve
# regardless of which directory the Flask app is launched from.
_STUDY_ROOT = Path(__file__).resolve().parent.parent
if str(_STUDY_ROOT) not in sys.path:
    sys.path.insert(0, str(_STUDY_ROOT))

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)


def create_agent_client(mode: str = "online"):
    """
    Build and return a fully-wired AgentClient for the given mode.

    Args:
        mode: "online" or "offline"

    Returns:
        AgentClient ready to use.

    Raises:
        ValueError: for unknown mode or missing required env vars.
    """
    from agent_client import AgentClient

    if mode == "online":
        backend = _build_online_backend()
    elif mode == "offline":
        backend = _build_offline_backend()
    else:
        raise ValueError(f"Unknown mode: {mode!r}. Must be 'online' or 'offline'.")

    return AgentClient(backend=backend)


# ── Backend builders ──────────────────────────────────────────────────────────

def _build_online_backend():
    """Wire up an OnlineAgentBackend with Foundry credentials."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from backends.online import OnlineAgentBackend

    endpoint = os.getenv("AGENT_ENDPOINT", "").replace("/responses", "").rstrip("/")
    if not endpoint:
        raise ValueError("AGENT_ENDPOINT is not set in environment variables.")

    client = OpenAI(
        api_key=get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://ai.azure.com/.default",
        ),
        base_url=endpoint,
        default_query={"api-version": "v1"},
    )
    return OnlineAgentBackend(client=client)


def _build_offline_backend():
    """Wire up an OfflineAgentBackend with a populated ToolRegistry."""
    from backends.offline import OfflineAgentBackend, ToolRegistry
    from mcp_server.tools.fetch_url import fetch_url_content
    from mcp_server.tools.progress import save_progress

    endpoint = os.getenv("OFFLINE_ENDPOINT", "http://localhost:11434/v1").rstrip("/")
    api_key = os.getenv("OFFLINE_API_KEY", "ollama")
    model = os.getenv("OFFLINE_MODEL", "llama3.2")

    client = OpenAI(base_url=endpoint, api_key=api_key)

    # Populate the registry — add registry.register() calls here for new tools
    registry = ToolRegistry()
    registry.register("fetch_url_content", fetch_url_content)
    registry.register(
        "save_progress",
        lambda topic, score, total: save_progress(topic, int(score), int(total))
    )
    registry.register(
        "generate_quiz",
        lambda topic, num_questions=5: _generate_quiz_local(
            client, model, topic, int(num_questions)
        )
    )

    return OfflineAgentBackend(client=client, model=model, registry=registry)


def _generate_quiz_local(
    client: OpenAI, model: str, topic: str, num_questions: int = 5
) -> str:
    """Generate quiz questions using the local model directly."""
    prompt = (
        f"Create {num_questions} multiple-choice questions about: {topic}. "
        "Return ONLY a raw JSON array — no markdown fences, no explanation. "
        'Each item: {"question": "...", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "answer": "A"}'
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a quiz generator. Output only a raw JSON array."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return resp.choices[0].message.content or "[]"
    except Exception as exc:
        logger.error("Offline quiz generation failed: %s", exc)
        return f"Error generating quiz: {exc}"
