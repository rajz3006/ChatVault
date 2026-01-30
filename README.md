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

- **Python 3.12+** ([download](https://www.python.org/downloads/))
- **Node.js 18+** ([download](https://nodejs.org/))
- **Ollama** (for local LLM) — or an Anthropic API key for Claude

Install Ollama:

```bash
brew install ollama   # macOS
ollama serve          # start the server (keep running in a separate terminal)
```

### 1. Clone the repo

```bash
git clone https://github.com/your-username/chatvault.git
cd chatvault
```

### 2. Start the backend (FastAPI)

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Place your AI chat export JSON files in data/
mkdir -p data
# Copy your Claude export files into data/

# Run ingestion and embeddings (first time only)
python -m chatvault.ingest
python -m chatvault.embeddings

# Start the FastAPI server
python -m chatvault.api
```

The API server starts at **http://localhost:8000**.

### 3. Start the frontend (React + Vite)

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

The React dev server starts at **http://localhost:5173** with API requests proxied to `:8000`.

### Production build (single server)

```bash
cd frontend
npm run build        # builds to frontend/dist/
cd ..
python -m chatvault.api   # serves both API and frontend on :8000
```

### Alternative: One-command start with `run.sh`

For the Streamlit-based UI (legacy), you can also run:

```bash
chmod +x run.sh
./run.sh
```

This handles venv creation, dependency install, embedding model download, and launches the Streamlit UI at **http://localhost:8502**. A setup wizard walks you through first-time configuration.

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
├── onboarding.py        # First-run setup wizard (Streamlit)
└── app.py               # Streamlit UI (legacy)

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
| `Python 3.12+ is required` | Install Python 3.12+ from [python.org](https://www.python.org/downloads/) or `brew install python@3.12` |
| `Ollama is not running` | Run `ollama serve` in a separate terminal |
| Embedding model download hangs | Check your internet connection; the model (~80 MB) downloads from HuggingFace on first run |
| Import fails | Ensure your export files are unzipped JSON in the `data/` directory |
| Frontend can't reach API | Make sure the FastAPI server is running on `:8000` before starting the frontend dev server |
| `npm run build` fails | Run `npm install` first; ensure Node.js 18+ is installed |

---

## Fresh Restart (Clean DB & Cache)

To wipe all ingested data and start from scratch:

### 1. Stop both servers

```bash
# Kill FastAPI backend and Vite frontend
kill $(lsof -ti:8000) $(lsof -ti:5173) 2>/dev/null
```

### 2. Delete database and vector store

```bash
# SQLite database
rm -f chatvault.db chatvault.db-shm chatvault.db-wal

# ChromaDB vector store
rm -rf chroma_data/

# (Optional) Remove saved config to re-trigger the setup wizard
rm -f ~/.chatvault/config.yaml
```

### 3. Re-ingest and restart

```bash
# Activate venv
source .venv/bin/activate

# Re-run ingestion from data/ directory
python -m chatvault.ingest

# Re-generate embeddings
python -m chatvault.embeddings

# Start backend
python -m chatvault.api &

# Start frontend (in another terminal)
cd frontend && npm run dev
```

> **Note:** The FastAPI backend holds data in memory via lazy singletons. Deleting files on disk while the server is running will not take effect — you must restart the server.

---

## License

MIT
