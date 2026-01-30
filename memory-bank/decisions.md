# Architecture & Implementation Decisions

## Decision Log

### 2026-01-29 — Project Setup
- **Decision**: Use `memory-bank/` folder for agentic context and session tracking
- **Rationale**: Allows any Claude session to pick up where the last one left off by reading session-state.md
- **Decision**: CLAUDE.md references memory-bank for current progress rather than duplicating state
- **Rationale**: Single source of truth for session state avoids drift
