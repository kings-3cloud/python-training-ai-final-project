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
```
# from inside mcp_server/ (what mcp dev does)
mcp dev server.py

# from study-assistant/ root
python -m mcp_server.server

mcp inspector
npx @modelcontextprotocol/inspector
```