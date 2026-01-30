import { useState, useCallback, useEffect, useRef } from "react";
import * as api from "../api";

interface Props {
  onComplete: () => void;
}

export default function SetupWizard({ onComplete }: Props) {
  const [step, setStep] = useState(1);

  // Step 1
  const [platform, setPlatform] = useState("claude");

  // Step 3
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);
  const [validationPassed, setValidationPassed] = useState(false);
  const [validationMsg, setValidationMsg] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step 4
  const [llmBackend, setLlmBackend] = useState<"ollama" | "claude">("ollama");
  const [selectedModel, setSelectedModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [ollamaAvailable, setOllamaAvailable] = useState(false);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [pullProgress, setPullProgress] = useState("");

  // Step 5
  const [importProgress, setImportProgress] = useState(0);
  const [importDone, setImportDone] = useState(false);
  const [importError, setImportError] = useState("");

  // Fetch Ollama status when entering step 4
  useEffect(() => {
    if (step === 4) {
      api.getOllamaStatus().then((status) => {
        setOllamaAvailable(status.available);
        setOllamaModels(status.models);
        if (status.models.length > 0 && !selectedModel) {
          setSelectedModel(status.models[0]);
        }
      }).catch(() => {
        setOllamaAvailable(false);
      });
    }
  }, [step]);

  const handleFiles = useCallback(async (files: File[]) => {
    try {
      const result = await api.uploadFiles(files);
      setUploadedFiles(result.uploaded);
      const validation = await api.validateUpload();
      setValidationPassed(validation.valid);
      setValidationMsg(validation.valid ? "Validation passed" : "Validation failed — files may not be valid exports");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setValidationMsg(msg);
      setValidationPassed(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) handleFiles(files);
  }, [handleFiles]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragging(false);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) handleFiles(files);
  }, [handleFiles]);

  const handlePullModel = useCallback(async () => {
    const model = selectedModel || "llama3.2";
    setPullProgress("Starting pull...");
    try {
      await api.pullOllamaModel(model, (status) => setPullProgress(status));
      setPullProgress("Pull complete");
      const status = await api.getOllamaStatus();
      setOllamaModels(status.models);
      if (!selectedModel && status.models.length > 0) {
        setSelectedModel(status.models[0]);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Pull failed";
      setPullProgress(msg);
    }
  }, [selectedModel]);

  const handleImport = useCallback(async () => {
    setImportError("");
    setImportProgress(0);
    try {
      setImportProgress(10);
      await api.ingest();
      setImportProgress(50);
      await api.embed();
      setImportProgress(90);
      await api.saveConfig({
        backend: llmBackend,
        model: selectedModel,
        ...(llmBackend === "claude" && apiKey ? { api_key: apiKey } : {}),
      });
      setImportProgress(100);
      setImportDone(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Import failed";
      setImportError(msg);
    }
  }, [llmBackend, selectedModel, apiKey]);

  const canNext = (): boolean => {
    switch (step) {
      case 1: return !!platform;
      case 2: return true;
      case 3: return validationPassed;
      case 4: return true;
      case 5: return importDone;
      default: return false;
    }
  };

  const renderProgressDots = () => (
    <div className="wizard-progress">
      {[1, 2, 3, 4, 5].map((s, i) => (
        <div key={s} className="wizard-progress-segment">
          <div
            className={`wizard-dot${s < step ? " completed" : ""}${s === step ? " active" : ""}`}
          />
          {i < 4 && <div className={`wizard-line${s < step ? " completed" : ""}`} />}
        </div>
      ))}
    </div>
  );

  const renderStep = () => {
    switch (step) {
      case 1:
        return (
          <div className="wizard-step-content">
            <h2>Choose Your Platform</h2>
            <p className="wizard-subtitle">Select the AI platform you exported your chats from</p>
            <div className="wizard-cards">
              <div
                className={`platform-card${platform === "claude" ? " selected" : ""}`}
                onClick={() => setPlatform("claude")}
              >
                <div className="platform-card-name">Claude</div>
              </div>
              <div className="platform-card disabled">
                <div className="platform-card-name">ChatGPT</div>
                <span className="coming-soon">Coming Soon</span>
              </div>
              <div className="platform-card disabled">
                <div className="platform-card-name">Gemini</div>
                <span className="coming-soon">Coming Soon</span>
              </div>
            </div>
          </div>
        );

      case 2:
        return (
          <div className="wizard-step-content">
            <h2>Export Your Conversations</h2>
            <ol className="wizard-instructions">
              <li>Go to <strong>claude.ai/settings</strong></li>
              <li>Click <strong>"Export Data"</strong></li>
              <li>Wait for email with download link</li>
              <li>Download and extract the ZIP file</li>
              <li>You'll need the JSON files from the extracted folder</li>
            </ol>
          </div>
        );

      case 3:
        return (
          <div className="wizard-step-content">
            <h2>Upload Your Data</h2>
            <p className="wizard-subtitle">Drag &amp; drop your exported JSON files or click to browse</p>
            <div
              className={`drop-zone${dragging ? " dragging" : ""}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <p>Drop JSON files here or click to browse</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                multiple
                style={{ display: "none" }}
                onChange={handleFileSelect}
              />
            </div>
            {uploadedFiles.length > 0 && (
              <ul className="uploaded-files">
                {uploadedFiles.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            )}
            {validationMsg && (
              <div className={`validation-status ${validationPassed ? "valid" : "invalid"}`}>
                {validationMsg}
              </div>
            )}
          </div>
        );

      case 4:
        return (
          <div className="wizard-step-content">
            <h2>Configure AI Backend</h2>
            <p className="wizard-subtitle">Choose how ChatVault will power its AI features</p>
            <div className="wizard-cards">
              <div
                className={`llm-card${llmBackend === "ollama" ? " selected" : ""}`}
                onClick={() => setLlmBackend("ollama")}
              >
                <div className="llm-card-name">Ollama (Local)</div>
                <div className={`status-indicator ${ollamaAvailable ? "available" : "unavailable"}`}>
                  {ollamaAvailable ? "Available" : "Not detected"}
                </div>
                {llmBackend === "ollama" && (
                  <select
                    className="model-select"
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                  >
                    {ollamaModels.map((m) => (
                      <option key={m} value={m}>{m} (installed)</option>
                    ))}
                    {!ollamaModels.includes("tinyllama") && <option value="tinyllama">tinyllama — 1.1B, ~700 MB, fast</option>}
                    {!ollamaModels.includes("llama3.2:1b") && <option value="llama3.2:1b">llama3.2:1b — 1.3B, ~1.3 GB</option>}
                    {!ollamaModels.includes("llama3:latest") && !ollamaModels.includes("llama3") && <option value="llama3">llama3 — 8B, ~4.7 GB (recommended)</option>}
                    {!ollamaModels.includes("llama3.1:latest") && !ollamaModels.includes("llama3.1") && <option value="llama3.1">llama3.1 — 70B, ~40 GB</option>}
                  </select>
                )}
                {llmBackend === "ollama" && (
                  <button className="pull-model-btn" onClick={(e) => { e.stopPropagation(); handlePullModel(); }}>
                    Pull Model
                  </button>
                )}
                {pullProgress && <div className="pull-progress">{pullProgress}</div>}
              </div>
              <div
                className={`llm-card${llmBackend === "claude" ? " selected" : ""}`}
                onClick={() => setLlmBackend("claude")}
              >
                <div className="llm-card-name">Claude API</div>
                {llmBackend === "claude" && (
                  <input
                    type="text"
                    className="api-key-input"
                    placeholder="Enter API key"
                    value={apiKey}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                )}
              </div>
            </div>
          </div>
        );

      case 5:
        return (
          <div className="wizard-step-content">
            <h2>Import &amp; Launch</h2>
            <p className="wizard-subtitle">We'll now import your conversations and generate embeddings</p>
            {!importDone && !importError && importProgress === 0 && (
              <button className="wizard-btn primary" onClick={handleImport}>
                Start Import
              </button>
            )}
            {importProgress > 0 && (
              <div className="import-progress-bar">
                <div className="import-progress-fill" style={{ width: `${importProgress}%` }} />
                <span className="import-progress-label">{importProgress}%</span>
              </div>
            )}
            {importError && <div className="import-error">{importError}</div>}
            {importDone && (
              <button className="wizard-btn primary" onClick={onComplete}>
                Launch ChatVault
              </button>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="wizard-overlay">
      <div className="wizard-card">
        {renderProgressDots()}
        {renderStep()}
        <div className="wizard-nav">
          {step > 1 && (
            <button className="wizard-btn secondary" onClick={() => setStep(step - 1)}>
              Back
            </button>
          )}
          {step === 4 && (
            <button className="wizard-btn secondary" onClick={() => setStep(5)}>
              Skip
            </button>
          )}
          {step < 5 && (
            <button
              className="wizard-btn primary"
              disabled={!canNext()}
              onClick={() => setStep(step + 1)}
            >
              Next
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
