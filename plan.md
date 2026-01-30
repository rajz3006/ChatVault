# ChatVault — Open-Source Personal AI Chat History Assistant

## Overview

An open-source, local-first **personal knowledge assistant** that lets anyone ingest their AI chat history, search it semantically, and chat with it via RAG. Ships with a **Claude connector** first, designed with a **pluggable connector architecture** so the community can add Google Gemini, ChatGPT, Copilot, and others.

Users clone the repo, drop their export, run one command, and have a private, searchable knowledge base with an AI chat interface.

**Stack**: Python + SQLite + ChromaDB + sentence-transformers + Ollama + Claude API (toggle) + Streamlit

---

## Design Principles

1. **Pluggable connectors** — Each AI platform is a connector that transforms its export format into a universal schema. Adding a new platform = adding one Python file.
2. **Universal schema** — All connectors normalize into the same tables. The search/RAG/UI layers never know which platform the data came from.
3. **Local-first, privacy-first** — Everything runs on the user's machine. No cloud, no telemetry, no accounts.
4. **One-command setup** — `./run.sh` handles install, ingest, and launch.
5. **Community-friendly** — Clear contribution guide, connector template, MIT license.

---

## Universal Data Schema

All connectors normalize into this schema. This is the contract between ingestion and everything downstream.

```sql
-- Source platform tracking
CREATE TABLE sources (
    id TEXT PRIMARY KEY,          -- e.g., "claude", "gemini", "chatgpt"
    name TEXT,                    -- "Anthropic Claude"
    import_date TIMESTAMP,
    file_path TEXT                -- original export path
);

-- Conversations from any platform
CREATE TABLE conversations (
    uuid TEXT PRIMARY KEY,
    source_id TEXT REFERENCES sources(id),
    name TEXT,                    -- conversation title
    summary TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    metadata JSON                -- platform-specific extras (projects, tags, etc.)
);

-- Individual messages (the conversation_detail you asked about)
CREATE TABLE messages (
    uuid TEXT PRIMARY KEY,
    conversation_uuid TEXT REFERENCES conversations(uuid),
    position INTEGER,            -- order within conversation (1, 2, 3...)
    sender TEXT,                  -- normalized: "human" | "assistant"
    text TEXT,                    -- plain text content
    created_at TIMESTAMP,
    metadata JSON                -- attachments, files, citations, model used, etc.
);

-- FTS5 for keyword search fallback
CREATE VIRTUAL TABLE messages_fts USING fts5(text, conversation_name, summary, content=messages);
```

Key design choices:
- `sender` is normalized across platforms ("human"/"assistant" regardless of source)
- `metadata JSON` captures platform-specific fields without schema changes
- `source_id` lets users ingest from multiple platforms into one searchable DB

---

## Connector Architecture

```
data/
├── claude_export/           ← user drops Claude JSON here
│   ├── conversations.json
│   ├── projects.json
│   └── memories.json
├── gemini_export/           ← future: Gemini Takeout
├── chatgpt_export/          ← future: ChatGPT export
└── ...

connectors/
├── base.py                  ← abstract BaseConnector class
├── claude.py                ← Claude connector (Phase 1)
├── gemini.py                ← future
├── chatgpt.py               ← future
└── __init__.py              ← auto-discovery registry
```

### BaseConnector interface

```python
class BaseConnector(ABC):
    """All connectors implement this interface."""

    source_id: str           # "claude", "gemini", etc.
    source_name: str         # "Anthropic Claude"

    @abstractmethod
    def detect(self, data_dir: Path) -> bool:
        """Return True if this connector's export exists in data_dir."""

    @abstractmethod
    def ingest(self, data_dir: Path, db: Database) -> IngestResult:
        """Parse export files and insert into universal schema.
        Returns count of conversations and messages ingested."""

    @abstractmethod
    def get_export_instructions(self) -> str:
        """Return user-facing instructions for how to export from this platform."""
```

### Auto-discovery

The ingestion script scans `connectors/` for all `BaseConnector` subclasses, calls `detect()` on the data directory, and runs `ingest()` for any that match. Users just drop their export in `data/` and the system figures out which connector to use.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       Streamlit UI                            │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Chat (RAG)  │  │  Search      │  │  Browse / Stats    │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────────┘  │
└─────────┼─────────────────┼──────────────────┼───────────────┘
          │                 │                  │
    ┌─────▼─────────────────▼──────┐    ┌─────▼──────┐
    │         RAG Pipeline          │    │   SQLite    │
    │  retrieve → prompt → generate │    │ (universal  │
    │     ┌──────────┐              │    │  schema)    │
    │     │ Ollama   │ (default)    │    └────────────┘
    │     │ Claude   │ (toggle)     │          ▲
    │     └──────────┘              │          │
    └───────────┬───────────────────┘          │
          ┌─────▼─────┐                        │
          │  ChromaDB  │                        │
          └────────────┘                        │
                ▲                               │
                │       Ingestion Engine        │
                └────────── + ─────────────────┘
                     Connector Registry
                    ┌────┬────┬────┐
                    │ C  │ G  │ O  │  ← pluggable connectors
                    └────┴────┴────┘
                         ▲
                    data/ folder
              (drop any platform export)
```

---

## Phase 0: Project Scaffolding

**Goal**: Create a valid, runnable Python package structure before any code is written.

**Files to create**:
- `chatvault/__init__.py` — package init (version string)
- `chatvault/connectors/__init__.py` — empty, makes it a subpackage
- `chatvault/llm/__init__.py` — empty, makes it a subpackage
- `pyproject.toml` — project metadata, dependencies, entry points
- `.env.example` — template with all env vars (documented, no real values)
- `.gitignore` — data/, chroma_data/, *.db, .env, __pycache__, .venv/, etc.
- `data/.gitkeep` — ensures the data/ directory exists in git
- `run.sh` — launcher script (executable)
- `README.md` — minimal placeholder (fleshed out in Phase 5)

**Tasks**:

1. Create directory structure:
   ```
   chatvault/
   ├── __init__.py
   ├── connectors/
   │   └── __init__.py
   └── llm/
       └── __init__.py
   data/
       └── .gitkeep
   ```

2. `pyproject.toml`:
   ```toml
   [project]
   name = "chatvault"
   version = "0.1.0"
   description = "Open-source personal AI chat history assistant with RAG"
   requires-python = ">=3.10"
   dependencies = [
       "streamlit",
       "chromadb",
       "sentence-transformers",
       "anthropic",
       "requests",
       "pyyaml",
   ]

   [project.scripts]
   chatvault = "chatvault.app:main"
   ```

3. `.env.example`:
   ```
   # Optional: Anthropic API key for Claude LLM backend
   ANTHROPIC_API_KEY=

   # Optional: Ollama host (default: http://localhost:11434)
   OLLAMA_HOST=http://localhost:11434

   # Optional: Ollama model (default: llama3)
   OLLAMA_MODEL=llama3
   ```

4. `.gitignore`:
   ```
   data/*/
   !data/.gitkeep
   chroma_data/
   *.db
   .env
   .venv/
   __pycache__/
   *.egg-info/
   dist/
   build/
   ```

5. `run.sh` (basic version — Phase 5 enhances it):
   ```bash
   #!/bin/bash
   set -e
   cd "$(dirname "$0")"
   python -m venv .venv 2>/dev/null || true
   source .venv/bin/activate
   pip install -e . --quiet
   python -m chatvault.ingest --append
   streamlit run chatvault/app.py
   ```

**Verification**: `cd chatvault && python -c "import chatvault"` succeeds. `.venv` can be created. `pip install -e .` installs the package.

---

## Phase 1: Connector Framework + Claude Connector + Storage

**Goal**: Build the connector architecture and the first connector (Claude). Parse JSON → SQLite.

**Files to create**:
- `chatvault/connectors/base.py` — BaseConnector ABC
- `chatvault/connectors/__init__.py` — auto-discovery registry
- `chatvault/connectors/claude.py` — Claude export connector
- `chatvault/db.py` — SQLite schema (universal) and helpers
- `chatvault/ingest.py` — ingestion orchestrator

**Tasks**:

1. Define `BaseConnector` abstract class with `detect()`, `ingest()`, `get_export_instructions()`

2. Implement `ClaudeConnector`:
   - `detect()`: look for `conversations.json` with Claude's schema signature
   - `ingest()`: parse conversations.json, projects.json, memories.json
   - Extract `text` from content blocks (type=text), concatenate
   - Map `sender` values to normalized "human"/"assistant"
   - Store Claude-specific fields (projects, memories) in `metadata` JSON
   - Deduplication by message uuid for re-imports

3. Define universal SQLite schema (sources, conversations, messages, FTS5)

4. Build ingestion orchestrator:
   - Scan `connectors/` for registered connectors
   - For each connector where `detect()` returns True, run `ingest()`
   - Support `--force` (rebuild) and `--append` (incremental) modes
   - Print summary: "Ingested 695 conversations, 7409 messages from Claude"

5. Chunking logic (prepare chunks, don't embed yet):
   - Conversation-level: name + summary + first 2 human messages
   - Message-level: each assistant message as a chunk
   - Long messages (>500 tokens): overlapping splits ~400 tokens, 50-token overlap
   - Metadata per chunk: conversation_uuid, message_uuid, sender, date, conversation_name, source_id

**Verification**: `python -m chatvault.ingest data/` → 695 convos, 7409 messages, 16 projects from Claude source.

---

## Phase 2: Embedding Generation & Vector Store

**Goal**: Generate embeddings for all chunks, store in ChromaDB

**Files to create**:
- `chatvault/embeddings.py` — embedding + ChromaDB logic

**Tasks**:
1. Load `sentence-transformers/all-MiniLM-L6-v2` (22M params, CPU-friendly)

2. Two ChromaDB collections:
   - `conversation_topics` (~695 vectors) — broad topic search
   - `message_chunks` (~8K-12K vectors) — specific answer search

3. Embed all chunks with metadata (including `source_id` for multi-platform filtering)

4. Persist to `chatvault/chroma_data/`

5. Incremental: only embed new/changed chunks on `--append`

**Verification**: Test query "Bitcoin investment strategy" → top 5 results with scores and source attribution.

---

## Phase 3: Search & RAG Pipeline

**Goal**: Hybrid search + RAG with dual-LLM support

**Files to create**:
- `chatvault/search.py` — search engine
- `chatvault/rag.py` — RAG pipeline + LLM backends
- `chatvault/llm/base.py` — LLM backend interface
- `chatvault/llm/ollama.py` — Ollama backend
- `chatvault/llm/claude.py` — Claude API backend
- `chatvault/llm/__init__.py` — backend registry

### Search (search.py)

1. Semantic search (ChromaDB) + keyword fallback (FTS5) + hybrid ranking (RRF)
2. Metadata filters: date range, sender, source platform, project
3. SearchResult dataclass with source_id field
4. Conversation loader from SQLite

### RAG Pipeline (rag.py)

1. Retrieve top-10 chunks → assemble context with source citations → LLM generates answer
2. System prompt: "You are a personal knowledge assistant. Answer based on the user's past AI conversations. Always cite the conversation name, date, and platform."
3. Conversation memory (last N turns) for follow-ups

### LLM Backend (llm/)

Pluggable LLM interface — same pattern as connectors:
```python
class BaseLLM(ABC):
    @abstractmethod
    def generate(self, system: str, messages: list[dict], context: str) -> str: ...
```
- `OllamaLLM`: calls localhost:11434, configurable model
- `ClaudeLLM`: calls Anthropic API
- Future: `GeminiLLM`, `OpenAILLM`

**Verification**:
- "What was my investment strategy?" → synthesized answer citing sources
- Follow-up "tell me more" → uses session context

---

## Phase 4: Streamlit UI

**Goal**: Chat-first interface with search and browse

**Files to create**:
- `chatvault/app.py` — Streamlit application

### Tab 1: Chat (primary)
- Chat input, message history (st.chat_message)
- Cited sources as expandable cards below each answer
- Sidebar: LLM toggle, model selector, source platform filter

### Tab 2: Search
- Natural language search bar
- Filters: date range, sender, platform, project
- Result cards with conversation name, date, snippet, score, platform badge

### Tab 3: Browse
- Sortable table of all conversations with platform icon column
- Click → expand full Q&A thread

### Tab 4: Stats
- Per-platform breakdown (conversations, messages, date range)
- Timeline chart, topic frequency

### Tab 5: Settings / Import
- Drop new export files → trigger re-ingest
- Connector status: which platforms detected, last import date
- LLM configuration
- Export search results / chat transcripts as JSON/CSV

**Verification**: Launch app, test all tabs, verify multi-source display (even if only Claude data exists).

---

## Phase 5: Packaging & Community

**Goal**: Make it clone-and-run for anyone, with clear contribution path

**Files to create**:
- `chatvault/config.py` — config management
- `requirements.txt`
- `setup.py` or `pyproject.toml`
- `run.sh` — one-command launcher
- `README.md` — setup + usage guide
- `CONTRIBUTING.md` — how to add a connector
- `connectors/TEMPLATE.py` — annotated connector template

**Tasks**:

1. **requirements.txt** with all dependencies

2. **config.py**: YAML-based config file (`~/.chatvault/config.yaml`)
   - Data directory, LLM backend, model name, API keys (env vars)
   - First-run wizard: auto-generates config interactively

3. **run.sh**:
   ```bash
   #!/bin/bash
   cd "$(dirname "$0")"
   python -m venv .venv 2>/dev/null
   source .venv/bin/activate
   pip install -r requirements.txt --quiet
   python -m chatvault.ingest --append
   streamlit run chatvault/app.py
   ```

4. **README.md**:
   - What it does (with screenshot)
   - Quick start (3 steps: clone, drop export, run)
   - Supported platforms table
   - How to add a new connector (link to CONTRIBUTING.md)

5. **CONTRIBUTING.md**:
   - Connector development guide
   - BaseConnector interface docs
   - Testing your connector
   - PR template

6. **connectors/TEMPLATE.py**: copy-and-fill connector template with inline comments

7. **.gitignore**: exclude data/, chroma_data/, *.db, .env, __pycache__

**Verification**: Fresh clone on a different machine → `./run.sh` works end-to-end.

---

## Phase 6: Security Hardening

**Goal**: Protect sensitive personal data at rest

**Tasks**:

1. **SQLCipher**: Encrypted SQLite (passphrase on startup, in-memory decrypt only)
2. **ChromaDB encryption**: Wrap `chroma_data/` in encrypted volume (APFS on macOS, LUKS on Linux)
3. **Raw export cleanup**: Post-ingest prompt to securely delete raw JSON
4. **Ollama binding check**: Startup validation that Ollama is localhost-only
5. **Cloud sync detection**: Warn if project dir is inside iCloud/Dropbox/GDrive/OneDrive
6. **API keys**: Env vars only, never in config files, `.env` in .gitignore
7. **Session data**: In-memory only, never persisted to disk
8. **Disk encryption check**: Warn if FileVault (macOS) / LUKS (Linux) not enabled

**Verification**: DB unreadable without passphrase, no plaintext sensitive data on disk.

---

## Dependency Graph

```
Phase 0 (Scaffolding) ──→ Phase 1 (Connectors + Ingest) ──→ Phase 2 (Embeddings) ──→ Phase 3 (Search + RAG) ──→ Phase 4 (UI)
                                                                                                                      │
                                                                                                            Phase 5 (Packaging)
                                                                                                                      +
                                                                                                            Phase 6 (Security)
```

- Phase 0 must run first (creates the package structure all other phases write into)
- Phases 1→4 are sequential
- Phases 5 and 6 can run in parallel with Phase 4
- Each phase fits within ~200K token agent execution

---

## Project Structure

```
chatvault/
├── connectors/
│   ├── __init__.py        # Auto-discovery registry
│   ├── base.py            # BaseConnector ABC
│   ├── claude.py          # Claude connector (Phase 1)
│   ├── TEMPLATE.py        # Connector template for contributors
│   └── (gemini.py)        # Future
│   └── (chatgpt.py)       # Future
├── llm/
│   ├── __init__.py        # LLM backend registry
│   ├── base.py            # BaseLLM ABC
│   ├── ollama.py          # Ollama backend
│   └── claude.py          # Claude API backend
├── db.py                  # Universal SQLite schema
├── ingest.py              # Ingestion orchestrator
├── embeddings.py          # ChromaDB + sentence-transformers
├── search.py              # Hybrid search engine
├── rag.py                 # RAG pipeline
├── config.py              # Configuration management
├── app.py                 # Streamlit UI
├── requirements.txt
├── run.sh
├── README.md
├── CONTRIBUTING.md
├── .gitignore
├── data/                  # User drops exports here (gitignored)
├── chatvault.db           # Generated (gitignored)
└── chroma_data/           # Generated (gitignored)
```

---

## Prerequisites

- Python 3.10+
- Ollama installed with a model pulled (`ollama pull llama3`)
- Optional: `ANTHROPIC_API_KEY` env var for Claude API toggle
- An export from any supported platform (Claude to start)

---

## Future Connectors Roadmap (community-driven)

| Platform | Export Method | Priority |
|---|---|---|
| **Claude** (Anthropic) | Data export from Settings | ✅ Phase 1 |
| **ChatGPT** (OpenAI) | Settings → Export data | High — largest user base |
| **Google Gemini** | Google Takeout | High |
| **GitHub Copilot Chat** | VS Code export | Medium |
| **Perplexity** | No official export yet | Low (scraping needed) |
| **Claude Code** (CLI) | Local ~/.claude/ conversations | Medium |

---

## Phase 7: Test Suite & CI/CD

**Goal**: Comprehensive test coverage and automated quality gates for contributors.

**Persona**: Senior Python Backend Engineer + DevOps/Build Engineer

**Files to create**:
- `tests/__init__.py`
- `tests/conftest.py` — shared fixtures (temp DB, sample exports, mock connectors)
- `tests/test_connectors.py` — connector detect/ingest tests
- `tests/test_db.py` — schema creation, insert, query, FTS5
- `tests/test_ingest.py` — orchestrator with mock connectors
- `tests/test_embeddings.py` — chunking, embedding, ChromaDB round-trip
- `tests/test_search.py` — hybrid search, RRF ranking, metadata filters
- `tests/test_rag.py` — RAG pipeline with mock LLM
- `tests/test_security.py` — encryption, cloud sync detection, env-var enforcement
- `.github/workflows/ci.yml` — GitHub Actions pipeline

**Tasks**:

1. **Test fixtures** (`conftest.py`):
   - Minimal Claude export JSON fixture (3 conversations, 10 messages)
   - In-memory SQLite DB factory
   - Temp directory with sample export structure
   - Mock LLM backend returning deterministic responses

2. **Unit tests per module**:
   - `test_connectors.py`: detect returns True/False correctly, ingest produces correct row counts, deduplication on re-import, malformed JSON handling
   - `test_db.py`: schema creation idempotent, insert/query round-trip, FTS5 search returns expected matches
   - `test_ingest.py`: orchestrator discovers connectors, --force rebuilds, --append skips existing
   - `test_embeddings.py`: chunking splits long messages correctly, overlap is correct, metadata preserved through embed→query cycle
   - `test_search.py`: semantic results ranked by relevance, FTS5 fallback works, RRF fusion produces stable ordering, filters narrow results
   - `test_rag.py`: context assembly includes citations, system prompt is correct, conversation memory tracks turns
   - `test_security.py`: cloud sync paths detected, env vars not leaked to config files

3. **Integration test**:
   - End-to-end: drop fixture export → ingest → embed → search → RAG answer
   - Verify answer cites correct conversation

4. **GitHub Actions CI** (`.github/workflows/ci.yml`):
   - Trigger on push/PR to main
   - Matrix: Python 3.10, 3.11, 3.12
   - Steps: install deps → lint (ruff) → type check (mypy) → pytest
   - Connector PR template: must include tests for new connector

5. **Add dev dependencies to `pyproject.toml`**:
   - `pytest`, `pytest-cov`, `ruff`, `mypy`

**Verification**: `pytest --cov=chatvault` passes with >80% coverage. CI green on push.

---

## Phase 8: First-Run Experience (Basic)

**Goal**: Basic first-run onboarding wizard in Streamlit.

**Status**: ✅ Complete (basic 4-step wizard). **Superseded by Phase 12** for the full guided setup experience with model download.

**Persona**: DevOps/Build Engineer + Senior Frontend/UX Engineer

**Files created**:
- `chatvault/onboarding.py` — basic first-run wizard logic
- Updates to `app.py` — onboarding UI integration

**What was built**:
- Detect empty DB (no conversations ingested)
- 4-step wizard: export instructions → data upload → LLM selection → ingest
- Skip wizard on subsequent launches

**Note**: Docker support (Dockerfile, docker-compose.yml) was removed from the project. ChatVault is local-only via `./run.sh`.

---

## Phase 9: Multimodal Support & Attachments

**Goal**: Preserve images, files, and code blocks from AI chat exports instead of silently dropping them.

**Persona**: ML/NLP Engineer + Senior Python Backend Engineer

**Files to modify**:
- `chatvault/connectors/claude.py` — extract non-text content blocks
- `chatvault/db.py` — attachments table
- `chatvault/embeddings.py` — code block embedding strategy
- `chatvault/app.py` — render attachments in Browse tab

**Tasks**:

1. **Attachments schema** (add to `db.py`):
   ```sql
   CREATE TABLE attachments (
       uuid TEXT PRIMARY KEY,
       message_uuid TEXT REFERENCES messages(uuid),
       type TEXT,              -- "image", "file", "code_block"
       filename TEXT,
       mime_type TEXT,
       content BLOB,           -- binary content or code text
       metadata JSON
   );
   ```

2. **Claude connector updates**:
   - Extract `type=image` content blocks → store as attachments
   - Extract `type=code` content blocks → store as attachments with language metadata
   - Extract file attachments from message metadata
   - Keep text extraction unchanged (no regression)

3. **Code block embeddings**:
   - Embed code blocks separately with metadata tag `type=code, language=python`
   - Include in `message_chunks` collection with code-specific prefix for better retrieval

4. **UI rendering**:
   - Browse tab: render images inline, code blocks with syntax highlighting
   - Search results: show code snippets with language badge
   - Chat/RAG: include code context in retrieved chunks

**Verification**: Import export containing images and code → Browse shows them rendered. Search for code-related query → finds relevant code blocks.

---

## Phase 10: Advanced RAG & Search Quality

**Goal**: Measurably better retrieval through reranking, smart context management, and user feedback.

**Persona**: ML/NLP Engineer + AI/LLM Integration Specialist

**Files to create/modify**:
- `chatvault/reranker.py` — cross-encoder reranking
- `chatvault/search.py` — integrate reranker
- `chatvault/rag.py` — token-aware context assembly
- `chatvault/db.py` — feedback table
- `chatvault/app.py` — feedback UI

**Tasks**:

1. **Cross-encoder reranker** (`reranker.py`):
   - Load `cross-encoder/ms-marco-MiniLM-L-6-v2` (CPU-friendly)
   - Rerank top-20 bi-encoder results → return top-5
   - Lazy-load model (only when search is triggered, not on startup)
   - Configurable: can disable reranker for faster but less precise search

2. **Token-aware context assembly** (`rag.py`):
   - Count tokens in retrieved chunks + conversation history
   - Fit within LLM context window (configurable, default 4096 for Ollama, 100K for Claude)
   - Priority: most relevant chunks first, then trim older conversation turns
   - Never truncate mid-chunk; drop lowest-ranked chunks instead

3. **User feedback loop**:
   - Thumbs up/down on RAG answers in chat UI
   - Store in `feedback` table: query, retrieved chunk IDs, rating, timestamp
   - Surface feedback stats in Stats tab
   - Future: use feedback to fine-tune retrieval (boost/bury chunks)

4. **Search quality metrics**:
   - Log search latency, result count, click-through (which result user expanded)
   - Dashboard in Stats tab: avg search time, most-searched queries, low-result queries

**Verification**: Reranked results demonstrably more relevant than raw bi-encoder. Token budget never exceeded. Feedback persists across sessions.

---

## Phase 11: Export, Tagging & Conversation Management

**Goal**: Let users organize, annotate, and export their knowledge base.

**Persona**: Senior Frontend/UX Engineer + Senior Python Backend Engineer

**Files to modify**:
- `chatvault/db.py` — tags table, export queries
- `chatvault/app.py` — tagging UI, export UI
- `chatvault/export.py` — export engine (new)

**Tasks**:

1. **Tagging system** (`db.py`):
   ```sql
   CREATE TABLE tags (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       name TEXT UNIQUE
   );
   CREATE TABLE conversation_tags (
       conversation_uuid TEXT REFERENCES conversations(uuid),
       tag_id INTEGER REFERENCES tags(id),
       PRIMARY KEY (conversation_uuid, tag_id)
   );
   ```

2. **Bookmarks/favorites**:
   - Boolean `starred` column on conversations table
   - Filter by starred in Browse and Search tabs

3. **Export engine** (`export.py`):
   - Export formats: JSON, CSV, Markdown
   - Scopes: single conversation, search results, all conversations, tagged subset
   - Include metadata, timestamps, source platform
   - RAG chat transcripts exportable as markdown

4. **UI integration**:
   - Browse tab: tag editor, star toggle, bulk actions
   - Search tab: filter by tag
   - Settings tab: export panel with format/scope selectors, download button

**Verification**: Tag conversations → filter by tag. Export search results as CSV → valid file with all fields. Star conversations → filter works.

---

## Updated Dependency Graph

```
Phase 0 (Scaffolding)
  └──→ Phase 1 (Connectors) ──→ Phase 2 (Embeddings) ──→ Phase 3 (Search+RAG) ──→ Phase 4 (UI)
                                                                                      │
                                                                            ┌─────────┼─────────┐
                                                                            ▼         ▼         ▼
                                                                      Phase 5    Phase 6    Phase 7
                                                                     (Package)  (Security)  (Tests)
                                                                                              │
                                                                            ┌─────────────────┤
                                                                            ▼                 ▼
                                                                      Phase 8            Phase 9
                                                                     (Docker)         (Multimodal)
                                                                            │                 │
                                                                            └────────┬────────┘
                                                                                     ▼
                                                                               Phase 10
                                                                            (Advanced RAG)
                                                                                     │
                                                                                     ▼
                                                                               Phase 11
                                                                          (Export & Tagging)
```

- Phases 5, 6, 7 can run in parallel after Phase 4
- Phase 8 (basic onboarding) superseded by Phase 12
- Phase 9 can run independently after Phase 4
- Phase 10 depends on Phase 3 (enhances existing RAG)
- Phase 11 depends on Phase 4 (extends UI)
- Phase 12 depends on Phase 4 (UI) and Phase 5 (config)

---

## Phase 12: First-Time Setup Wizard

**Goal**: Replace the basic onboarding with a full interactive Streamlit wizard that handles platform selection, data export guidance, Ollama model selection & automatic download with progress, and ingestion.

**Persona**: Senior Frontend/UX Engineer + AI/LLM Integration Specialist

**Files to modify**:
- `chatvault/onboarding.py` — rewrite wizard (5 steps)
- `chatvault/llm/ollama.py` — add `list_models()` and `pull_model()` helpers
- `chatvault/config.py` — persist wizard choices

**Tasks**:

### Step 1: Welcome + Platform Selection
- Welcome message explaining what ChatVault does
- Radio buttons for data source:
  - **Claude** (enabled) — "Ready"
  - **ChatGPT** (disabled) — "Coming Soon" badge
  - **Gemini** (disabled) — "Coming Soon" badge
- Selection stored in session state

### Step 2: Export Instructions
- Based on platform selected in Step 1, show that connector's `get_export_instructions()`
- For Claude: step-by-step guide to export from claude.ai → Settings → Account → Export Data

### Step 3: Upload / Provide Data
- File upload or folder path input
- Validate that the selected connector's `detect()` passes on the provided data
- Clear error message if validation fails

### Step 4: LLM Model Selection & Download
- Check if Ollama is running via `is_available()`
  - If not running: show install instructions (`brew install ollama && ollama serve`)
  - If running: proceed to model selection
- Model selection cards with radio buttons:
  - **tinyllama** (1.1B) — "Fastest, lowest quality. ~700MB. Good for testing."
  - **llama3.2:1b** (1.3B) — "Fast, decent quality. ~1.3GB."
  - **llama3** (8B) — "Recommended. Good balance of speed and quality. ~4.7GB."
  - **llama3.1** (70B) — "Best quality, very slow. ~40GB. Needs 64GB+ RAM."
- Also show Claude API option: text input for API key (saved to env)
- "Download & Install" button triggers `ollama pull <model>` via streaming API
- Real-time progress bar in Streamlit using Ollama's `/api/pull` streaming endpoint
- On completion, verify model is available via API

### Step 5: Import & Go
- Run ingestion + embedding with progress bar (same as current Step 4)
- Save config (chosen model, backend) to `~/.chatvault/config.yaml`
- Show success, launch app

### Ollama helpers (`chatvault/llm/ollama.py`)

```python
def list_models(host: str = "http://localhost:11434") -> list[str]:
    """GET /api/tags, return list of installed model names."""

def pull_model(model_name: str, host: str = "http://localhost:11434") -> Generator[dict, None, None]:
    """POST /api/pull with stream=true, yield progress dicts with status/completed/total fields."""
```

The pull uses `requests.post(host + "/api/pull", json={"name": model, "stream": True}, stream=True)` and parses newline-delimited JSON for real-time progress updates.

**Verification**: Delete `~/.chatvault/config.yaml` and `chatvault.db` → run `streamlit run chatvault/app.py` → wizard appears → select Claude → see instructions → upload data → pick model → watch download progress → ingestion runs → app launches with working search/chat.
