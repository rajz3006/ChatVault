import { useState, useCallback } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");

  const handleSubmit = useCallback(() => {
    if (disabled) return;
    const trimmed = value.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setValue("");
  }, [value, onSend, disabled]);

  return (
    <div className="chat-input-bar">
      <input
        type="text"
        className="chat-input"
        placeholder="Interact with your chat history..."
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
          }
        }}
      />
      <button className="chat-send-btn" onClick={handleSubmit} disabled={disabled || !value.trim()}>
        {"\u2B06"}
      </button>
    </div>
  );
}
