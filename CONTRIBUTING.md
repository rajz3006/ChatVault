# Contributing to ChatVault

## Adding a New Connector

ChatVault uses a pluggable connector system. To add support for a new AI platform:

### Step 1: Copy the template

```bash
cp chatvault/connectors/TEMPLATE.py chatvault/connectors/myplatform.py
```

### Step 2: Implement the interface

Your connector must extend `BaseConnector` and implement three methods:

```python
class BaseConnector(ABC):
    source_id: str       # Unique identifier, e.g. "chatgpt"
    source_name: str     # Display name, e.g. "ChatGPT"

    def detect(self, data_dir: Path) -> bool:
        """Return True if this connector's export files exist in data_dir."""

    def ingest(self, data_dir: Path, db: Database) -> IngestResult:
        """Parse export files, insert into the universal schema, return result."""

    def get_export_instructions(self) -> str:
        """Return user-facing instructions for exporting from this platform."""
```

### Step 3: Follow the universal schema

When ingesting, use the `Database` methods to insert:

1. **Source** -- register your platform via `db.upsert_source()`
2. **Conversations** -- one per chat thread via `db.insert_conversation()`
3. **Messages** -- normalize sender to `"human"` or `"assistant"` via `db.insert_message()`

Platform-specific fields go in the `metadata` JSON column.

### Step 4: Auto-discovery

Connectors are auto-discovered from `chatvault/connectors/`. Just place your file there and it will be picked up -- no registration needed.

### Step 5: Test

- Place a sample export in `data/` and run `python -m chatvault.ingest --append`
- Verify conversations and messages appear in the database
- Check edge cases: empty exports, missing fields, duplicate runs (idempotency)

## Testing Guidelines

- Test with real and minimal exports
- Ensure idempotent ingestion (running twice should not duplicate data)
- Verify sender normalization (`"human"` / `"assistant"` only)
- Check that `detect()` returns `False` for unrelated files

## PR Guidelines

- One connector per PR
- Include a sample (anonymized) export snippet in the PR description
- Ensure no hardcoded paths or secrets
- Add a brief entry to the Supported Platforms table in README.md
