# Personal Study Assistant

A two-part app: an MCP server exposing study tools, and a Flask agent client connected to a Foundry-hosted agent.

## Structure

```
study-assistant/
  mcp_server/       # MCP server with fetch_url_content, generate_quiz, save_progress tools
  agent/            # Flask web app + AgentClient
  data/             # Persisted quiz progress
```

## Setup
Change directory to `cd study-assistant`
1. Rename `.env.example` to `.env` and fill in `AGENT_ENDPOINT`.
2. Install dependencies: `pip install -r requirements.txt`
3. Run MCP server: `python -m mcp_server.server`
4. Run agent app: `python agent/app.py`

## Run MCP server
```powershell
# from study-assistant/ root — run the server directly (stdio transport)
python -m mcp_server.server

# from study-assistant/ root — run with MCP Inspector UI (opens http://localhost:6274)
# Note: uv installs mcp.exe as a trampoline that fails on Windows; invoke via Python instead
python -c "from mcp.cli.cli import app; app()" dev mcp_server/server.py

# Alternative: Node-based inspector (requires Node.js)
npx @modelcontextprotocol/inspector python -m mcp_server.server
```