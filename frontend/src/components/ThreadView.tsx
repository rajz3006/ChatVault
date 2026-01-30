import { useEffect, useRef } from "react";
import type { Message } from "../types";
import ChatMessageBubble from "./ChatMessage";

interface Props {
  messages: Message[];
}

export default function ThreadView({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return <div className="thread-empty">No messages in this conversation</div>;
  }

  return (
    <div className="thread-view">
      {messages.map((msg, idx) => (
        <ChatMessageBubble
          key={msg.uuid}
          sender={msg.sender}
          text={msg.text}
          created_at={msg.created_at}
          attachments={msg.attachments}
          animationDelay={idx * 50}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
