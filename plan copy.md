# Claude Chat History — Personal Knowledge Assistant

## Overview

Build a local-first **personal knowledge assistant** over your Claude conversation history. Not just search — a RAG-powered chat interface where you can ask questions about your past conversations and get synthesized answers with citations. Also serves as a persistent, growing backup of all your Claude data.

**Stack**: Python + SQLite + ChromaDB + sentence-transformers + Ollama + Claude API (toggle) + Streamlit

---

## Data Profile

| File | Records | Key Fields |
|---|---|---|
| `conversations.json` | 695 convos, 7,409 msgs | uuid, name, summary, created_at, chat_messages[].text/sender |
| `projects.json` | 16 projects | uuid, name, description, docs |
| `memories.json` | 1 record | conversations_memory, project_memories |

Each message has: uuid, text, content (list of blocks with type/text), sender (human/assistant), timestamps, attachments, files.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Streamlit UI                           │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Chat (RAG)  │  │  Search      │  │  Browse/Stats  │  │
│  │  Ask anything │  │  Find convos │  │  All convos    │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  │
└─────────┼─────────────────┼──────────────────┼───────────┘
          │                 │                  │
    ┌─────▼─────────────────▼──────┐    ┌─────▼─────┐
    │         RAG Pipeline          │    │  SQLite    │
    │  1. Embed query               │    │ (structured│
    │  2. Retrieve chunks (ChromaDB)│    │  data)     │
    │  3. Build prompt + context    │    └───────────┘
    │  4. LLM generates answer      │          ▲
    │     ┌──────────┐              │          │
    │     │ Ollama   │ (default)    │          │
    │     │ Claude   │ (toggle)     │          │
    │     └──────────┘              │          │
    └───────────┬───────────────────┘          │
                │                              │
          ┌─────▼─────┐                        │
          │  ChromaDB  │                        │
          │  (vectors) │                        │
          └────────────┘                        │
                ▲                               │
                │         Ingestion             │
                └───────── Script ──────────────┘
                             ▲
                             │
                     JSON dump files
                  (initial + future exports)
```

---

## Phase 1: Data Ingestion & Storage Layer

**Goal**: Parse JSON → SQLite database + prepare chunking logic

**Files to create**:
- `chat_search/ingest.py` — main ingestion script
- `chat_search/db.py` — SQLite schema and helpers

**Tasks**:
1. Define SQLite schema:
   - `conversations` (uuid PK, name, summary, project_uuid, created_at, updated_at)
   - `messages` (uuid PK, conversation_uuid FK, sender, text, created_at, position INT)
   - `projects` (uuid PK, name, description)
   - `memories` (id PK, type TEXT, content TEXT)
   - FTS5 virtual table on messages.text + conversations.name + conversations.summary (keyword fallback)

2. Parse `conversations.json`:
   - Extract `text` from each `content` block (type=text) and concatenate
   - Store each message as a row with `position` (order in conversation)
   - Link to project if `account` field maps to a project

3. Parse `projects.json` and `memories.json`

4. Chunking strategy for embeddings (prepare, don't embed yet):
   - **Conversation-level chunk**: name + summary + first 2 human messages (topic discovery)
   - **Message-level chunks**: each assistant message as its own chunk (specific answers)
   - Metadata per chunk: conversation_uuid, message_uuid, sender, date, conversation_name
   - Long messages (>500 tokens): split into overlapping chunks ~400 tokens, 50-token overlap

5. Re-ingestion support: `--force` flag to rebuild; `--append` to add a new export without rebuilding. Deduplication by message uuid.

**Verification**: Run `ingest.py`, confirm row counts (695 convos, 7409 messages, 16 projects).

---

## Phase 2: Embedding Generation & Vector Store

**Goal**: Generate embeddings for all chunks, store in ChromaDB

**Files to create**:
- `chat_search/embeddings.py` — embedding + ChromaDB logic

**Tasks**:
1. Load `sentence-transformers/all-MiniLM-L6-v2` (22M params, fast on CPU)

2. Create two ChromaDB collections:
   - `conversation_topics` — conversation-level chunks (~695 vectors)
   - `message_chunks` — message-level chunks (~8K-12K vectors)

3. Embed all chunks with metadata:
   - Each vector stores: conversation_uuid, message_uuid, sender, date, conversation_name

4. Persist ChromaDB to `chat_search/chroma_data/`

5. Incremental embedding: only embed new chunks when `--append` is used

**Verification**: Confirm collection counts. Test query "Bitcoin investment strategy" → print top 5 with scores.

---

## Phase 3: Search & RAG Pipeline

**Goal**: Build search functions + RAG pipeline with dual-LLM support

**Files to create**:
- `chat_search/search.py` — search logic
- `chat_search/rag.py` — RAG pipeline + LLM integration

### Search (search.py)

1. **Semantic search**: Query ChromaDB, return top-K with similarity scores
2. **Keyword fallback**: SQLite FTS5 when semantic scores are poor
3. **Hybrid ranking**: Reciprocal rank fusion (RRF) combining vector + FTS5
4. **Metadata filters**: date range, sender, project
5. **Result format**:
   ```python
   @dataclass
   class SearchResult:
       conversation_uuid: str
       conversation_name: str
       message_uuid: str | None
       matched_text: str
       score: float
       date: str
       sender: str
   ```
6. **Conversation loader**: full threaded conversation from SQLite by uuid

### RAG Pipeline (rag.py)

1. **Retrieval**: Given user question → embed → retrieve top-10 relevant chunks from ChromaDB
2. **Context assembly**: Build prompt with:
   - System instruction: "You are a personal knowledge assistant. Answer based on the user's past conversations. Always cite which conversation and date your answer comes from."
   - Retrieved chunks formatted as context blocks with source metadata
   - User's question
3. **LLM backends** (toggle via config):
   - **Ollama** (default): Call local Ollama API (`http://localhost:11434`), model: `llama3` or `mistral`
   - **Claude API** (optional): Call Anthropic API with user's API key
   - Common interface: `generate(prompt, model_backend) → response`
4. **Response format**: Answer text + list of cited sources (conversation name, date, link to conversation)
5. **Conversation memory**: Keep last N turns of the chat session so follow-up questions work ("tell me more about that")

**Verification**:
- "What was my investment strategy?" → should synthesize from multiple investment convos
- "What Cisco projects did I work on?" → should cite career-related convos
- Follow-up: "Can you draft a resume bullet from that?" → should use prior context

---

## Phase 4: Streamlit UI

**Goal**: Chat-first interface with search and browse as secondary tabs

**Files to create**:
- `chat_search/app.py` — Streamlit application

**Tasks**:

### Tab 1: Chat (primary)
- Chat input at bottom, message history above (ChatGPT-style layout using `st.chat_message`)
- Each assistant response shows cited sources as expandable cards below the answer
- Click a source → expands to show the full original conversation snippet
- Sidebar: LLM toggle (Ollama / Claude API), model selector
- Session memory: follow-up questions work within a session

### Tab 2: Search
- Search bar with natural language input
- Filters sidebar: date range picker, sender toggle, project dropdown
- Results as cards: conversation name, date, matched snippet, relevance score
- Click result → opens conversation detail in a modal/expander

### Tab 3: Browse
- Sortable/filterable table of all conversations (name, date, message count, summary)
- Click row → expand full conversation thread (alternating human/assistant bubbles)

### Tab 4: Stats
- Total conversations, messages, date range
- Conversations per month bar chart
- Top topics word cloud or frequency chart from conversation names

### Global
- LLM status indicator in sidebar (Ollama connected / Claude API configured)
- "Re-ingest" button to load new JSON exports without leaving the UI

**Verification**: Launch app, test chat with follow-ups, search, browse, and stats tabs.

---

## Phase 5: Polish & Packaging

**Goal**: One-command setup, easy maintenance, future-proof

**Files to create**:
- `chat_search/requirements.txt`
- `chat_search/config.py` — configuration management
- `chat_search/run.sh` — launcher

**Tasks**:

1. `requirements.txt`:
   ```
   streamlit
   chromadb
   sentence-transformers
   torch --index-url https://download.pytorch.org/whl/cpu
   anthropic
   requests  # for Ollama API
   ```

2. `config.py`:
   - Data directory path (where JSON dumps live)
   - LLM backend selection (ollama / claude)
   - Ollama model name + URL
   - Claude API key (from env var `ANTHROPIC_API_KEY`)
   - ChromaDB / SQLite paths

3. `run.sh`:
   ```bash
   #!/bin/bash
   cd "$(dirname "$0")"
   pip install -r requirements.txt --quiet
   python ingest.py --append  # ingest new data, skip existing
   streamlit run app.py
   ```

4. Export: download search results or chat transcripts as JSON/CSV from UI

5. Future data ingestion: document how to drop a new JSON export into the data folder and re-ingest

**Verification**: Fresh install test — delete generated files, run `./run.sh`, confirm full pipeline.

---

## Dependency Graph

```
Phase 1 (Ingestion) ──→ Phase 2 (Embeddings) ──→ Phase 3 (Search + RAG) ──→ Phase 4 (UI)
                                                                                  │
                                                                        Phase 5 (Polish) + Phase 6 (Security)
```

- Phases are sequential (each needs the prior phase's output)
- Phase 5 and Phase 6 can run in parallel with Phase 4
- Each phase is scoped to ~200K token agent execution

---

## Project Structure

```
chat_search/
├── ingest.py          # Phase 1: JSON → SQLite + chunking
├── db.py              # Phase 1: SQLite schema/helpers
├── embeddings.py      # Phase 2: Embedding + ChromaDB
├── search.py          # Phase 3: Search engine
├── rag.py             # Phase 3: RAG pipeline + LLM backends
├── config.py          # Phase 5: Configuration
├── app.py             # Phase 4: Streamlit UI
├── requirements.txt   # Phase 5: Dependencies
├── run.sh             # Phase 5: Launcher
├── chat_search.db     # Generated: SQLite database
└── chroma_data/       # Generated: ChromaDB persistence
```

---

## Phase 6: Security Hardening

**Goal**: Protect sensitive personal data at rest and in transit

**Tasks**:

1. **Encrypt SQLite database**: Use `sqlcipher` (drop-in replacement for sqlite3) with a passphrase. App prompts for password on startup, decrypts in memory only.

2. **Encrypt ChromaDB at rest**: ChromaDB stores data as parquet files on disk. Wrap the `chroma_data/` directory in an encrypted APFS volume (macOS native) that mounts on app start.

3. **Secure raw JSON dumps**: After successful ingestion, the app prompts to securely delete the raw JSON files (they're the most dangerous artifact — plaintext, portable, complete).

4. **Ollama network binding**: Verify and enforce `localhost` only binding. Add a startup check in `run.sh` that confirms Ollama is not exposed on `0.0.0.0`.

5. **No cloud sync**: Startup warning if `chat_search/` directory is inside iCloud Drive, Dropbox, Google Drive, or OneDrive paths.

6. **API key handling**: Claude API key read from env var only, never stored in config files or committed to any repo.

7. **Session data**: Chat session history (RAG conversation memory) stored in-memory only, never written to disk.

8. **FileVault check**: `run.sh` warns if macOS FileVault (full-disk encryption) is not enabled.

**Verification**:
- Confirm DB cannot be read without passphrase
- Confirm `chroma_data/` is not accessible without mount
- Confirm no sensitive data in plaintext on disk after setup

---

## Prerequisites (user must have installed)

- Python 3.10+
- Ollama installed (`brew install ollama`) with a model pulled (`ollama pull llama3`)
- Optional: `ANTHROPIC_API_KEY` env var for Claude API toggle
