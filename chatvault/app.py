"""ChatVault Streamlit UI — local-first AI chat history assistant."""
from __future__ import annotations

import datetime
import json
from pathlib import Path
import streamlit as st

from chatvault.db import Database
from chatvault.embeddings import EmbeddingEngine, DEFAULT_DB_PATH, DEFAULT_CHROMA_DIR
from chatvault.search import SearchEngine
from chatvault.rag import RAGPipeline
from chatvault.llm import get_available_backends
from chatvault.connectors import get_connectors
from chatvault.onboarding import is_first_run, render_onboarding
from chatvault.export import ExportEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_date(raw: str | None) -> str:
    if not raw:
        return "Unknown date"
    try:
        dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %-I:%M %p")
    except (ValueError, TypeError):
        return raw


def fmt_date_short(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%b %d")
    except (ValueError, TypeError):
        return raw


def get_recency_label(raw: str | None) -> str:
    """Bucket a date string into a human-friendly recency label."""
    if not raw:
        return "Older"
    try:
        dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = (now.date() - dt.date()).days
        if delta == 0:
            return "Today"
        elif delta == 1:
            return "Yesterday"
        elif delta <= 6:
            return f"{delta} days ago"
        elif delta <= 13:
            return "Last week"
        elif delta <= 20:
            return "2 weeks ago"
        elif delta <= 30:
            return "3 weeks ago"
        else:
            return "Older"
    except (ValueError, TypeError):
        return "Older"


def truncate(text: str, max_chars: int = 200) -> str:
    clean = text
    if "```" in clean:
        parts = clean.split("```")
        clean = parts[0]
    clean = clean.strip()
    if len(clean) > max_chars:
        return clean[:max_chars].rstrip() + "..."
    return clean if clean else text[:max_chars].rstrip() + "..."


def mi(name: str, sz: int = 18) -> str:
    """Material icon inline HTML."""
    return f'<span class="mi" style="font-size:{sz}px">{name}</span>'


# Avatar constants
AVATAR_HUMAN = "\U0001F464"   # 👤
AVATAR_AI = "\u2728"          # ✨


def render_conversation_thread(messages: list[dict], title: str = "", db: Database | None = None) -> None:
    if title:
        st.markdown(f"#### {title}")
    for m in messages:
        sender = m.get("sender", "human")
        role = "user" if sender == "human" else "assistant"
        avatar = AVATAR_HUMAN if role == "user" else AVATAR_AI
        with st.chat_message(role, avatar=avatar):
            date_str = fmt_date(m.get("created_at"))
            st.caption(date_str)
            st.markdown(m.get("text") or "_(empty)_")
            if db and m.get("uuid"):
                attachments = db.get_message_attachments(m["uuid"])
                for att in attachments:
                    if att["type"] == "code_block":
                        meta = json.loads(att.get("metadata") or "{}")
                        lang = meta.get("language", "")
                        code = att["content"].decode("utf-8") if isinstance(att["content"], bytes) else att["content"] or ""
                        st.code(code, language=lang)
                    elif att["type"] == "image":
                        if att["content"]:
                            st.image(att["content"])


# ---------------------------------------------------------------------------
# Cached resource initialisers
# ---------------------------------------------------------------------------

@st.cache_resource
def init_db() -> Database:
    return Database(DEFAULT_DB_PATH)


@st.cache_resource(show_spinner="Loading embedding model...")
def init_search() -> SearchEngine:
    return SearchEngine(db_path=DEFAULT_DB_PATH, chroma_dir=DEFAULT_CHROMA_DIR)


@st.cache_resource(show_spinner="Loading embedding model...")
def init_embedding_engine() -> EmbeddingEngine:
    return EmbeddingEngine(db_path=DEFAULT_DB_PATH, chroma_dir=DEFAULT_CHROMA_DIR)


def init_rag(backend_name: str) -> RAGPipeline:
    return RAGPipeline(db_path=DEFAULT_DB_PATH, chroma_dir=DEFAULT_CHROMA_DIR, llm_backend=backend_name)


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def inject_css() -> None:
    st.markdown(
        '<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">',
        unsafe_allow_html=True,
    )
    st.markdown("""<style>
    :root {
        --bg: #f3f4f6;
        --surface: #ffffff;
        --surface-alt: #f9fafb;
        --left-bg: #f8f8fb;
        --border: #e5e7eb;
        --border-strong: #d1d5db;
        --text-1: #111827;
        --text-2: #4b5563;
        --text-3: #9ca3af;
        --accent: #5b5fc7;
        --accent-bg: #eef0ff;
        --star-color: #d97706;
    }

    .mi {
        font-family: 'Material Symbols Outlined';
        font-weight: normal;
        font-style: normal;
        display: inline-block;
        line-height: 1;
        text-transform: none;
        letter-spacing: normal;
        word-wrap: normal;
        white-space: nowrap;
        direction: ltr;
        vertical-align: middle;
        -webkit-font-smoothing: antialiased;
        font-variation-settings: 'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 20;
    }

    /* ── Global ─────────────────────────────────────────────── */
    .stApp { background: var(--bg) !important; }
    section[data-testid="stSidebar"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    .block-container {
        padding: 1rem 2rem !important;
        max-width: 100% !important;
    }

    /* ── Brand ──────────────────────────────────────────────── */
    .cv-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--text-1);
        letter-spacing: -0.3px;
        padding: 4px 0 12px 0;
    }
    .cv-brand-icon {
        width: 30px; height: 30px;
        background: var(--accent);
        border-radius: 8px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
    }
    .cv-brand-icon .mi {
        font-size: 17px;
        color: #fff;
        font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 17;
    }

    /* ── Date group header ─────────────────────────────────── */
    .cv-date-group {
        font-size: 0.7rem;
        font-weight: 600;
        color: var(--text-3);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 10px 4px 4px 4px;
    }

    /* ── Conversation list items — plain text, no borders ──── */
    .cv-conv-list .stButton > button {
        border: none !important;
        border-radius: 4px !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 6px 8px !important;
        font-size: 0.82rem !important;
        font-weight: 400 !important;
        color: var(--text-1) !important;
        background: transparent !important;
        transition: background 0.1s !important;
        box-shadow: none !important;
    }
    .cv-conv-list .stButton > button:hover {
        background: var(--border) !important;
    }
    .cv-conv-list .stButton > button[data-testid="stBaseButton-primary"] {
        background: var(--accent-bg) !important;
        color: var(--accent) !important;
        font-weight: 600 !important;
    }

    /* ── Stats footer ───────────────────────────────────────── */
    .cv-stats {
        display: flex;
        gap: 14px;
        font-size: 0.68rem;
        color: var(--text-3);
        padding: 8px 2px;
        font-weight: 500;
    }
    .cv-stats .mi { font-size: 12px; margin-right: 2px; }

    /* ── Source card (RAG) ───────────────────────────────────── */
    .source-card {
        border-left: 3px solid var(--accent);
        padding: 8px 12px;
        margin: 4px 0;
        background: var(--accent-bg);
        border-radius: 0 6px 6px 0;
        font-size: 0.82rem;
    }

    /* ── Empty state ────────────────────────────────────────── */
    .cv-empty {
        text-align: center;
        padding: 80px 20px;
        color: var(--text-3);
    }
    .cv-empty .mi {
        font-size: 48px;
        color: var(--border-strong);
        display: block;
        margin-bottom: 12px;
        font-variation-settings: 'FILL' 0, 'wght' 200, 'GRAD' 0, 'opsz' 48;
    }

    /* ── Right panel title ──────────────────────────────────── */
    .cv-title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-1);
        padding: 6px 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* ── Streamlit overrides ────────────────────────────────── */
    .stButton > button {
        border-radius: 6px;
        font-size: 0.8rem;
        padding: 4px 12px;
    }
    .stDownloadButton > button {
        font-size: 0.78rem;
        padding: 4px 10px;
        border-radius: 6px;
    }
    .stTextInput > div > div > input {
        font-size: 0.82rem;
        padding: 6px 10px;
    }
    .stSelectbox > div > div { font-size: 0.82rem; }
    .stMultiSelect > div { font-size: 0.82rem; }
    div[data-testid="stPopoverBody"] { min-width: 360px; }
    .stChatMessage { padding: 12px 16px; }
    .stDivider { margin: 6px 0 !important; }
    </style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def init_session_state() -> None:
    defaults = {
        "global_search_query": "",
        "selected_conv_uuid": None,
        "chat_history": [],
        "selected_backend": None,
        "source_filter": [],
        "starred_only": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if st.session_state["selected_backend"] is None:
        try:
            available = get_available_backends()
            if available:
                st.session_state["selected_backend"] = available[0].name
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Settings popover content
# ---------------------------------------------------------------------------

def render_settings_content(db: Database) -> None:
    # Source filter (moved from left panel)
    sources = db.get_stats()
    source_ids = [s["id"] for s in sources]
    if source_ids:
        st.markdown("**Source Filter**")
        selected = st.multiselect("Source", source_ids, default=source_ids, key="source_filter_select", label_visibility="collapsed", placeholder="All sources")
        st.session_state["source_filter"] = selected
        st.divider()

    st.markdown("**Connectors**")
    connectors = get_connectors()
    data_dir = Path("data")
    for c in connectors:
        detected = c.detect(data_dir) if data_dir.exists() else False
        ico = mi("check_circle", 14) if detected else mi("cancel", 14)
        st.markdown(f"{ico} {c.source_name}", unsafe_allow_html=True)

    st.divider()
    st.markdown("**LLM Backend**")
    try:
        available = get_available_backends()
        available_names = {b.name for b in available}
    except Exception:
        available = []
        available_names = set()

    backend_names = [b.name for b in available]
    if backend_names:
        current = st.session_state.get("selected_backend", backend_names[0])
        idx = backend_names.index(current) if current in backend_names else 0
        chosen = st.selectbox("Active backend", backend_names, index=idx, key="settings_backend")
        st.session_state["selected_backend"] = chosen
    else:
        st.caption("No backends available. Configure Ollama or set ANTHROPIC_API_KEY.")

    for name in ["ollama", "claude"]:
        ico = mi("check_circle", 14) if name in available_names else mi("cancel", 14)
        st.markdown(f"{ico} {name}", unsafe_allow_html=True)

    st.divider()
    st.markdown("**Data**")
    st.caption(str(data_dir.resolve()))
    if st.button("Re-import from data/", key="btn_reimport"):
        with st.spinner("Importing..."):
            try:
                from chatvault.ingest import main as ingest_main
                ingest_main(data_dir=data_dir)
                st.success("Import complete. Refresh the page.")
                st.cache_resource.clear()
            except Exception as e:
                st.error(f"Import failed: {e}")

    st.divider()
    st.markdown("**Vector Store**")
    try:
        engine = init_embedding_engine()
        vec_stats = engine.get_stats()
        for col_name, count in vec_stats.items():
            st.caption(f"{col_name}: {count} vectors")
    except Exception as e:
        st.caption(f"Could not load: {e}")
    if st.button("Re-embed all", key="btn_reembed"):
        with st.spinner("Embedding..."):
            try:
                engine = init_embedding_engine()
                result = engine.embed_all(force=True)
                st.success(f"Embedded {result['conversations']} convs, {result['messages']} chunks.")
                st.cache_resource.clear()
            except Exception as e:
                st.error(f"Embedding failed: {e}")


# ---------------------------------------------------------------------------
# Left panel
# ---------------------------------------------------------------------------

def render_left_panel(db: Database) -> None:
    # Brand
    st.markdown(
        f'<div class="cv-brand">'
        f'<div class="cv-brand-icon"><span class="mi" style="font-size:17px;color:#fff;font-variation-settings:\'FILL\' 1,\'wght\' 400,\'GRAD\' 0,\'opsz\' 17">forum</span></div>'
        f'ChatVault'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Search + Starred on same row
    col_search, col_star = st.columns([5, 1])
    with col_search:
        query = st.text_input("Search", placeholder="Search conversations...", key="global_search_input", label_visibility="collapsed")
        st.session_state["global_search_query"] = query
    with col_star:
        starred = st.toggle("\u2605", key="starred_toggle", value=st.session_state.get("starred_only", False))
        st.session_state["starred_only"] = starred

    # Get conversations
    search_query = st.session_state.get("global_search_query", "").strip()
    if search_query:
        search = init_search()
        results = search.hybrid_search(search_query, n=30)
        seen: set[str] = set()
        conv_uuids: list[str] = []
        for r in results:
            if r.conversation_uuid not in seen:
                seen.add(r.conversation_uuid)
                conv_uuids.append(r.conversation_uuid)
        all_convs = db.get_all_conversations()
        conv_map = {c["uuid"]: c for c in all_convs}
        conversations = [conv_map[u] for u in conv_uuids if u in conv_map]
    elif starred:
        conversations = db.get_starred_conversations()
    else:
        conversations = db.get_all_conversations()

    # Source filter (applied from settings)
    source_filter = st.session_state.get("source_filter", [])
    if source_filter:
        conversations = [c for c in conversations if c.get("source_id") in source_filter]

    # Group conversations by recency
    if not conversations:
        st.caption("No conversations found.")
    else:
        grouped: dict[str, list[dict]] = {}
        for c in conversations:
            label = get_recency_label(c.get("created_at"))
            grouped.setdefault(label, []).append(c)

        # Maintain order of groups
        group_order = ["Today", "Yesterday"]
        for i in range(2, 7):
            group_order.append(f"{i} days ago")
        group_order.extend(["Last week", "2 weeks ago", "3 weeks ago", "Older"])

        list_container = st.container(height=480)
        with list_container:
            st.markdown('<div class="cv-conv-list">', unsafe_allow_html=True)
            for group in group_order:
                if group not in grouped:
                    continue
                st.markdown(f'<div class="cv-date-group">{group}</div>', unsafe_allow_html=True)
                for c in grouped[group]:
                    conv_uuid = c["uuid"]
                    name = c.get("name") or "Untitled"
                    is_selected = st.session_state.get("selected_conv_uuid") == conv_uuid

                    if st.button(
                        name,
                        key=f"conv_{conv_uuid}",
                        use_container_width=True,
                        type="primary" if is_selected else "secondary",
                    ):
                        st.session_state["selected_conv_uuid"] = conv_uuid
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # Stats
    conv_count = db.get_conversation_count()
    total_msgs = db.get_message_count()
    try:
        from chromadb import PersistentClient
        client = PersistentClient(path=DEFAULT_CHROMA_DIR)
        vec_count = sum(col.count() for col in client.list_collections())
    except Exception:
        vec_count = 0

    st.markdown(
        f'<div class="cv-stats">'
        f'<span>{mi("forum", 12)} {conv_count} convs</span>'
        f'<span>{mi("chat", 12)} {total_msgs} msgs</span>'
        f'<span>{mi("database", 12)} {vec_count} vecs</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Right panel
# ---------------------------------------------------------------------------

def render_right_panel(db: Database) -> None:
    conv_uuid = st.session_state.get("selected_conv_uuid")

    # Row 1: Title + Settings
    col_title, col_settings = st.columns([7, 1])
    with col_title:
        if conv_uuid:
            all_convs = db.get_all_conversations()
            conv_name = "Untitled"
            is_starred = False
            for c in all_convs:
                if c["uuid"] == conv_uuid:
                    conv_name = c.get("name") or "Untitled"
                    is_starred = bool(c.get("starred"))
                    break
            st.markdown(f'<div class="cv-title">{conv_name}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="cv-title">ChatVault</div>', unsafe_allow_html=True)
            conv_name = "ChatVault"
            is_starred = False
    with col_settings:
        with st.popover("\u2699 Settings"):
            render_settings_content(db)

    # Row 2: Action bar (only if a conversation is selected)
    if conv_uuid:
        col_star, col_tag, col_fmt, col_dl = st.columns([1, 2.5, 1.2, 1.2])
        with col_star:
            star_icon = "\u2605 Unstar" if is_starred else "\u2606 Star"
            if st.button(star_icon, key="btn_star_thread"):
                db.toggle_star(conv_uuid)
                st.rerun()
        with col_tag:
            new_tag = st.text_input("Tag", placeholder="Add tag...", key="tag_input", label_visibility="collapsed")
            if new_tag:
                tag_id = db.create_tag(new_tag.strip())
                db.tag_conversation(conv_uuid, tag_id)
                st.rerun()
        with col_fmt:
            fmt = st.selectbox("Fmt", ["Markdown", "JSON", "CSV"], key="export_fmt", label_visibility="collapsed")
        with col_dl:
            exporter = ExportEngine(db)
            if fmt == "JSON":
                data = exporter.export_conversation_json(conv_uuid)
                st.download_button("Export", data, f"{conv_uuid}.json", "application/json", key="dl_thread")
            elif fmt == "CSV":
                data = exporter.export_conversation_csv(conv_uuid)
                st.download_button("Export", data, f"{conv_uuid}.csv", "text/csv", key="dl_thread")
            else:
                data = exporter.export_conversation_markdown(conv_uuid)
                st.download_button("Export", data, f"{conv_uuid}.md", "text/markdown", key="dl_thread")

    st.divider()

    # Thread area
    if not conv_uuid:
        st.markdown(
            f'<div class="cv-empty">'
            f'<span class="mi">chat_bubble_outline</span>'
            f'Select a conversation to view'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        messages = db.get_conversation_messages(conv_uuid)
        if not messages:
            st.info("No messages in this conversation.")
        else:
            thread_box = st.container(height=420)
            with thread_box:
                render_conversation_thread(messages, db=db)

    # AI chat history (shown above input)
    if st.session_state["chat_history"]:
        st.divider()
        ai_box = st.container(height=200)
        with ai_box:
            for msg in st.session_state["chat_history"]:
                role = msg["role"]
                avatar = AVATAR_HUMAN if role == "user" else AVATAR_AI
                with st.chat_message(role, avatar=avatar):
                    st.markdown(msg["content"])
                    if msg.get("sources"):
                        with st.expander(f"Sources ({len(msg['sources'])})"):
                            for src in msg["sources"]:
                                name = src.conversation_name or "Untitled"
                                date = fmt_date(src.created_at)
                                preview = truncate(src.text, 200)
                                st.markdown(
                                    f'<div class="source-card"><strong>{name}</strong><br/>'
                                    f'<small style="color:var(--text-3)">{date}</small><br/>'
                                    f'<span style="color:var(--text-2)">{preview}</span></div>',
                                    unsafe_allow_html=True,
                                )

    # Floating chat input — always visible at bottom
    if prompt := st.chat_input("Ask about your chat history..."):
        selected_backend = st.session_state.get("selected_backend")
        st.session_state["chat_history"].append({"role": "user", "content": prompt})

        if not selected_backend:
            st.session_state["chat_history"].append({"role": "assistant", "content": "No LLM backend available. Configure one in Settings."})
            st.rerun()
        else:
            try:
                rag = init_rag(selected_backend)
                history = [{"role": m["role"], "content": m["content"]} for m in st.session_state["chat_history"][:-1]]
                response = rag.query(prompt, chat_history=history)
                sources = response.sources[:5]
                st.session_state["chat_history"].append({"role": "assistant", "content": response.answer, "sources": sources})
                # Feedback
                db.insert_feedback(query=prompt, answer=response.answer, chunk_ids=[s.message_uuid for s in response.sources], rating=0)
            except Exception as e:
                st.session_state["chat_history"].append({"role": "assistant", "content": f"Error: {e}"})
            st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if is_first_run():
        render_onboarding()
        st.stop()

    st.set_page_config(
        page_title="ChatVault",
        page_icon="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><text y='14' font-size='14'>V</text></svg>",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    inject_css()
    init_session_state()

    db = init_db()

    # Two-column split
    col_left, col_right = st.columns([3, 7], gap="large")

    with col_left:
        render_left_panel(db)

    with col_right:
        render_right_panel(db)


if __name__ == "__main__":
    main()
