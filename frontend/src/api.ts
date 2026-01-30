import type { Conversation, Message, SearchResult, ChatMessage, Stats } from "./types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

export async function getConversations(starred?: boolean): Promise<Conversation[]> {
  const params = starred ? "?starred=true" : "";
  return request<Conversation[]>(`/conversations${params}`);
}

export async function getMessages(uuid: string): Promise<Message[]> {
  return request<Message[]>(`/conversations/${uuid}/messages`);
}

export async function toggleStar(uuid: string): Promise<{ starred: boolean }> {
  return request<{ starred: boolean }>(`/conversations/${uuid}/star`, { method: "POST" });
}

export async function addTag(uuid: string, name: string): Promise<void> {
  await request<unknown>(`/conversations/${uuid}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function removeTag(uuid: string, tagId: number): Promise<void> {
  await request<unknown>(`/conversations/${uuid}/tags/${tagId}`, { method: "DELETE" });
}

export async function getTags(uuid: string): Promise<{ id: number; name: string }[]> {
  return request<{ id: number; name: string }[]>(`/conversations/${uuid}/tags`);
}

export async function search(query: string, n?: number): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q: query });
  if (n !== undefined) params.set("n", String(n));
  return request<SearchResult[]>(`/search?${params}`);
}

export async function chat(
  message: string,
  history: ChatMessage[]
): Promise<{ answer: string; sources: SearchResult[] }> {
  return request<{ answer: string; sources: SearchResult[] }>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
}

export async function exportConversation(uuid: string, format: string): Promise<Blob> {
  const res = await fetch(`${BASE}/conversations/${uuid}/export?format=${format}`);
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);
  return res.blob();
}

export async function getStats(): Promise<Stats> {
  return request<Stats>("/stats");
}

export async function getSettings(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/settings");
}

export async function setBackend(name: string): Promise<void> {
  await request<unknown>("/settings/backend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ backend: name }),
  });
}
