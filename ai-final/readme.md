# Personal Study Assistant — AI Final Project

A two-part application that combines a **Python MCP Server** exposing study tools with a **Flask web client** connected to a **Microsoft Foundry-hosted agent**. The agent orchestrates tool calls to fetch web content, generate quizzes, and persist study progress.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│              http://localhost:5000                          │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP (JSON)
┌────────────────────────▼────────────────────────────────────┐
│              Flask Web App  (agent/app.py)                  │
│          POST /chat   POST /reset   GET /                   │
└────────────────────────┬────────────────────────────────────┘
                         │ OpenAI Responses API
                         │ DefaultAzureCredential
┌────────────────────────▼────────────────────────────────────┐
│         Foundry-hosted Agent  (Microsoft Foundry)           │
│   • System prompt       • Tool routing       • gpt-4o       │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP (stdio)
┌────────────────────────▼────────────────────────────────────┐
│            MCP Server  (mcp_server/server.py)               │
│  ┌─────────────────┐ ┌──────────────────┐ ┌─────────────┐  │
│  │ fetch_url_      │ │ generate_quiz_   │ │ save_       │  │
│  │ content_tool    │ │ tool             │ │ progress_   │  │
│  │ (httpx/PyPDF2)  │ │ (OpenAI API)     │ │ tool (JSON) │  │
│  └─────────────────┘ └──────────────────┘ └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                                │
                                    ┌───────────▼────────────┐
                                    │  data/progress.json    │
                                    └────────────────────────┘
```

---

## Project Structure

```
ai-final/
├── study-assistant/
│   ├── mcp_server/
│   │   ├── server.py              # FastMCP server — registers all three tools
│   │   ├── __init__.py
│   │   └── tools/
│   │       ├── fetch_url.py       # fetch_url_content: fetches web pages / PDFs
│   │       ├── quiz.py            # generate_quiz: calls Foundry model via OpenAI API
│   │       ├── progress.py        # save_progress: appends score to progress.json
│   │       └── __init__.py
│   ├── agent/
│   │   ├── agent_client.py        # AgentClient: wraps OpenAI Responses API + auth
│   │   ├── app.py                 # Flask app: /  /chat  /reset
│   │   ├── templates/
│   │   │   └── index.html         # Chat UI (Jinja2)
│   │   └── static/
│   │       ├── style.css          # Chat styles (teal theme)
│   │       └── script.js          # Fetch-based chat + typing indicator
│   ├── data/
│   │   └── progress.json          # Persisted quiz results (append-only)
│   ├── .env.example               # Environment variable template
│   ├── requirements.txt           # All Python dependencies
│   └── README.md                  # Quick-start for this sub-project
└── computer-history-client/       # Reference implementation (pattern source)
```

---

## Tech Stack

### MCP Server
| Package | Version | Purpose |
|---|---|---|
| `mcp[cli]` | ≥ 1.0.0 | FastMCP framework; `mcp dev` / `mcp run` CLI |
| `httpx` | ≥ 0.27.0 | HTTP client for `fetch_url_content` |
| `PyPDF2` | ≥ 3.0.0 | PDF text extraction |
| `beautifulsoup4` | ≥ 4.12.0 | HTML parsing helpers |

### Agent Client (Flask app)
| Package | Version | Purpose |
|---|---|---|
| `flask` | ≥ 3.0.0 | Web framework |
| `openai` | ≥ 2.38.0 | OpenAI-compatible client for Foundry endpoints |
| `azure-identity` | ≥ 1.15.0 | `DefaultAzureCredential` for Foundry auth |
| `python-dotenv` | ≥ 1.0.0 | Loads `.env` into `os.environ` |
| `markdown` | ≥ 3.7 | Converts agent responses from Markdown to HTML |
| `bleach` | ≥ 6.1.0 | Sanitises rendered HTML before display |

### Cloud / Infrastructure
| Service | Role |
|---|---|
| **Microsoft Foundry** | Hosts the agent, manages system prompt, routes tool calls |
| **Azure AI (gpt-4o)** | Model used by the hosted agent and `generate_quiz` |
| **DefaultAzureCredential** | Passwordless auth — uses `az login` locally, Managed Identity in production |

### MCP Transport
- **stdio** — the MCP server communicates over stdin/stdout
- Foundry Toolkit launches the server process automatically via `mcp.json`

---

## Setup

### Prerequisites
- Python ≥ 3.11
- Node.js (for `npx @modelcontextprotocol/inspector` — optional)
- Azure CLI logged in: `az login`
- A Microsoft Foundry project with a `study-assistant` agent deployed

### 1 — Clone and activate the virtual environment
```powershell
cd ai-final
.\.venv\Scripts\Activate.ps1
```

### 2 — Install dependencies
```powershell
pip install -r study-assistant/requirements.txt
```

### 3 — Configure environment variables
```powershell
cd study-assistant
Copy-Item .env.example .env
```
Edit `.env` and set:
```dotenv
AGENT_ENDPOINT=https://<your-foundry-resource>.services.ai.azure.com/api/projects/<your-project-name>/
```

### 4 — Configure the MCP server in Foundry Toolkit
`C:\Users\<you>\.aitk\mcp.json` should contain:
```json
{
  "servers": {
    "study-assistant": {
      "type": "stdio",
      "command": "<absolute-path-to-.venv>\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "<absolute-path-to>\\study-assistant"
    }
  }
}
```

---

## Running the Application

### Start the Flask web app
```powershell
cd study-assistant/agent
python app.py
```
Open **http://localhost:5000**

### Start the MCP server (standalone / for testing)
```powershell
# From study-assistant/ root — correct way
cd study-assistant
python -m mcp_server.server

# Via mcp dev (also from study-assistant/)
mcp dev mcp_server/server.py
```

### Inspect tools with MCP Inspector
```powershell
npx @modelcontextprotocol/inspector
```

---

## MCP Tools

### `fetch_url_content_tool`
Fetches and returns the text content of a URL (web page or PDF).
- **Input:** `url: str`
- **Output:** Plain text, truncated to 4 000 characters
- **PDF support:** Uses PyPDF2 for `.pdf` URLs
- **Error handling:** Returns an error string instead of raising

### `generate_quiz_tool`
Generates a multiple-choice quiz on a topic via the Foundry model.
- **Input:** `topic: str`, `num_questions: int` (default 5)
- **Output:** `list[dict]` — each item has `question`, `options: [A,B,C,D]`, `answer`
- **Auth:** Same `DefaultAzureCredential` + `AGENT_ENDPOINT` pattern as the Flask client

### `save_progress_tool`
Persists a quiz result to `data/progress.json`.
- **Input:** `topic: str`, `score: int`, `total: int`
- **Output:** Summary string e.g. `"Saved: 4/5 on Python Basics"`
- **Storage:** Append-only JSON array with ISO 8601 UTC timestamps

---

## Checking Progress Data

```powershell
Get-Content study-assistant/data/progress.json
```

Expected format:
```json
[
  {
    "topic": "Python list comprehensions",
    "score": 4,
    "total": 5,
    "timestamp": "2026-06-15T10:42:17+00:00"
  }
]
```

---

## Key Design Decisions

- **No agent SDK in client code** — `agent_client.py` uses the plain `openai` package pointed at the Foundry endpoint. The agent framework (tool routing, system prompt, context management) runs entirely inside Foundry.
- **MCP over stdio** — the server is a subprocess launched by the MCP host; no HTTP port needed.
- **Append-only progress** — `save_progress` never overwrites existing records, so full quiz history is preserved.
- **Markdown sanitisation** — agent responses are rendered via `markdown` → `bleach` before being sent to the browser, preventing XSS while preserving rich formatting.
- **Path-independent imports** — `server.py` inserts `study-assistant/` onto `sys.path` at startup, so `mcp dev server.py` and `python -m mcp_server.server` both work.
