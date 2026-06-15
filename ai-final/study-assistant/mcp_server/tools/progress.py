# save_progress tool: persists a user's quiz score and topic to data/progress.json.

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Resolve data/progress.json relative to this file's location:
# mcp_server/tools/progress.py → ../../data/progress.json
_DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "progress.json"


def save_progress(topic: str, score: int, total: int) -> str:
    """
    Append a quiz result to data/progress.json and return a summary string.

    Args:
        topic:  The study topic (e.g. "Python Basics").
        score:  Number of correct answers.
        total:  Total number of questions.

    Returns:
        A summary string, e.g. "Saved: 4/5 on Python Basics".
        Returns an error string instead of raising on failure.
    """
    entry = {
        "topic": topic,
        "score": score,
        "total": total,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        # Read existing records (handle missing or empty file)
        if _DATA_FILE.exists() and _DATA_FILE.stat().st_size > 0:
            with _DATA_FILE.open("r", encoding="utf-8") as f:
                records = json.load(f)
            if not isinstance(records, list):
                records = []
        else:
            records = []

        records.append(entry)

        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _DATA_FILE.open("w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

        return f"Saved: {score}/{total} on {topic}"

    except json.JSONDecodeError as e:
        logger.error("Corrupt progress.json — could not parse: %s", e)
        return f"Error: progress.json is corrupt ({e})"
    except OSError as e:
        logger.error("Could not write to %s: %s", _DATA_FILE, e)
        return f"Error: Could not write progress file — {e}"
    except Exception as e:
        logger.error("Unexpected error in save_progress: %s", e)
        return f"Error: Unexpected failure — {e}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = save_progress("Python Basics", score=4, total=5)
    print(result)

    result2 = save_progress("Azure Fundamentals", score=7, total=10)
    print(result2)

    # Verify the file contents
    if _DATA_FILE.exists():
        print(f"\nContents of {_DATA_FILE}:")
        print(_DATA_FILE.read_text(encoding="utf-8"))
