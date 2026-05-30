#!/bin/bash

# Start All Services for Open Navigator
# This script launches the API backend, React dashboard, and Docusaurus docs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting Open Navigator"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if dependencies are installed
echo -e "${BLUE}Checking dependencies...${NC}"

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Run ./install.sh first${NC}"
    exit 1
fi

if [ ! -d "web_app/node_modules" ]; then
    echo -e "${YELLOW}Installing web_app dependencies...${NC}"
    cd web_app && npm install && cd ..
fi

if [ ! -d "web_docs/node_modules" ]; then
    echo -e "${YELLOW}Installing documentation site dependencies...${NC}"
    cd web_docs && npm install && cd ..
fi

echo -e "${GREEN}✅ Dependencies OK${NC}"
echo ""

# Function to kill processes on required ports
kill_port_processes() {
    local ports=(3000 5173 8000)
    
    echo -e "${BLUE}Checking for processes on ports...${NC}"
    
    for port in "${ports[@]}"; do
        local pid=$(lsof -ti:$port 2>/dev/null)
        if [ ! -z "$pid" ]; then
            echo -e "${YELLOW}⚠️  Killing process on port $port (PID: $pid)${NC}"
            kill -9 $pid 2>/dev/null || true
            sleep 0.5
        fi
    done
    
    echo -e "${GREEN}✅ Ports cleared${NC}"
    echo ""
}

# Function to check if tmux is available
has_tmux() {
    command -v tmux >/dev/null 2>&1
}

# Kill any processes on the ports we need
kill_port_processes

# Function to start with tmux (preferred)
start_with_tmux() {
    SESSION="open-navigator"
    
    # Kill existing session if it exists
    tmux kill-session -t $SESSION 2>/dev/null || true
    
    echo -e "${BLUE}Starting services in tmux session: $SESSION${NC}"
    echo ""
    
    # Create new session with first window for API
    tmux new-session -d -s $SESSION -n "API" "cd '$SCRIPT_DIR' && source .venv/bin/activate && echo '🔥 Starting API Backend...' && python main.py serve; read"
    
    # Create window for Dashboard
    tmux new-window -t $SESSION -n "Dashboard" "cd '$SCRIPT_DIR/web_app' && echo '⚛️  Starting React Dashboard...' && npm run dev; read"
    
    # Create window for Docs
    tmux new-window -t $SESSION -n "Docs" "cd '$SCRIPT_DIR/web_docs' && echo '📚 Starting Documentation Site...' && npm start; read"
    
    # Create window for logs/commands
    tmux new-window -t $SESSION -n "Shell" "cd '$SCRIPT_DIR' && source .venv/bin/activate && bash"
    
    # Select first window
    tmux select-window -t $SESSION:0
    
    echo -e "${GREEN}✅ All services started in tmux!${NC}"
    echo ""
    echo "📡 Services:"
    echo "  • 🚀 MAIN APP:       http://localhost:5173 (Open Navigator - search, filters, heatmap)"
    echo "  • 📚 Documentation:  http://localhost:3000 (Docusaurus - guides & tutorials)"
    echo "  • 🔥 API Backend:    http://localhost:8000 (FastAPI)"
    echo "  • 📖 API Docs:       http://localhost:8000/docs"
    echo ""
    echo "💡 Start here: http://localhost:5173 (Open Navigator - MAIN APPLICATION)"
    echo ""
    echo "🎮 tmux Controls:"
    echo "  • Attach to session: tmux attach -t $SESSION"
    echo "  • Switch windows:    Ctrl+b then 0/1/2/3"
    echo "  • Detach:           Ctrl+b then d"
    echo "  • Stop all:         tmux kill-session -t $SESSION"
    echo ""
    
    # Ask if user wants to attach
    read -p "Attach to tmux session now? [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        # Open browser before attaching
        if command -v xdg-open >/dev/null 2>&1; then
            sleep 2  # Give services time to start
            xdg-open http://localhost:5173 2>/dev/null &
        fi
        tmux attach -t $SESSION
    else
        # Offer to open browser if not attaching
        if command -v xdg-open >/dev/null 2>&1; then
            read -p "Open main application in browser? [Y/n] " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                sleep 2
                xdg-open http://localhost:5173 2>/dev/null &
            fi
        fi
    fi
}

# Function to start without tmux (fallback)
start_without_tmux() {
    echo -e "${YELLOW}tmux not found. Starting services in background...${NC}"
    echo -e "${YELLOW}(Install tmux for better experience: sudo apt install tmux)${NC}"
    echo ""
    
    # Create log directory
    mkdir -p logs
    
    # Start API
    echo -e "${BLUE}Starting API Backend...${NC}"
    source .venv/bin/activate
    nohup python main.py serve > logs/api.log 2>&1 &
    API_PID=$!
    echo $API_PID > logs/api.pid
    echo -e "${GREEN}✅ API started (PID: $API_PID)${NC}"
    
    # Start Dashboard
    echo -e "${BLUE}Starting React Dashboard...${NC}"
    cd web_app
    nohup npm run dev > ../logs/dashboard.log 2>&1 &
    DASHBOARD_PID=$!
    echo $DASHBOARD_PID > ../logs/dashboard.pid
    cd ..
    echo -e "${GREEN}✅ Dashboard started (PID: $DASHBOARD_PID)${NC}"
    
    # Start Docs
    echo -e "${BLUE}Starting Documentation Site...${NC}"
    cd web_docs
    nohup npm start > ../logs/docs.log 2>&1 &
    DOCS_PID=$!
    echo $DOCS_PID > ../logs/docs.pid
    cd ..
    echo -e "${GREEN}✅ Docs started (PID: $DOCS_PID)${NC}"
    
    echo ""
    echo -e "${GREEN}✅ All services started!${NC}"
    echo ""
    echo "📡 Services:"
    echo "  • 🚀 MAIN APP:       http://localhost:5173 (Open Navigator - search, filters, heatmap)"
    echo "  • 📚 Documentation:  http://localhost:3000 (Docusaurus - guides & tutorials)"
    echo "  • 🔥 API Backend:    http://localhost:8000 (FastAPI)"
    echo "  • 📖 API Docs:       http://localhost:8000/docs"
    echo ""
    echo "💡 Start here: http://localhost:5173 (Open Navigator - MAIN APPLICATION)"
    echo ""
    echo "📋 Logs:"
    echo "  • API:        tail -f logs/api.log"
    echo "  • Dashboard:  tail -f logs/dashboard.log"
    echo "  • Docs:       tail -f logs/docs.log"
    echo ""
    echo "🛑 To stop all services:"
    echo "  ./stop-all.sh"
    echo "  (or kill \$(cat logs/*.pid))"
    echo ""
    
    # Wait a bit for services to start
    echo "⏳ Waiting for services to initialize..."
    sleep 5
    
    echo ""
    echo "🎉 Open Navigator is ready!"
    echo ""
    echo "🚀 MAIN APP: http://localhost:5173 (Open Navigator - search, filters, heatmap)"
    echo "📚 Documentation: http://localhost:3000 (guides, API docs, tutorials)"
    echo "🔥 API: http://localhost:8000/docs (FastAPI interactive docs)"
    echo ""
    
    # Offer to open browser
    if command -v xdg-open >/dev/null 2>&1; then
        read -p "Open main application in browser? [Y/n] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            sleep 2  # Give services a moment to fully start
            xdg-open http://localhost:5173 2>/dev/null &
        fi
    fi
}

# Main execution
if has_tmux; then
    start_with_tmux
else
    start_without_tmux
fi
