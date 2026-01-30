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

export async function search(query: string, n?: number, mode?: "hybrid" | "keyword"): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q: query });
  if (n !== undefined) params.set("n", String(n));
  if (mode) params.set("mode", mode);
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

export async function ingest(): Promise<{ conversations: number; messages: number }> {
  return request<{ conversations: number; messages: number }>("/ingest", {
    method: "POST",
  });
}

export async function embed(): Promise<{ embedded: number }> {
  return request<{ embedded: number }>("/embed", {
    method: "POST",
  });
}

export async function uploadFiles(files: File[]): Promise<{ uploaded: string[] }> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  return request<{ uploaded: string[] }>("/upload", {
    method: "POST",
    body: formData,
  });
}

export async function validateUpload(): Promise<{ valid: boolean; platform: string | null }> {
  return request<{ valid: boolean; platform: string | null }>("/upload/validate", {
    method: "POST",
  });
}

export async function getOllamaStatus(): Promise<{ available: boolean; models: string[] }> {
  return request<{ available: boolean; models: string[] }>("/ollama/status");
}

export async function pullOllamaModel(
  model: string,
  onProgress: (status: string) => void
): Promise<void> {
  const res = await fetch(`${BASE}/ollama/pull?model=${encodeURIComponent(model)}`, {
    method: "POST",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop()!;
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const jsonStr = trimmed.startsWith("data: ") ? trimmed.slice(6) : trimmed;
      try {
        const parsed = JSON.parse(jsonStr);
        onProgress(parsed.status);
      } catch { /* skip non-JSON lines */ }
    }
  }
  if (buffer.trim()) {
    const jsonStr = buffer.trim().startsWith("data: ") ? buffer.trim().slice(6) : buffer.trim();
    try {
      const parsed = JSON.parse(jsonStr);
      onProgress(parsed.status);
    } catch { /* skip */ }
  }
}

export async function saveConfig(config: {
  backend: string;
  model: string;
  api_key?: string;
}): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>("/settings/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
}
