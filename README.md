# Personal Study Assistant — AI Final Project

A two-part application that combines a **Python MCP Server** exposing study tools with a **Flask web client** that supports two agent modes:

- **Online** — connected to a Microsoft Foundry-hosted agent (gpt-4o, tool calls via MCP over stdio)
- **Offline** — a local agent loop using any OpenAI-compatible model (Ollama, LM Studio) with tool calling handled directly in Python

Both modes support fetching web content, generating quizzes, and persisting study progress.

---

## Architecture

### Online mode (Foundry)
```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│              http://localhost:5000                          │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP (JSON)
┌────────────────────────▼────────────────────────────────────┐
│              Flask Web App  (agent/app.py)                  │
│       GET /   POST /chat   POST /reset   POST /upload       │
│       GET /mode   POST /mode                                │
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

### Offline mode (local model)
```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP (JSON)
┌────────────────────────▼────────────────────────────────────┐
│              Flask Web App  (agent/app.py)                  │
└────────────────────────┬────────────────────────────────────┘
                         │ Chat Completions API + tool_choice="auto"
┌────────────────────────▼────────────────────────────────────┐
│        Local model  (Ollama / LM Studio)                    │
│   llama3.1 / llama3.2 / mistral / qwen2.5 / gemma3          │
│   (model must support function/tool calling)                │
└────────────────────────┬────────────────────────────────────┘
                         │ Python function calls (no MCP needed)
┌────────────────────────▼────────────────────────────────────┐
│   OfflineAgentBackend + ToolRegistry  (backends/offline.py) │
│  fetch_url_content()  generate_quiz()  save_progress()      │
│  (imports mcp_server/tools/* directly — no MCP process)     │
└────────────────────────┬────────────────────────────────────┘
                                                │
                                    ┌───────────▼────────────┐
                                    │  data/progress.json    │
                                    └────────────────────────┘
```

---

## Project Structure

```
root folder/
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
│   │   ├── app.py                 # Flask routes only: / /chat /reset /upload /mode
│   │   ├── factories.py           # Object construction — wires all dependencies (DIP)
│   │   ├── agent_client.py        # Session manager only: history + backend delegation
│   │   ├── backends/
│   │   │   ├── base.py            # AgentBackend ABC (LSP / DIP)
│   │   │   ├── online.py          # OnlineAgentBackend — Foundry Responses API
│   │   │   ├── offline.py         # OfflineAgentBackend + ToolRegistry (OCP)
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   ├── markdown_renderer.py  # MarkdownRenderer — HTML rendering (SRP)
│   │   │   ├── pdf_extractor.py      # PdfExtractor — PDF text extraction (SRP)
│   │   │   └── __init__.py
│   │   ├── templates/
│   │   │   └── index.html         # Chat UI with mode toggle + PDF upload
│   │   └── static/
│   │       ├── style.css          # Chat styles (teal theme)
│   │       └── script.js          # Chat, upload, mode-switch logic
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
| `PyPDF2` | ≥ 3.0.0 | PDF text extraction (URL + file upload) |
| `beautifulsoup4` | ≥ 4.12.0 | HTML parsing helpers |

### Agent Client (Flask app)
| Package | Version | Purpose |
|---|---|---|
| `flask` | ≥ 3.0.0 | Web framework |
| `openai` | ≥ 2.38.0 | OpenAI-compatible client (Foundry + local models) |
| `azure-identity` | ≥ 1.15.0 | `DefaultAzureCredential` for online/Foundry auth |
| `python-dotenv` | ≥ 1.0.0 | Loads `.env` into `os.environ` |
| `markdown` | ≥ 3.7 | Converts agent responses from Markdown to HTML |
| `bleach` | ≥ 6.1.0 | Sanitises rendered HTML before display |
| `werkzeug` | (Flask dep) | `secure_filename` for PDF upload safety |

### Online mode — Cloud / Infrastructure
| Service | Role |
|---|---|
| **Microsoft Foundry** | Hosts the agent, manages system prompt, routes tool calls |
| **Azure AI (gpt-4o)** | Model used by the hosted agent and `generate_quiz` |
| **DefaultAzureCredential** | Passwordless auth — `az login` locally, Managed Identity in production |
| **MCP stdio transport** | Foundry Toolkit launches the MCP server subprocess via `mcp.json` |

### Offline mode — Local model
| Component | Details |
|---|---|
| **Ollama / LM Studio** | Local OpenAI-compatible server |
| **Supported models** | `llama3.1`, `llama3.2`, `mistral`, `qwen2.5`, `gemma3` |
| **NOT supported** | `llama3` (3.0), `phi3-mini` — no tool/function calling |
| **Tool execution** | `OfflineAgentBackend` + `ToolRegistry` import `mcp_server/tools/*` directly — no MCP process needed |

---

## Setup

### Prerequisites
- Python ≥ 3.11
- Azure CLI logged in (`az login`) — **online mode only**
- A Microsoft Foundry project with a `study-assistant` agent deployed — **online mode only**
- Ollama or LM Studio with a tool-capable model — **offline mode only**
- Node.js (for `npx @modelcontextprotocol/inspector` — optional)

### 1 — Activate the virtual environment
```powershell
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

Edit `.env`:

```dotenv
# Which mode to start in (can be switched at runtime from the UI)
DEFAULT_MODE=online

# ── Online (Foundry) ──────────────────────────────────
AGENT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>/

# ── Offline (local model) ─────────────────────────────
OFFLINE_ENDPOINT=http://localhost:11434/v1   # Ollama default
OFFLINE_MODEL=llama3.1                       # must support tool calling
OFFLINE_API_KEY=ollama                       # Ollama ignores the value
```

### 4 — Configure the MCP server in Foundry Toolkit (online mode only)
`C:\Users\<you>\.aitk\mcp.json`:
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

### 5 — Pull a local model (offline mode only)
```powershell
ollama pull llama3.1
```

---

## Running the Application

### Start the Flask web app
```powershell
cd study-assistant/agent
python app.py
```
Open **http://localhost:5000**

Use the **☁️ Online / 💻 Offline** toggle in the toolbar to switch modes at runtime. Switching resets the conversation history.

### Start the MCP server (standalone / for testing)
```powershell
# From study-assistant/ root
cd study-assistant
python -m mcp_server.server

# Via mcp dev
mcp dev mcp_server/server.py
```

### Inspect MCP tools
```powershell
npx @modelcontextprotocol/inspector
```

---

## Flask Endpoints

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/` | Serve the chat UI |
| `POST` | `/chat` | `{ message }` → `{ response, response_html }` |
| `POST` | `/reset` | Clear conversation history |
| `POST` | `/upload` | Multipart PDF upload → `{ filename, content, truncated }` |
| `GET` | `/mode` | Return current mode (`online`\|`offline`) |
| `POST` | `/mode` | `{ mode }` → switch agent mode, reinitialise client |

---

## MCP Tools

### `fetch_url_content_tool`
Fetches and returns the text content of a URL (web page or PDF).
- **Input:** `url: str`
- **Output:** Plain text, truncated to 4 000 characters
- **PDF support:** Uses PyPDF2 for `.pdf` URLs
- **Also available as:** PDF file upload via `/upload` endpoint

### `generate_quiz_tool`
Generates a multiple-choice quiz on a topic.
- **Input:** `topic: str`, `num_questions: int` (default 5)
- **Output:** `list[dict]` — each item has `question`, `options: [A,B,C,D]`, `answer`
- **Online:** calls Foundry model via OpenAI API
- **Offline:** calls local model directly with a strict JSON-only prompt

### `save_progress_tool`
Persists a quiz result to `data/progress.json`.
- **Input:** `topic: str`, `score: int`, `total: int`
- **Output:** Summary string e.g. `"Saved: 4/5 on Python Basics"`
- **Storage:** Append-only JSON array with ISO 8601 UTC timestamps
- **Works in both modes** — offline calls `progress.py` directly, no MCP needed

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

Records accumulate across sessions — the file is never overwritten.

---

## Key Design Decisions

### Architecture — SOLID principles

- **Single Responsibility** — each class/module does one thing: `app.py` routes requests; `AgentClient` manages history; `OnlineAgentBackend`/`OfflineAgentBackend` own their transport; `MarkdownRenderer` renders HTML; `PdfExtractor` parses PDFs; `factories.py` constructs the object graph.
- **Open/Closed** — adding a new tool requires one `registry.register()` call in `factories.py`. Adding a new agent mode requires one `_build_*_backend()` function. No existing code is modified.
- **Liskov Substitution** — `OnlineAgentBackend` and `OfflineAgentBackend` both implement `AgentBackend` and are fully interchangeable. `AgentClient` never checks which concrete type it holds.
- **Interface Segregation** — `AgentBackend` exposes only `mode` and `send()`. `AgentClient` exposes only `send_message()`, `reset_session()`, and `mode`. Callers depend on nothing they don't use.
- **Dependency Inversion** — `AgentClient` receives an `AgentBackend` instance; it never touches `OpenAI` or env vars. `app.py` calls `create_agent_client()` from `factories.py`; it never imports a concrete backend.

### Runtime behaviour

- **Dual-mode agent** — `create_agent_client(mode)` in `factories.py` selects the backend at init time. The UI toggle calls `POST /mode` which reinitialises the client without restarting Flask.
- **Online uses Responses API** — Foundry endpoints expose `client.responses.create()`, not `chat.completions`. Tool routing and context management run entirely in Foundry.
- **Offline uses Chat Completions + native tool calling** — `OfflineAgentBackend.send()` passes `TOOL_SCHEMAS` to the model, handles `finish_reason == "tool_calls"`, delegates to `ToolRegistry.execute()`, and loops until a final text response is returned.
- **Offline tools call `mcp_server/tools/*` directly** — no MCP subprocess or stdio needed in offline mode. `fetch_url_content`, `save_progress` are imported and called as plain functions via `ToolRegistry`.
- **MCP over stdio (online only)** — Foundry Toolkit launches the MCP server subprocess via `mcp.json`. The server is not needed for offline operation.
- **Tool-calling model required for offline** — `llama3.1`/`3.2`, `mistral`, `qwen2.5`, `gemma3` support function calling. `llama3` (3.0) does not.
- **PDF upload bypasses the URL tool** — `POST /upload` delegates to `PdfExtractor.extract()` and injects extracted text into the conversation directly, avoiding network round-trips for local files.
- **Append-only progress** — `save_progress` never overwrites existing records, so full quiz history is preserved.
- **Markdown sanitisation** — agent responses are rendered via `MarkdownRenderer` (`markdown` → `bleach`) before being sent to the browser, preventing XSS while preserving rich formatting.
- **Path-independent imports** — `server.py` and `factories.py` each insert `study-assistant/` onto `sys.path` at startup, so all launch styles work correctly.
