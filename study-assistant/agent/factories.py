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
import functools
import json as _json
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

# Configurable default question count — reads the same env var as quiz.py.
_QUIZ_NUM_QUESTIONS: int = max(1, int(os.getenv("QUIZ_NUM_QUESTIONS", "5")))


# ---------------------------------------------------------------------------
# Quiz state — updated every time generate_quiz is called so that score_quiz
# can grade answers deterministically instead of relying on LLM reasoning.
# ---------------------------------------------------------------------------
_active_quiz_answers: list = []


def _quiz_state_wrapper(fn):
    """Wrap a quiz-generation callable to capture the correct answers."""
    @functools.wraps(fn)
    def _wrapper(*args, **kwargs):
        global _active_quiz_answers
        result = fn(*args, **kwargs)
        try:
            if isinstance(result, list):
                questions = result
                # Normalise to JSON string so the LLM always receives the same format
                serialised = _json.dumps(questions)
            else:
                raw = str(result).strip()
                # Strip optional markdown code fences from LLM output
                if raw.startswith("```"):
                    raw = raw.split("```", 2)[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                    raw = raw.rsplit("```", 1)[0].strip()
                questions = _json.loads(raw)
                serialised = result
            _active_quiz_answers = [
                str(q.get("answer", "")).strip().upper() for q in questions
            ]
            return serialised
        except Exception as exc:
            logger.warning("Could not store quiz answers for scoring: %s", exc)
            return result
    return _wrapper


def _score_quiz(answers) -> str:
    """Compare the user's answers to the stored correct answers. Returns 'X/Y'."""
    if not _active_quiz_answers:
        return "Error: no active quiz. Please call generate_quiz first."
    if isinstance(answers, str):
        user = [a.strip().upper() for a in answers.replace(",", " ").split() if a.strip()]
    else:
        user = [str(a).strip().upper() for a in answers]
    total = len(_active_quiz_answers)
    correct = sum(
        1 for i, a in enumerate(user[:total]) if a == _active_quiz_answers[i]
    )
    return f"{correct}/{total}"


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
    """Wire up an OnlineAgentBackend with Foundry Chat Completions and local tools."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from backends.online import OnlineAgentBackend
    from backends.offline import ToolRegistry
    from mcp_server.tools.fetch_url import fetch_url_content
    from mcp_server.tools.progress import save_progress
    from mcp_server.tools.quiz import generate_quiz as _generate_quiz_azure

    endpoint = os.getenv("AGENT_ENDPOINT", "").replace("/responses", "").rstrip("/")
    if not endpoint:
        raise ValueError("AGENT_ENDPOINT is not set in environment variables.")

    model = os.getenv("ONLINE_MODEL", "gpt-4o")

    client = OpenAI(
        api_key=get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://ai.azure.com/.default",
        ),
        base_url=endpoint,
        default_query={"api-version": "v1"},
    )

    registry = ToolRegistry()
    registry.register("fetch_url_content", fetch_url_content)
    registry.register(
        "save_progress",
        lambda topic, score, total: save_progress(topic, int(score), int(total))
    )
    registry.register(
        "generate_quiz",
        _quiz_state_wrapper(
            lambda topic, num_questions=_QUIZ_NUM_QUESTIONS: _generate_quiz_azure(topic, int(num_questions))
        )
    )
    registry.register("score_quiz", _score_quiz)

    return OnlineAgentBackend(client=client, model=model, registry=registry)


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
        _quiz_state_wrapper(
            lambda topic, num_questions=_QUIZ_NUM_QUESTIONS: _generate_quiz_local(
                client, model, topic, int(num_questions)
            )
        )
    )
    registry.register("score_quiz", _score_quiz)

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
