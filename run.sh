#!/bin/bash
cd "$(dirname "$0")"

trap 'echo ""; echo "Shutting down ChatVault..."; exit 0' SIGINT

# --reset flag: wipe DB, vector store, and config for a fresh start
if [ "$1" = "--reset" ]; then
    echo "Resetting ChatVault to a fresh state..."
    # Stop any running server
    PID=$(lsof -ti:8000 2>/dev/null)
    if [ -n "$PID" ]; then
        kill "$PID" 2>/dev/null
        echo "  Stopped running server."
    fi
    rm -f chatvault.db chatvault.db-shm chatvault.db-wal
    rm -rf chroma_data/
    rm -f ~/.chatvault/config.yaml
    echo "  Deleted database, vector store, and config."
    echo "  The setup wizard will run on next launch."
    echo ""
fi

echo "========================================="
echo "  ChatVault — Local AI Chat Assistant"
echo "========================================="
echo ""

# Find Python 3.10+
PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &> /dev/null; then
        PY_OK=$("$candidate" -c "import sys; print(sys.version_info[:2] >= (3, 10))" 2>/dev/null)
        if [ "$PY_OK" = "True" ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.10+ is required but was not found."
    echo "Please install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

echo "Using Python: $("$PYTHON" --version)"
echo ""

# Create virtual environment if needed
if [ ! -d ".venv" ]; then
    echo "[1/5] Creating Python virtual environment..."
    "$PYTHON" -m venv .venv
else
    echo "[1/5] Virtual environment found."
fi
source .venv/bin/activate

# Install Python dependencies (skip if already done)
if [ ! -f ".venv/.deps_installed" ] || [ requirements.txt -nt ".venv/.deps_installed" ]; then
    echo "[2/5] Installing Python dependencies..."
    pip install -r requirements.txt --quiet
    pip install -e . --quiet
    touch .venv/.deps_installed
    echo "       Done."
else
    echo "[2/5] Python dependencies already installed."
fi

# Build frontend
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is required but was not found."
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

if [ ! -d "frontend/node_modules" ] || [ "frontend/package.json" -nt "frontend/node_modules/.package-lock.json" ]; then
    echo "[3/5] Installing frontend dependencies..."
    (cd frontend && npm install --silent)
    echo "       Done."
else
    echo "[3/5] Frontend dependencies already installed."
fi

if [ ! -d "frontend/dist" ] || [ "frontend/src/App.tsx" -nt "frontend/dist/index.html" ]; then
    echo "       Building frontend..."
    (cd frontend && npm run build --silent)
    echo "       Done."
else
    echo "       Frontend already built."
fi

# If DB exists and data/ has changed, re-ingest + re-embed
if [ -f "chatvault.db" ]; then
    DATA_CHANGED=false
    if [ -d "data" ]; then
        NEWER=$(find data -type f -newer chatvault.db 2>/dev/null | head -1)
        if [ -n "$NEWER" ]; then
            DATA_CHANGED=true
        fi
    fi

    if [ "$DATA_CHANGED" = true ]; then
        echo "[4/5] New data detected — re-ingesting..."
        python -m chatvault.ingest --append
        echo "       Generating embeddings..."
        python -m chatvault.embeddings
        echo "       Done."
    else
        echo "[4/5] No new data. Skipping ingestion."
    fi
else
    echo "[4/5] First run — the setup wizard will handle ingestion."
fi

# Pre-download embedding model so the UI doesn't hang on first load
python -c "
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
    echo "Note: Ollama is not running. RAG chat requires Ollama (ollama serve) or a Claude API key."
fi

# Launch API server (serves built frontend from frontend/dist/)
echo "[5/5] Launching ChatVault..."
echo "       Open http://localhost:8000 in your browser."
echo ""
python -m uvicorn chatvault.api:app --host localhost --port 8000
