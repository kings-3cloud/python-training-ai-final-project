# MCP server entry point: registers and serves the three study-assistant tools via MCP.

import sys
from pathlib import Path

# Ensure study-assistant/ is on the path so `mcp_server.*` imports resolve
# whether the server is launched via `python -m mcp_server.server` or `mcp dev server.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP

from mcp_server.tools.fetch_url import fetch_url_content
from mcp_server.tools.quiz import generate_quiz
from mcp_server.tools.progress import save_progress

mcp = FastMCP("study-assistant")


@mcp.tool()
def fetch_url_content_tool(url: str) -> str:
    """
    Fetch and return the text content of a web page or PDF.

    Args:
        url: The fully-qualified URL to retrieve
             (e.g. "https://example.com" or "https://example.com/doc.pdf").

    Returns:
        The extracted plain text, truncated to 4 000 characters,
        or an error string if the request fails.
    """
    return fetch_url_content(url)


@mcp.tool()
def generate_quiz_tool(topic: str, num_questions: int = 5) -> list[dict]:
    """
    Generate a multiple-choice quiz on a given study topic.

    Args:
        topic:         The subject to be quizzed on
                       (e.g. "Python list comprehensions").
        num_questions: How many questions to generate (default 5).

    Returns:
        A list of dicts, each with keys:
        - question (str)
        - options  (list[str])  — four choices labelled A–D
        - answer   (str)        — the correct option label
        Returns an empty list if generation fails.
    """
    return generate_quiz(topic, num_questions)


@mcp.tool()
def save_progress_tool(topic: str, score: int, total: int) -> str:
    """
    Persist a quiz result to the study progress log.

    Args:
        topic: The study topic (e.g. "Python Basics").
        score: Number of correct answers achieved.
        total: Total number of questions in the quiz.

    Returns:
        A confirmation string such as "Saved: 4/5 on Python Basics",
        or an error string if the write fails.
    """
    return save_progress(topic, score, total)


if __name__ == "__main__":
    mcp.run(transport="stdio")
