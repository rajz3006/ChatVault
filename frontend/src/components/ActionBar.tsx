import { useState, useCallback, useEffect } from "react";
import type { Conversation } from "../types";
import * as api from "../api";

interface Tag {
  id: number;
  name: string;
}

interface Props {
  conversation: Conversation;
  onToggleStar: () => void;
  onRefresh: () => void;
}

export default function ActionBar({ conversation, onToggleStar, onRefresh }: Props) {
  const [tagInput, setTagInput] = useState("");
  const [tags, setTags] = useState<Tag[]>([]);
  const [format, setFormat] = useState("markdown");

  const fetchTags = useCallback(async () => {
    try {
      const data = await api.getTags(conversation.uuid);
      setTags(data);
    } catch {
      // ignore
    }
  }, [conversation.uuid]);

  useEffect(() => {
    fetchTags();
  }, [fetchTags]);

  const handleAddTag = useCallback(async () => {
    const name = tagInput.trim();
    if (!name) return;
    try {
      await api.addTag(conversation.uuid, name);
      setTagInput("");
      await fetchTags();
    } catch {
      // ignore
    }
  }, [tagInput, conversation.uuid, fetchTags]);

  const handleRemoveTag = useCallback(async (tagId: number) => {
    try {
      await api.removeTag(conversation.uuid, tagId);
      await fetchTags();
    } catch {
      // ignore
    }
  }, [conversation.uuid, fetchTags]);

  const handleToggleStar = useCallback(async () => {
    onToggleStar();
    // Small delay to let state propagate, then refresh conversation list
    setTimeout(() => onRefresh(), 100);
  }, [onToggleStar, onRefresh]);

  const handleExport = useCallback(async () => {
    try {
      const blob = await api.exportConversation(conversation.uuid, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${conversation.name || "conversation"}.${format === "markdown" ? "md" : format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // ignore
    }
  }, [conversation, format]);

  return (
    <div className="action-bar">
      <button className="action-btn" onClick={handleToggleStar} title="Toggle star">
        {conversation.starred ? "\u2605" : "\u2606"} Star
      </button>

      <div className="tag-input-group">
        <input
          type="text"
          className="tag-input"
          placeholder="Add tag..."
          value={tagInput}
          onChange={(e) => setTagInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleAddTag();
          }}
        />
      </div>

      {tags.length > 0 && (
        <div className="tag-list">
          {tags.map((tag) => (
            <span key={tag.id} className="tag-chip">
              {tag.name}
              <button
                className="tag-remove-btn"
                onClick={() => handleRemoveTag(tag.id)}
                title="Remove tag"
              >
                &times;
              </button>
            </span>
          ))}
        </div>
      )}

      <select
        className="format-select"
        value={format}
        onChange={(e) => setFormat(e.target.value)}
      >
        <option value="markdown">Markdown</option>
        <option value="json">JSON</option>
        <option value="txt">Plain Text</option>
      </select>

      <button className="action-btn" onClick={handleExport}>
        Export
      </button>
    </div>
  );
}
