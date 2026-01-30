# ChatVault

> **Open-source, local-first AI chat history assistant.**
> Import your AI conversations, search them semantically, and chat with your own history using RAG.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/frontend-React%2018-61DAFB.svg)](https://react.dev)

---

## Features

- **Import** — Ingest AI chat exports (Claude today, ChatGPT & Gemini coming soon) into a local SQLite database
- **Search** — Hybrid semantic + keyword search across your entire conversation history
- **RAG Chat** — Ask questions about your past conversations; get answers grounded in your own data
- **Browse & Stats** — Explore conversations, view usage statistics, and filter by date/platform
- **100% Local** — Everything runs on your machine. No cloud, no telemetry, no data leaves your laptop

---

## Quick Start

### Prerequisites

- **Python 3.10+** ([download](https://www.python.org/downloads/))
- **Node.js 18+** ([download](https://nodejs.org/))
- **Ollama** (optional, for local LLM) — or an Anthropic API key for Claude

### 1. Clone and run

```bash
git clone https://github.com/your-username/chatvault.git
cd chatvault
chmod +x run.sh
./run.sh
```

### 2. Open in your browser

```
http://localhost:8000
```

That's it. `run.sh` handles everything: Python venv, dependencies, frontend build, embedding model download, and server launch. On first run the setup wizard will guide you through importing your data and configuring the LLM backend.

<details>
<summary><strong>Development setup (manual)</strong></summary>

If you prefer to run the backend and frontend separately for development:

```bash
# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python -m chatvault.api
```

```bash
# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

The Vite dev server runs at `http://localhost:5173` with API requests proxied to `:8000`.

</details>

---

## How to Export Your Claude Data

1. Go to [claude.ai](https://claude.ai) > **Settings** > **Account** > **Export Data**
2. You'll receive an email with a download link
3. Download and unzip — you'll get a folder of JSON files
4. Place those files in the `data/` directory

---

## Supported Platforms

| Platform | Status |
|----------|--------|
| Claude (Anthropic) | Supported |
| ChatGPT (OpenAI) | Coming soon |
| Google Gemini | Coming soon |

Want to add a platform? See [Contributing](#contributing).

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/conversations` | List all conversations |
| `GET` | `/api/conversations/{uuid}/messages` | Get messages for a conversation |
| `POST` | `/api/conversations/{uuid}/star` | Toggle star on a conversation |
| `POST` | `/api/conversations/{uuid}/tags` | Add/remove tags |
| `GET` | `/api/search?q=...&limit=20` | Hybrid semantic + keyword search |
| `POST` | `/api/chat` | RAG chat with conversation history |
| `GET` | `/api/conversations/{uuid}/export?format=md` | Export conversation (md/json/csv) |
| `GET` | `/api/stats` | Database and embedding statistics |
| `GET` | `/api/settings` | Current backend and connector info |
| `POST` | `/api/settings/backend` | Switch LLM backend |
| `POST` | `/api/settings/reimport` | Force re-import from data directory |
| `POST` | `/api/settings/reembed` | Force re-embed all data |

---

## Architecture

```
Export JSON ──> Connector ──> SQLite DB ──> Embeddings ──> ChromaDB
                                                              |
                                               Search + RAG ──> LLM ──> Answer
                                                              |
                FastAPI (/api/*) <──────────────────────────────
                    |
                React Frontend (Vite + TypeScript)
```

- **Pluggable connectors** — each AI platform has its own connector that normalizes exports into a universal schema
- **Embeddings** — `all-MiniLM-L6-v2` via sentence-transformers, stored in ChromaDB
- **Hybrid search** — combines semantic similarity with FTS5 keyword matching
- **LLM backends** — Ollama (local) or Claude API (remote), switchable in settings
- **FastAPI backend** — RESTful API serving data to the React frontend
- **React frontend** — TypeScript + Vite SPA with API proxy in development

---

## Project Structure

```
chatvault/
├── api.py               # FastAPI backend (uvicorn entry point)
├── connectors/          # Pluggable platform connectors
│   ├── base.py          # BaseConnector ABC
│   ├── claude.py        # Claude connector
│   └── TEMPLATE.py      # Template for new connectors
├── llm/                 # LLM backends
│   ├── base.py          # BaseLLM ABC
│   ├── ollama.py        # Ollama (local)
│   └── claude.py        # Claude API
├── db.py                # SQLite schema & helpers
├── ingest.py            # Ingestion orchestrator
├── embeddings.py        # ChromaDB + sentence-transformers
├── search.py            # Hybrid search engine
├── rag.py               # RAG pipeline
├── export.py            # Conversation export (MD/JSON/CSV)
├── config.py            # YAML config management
├── api.py               # FastAPI backend

frontend/                # React + Vite + TypeScript
├── src/
│   ├── main.tsx         # React entry point
│   ├── App.tsx          # Main app component
│   ├── api.ts           # API client for FastAPI
│   ├── types.ts         # TypeScript interfaces
│   ├── components/
│   │   ├── LeftPanel.tsx
│   │   ├── RightPanel.tsx
│   │   ├── ChatInput.tsx
│   │   ├── ChatMessage.tsx
│   │   ├── ThreadView.tsx
│   │   ├── ActionBar.tsx
│   │   └── SettingsPopover.tsx
│   └── styles/
│       └── app.css
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts       # Vite config with /api proxy to :8000
```

---

## Configuration

Config is stored at `~/.chatvault/config.yaml` and created automatically by the setup wizard. Defaults:

```yaml
data_dir: ./data
db_path: chatvault.db
chroma_dir: chroma_data
llm_backend: ollama          # "ollama" or "claude"
ollama_host: http://localhost:11434
ollama_model: llama3
anthropic_model: claude-sonnet-4-20250514
```

### Environment Variable Overrides

| Variable | Overrides |
|----------|-----------|
| `OLLAMA_HOST` | `ollama_host` |
| `OLLAMA_MODEL` | `ollama_model` |
| `ANTHROPIC_API_KEY` | Used directly by the Claude LLM backend |

---

## LLM Options

### Option A: Ollama (Local, Free)

The setup wizard can download a model for you. Recommended models:

| Model | Parameters | Download Size | Notes |
|-------|-----------|---------------|-------|
| `tinyllama` | 1.1B | ~700 MB | Fast, good for testing |
| `llama3.2:1b` | 1.3B | ~1.3 GB | Fast, decent quality |
| `llama3` | 8B | ~4.7 GB | **Recommended** — good balance |
| `llama3.1` | 70B | ~40 GB | Best quality, needs 64 GB+ RAM |

### Option B: Claude API (Remote)

Set your API key as an environment variable or enter it in the setup wizard:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Contributing

ChatVault is designed to be extended. The most impactful contribution is **adding a new connector** for another AI platform.

1. Copy `chatvault/connectors/TEMPLATE.py`
2. Implement `detect()`, `ingest()`, and `get_export_instructions()`
3. Drop it in `chatvault/connectors/` — it's auto-discovered

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Python 3.10+ is required` | Install Python 3.10+ from [python.org](https://www.python.org/downloads/) or `brew install python@3.10` |
| `Ollama is not running` | Run `ollama serve` in a separate terminal |
| Embedding model download hangs | Check your internet connection; the model (~80 MB) downloads from HuggingFace on first run |
| Import fails | Ensure your export files are unzipped JSON in the `data/` directory |
| Frontend not loading | Run `./run.sh` which builds the frontend automatically; for dev mode ensure both servers are running |
| `npm run build` fails | Run `npm install` first; ensure Node.js 18+ is installed |

---

## Stopping the Server

```bash
./stop.sh
```

Or press `Ctrl+C` in the terminal where `run.sh` is running.

## Fresh Restart (Clean DB & Cache)

To wipe all ingested data and start from scratch:

```bash
./run.sh --reset
```

This deletes the database, vector store, and config, then relaunches with the setup wizard.

---

## License

MIT
