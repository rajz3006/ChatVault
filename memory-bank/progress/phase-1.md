# Phase 1: Connector Framework + Claude Connector + Storage

## Status: NOT STARTED

## Tasks

- [ ] 1. Define `BaseConnector` ABC (`chatvault/connectors/base.py`)
  - `detect()`, `ingest()`, `get_export_instructions()`
  - `IngestResult` dataclass

- [ ] 2. Implement `ClaudeConnector` (`chatvault/connectors/claude.py`)
  - `detect()`: look for conversations.json with Claude schema signature
  - `ingest()`: parse conversations.json, projects.json, memories.json
  - Extract text from content blocks, normalize sender to human/assistant
  - Store Claude-specific fields in metadata JSON
  - Deduplication by message uuid

- [ ] 3. Connector auto-discovery registry (`chatvault/connectors/__init__.py`)

- [ ] 4. Universal SQLite schema (`chatvault/db.py`)
  - sources, conversations, messages tables
  - FTS5 virtual table for keyword search
  - Helper functions for inserts/queries

- [ ] 5. Ingestion orchestrator (`chatvault/ingest.py`)
  - Scan connectors, detect, ingest
  - `--force` (rebuild) and `--append` (incremental) modes
  - Print summary

- [ ] 6. Chunking logic (prepare chunks for Phase 2)
  - Conversation-level chunks
  - Message-level chunks
  - Long message splitting (>500 tokens, ~400 token chunks, 50 overlap)
  - Metadata per chunk

## Verification
`python -m chatvault.ingest data/` → 695 convos, 7409 messages, 16 projects from Claude source
