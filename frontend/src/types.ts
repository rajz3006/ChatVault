export interface Conversation {
  uuid: string;
  name: string;
  created_at: string;
  source_id: string;
  starred: boolean;
  recency_label: string;
}

export interface Message {
  uuid: string;
  sender: "human" | "assistant";
  text: string;
  created_at: string;
  attachments?: Attachment[];
}

export interface Attachment {
  type: "code_block" | "image";
  content: string;
  metadata?: Record<string, string>;
}

export interface SearchResult {
  conversation_uuid: string;
  message_uuid: string;
  conversation_name: string;
  text: string;
  score: number;
  created_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: SearchResult[];
}

export interface Stats {
  conversations: number;
  messages: number;
  vectors: number;
}
