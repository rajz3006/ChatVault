"""First-run onboarding wizard for ChatVault."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from chatvault.db import Database
from chatvault.embeddings import DEFAULT_DB_PATH, DEFAULT_CHROMA_DIR
from chatvault.connectors import get_connectors
from chatvault.config import load_config, save_config, Config


# ---------------------------------------------------------------------------
# Model catalogue shown in the wizard
# ---------------------------------------------------------------------------

OLLAMA_MODELS: list[dict[str, str]] = [
    {
        "name": "tinyllama",
        "params": "1.1B",
        "size": "~700 MB",
        "description": "Fastest, lowest quality. Good for testing.",
    },
    {
        "name": "llama3.2:1b",
        "params": "1.3B",
        "size": "~1.3 GB",
        "description": "Fast, decent quality.",
    },
    {
        "name": "llama3",
        "params": "8B",
        "size": "~4.7 GB",
        "description": "Recommended. Good balance of speed and quality.",
    },
    {
        "name": "llama3.1",
        "params": "70B",
        "size": "~40 GB",
        "description": "Best quality, very slow. Needs 64 GB+ RAM.",
    },
]

# Platforms displayed in the wizard (only Claude is functional for now)
PLATFORMS = [
    {"id": "claude", "name": "Claude (Anthropic)", "ready": True},
    {"id": "chatgpt", "name": "ChatGPT (OpenAI)", "ready": False},
    {"id": "gemini", "name": "Google Gemini", "ready": False},
]

TOTAL_STEPS = 5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_first_run(db_path: str | Path = DEFAULT_DB_PATH) -> bool:
    """Check if the database has zero conversations (i.e. first run)."""
    try:
        db = Database(db_path)
        return db.get_conversation_count() == 0
    except Exception:
        return True


def render_onboarding() -> None:
    """Render the first-run onboarding wizard (5 steps)."""
    st.set_page_config(page_title="ChatVault - Setup", page_icon="\U0001F5C3\uFE0F", layout="centered")

    st.title("Welcome to ChatVault")
    st.caption("Local-first AI chat history assistant")
    st.divider()

    if "onboard_step" not in st.session_state:
        st.session_state["onboard_step"] = 1

    step = st.session_state["onboard_step"]
    st.progress(step / TOTAL_STEPS, text=f"Step {step} of {TOTAL_STEPS}")

    if step == 1:
        _step_platform_selection()
    elif step == 2:
        _step_export_instructions()
    elif step == 3:
        _step_provide_data()
    elif step == 4:
        _step_model_selection()
    elif step == 5:
        _step_import()


# ---------------------------------------------------------------------------
# Step 1 — Platform selection
# ---------------------------------------------------------------------------

def _step_platform_selection() -> None:
    st.subheader("Step 1: Choose Your Platform")
    st.write(
        "ChatVault imports your AI chat history so you can search and chat with it. "
        "Select the platform you exported your data from."
    )

    ready_platforms = [p for p in PLATFORMS if p["ready"]]
    coming_soon = [p for p in PLATFORMS if not p["ready"]]

    selected = st.radio(
        "Select your platform",
        [p["name"] for p in ready_platforms],
        key="onboard_platform_radio",
    )

    if coming_soon:
        st.markdown("---")
        st.markdown("**Coming soon**")
        for p in coming_soon:
            st.markdown(f"- {p['name']}  \u2014  *Coming Soon*")

    if st.button("Next", key="step1_next", type="primary"):
        # Map display name back to id
        for p in ready_platforms:
            if p["name"] == selected:
                st.session_state["onboard_platform"] = p["id"]
                break
        st.session_state["onboard_step"] = 2
        st.rerun()


# ---------------------------------------------------------------------------
# Step 2 — Export instructions
# ---------------------------------------------------------------------------

def _step_export_instructions() -> None:
    platform_id = st.session_state.get("onboard_platform", "claude")

    st.subheader("Step 2: Export Your Chat History")
    st.write("Follow these instructions to download your data, then come back here.")

    connectors = get_connectors()
    matched = [c for c in connectors if c.source_id == platform_id]

    if matched:
        for conn in matched:
            with st.expander(f"{conn.source_name} Export Instructions", expanded=True):
                st.markdown(conn.get_export_instructions())
    else:
        st.info("No connector available for this platform yet.")

    _nav_buttons("step2", back_step=1, next_step=3)


# ---------------------------------------------------------------------------
# Step 3 — Provide data
# ---------------------------------------------------------------------------

def _step_provide_data() -> None:
    st.subheader("Step 3: Provide Your Export Data")

    method = st.radio(
        "How would you like to provide your data?",
        ["Upload files", "Specify a folder path"],
        key="onboard_method",
    )

    if method == "Upload files":
        uploaded = st.file_uploader(
            "Upload your JSON export file(s)",
            type=["json"],
            accept_multiple_files=True,
            key="onboard_upload",
        )
        if uploaded:
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            for f in uploaded:
                dest = data_dir / f.name
                dest.write_bytes(f.getvalue())
            st.success(f"Saved {len(uploaded)} file(s) to data/")
            st.session_state["onboard_data_dir"] = str(data_dir)
    else:
        folder_path = st.text_input(
            "Path to export folder",
            value="data",
            key="onboard_folder",
        )
        if folder_path:
            st.session_state["onboard_data_dir"] = folder_path

    # Validate on Next
    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("Back", key="step3_back"):
            st.session_state["onboard_step"] = 2
            st.rerun()
    with col_next:
        if st.button("Next", key="step3_next", type="primary"):
            data_dir_str = st.session_state.get("onboard_data_dir")
            if not data_dir_str:
                st.warning("Please provide your export data first.")
                return

            data_path = Path(data_dir_str)
            platform_id = st.session_state.get("onboard_platform", "claude")
            connectors = get_connectors()
            matched = [c for c in connectors if c.source_id == platform_id]

            if matched and data_path.exists():
                if matched[0].detect(data_path):
                    st.session_state["onboard_step"] = 4
                    st.rerun()
                else:
                    st.error(
                        f"Could not detect {matched[0].source_name} export files "
                        f"in `{data_path.resolve()}`. Make sure the correct files are there."
                    )
            elif not data_path.exists():
                st.error(f"Directory `{data_path}` does not exist.")
            else:
                st.session_state["onboard_step"] = 4
                st.rerun()


# ---------------------------------------------------------------------------
# Step 4 — LLM model selection & download
# ---------------------------------------------------------------------------

def _step_model_selection() -> None:
    st.subheader("Step 4: Set Up Your LLM")
    st.write(
        "ChatVault uses a local LLM (via Ollama) or the Claude API "
        "to power RAG chat. Pick one below."
    )

    # --- Ollama section ---------------------------------------------------
    from chatvault.llm.ollama import list_models, pull_model
    import os

    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    ollama_ok = _check_ollama_available()

    st.markdown("### Option A: Local LLM (Ollama)")

    if not ollama_ok:
        st.warning(
            "Ollama is not running. Start it first:\n\n"
            "```\nbrew install ollama\nollama serve\n```\n\n"
            "Then refresh this page."
        )
        if st.button("Retry connection", key="ollama_retry"):
            st.rerun()
    else:
        st.success("Ollama is running.")

        installed = list_models(host)
        if installed:
            st.caption(f"Already installed: {', '.join(installed)}")

        # Model radio
        labels = [
            f"{m['name']}  ({m['params']}, {m['size']}) — {m['description']}"
            for m in OLLAMA_MODELS
        ]
        choice_idx = st.radio(
            "Choose a model to download",
            range(len(labels)),
            format_func=lambda i: labels[i],
            index=2,  # default to llama3
            key="onboard_model_radio",
        )
        chosen_model = OLLAMA_MODELS[choice_idx]["name"]

        # Already installed?
        already_installed = any(
            chosen_model == m or m.startswith(f"{chosen_model}:")
            for m in installed
        )

        if already_installed:
            st.info(f"`{chosen_model}` is already installed.")
            st.session_state["onboard_ollama_model"] = chosen_model
            st.session_state["onboard_backend"] = "ollama"
        else:
            if st.button(f"Download {chosen_model}", key="ollama_pull", type="primary"):
                progress = st.progress(0, text=f"Pulling {chosen_model}...")
                status_text = st.empty()

                try:
                    for update in pull_model(chosen_model, host):
                        status = update.get("status", "")
                        completed = update.get("completed", 0)
                        total = update.get("total", 0)

                        if total > 0:
                            pct = min(completed / total, 1.0)
                            size_mb = total / (1024 * 1024)
                            done_mb = completed / (1024 * 1024)
                            progress.progress(pct, text=f"{status} — {done_mb:.0f}/{size_mb:.0f} MB")
                        else:
                            status_text.caption(status)

                    progress.progress(1.0, text="Download complete!")
                    st.success(f"`{chosen_model}` installed successfully.")
                    st.session_state["onboard_ollama_model"] = chosen_model
                    st.session_state["onboard_backend"] = "ollama"
                except Exception as e:
                    progress.progress(0, text="Download failed.")
                    st.error(f"Failed to pull model: {e}")

    # --- Claude API section -----------------------------------------------
    st.markdown("---")
    st.markdown("### Option B: Claude API")
    st.write("If you have an Anthropic API key, you can use Claude instead of a local model.")

    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        key="onboard_api_key",
    )
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
        st.session_state["onboard_backend"] = "claude"
        st.success("Claude API key set for this session.")

    # --- Navigation -------------------------------------------------------
    _nav_buttons("step4", back_step=3, next_step=5)


# ---------------------------------------------------------------------------
# Step 5 — Import & go
# ---------------------------------------------------------------------------

def _step_import() -> None:
    # If import already completed, show launch button persistently
    if st.session_state.get("onboard_import_done"):
        st.subheader("Step 5: Import Your Data")
        st.success("Your chat history has been imported successfully!")
        if st.button("Launch ChatVault", key="step5_launch", type="primary"):
            for key in list(st.session_state.keys()):
                if key.startswith("onboard"):
                    del st.session_state[key]
            st.rerun()
        return

    st.subheader("Step 5: Import Your Data")

    data_dir = st.session_state.get("onboard_data_dir", "data")
    data_path = Path(data_dir)
    backend = st.session_state.get("onboard_backend", "ollama")
    model = st.session_state.get("onboard_ollama_model", "llama3")

    st.write(f"**Data source:** `{data_path.resolve()}`")
    st.write(f"**LLM backend:** {backend}" + (f" (model: {model})" if backend == "ollama" else ""))

    connectors = get_connectors()
    detected = [c for c in connectors if data_path.exists() and c.detect(data_path)]
    if detected:
        st.info(f"Detected: {', '.join(c.source_name for c in detected)}")
    else:
        st.warning("No compatible export files detected.")

    if st.button("Start Import", key="step5_import", type="primary"):
        progress_bar = st.progress(0.0, text="Starting import...")

        try:
            from chatvault.ingest import main as ingest_main

            progress_bar.progress(0.20, text="Running ingestion...")
            ingest_main(data_dir=data_path)

            progress_bar.progress(0.30, text="Generating embeddings...")
            from chatvault.embeddings import EmbeddingEngine
            engine = EmbeddingEngine(db_path=DEFAULT_DB_PATH, chroma_dir=DEFAULT_CHROMA_DIR)

            status_text = st.empty()

            def on_progress(current: int, total: int, label: str) -> None:
                pct = current / total if total > 0 else 0
                # Conversations: 30-55%, Messages: 55-90%
                if label == "conversations":
                    overall = 0.30 + (pct * 0.25)
                else:
                    overall = 0.55 + (pct * 0.35)
                progress_bar.progress(min(overall, 0.90), text=f"Embedding {label}... {current}/{total}")

            engine.embed_all(progress_callback=on_progress)

            progress_bar.progress(0.90, text="Saving configuration...")
            _save_wizard_config(backend, model)

            progress_bar.progress(1.0, text="Import complete!")
            st.balloons()
            st.session_state["onboard_import_done"] = True
            st.rerun()

        except Exception as e:
            progress_bar.progress(0.0, text="Import failed.")
            st.error(f"Import failed: {e}")
            st.write("Check that your export files are in the correct format and location.")

    col_back, _ = st.columns(2)
    with col_back:
        if st.button("Back", key="step5_back"):
            st.session_state["onboard_step"] = 4
            st.rerun()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nav_buttons(prefix: str, back_step: int, next_step: int) -> None:
    """Render Back / Next buttons for a wizard step."""
    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("Back", key=f"{prefix}_back"):
            st.session_state["onboard_step"] = back_step
            st.rerun()
    with col_next:
        if st.button("Next", key=f"{prefix}_next", type="primary"):
            st.session_state["onboard_step"] = next_step
            st.rerun()


def _check_ollama_available() -> bool:
    """Return True if Ollama is reachable."""
    try:
        import requests
        import os
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        resp = requests.get(f"{host}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _save_wizard_config(backend: str, model: str) -> None:
    """Persist the wizard choices to ~/.chatvault/config.yaml."""
    try:
        cfg = load_config()
    except Exception:
        cfg = Config()

    cfg.llm_backend = backend
    if backend == "ollama":
        cfg.ollama_model = model
    save_config(cfg)
