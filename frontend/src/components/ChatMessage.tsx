import ReactMarkdown from "react-markdown";
import type { Attachment } from "../types";

interface Props {
  sender: "human" | "assistant";
  text: string;
  created_at: string;
  attachments?: Attachment[];
  animationDelay?: number;
}

export default function ChatMessageBubble({ sender, text, created_at, attachments, animationDelay = 0 }: Props) {
  const isHuman = sender === "human";

  const formatTime = (iso: string) => {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <div className={`chat-msg ${isHuman ? "chat-msg-human" : "chat-msg-assistant"}`} style={{ animationDelay: `${animationDelay}ms` }}>
      <div className={isHuman ? "avatar-human" : "avatar-assistant"}>
        {isHuman ? "R" : "\u2726"}
      </div>
      <div className="chat-msg-body">
        <div className="chat-msg-meta">
          <span className="chat-msg-sender">{isHuman ? "You" : "Assistant"}</span>
          {created_at && <span className="chat-msg-time">{formatTime(created_at)}</span>}
        </div>
        <div className="chat-msg-content">
          <ReactMarkdown
            components={{
              code({ className, children, ...props }) {
                const isBlock = className?.startsWith("language-");
                if (isBlock) {
                  return (
                    <pre className="code-block">
                      <code className={className} {...props}>
                        {children}
                      </code>
                    </pre>
                  );
                }
                return (
                  <code className="inline-code" {...props}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {text}
          </ReactMarkdown>
        </div>
        {attachments?.map((att, i) => (
          <div key={i} className="chat-attachment">
            {att.type === "code_block" ? (
              <pre className="code-block">
                <code>{att.content}</code>
              </pre>
            ) : (
              <img src={att.content} alt="attachment" className="chat-img" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
