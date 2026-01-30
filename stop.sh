#!/bin/bash
cd "$(dirname "$0")"

echo "Stopping ChatVault..."

# Kill any process on port 8000
PID=$(lsof -ti:8000 2>/dev/null)
if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null
    echo "Server stopped (PID $PID)."
else
    echo "No ChatVault server running on port 8000."
fi
