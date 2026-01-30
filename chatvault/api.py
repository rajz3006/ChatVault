"""FastAPI backend for ChatVault."""
from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chatvault.config import load_config, save_config
from chatvault.db import Database
from chatvault.embeddings import DEFAULT_DB_PATH, DEFAULT_CHROMA_DIR, EmbeddingEngine
from chatvault.search import SearchEngine
from chatvault.rag import RAGPipeline
from chatvault.export import ExportEngine
from chatvault.connectors import get_connectors
from chatvault.llm import get_available_backends, get_backend

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="ChatVault API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Module-level active backend name
_active_backend: str = os.environ.get("CHATVAULT_LLM_BACKEND", "ollama")

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_db: Database | None = None
_search: SearchEngine | None = None
_embeddings: EmbeddingEngine | None = None


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = Database(DEFAULT_DB_PATH)
    return _db


def _get_search() -> SearchEngine:
    global _search
    if _search is None:
        _search = SearchEngine(db_path=DEFAULT_DB_PATH, chroma_dir=DEFAULT_CHROMA_DIR)
    return _search


def _get_embeddings() -> EmbeddingEngine:
    global _embeddings
    if _embeddings is None:
        _embeddings = EmbeddingEngine(db_path=DEFAULT_DB_PATH, chroma_dir=DEFAULT_CHROMA_DIR)
    return _embeddings


def _get_rag() -> RAGPipeline:
    return RAGPipeline(
        db_path=DEFAULT_DB_PATH,
        chroma_dir=DEFAULT_CHROMA_DIR,
        llm_backend=_active_backend,
    )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TagRequest(BaseModel):
    name: str


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, Any]] = []


class BackendRequest(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recency_label(created_at: str | None) -> str:
    """Return a human-friendly recency label for a timestamp string."""
    if not created_at:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = now - dt
        days = delta.days
        if days == 0:
            return "Today"
        elif days == 1:
            return "Yesterday"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        elif days < 365:
            months = days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        else:
            years = days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
    except Exception:
        return "Unknown"


def _enrich_conversation(conv: dict[str, Any]) -> dict[str, Any]:
    """Add recency_label to a conversation dict."""
    conv["recency_label"] = _recency_label(conv.get("created_at"))
    conv["starred"] = bool(conv.get("starred"))
    return conv


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@app.get("/api/conversations")
def list_conversations(starred: bool | None = None):
    try:
        db = _get_db()
        if starred:
            convs = db.get_starred_conversations()
        else:
            convs = db.get_all_conversations()
        return [_enrich_conversation(c) for c in convs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations/{uuid}/messages")
def get_messages(uuid: str):
    try:
        db = _get_db()
        messages = db.get_conversation_messages(uuid)
        for m in messages:
            m["attachments"] = db.get_message_attachments(m["uuid"])
        return messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/conversations/{uuid}/star")
def toggle_star(uuid: str):
    try:
        db = _get_db()
        new_state = db.toggle_star(uuid)
        return {"starred": new_state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/conversations/{uuid}/tags")
def add_tag(uuid: str, body: TagRequest):
    try:
        db = _get_db()
        tag_id = db.create_tag(body.name)
        db.tag_conversation(uuid, tag_id)
        return {"tag_id": tag_id, "name": body.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/conversations/{uuid}/tags/{tag_id}")
def remove_tag(uuid: str, tag_id: int):
    try:
        db = _get_db()
        db.untag_conversation(uuid, tag_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations/{uuid}/tags")
def get_conversation_tags(uuid: str):
    try:
        db = _get_db()
        return db.get_conversation_tags(uuid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1),
    n: int = Query(30, ge=1, le=200),
    mode: str = Query("hybrid", pattern="^(hybrid|keyword)$"),
):
    try:
        engine = _get_search()
        if mode == "keyword":
            results = engine.keyword_search(q, n=n)
        else:
            results = engine.hybrid_search(q, n=n)
        return [asdict(r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Chat (RAG)
# ---------------------------------------------------------------------------

@app.post("/api/chat")
def chat(body: ChatRequest):
    try:
        rag = _get_rag()
        clean_history = [
            {"role": h["role"], "content": h["content"]}
            for h in body.history
            if "role" in h and "content" in h
        ] or None
        response = rag.query(user_message=body.message, chat_history=clean_history)
        sources = []
        for s in response.sources:
            sources.append({
                "conversation_uuid": s.conversation_uuid,
                "conversation_name": s.conversation_name,
                "text": s.text,
                "score": s.score,
                "created_at": s.created_at,
            })
        return {"answer": response.answer, "sources": sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@app.get("/api/conversations/{uuid}/export")
def export_conversation(uuid: str, format: str = Query("md", pattern="^(md|json|csv)$")):
    try:
        db = _get_db()
        exporter = ExportEngine(db)
        if format == "json":
            content = exporter.export_conversation_json(uuid)
            media_type = "application/json"
            ext = "json"
        elif format == "csv":
            content = exporter.export_conversation_csv(uuid)
            media_type = "text/csv"
            ext = "csv"
        else:
            content = exporter.export_conversation_markdown(uuid)
            media_type = "text/markdown"
            ext = "md"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename=conversation-{uuid[:8]}.{ext}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def get_stats():
    try:
        db = _get_db()
        embeddings = _get_embeddings()
        vec_stats = embeddings.get_stats()
        return {
            "conversations": db.get_conversation_count(),
            "messages": db.get_message_count(),
            "vectors": vec_stats.get("conversation_topics", 0) + vec_stats.get("message_chunks", 0),
            "sources": db.get_stats(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.get("/api/settings")
def get_settings():
    try:
        available = get_available_backends()
        connectors = get_connectors()
        cfg = load_config()
        return {
            "active_backend": _active_backend,
            "backend": _active_backend,
            "ollama_model": cfg.ollama_model,
            "available_backends": [type(b).__name__.replace("LLM", "").lower() for b in available],
            "connectors": [
                {
                    "name": type(c).__name__,
                    "platform": c.source_name,
                    "detected": c.detect(Path("data")),
                }
                for c in connectors
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/backend")
def set_backend(body: BackendRequest):
    global _active_backend
    try:
        # Validate the backend exists
        get_backend(body.name)
        _active_backend = body.name
        return {"active_backend": _active_backend}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/reimport")
def reimport():
    try:
        from chatvault.ingest import main as ingest_main
        ingest_main(data_dir="data", force=True)
        db = _get_db()
        return {
            "ok": True,
            "conversations": db.get_conversation_count(),
            "messages": db.get_message_count(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/reembed")
def reembed():
    try:
        embeddings = _get_embeddings()
        result = embeddings.embed_all(force=True)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_files(files: list[UploadFile]):
    """Accept multipart JSON files and save each to the data/ directory."""
    try:
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        uploaded: list[str] = []
        for f in files:
            dest = data_dir / f.filename
            content = await f.read()
            dest.write_bytes(content)
            uploaded.append(f.filename)
        return {"uploaded": uploaded}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload/validate")
def upload_validate():
    """Run connector detection on the data/ directory."""
    try:
        connectors = get_connectors()
        data_dir = Path("data")
        for c in connectors:
            if c.detect(data_dir):
                return {"valid": True, "platform": c.source_name}
        return {"valid": False, "platform": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

@app.get("/api/ollama/status")
def ollama_status():
    """Check if Ollama is running and return available models."""
    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        model_names = [m["name"] for m in data.get("models", [])]
        return {"available": True, "models": model_names}
    except Exception:
        return {"available": False, "models": []}


@app.post("/api/ollama/pull")
def ollama_pull(model: str = Query(...)):
    """Stream an Ollama model pull as SSE."""
    def _stream():
        with httpx.stream(
            "POST",
            "http://localhost:11434/api/pull",
            json={"name": model},
            timeout=None,
        ) as resp:
            for line in resp.iter_lines():
                if line:
                    yield f"data: {line}\n\n"
    return StreamingResponse(_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class ConfigRequest(BaseModel):
    backend: str
    model: str
    api_key: str | None = None


@app.post("/api/settings/config")
def save_settings(body: ConfigRequest):
    """Save LLM configuration via the config module."""
    try:
        cfg = load_config()
        cfg.llm_backend = body.backend
        if body.backend == "ollama":
            cfg.ollama_model = body.model
        else:
            cfg.anthropic_model = body.model
        if body.api_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = body.api_key
        save_config(cfg)
        # Also update the in-process active backend
        global _active_backend
        _active_backend = body.backend
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Ingest & Embed aliases
# ---------------------------------------------------------------------------

@app.post("/api/ingest")
def ingest():
    """Alias for /api/settings/reimport."""
    return reimport()


@app.post("/api/embed")
def embed():
    """Alias for /api/settings/reembed."""
    return reembed()


# ---------------------------------------------------------------------------
# Static file serving (production)
# ---------------------------------------------------------------------------

_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
