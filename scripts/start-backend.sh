#!/bin/bash
# Start backend with automatic restart and port cleanup
cd /home/pi/piboard/backend

while true; do
    # Kill any existing uvicorn on port 8000
    fuser -k 8000/tcp 2>/dev/null
    sleep 2

    echo "[BACKEND] Starting uvicorn..."
    /home/pi/piboard/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 2>&1
    EXIT_CODE=$?
    echo "[BACKEND] Exited with code $EXIT_CODE, restarting in 5s..."
    sleep 5
done
