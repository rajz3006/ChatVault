"""Claude (Anthropic) platform connector for ChatVault."""
import json
from pathlib import Path

from chatvault.connectors.base import BaseConnector, IngestResult
from chatvault.db import Database


class ClaudeConnector(BaseConnector):
    """Connector for Anthropic Claude chat exports."""

    source_id = "claude"
    source_name = "Anthropic Claude"

    def detect(self, data_dir: Path) -> bool:
        """Detect Claude export by looking for conversations.json with chat_messages."""
        conv_file = data_dir / "conversations.json"
        if not conv_file.exists():
            return False
        try:
            with open(conv_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                return "chat_messages" in data[0]
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
        return False

    def ingest(self, data_dir: Path, db: Database) -> IngestResult:
        """Parse Claude export files and insert into the database."""
        db.upsert_source(self.source_id, self.source_name, str(data_dir))

        conv_count = 0
        msg_count = 0
        extras: dict[str, int] = {}

        # --- Conversations ---
        conv_file = data_dir / "conversations.json"
        with open(conv_file, "r", encoding="utf-8") as f:
            conversations = json.load(f)

        # --- Projects (load for cross-referencing) ---
        projects_map: dict[str, dict] = {}
        proj_file = data_dir / "projects.json"
        if proj_file.exists():
            with open(proj_file, "r", encoding="utf-8") as f:
                projects = json.load(f)
            extras["projects"] = len(projects)
            for proj in projects:
                projects_map[proj.get("uuid", "")] = {
                    "name": proj.get("name"),
                    "description": proj.get("description"),
                }

        # --- Memories ---
        mem_file = data_dir / "memories.json"
        if mem_file.exists():
            with open(mem_file, "r", encoding="utf-8") as f:
                memories = json.load(f)
            extras["memories"] = len(memories)

        # --- Ingest conversations and messages ---
        for conv in conversations:
            conv_uuid = conv.get("uuid")
            if not conv_uuid:
                continue

            account = conv.get("account") or {}
            meta: dict = {"account_uuid": account.get("uuid")}

            # Link project if referenced
            project = conv.get("project")
            if project and isinstance(project, dict):
                proj_uuid = project.get("uuid", "")
                if proj_uuid in projects_map:
                    meta["project"] = projects_map[proj_uuid]

            db.upsert_conversation(
                uuid=conv_uuid,
                source_id=self.source_id,
                name=conv.get("name"),
                summary=conv.get("summary") or None,
                created_at=conv.get("created_at"),
                updated_at=conv.get("updated_at"),
                metadata=meta,
            )
            conv_count += 1

            messages = conv.get("chat_messages") or []
            for pos, msg in enumerate(messages):
                msg_uuid = msg.get("uuid")
                if not msg_uuid:
                    continue

                sender = msg.get("sender", "")
                if sender not in ("human", "assistant"):
                    continue  # skip unknown senders

                text = self._extract_text(msg)

                msg_meta: dict = {}
                if msg.get("attachments"):
                    msg_meta["attachments"] = len(msg["attachments"])
                if msg.get("files"):
                    msg_meta["files"] = len(msg["files"])

                db.upsert_message(
                    uuid=msg_uuid,
                    conversation_uuid=conv_uuid,
                    position=pos,
                    sender=sender,
                    text=text,
                    created_at=msg.get("created_at"),
                    metadata=msg_meta if msg_meta else None,
                )
                msg_count += 1

                # Extract attachments from content blocks
                att_index = 0
                content_blocks = msg.get("content") or []
                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type", "")
                    if block_type == "code":
                        att_uuid = f"{msg_uuid}-att-{att_index}"
                        code_text = block.get("text") or block.get("code") or ""
                        language = block.get("language") or ""
                        db.upsert_attachment(
                            uuid=att_uuid,
                            message_uuid=msg_uuid,
                            type="code_block",
                            content=code_text.encode("utf-8") if code_text else None,
                            metadata={"language": language},
                        )
                        att_index += 1
                    elif block_type == "image":
                        att_uuid = f"{msg_uuid}-att-{att_index}"
                        db.upsert_attachment(
                            uuid=att_uuid,
                            message_uuid=msg_uuid,
                            type="image",
                        )
                        att_index += 1
                if att_index > 0:
                    extras["attachments"] = extras.get("attachments", 0) + att_index

        db.commit()
        return IngestResult(
            source_id=self.source_id,
            conversations=conv_count,
            messages=msg_count,
            extras=extras,
        )

    def get_export_instructions(self) -> str:
        """Return instructions for exporting Claude chat data."""
        return (
            "To export your Claude data:\n"
            "1. Go to claude.ai -> Settings -> Account\n"
            "2. Click 'Export Data'\n"
            "3. You'll receive a download link via email\n"
            "4. Extract the ZIP and place the folder in ChatVault's data/ directory"
        )

    @staticmethod
    def _extract_text(msg: dict) -> str | None:
        """Extract text from a message's content blocks, falling back to top-level text."""
        content_blocks = msg.get("content") or []
        parts: list[str] = []
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if t:
                    parts.append(t)
        if parts:
            return "\n".join(parts)
        # Fallback to top-level text field
        return msg.get("text") or None
