"""Export engine for ChatVault — JSON, CSV, Markdown formats."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from chatvault.db import Database


class ExportEngine:
    """Export conversations in various formats."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def export_conversation_json(self, conv_uuid: str) -> str:
        messages = self.db.get_conversation_messages(conv_uuid)
        return json.dumps(messages, indent=2, default=str)

    def export_conversation_markdown(self, conv_uuid: str) -> str:
        convs = self.db.conn.execute(
            "SELECT * FROM conversations WHERE uuid = ?", (conv_uuid,)
        ).fetchone()
        conv = dict(convs) if convs else {}
        messages = self.db.get_conversation_messages(conv_uuid)
        lines = [f"# {conv.get('name', 'Untitled')}\n"]
        if conv.get('created_at'):
            lines.append(f"*{conv['created_at']}*\n")
        lines.append("---\n")
        for m in messages:
            role = "**You**" if m["sender"] == "human" else "**Assistant**"
            lines.append(f"{role}:\n\n{m.get('text', '')}\n")
            lines.append("---\n")
        return "\n".join(lines)

    def export_conversation_csv(self, conv_uuid: str) -> str:
        messages = self.db.get_conversation_messages(conv_uuid)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["uuid", "conversation_uuid", "position", "sender", "text", "created_at"])
        writer.writeheader()
        for m in messages:
            writer.writerow({k: m.get(k, "") for k in writer.fieldnames})
        return output.getvalue()

    def export_all_json(self) -> str:
        convs = self.db.get_all_conversations()
        result = []
        for c in convs:
            c["messages"] = self.db.get_conversation_messages(c["uuid"])
            result.append(c)
        return json.dumps(result, indent=2, default=str)

    def export_search_results_csv(self, results: list[dict[str, Any]]) -> str:
        if not results:
            return ""
        output = io.StringIO()
        fields = ["conversation_uuid", "message_uuid", "conversation_name", "text", "score", "sender", "created_at"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow({k: getattr(r, k, "") if hasattr(r, k) else r.get(k, "") for k in fields})
        return output.getvalue()
