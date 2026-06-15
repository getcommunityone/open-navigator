#!/bin/bash

# Stop All Services for Open Navigator

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🛑 Stopping Open Navigator"
echo "========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check for tmux session
if command -v tmux >/dev/null 2>&1; then
    if tmux has-session -t open-navigator 2>/dev/null; then
        echo -e "${YELLOW}Killing tmux session...${NC}"
        tmux kill-session -t open-navigator
        echo -e "${GREEN}✅ tmux session killed${NC}"
    fi
fi

# Stop background processes
if [ -d "logs" ]; then
    echo -e "${YELLOW}Stopping background services...${NC}"
    
    for pidfile in logs/*.pid; do
        if [ -f "$pidfile" ]; then
            PID=$(cat "$pidfile")
            SERVICE=$(basename "$pidfile" .pid)
            
            if kill -0 "$PID" 2>/dev/null; then
                echo "  Stopping $SERVICE (PID: $PID)"
                kill "$PID" 2>/dev/null || true
                rm "$pidfile"
            else
                echo "  $SERVICE already stopped"
                rm "$pidfile"
            fi
        fi
    done
    
    echo -e "${GREEN}✅ All services stopped${NC}"
fi

# Kill any remaining node/python processes on known ports
echo -e "${YELLOW}Cleaning up ports...${NC}"
lsof -ti:8001 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ All services stopped and ports cleaned${NC}"
