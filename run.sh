#!/bin/bash
cd "$(dirname "$0")"

trap 'echo ""; echo "Shutting down ChatVault..."; exit 0' SIGINT

echo "========================================="
echo "  ChatVault — Local AI Chat Assistant"
echo "========================================="
echo ""

# Find Python 3.12+
PYTHON=""
if command -v python3.12 &> /dev/null; then
    PYTHON="python3.12"
elif command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(sys.version_info[:2] >= (3, 12))" 2>/dev/null)
    if [ "$PY_VERSION" = "True" ]; then
        PYTHON="python3"
    fi
fi

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.12+ is required but was not found."
    echo "Please install Python 3.12 from https://www.python.org/downloads/"
    echo "or via your package manager (e.g., brew install python@3.12)."
    exit 1
fi

echo "Using Python: $("$PYTHON" --version)"
echo ""

# Create virtual environment if needed
if [ ! -d ".venv" ]; then
    echo "[1/4] Creating Python virtual environment..."
    "$PYTHON" -m venv .venv
else
    echo "[1/4] Virtual environment found."
fi
source .venv/bin/activate

# Install dependencies (skip if already done)
if [ ! -f ".venv/.deps_installed" ] || [ requirements.txt -nt ".venv/.deps_installed" ]; then
    echo "[2/4] Installing dependencies (first run or requirements changed)..."
    pip install -r requirements.txt --quiet
    pip install -e . --quiet
    touch .venv/.deps_installed
    echo "       Done."
else
    echo "[2/4] Dependencies already installed."
fi

# If DB exists and data/ has changed, re-ingest + re-embed
if [ -f "chatvault.db" ]; then
    DATA_CHANGED=false
    if [ -d "data" ]; then
        # Check if any data file is newer than the DB
        NEWER=$(find data -type f -newer chatvault.db 2>/dev/null | head -1)
        if [ -n "$NEWER" ]; then
            DATA_CHANGED=true
        fi
    fi

    if [ "$DATA_CHANGED" = true ]; then
        echo "[3/4] New data detected — re-ingesting..."
        "$PYTHON" -m chatvault.ingest --append
        echo "       Generating embeddings..."
        "$PYTHON" -m chatvault.embeddings
        echo "       Done."
    else
        echo "[3/4] No new data. Skipping ingestion."
    fi
else
    echo "[3/4] First run — the setup wizard will handle ingestion."
fi

# Pre-download embedding model so the UI doesn't hang on first load
"$PYTHON" -c "
import sys, os
cache_dir = os.path.expanduser('~/.cache/huggingface/hub')
if not os.path.isdir(os.path.join(cache_dir, 'models--sentence-transformers--all-MiniLM-L6-v2')):
    print('       Downloading embedding model (~80 MB, one-time)...')
    from sentence_transformers import SentenceTransformer
    SentenceTransformer('all-MiniLM-L6-v2')
    print('       Done.')
" 2>/dev/null

# Check for Ollama
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo ""
    echo "Warning: Ollama is not running. RAG chat will not work until you start it (ollama serve)."
fi

# Launch UI
echo "[4/4] Launching Streamlit UI..."
echo "       Open http://localhost:8502 in your browser."
echo ""
.venv/bin/python -m streamlit run chatvault/app.py --server.port 8502
