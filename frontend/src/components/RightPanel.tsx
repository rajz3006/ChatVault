import { useState } from "react";
import ReactMarkdown from "react-markdown";
import type { Conversation, Message, ChatMessage, SearchResult } from "../types";
import ThreadView from "./ThreadView";
import ChatInput from "./ChatInput";
import ActionBar from "./ActionBar";
import SettingsPopover from "./SettingsPopover";

interface Props {
  conversation: Conversation | null;
  messages: Message[];
  loadingMessages: boolean;
  chatHistory: ChatMessage[];
  showAiOverlay: boolean;
  isAiLoading: boolean;
  onSend: (text: string) => void;
  onToggleStar: () => void;
  onRefreshConversations: () => void;
  onDismissAi: () => void;
  onResumeAi: () => void;
  onClearAiChat: () => void;
}

function SourcesBlock({ sources }: { sources: SearchResult[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!sources || sources.length === 0) return null;

  return (
    <div className="ai-sources-block">
      <button
        className="ai-sources-toggle"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="ai-sources-icon">{expanded ? "\u25BE" : "\u25B8"}</span>
        <span>Sources ({sources.length})</span>
      </button>
      {expanded && (
        <ul className="ai-sources-list">
          {sources.map((s, i) => (
            <li key={i} className="ai-source-item">
              <span className="ai-source-num">[{i + 1}]</span>
              <span className="ai-source-title">{s.conversation_name || "Untitled"}</span>
              {s.created_at && (
                <span className="ai-source-date">
                  {new Date(s.created_at).toLocaleDateString()}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function RightPanel({
  conversation,
  messages,
  loadingMessages,
  chatHistory,
  showAiOverlay,
  isAiLoading,
  onSend,
  onToggleStar,
  onRefreshConversations,
  onDismissAi,
  onResumeAi,
  onClearAiChat,
}: Props) {
  const [showSettings, setShowSettings] = useState(false);

  return (
    <div className="right-panel">
      <div className="right-header">
        <h2 className="right-title">{conversation?.name || "ChatVault"}</h2>
        <div className="settings-wrapper">
          <button
            className="settings-btn"
            onClick={() => setShowSettings((v) => !v)}
          >
            {"\u2699"} Settings
          </button>
          {showSettings && (
            <SettingsPopover onClose={() => setShowSettings(false)} />
          )}
        </div>
      </div>

      {conversation && (
        <ActionBar
          conversation={conversation}
          onToggleStar={onToggleStar}
          onRefresh={onRefreshConversations}
        />
      )}

      <div className="right-divider" />

      <div className="thread-area">
        {loadingMessages ? (
          <div className="thread-loading">Loading messages...</div>
        ) : conversation ? (
          <ThreadView messages={messages} />
        ) : (
          <div className="empty-state">
            <div className="empty-icon">{"\uD83D\uDCAC"}</div>
            <p>Select a conversation or ask about your chat history</p>
            <p className="empty-sub">Browse your past conversations on the left, or type a question below to search across all your chats</p>
          </div>
        )}
      </div>

      {/* Resume AI Chat floating button - above the chat input */}
      {!showAiOverlay && chatHistory.length > 0 && (
        <button className="resume-ai-chat-btn" onClick={onResumeAi}>
          {"\u2726"} Resume AI Chat
        </button>
      )}

      <ChatInput onSend={onSend} />

      {/* AI Chat Overlay */}
      {showAiOverlay && chatHistory.length > 0 && (
        <div className="ai-chat-overlay">
          <div className="ai-chat-header">
            <span className="ai-chat-header-title">RAG Chat</span>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="ai-chat-close-btn" onClick={onDismissAi}>
                Back to conversation
              </button>
              <button className="ai-chat-close-btn" onClick={onClearAiChat}>
                Clear chat
              </button>
            </div>
          </div>
          <div className="ai-chat-body">
            {chatHistory.map((msg, i) => (
              <div key={i} className="ai-chat-msg" style={{ animationDelay: `${i * 50}ms` }}>
                <div className={msg.role === "user" ? "ai-avatar-user" : "ai-avatar-assistant"}>
                  {msg.role === "user" ? "R" : "\u2726"}
                </div>
                <div className="ai-msg-body">
                  <div className="ai-msg-sender">
                    {msg.role === "user" ? "You" : "AI Assistant"}
                  </div>
                  <div className="ai-msg-content">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                  {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                    <SourcesBlock sources={msg.sources} />
                  )}
                </div>
              </div>
            ))}
            {isAiLoading && (
              <div className="thinking-indicator">
                <div className="ai-avatar-assistant">{"\u2726"}</div>
                <div className="ai-msg-body">
                  <div className="ai-msg-sender">AI Assistant</div>
                  <div className="thinking-bubble">
                    <span className="thinking-dot" />
                    <span className="thinking-dot" />
                    <span className="thinking-dot" />
                  </div>
                </div>
              </div>
            )}
          </div>
          <ChatInput onSend={onSend} disabled={isAiLoading} />
        </div>
      )}
    </div>
  );
}
