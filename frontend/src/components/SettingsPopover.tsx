import { useState, useEffect, useRef } from "react";
import * as api from "../api";

interface Props {
  onClose: () => void;
}

export default function SettingsPopover({ onClose }: Props) {
  const [backend, setBackend] = useState("ollama");
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [importStatus, setImportStatus] = useState<{ type: "loading" | "success" | "error"; msg: string } | null>(null);
  const [embedStatus, setEmbedStatus] = useState<{ type: "loading" | "success" | "error"; msg: string } | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getSettings().then((s) => {
      if (typeof s.backend === "string") setBackend(s.backend);
      if (typeof s.ollama_model === "string") setSelectedModel(s.ollama_model);
    }).catch(() => {});
    api.getOllamaStatus().then((status) => {
      if (status.available && status.models.length > 0) {
        setOllamaModels(status.models);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  const handleBackendChange = async (name: string) => {
    setBackend(name);
    try {
      await api.setBackend(name);
    } catch {
      // ignore
    }
  };

  const handleModelChange = async (model: string) => {
    setSelectedModel(model);
    try {
      await api.saveConfig({ backend, model });
    } catch {
      // ignore
    }
  };

  return (
    <div className="settings-popover" ref={ref}>
      <h3 className="settings-title">Settings</h3>

      <div className="settings-section">
        <label className="settings-label">LLM Backend</label>
        <select
          className="settings-select"
          value={backend}
          onChange={(e) => handleBackendChange(e.target.value)}
        >
          <option value="ollama">Ollama (Local)</option>
          <option value="claude">Claude API</option>
        </select>
      </div>

      {backend === "ollama" && ollamaModels.length > 0 && (
        <div className="settings-section">
          <label className="settings-label">Ollama Model</label>
          <select
            className="settings-select"
            value={selectedModel}
            onChange={(e) => handleModelChange(e.target.value)}
          >
            {ollamaModels.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>
      )}

      <div className="settings-section">
        <label className="settings-label">Data</label>
        <button
          className="settings-action-btn"
          disabled={importStatus?.type === "loading"}
          onClick={async () => {
            setImportStatus({ type: "loading", msg: "Re-importing..." });
            try {
              const res = await fetch("/api/ingest", { method: "POST" });
              if (!res.ok) throw new Error(await res.text());
              const data = await res.json();
              setImportStatus({ type: "success", msg: `Imported ${data.conversations} convs, ${data.messages} msgs` });
            } catch (e: any) {
              setImportStatus({ type: "error", msg: e.message || "Import failed" });
            }
          }}
        >
          {importStatus?.type === "loading" ? "Importing..." : "Re-import Data"}
        </button>
        {importStatus && importStatus.type !== "loading" && (
          <span className={`settings-status settings-status--${importStatus.type}`}>{importStatus.msg}</span>
        )}
      </div>

      <div className="settings-section">
        <label className="settings-label">Vector Store</label>
        <button
          className="settings-action-btn"
          disabled={embedStatus?.type === "loading"}
          onClick={async () => {
            setEmbedStatus({ type: "loading", msg: "Re-embedding..." });
            try {
              const res = await fetch("/api/embed", { method: "POST" });
              if (!res.ok) throw new Error(await res.text());
              const data = await res.json();
              setEmbedStatus({ type: "success", msg: `Embedded ${data.messages ?? 0} msg chunks, ${data.conversations ?? 0} conv chunks` });
            } catch (e: any) {
              setEmbedStatus({ type: "error", msg: e.message || "Embedding failed" });
            }
          }}
        >
          {embedStatus?.type === "loading" ? "Embedding..." : "Re-embed Vectors"}
        </button>
        {embedStatus && embedStatus.type !== "loading" && (
          <span className={`settings-status settings-status--${embedStatus.type}`}>{embedStatus.msg}</span>
        )}
      </div>
    </div>
  );
}
