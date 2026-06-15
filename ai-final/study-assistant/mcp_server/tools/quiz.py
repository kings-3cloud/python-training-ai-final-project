# generate_quiz tool: generates quiz questions from supplied study content.

import json
import os
import logging
from typing import Any

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a quiz generator. "
    "Return a JSON array of {question, options: [A,B,C,D], answer} objects. "
    "Output only the raw JSON array — no markdown, no explanation."
)


def _make_client() -> OpenAI:
    """Build an OpenAI client authenticated with DefaultAzureCredential."""
    endpoint = os.getenv("AGENT_ENDPOINT", "").replace("/responses", "").rstrip("/")
    if not endpoint:
        raise ValueError("AGENT_ENDPOINT is not set in environment variables.")

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://ai.azure.com/.default",
    )
    return OpenAI(
        api_key=token_provider,
        base_url=endpoint,
        default_query={"api-version": "v1"},
    )


def generate_quiz(topic: str, num_questions: int = 5) -> list[dict[str, Any]]:
    """
    Generate a multiple-choice quiz on *topic* with *num_questions* questions.

    Returns a list of dicts, each with keys:
        question (str), options (list[str]), answer (str)

    Returns an empty list and logs the error on failure.
    """
    try:
        client = _make_client()
        user_prompt = (
            f"Create {num_questions} multiple-choice questions about: {topic}. "
            "Each question must have exactly 4 options labelled A, B, C, D."
        )

        response = client.chat.completions.create(
            model="gpt-4o",  # model name is ignored by Foundry; the agent endpoint selects the deployed model
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )

        raw = response.choices[0].message.content or ""

        # Strip optional markdown fences (```json ... ```)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()

        quiz: list[dict[str, Any]] = json.loads(raw)
        return quiz

    except json.JSONDecodeError as e:
        logger.error("Failed to parse quiz JSON: %s", e)
        return []
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        return []
    except Exception as e:
        logger.error("Unexpected error in generate_quiz: %s", e)
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_topic = "Python list comprehensions"
    print(f"Generating quiz on: {test_topic!r}")
    questions = generate_quiz(test_topic, num_questions=3)
    if questions:
        for i, q in enumerate(questions, 1):
            print(f"\nQ{i}: {q.get('question')}")
            for opt in q.get("options", []):
                print(f"   {opt}")
            print(f"   Answer: {q.get('answer')}")
    else:
        print("No questions returned — check logs for errors.")
