"""Template connector — copy this file to create a new connector.

Usage:
    cp chatvault/connectors/TEMPLATE.py chatvault/connectors/myplatform.py

Then rename the class, update source_id/source_name, and implement the three methods.
"""
from pathlib import Path
from chatvault.connectors.base import BaseConnector, IngestResult
from chatvault.db import Database


class MyPlatformConnector(BaseConnector):
    """Connector for MyPlatform exports.

    Each connector must define source_id (unique slug) and source_name (display name),
    then implement detect(), ingest(), and get_export_instructions().
    """

    # Unique identifier for this platform — used in the database source table.
    source_id = "myplatform"

    # Human-readable name — shown in the UI.
    source_name = "My Platform"

    def detect(self, data_dir: Path) -> bool:
        """Check if MyPlatform export files exist in data_dir.

        Return True if you find the expected export files.
        Be specific — don't match files from other platforms.

        Example:
            return (data_dir / "myplatform_export.json").exists()
        """
        # TODO: Replace with your platform's export file detection logic
        return False

    def ingest(self, data_dir: Path, db: Database) -> IngestResult:
        """Parse export files and insert into the universal schema.

        Steps:
            1. Register the source:       db.upsert_source(self.source_id, self.source_name)
            2. Parse your export files:    load JSON/CSV/etc from data_dir
            3. Insert conversations:       db.insert_conversation(...)
            4. Insert messages:            db.insert_message(...)
               - Normalize sender to "human" or "assistant"
               - Store platform-specific fields in the metadata JSON column

        Returns:
            IngestResult with counts of conversations and messages ingested.
        """
        # TODO: Implement ingestion logic
        conversations = 0
        messages = 0

        # Example skeleton:
        # db.upsert_source(self.source_id, self.source_name)
        # for chat in parsed_data:
        #     db.insert_conversation(source_id=self.source_id, ...)
        #     for msg in chat["messages"]:
        #         sender = "human" if msg["role"] == "user" else "assistant"
        #         db.insert_message(conversation_id=..., sender=sender, text=msg["text"])
        #         messages += 1
        #     conversations += 1

        return IngestResult(
            source_id=self.source_id,
            conversations=conversations,
            messages=messages,
        )

    def get_export_instructions(self) -> str:
        """Return user-facing instructions for exporting from this platform.

        This text is shown in the UI to help users obtain their export files.
        """
        return "Go to MyPlatform Settings > Export > Download"
