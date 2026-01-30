import { useState, useEffect, useRef } from "react";
import * as api from "../api";

interface Props {
  onClose: () => void;
}

export default function SettingsPopover({ onClose }: Props) {
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [backend, setBackend] = useState("ollama");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getSettings().then((s) => {
      setSettings(s);
      if (typeof s.backend === "string") setBackend(s.backend);
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

      <div className="settings-section">
        <label className="settings-label">Connectors</label>
        <div className="settings-info">
          {settings ? (
            <span>Active connectors: {String(settings.connectors ?? "claude")}</span>
          ) : (
            <span>Loading...</span>
          )}
        </div>
      </div>

      <div className="settings-section">
        <label className="settings-label">Data</label>
        <button className="settings-action-btn" onClick={() => {
          fetch("/api/ingest", { method: "POST" }).catch(() => {});
        }}>
          Re-import Data
        </button>
      </div>

      <div className="settings-section">
        <label className="settings-label">Vector Store</label>
        <button className="settings-action-btn" onClick={() => {
          fetch("/api/embed", { method: "POST" }).catch(() => {});
        }}>
          Re-embed Vectors
        </button>
      </div>
    </div>
  );
}
