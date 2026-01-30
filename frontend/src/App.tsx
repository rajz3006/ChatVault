import { useState, useEffect, useCallback, useRef } from "react";
import type { Conversation, Message, ChatMessage, Stats } from "./types";
import * as api from "./api";
import LeftPanel from "./components/LeftPanel";
import RightPanel from "./components/RightPanel";
import SetupWizard from "./components/SetupWizard";

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConvUuid, setSelectedConvUuid] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [contentMatchUuids, setContentMatchUuids] = useState<Set<string>>(new Set());
  const searchDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [starredOnly, setStarredOnly] = useState(false);
  const [stats, setStats] = useState<Stats>({ conversations: 0, messages: 0, vectors: 0 });
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [showAiOverlay, setShowAiOverlay] = useState(false);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [setupDone, setSetupDone] = useState<boolean | null>(null);

  // Resizable left panel
  const [leftWidth, setLeftWidth] = useState(300);
  const isDragging = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(300);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isDragging.current = true;
    startX.current = e.clientX;
    startWidth.current = leftWidth;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [leftWidth]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const delta = e.clientX - startX.current;
      const newWidth = Math.max(200, Math.min(600, startWidth.current + delta));
      setLeftWidth(newWidth);
    };
    const handleMouseUp = () => {
      if (isDragging.current) {
        isDragging.current = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  const fetchConversations = useCallback(async () => {
    try {
      const data = await api.getConversations(starredOnly || undefined);
      setConversations(data);
    } catch {
      // API not available yet — leave empty
    }
  }, [starredOnly]);

  useEffect(() => {
    fetchConversations();
    api.getStats().then((s) => {
      setStats(s);
      setSetupDone(s.conversations > 0);
    }).catch(() => {});
  }, [fetchConversations]);

  const handleSelect = useCallback(async (uuid: string) => {
    setSelectedConvUuid(uuid);
    setLoadingMessages(true);
    setShowAiOverlay(false);
    try {
      const msgs = await api.getMessages(uuid);
      setMessages(msgs);
    } catch {
      setMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  const handleSend = useCallback(
    async (text: string) => {
      const userMsg: ChatMessage = { role: "user", content: text };
      setChatHistory((prev) => [...prev, userMsg]);
      setShowAiOverlay(true);
      setIsAiLoading(true);
      try {
        const historyForApi = [...chatHistory, userMsg].map(({ role, content }) => ({ role, content }));
        const res = await api.chat(text, historyForApi);
        setChatHistory((prev) => [
          ...prev,
          { role: "assistant", content: res.answer, sources: res.sources },
        ]);
      } catch {
        setChatHistory((prev) => [
          ...prev,
          { role: "assistant", content: "Sorry, something went wrong." },
        ]);
      } finally {
        setIsAiLoading(false);
      }
    },
    [chatHistory]
  );

  const handleDismissAi = useCallback(() => {
    setShowAiOverlay(false);
  }, []);

  const handleResumeAi = useCallback(() => {
    setShowAiOverlay(true);
  }, []);

  const handleClearAiChat = useCallback(() => {
    setChatHistory([]);
    setShowAiOverlay(false);
  }, []);

  const handleToggleStar = useCallback(async () => {
    if (!selectedConvUuid) return;
    try {
      const res = await api.toggleStar(selectedConvUuid);
      setConversations((prev) =>
        prev.map((c) => (c.uuid === selectedConvUuid ? { ...c, starred: res.starred } : c))
      );
      // If filtering by starred, refresh the list to add/remove the conversation
      if (starredOnly) {
        fetchConversations();
      }
    } catch {
      // ignore
    }
  }, [selectedConvUuid, starredOnly, fetchConversations]);

  const selectedConv = conversations.find((c) => c.uuid === selectedConvUuid) ?? null;

  // Debounced keyword search for message content
  useEffect(() => {
    if (searchDebounce.current) clearTimeout(searchDebounce.current);
    if (searchQuery.length < 2) {
      setContentMatchUuids(new Set());
      return;
    }
    searchDebounce.current = setTimeout(() => {
      api.search(searchQuery, 20, "keyword").then((results) => {
        setContentMatchUuids(new Set(results.map((r) => r.conversation_uuid)));
      }).catch(() => setContentMatchUuids(new Set()));
    }, 300);
    return () => { if (searchDebounce.current) clearTimeout(searchDebounce.current); };
  }, [searchQuery]);

  const filtered = searchQuery
    ? conversations.filter((c) =>
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        contentMatchUuids.has(c.uuid)
      )
    : conversations;

  if (setupDone === null) return null; // loading

  if (!setupDone) {
    return (
      <SetupWizard
        onComplete={() => {
          setSetupDone(true);
          fetchConversations();
          api.getStats().then(setStats).catch(() => {});
        }}
      />
    );
  }

  return (
    <div className="app-layout">
      <LeftPanel
        conversations={filtered}
        selectedUuid={selectedConvUuid}
        onSelect={handleSelect}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        starredOnly={starredOnly}
        onStarredToggle={() => setStarredOnly((v) => !v)}
        stats={stats}
        width={leftWidth}
      />
      <div
        className="resize-handle"
        onMouseDown={handleMouseDown}
      />
      <RightPanel
        conversation={selectedConv}
        messages={messages}
        loadingMessages={loadingMessages}
        chatHistory={chatHistory}
        showAiOverlay={showAiOverlay}
        onSend={handleSend}
        onToggleStar={handleToggleStar}
        onRefreshConversations={fetchConversations}
        isAiLoading={isAiLoading}
        onDismissAi={handleDismissAi}
        onResumeAi={handleResumeAi}
        onClearAiChat={handleClearAiChat}
      />
    </div>
  );
}
