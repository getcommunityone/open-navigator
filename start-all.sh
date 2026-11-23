#!/bin/bash

# Start All Services for Open Navigator (#787)
#
#   ./start-all.sh            clear ports 3000/5173/8001, start API + web app + docs, check they answer
#   ./start-all.sh --attach   same, then attach to the tmux session (interactive)
#   ./start-all.sh --no-docs  skip the Docusaurus docs site (port 3000)
#
# It never asks a question, so it can run from a script or a phone session. It exits 0 only when
# the API (8001) and the web app (5173) both answer; docs (3000) is reported but never fails the run.
# Set START_ALL_NO_TMUX=1 to use plain background processes instead of tmux.
# Stop everything with ./stop-all.sh.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ATTACH=0
WITH_DOCS=1
for arg in "$@"; do
    case "$arg" in
        --attach)  ATTACH=1 ;;
        --no-docs) WITH_DOCS=0 ;;
        -h|--help) sed -n '3,12p' "$0"; exit 0 ;;
        *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
    esac
done

# Ports are overridable only so tests can use free ones; the app itself is fixed to 8001/5173/3000.
API_PORT="${START_ALL_API_PORT:-8001}"
WEB_PORT="${START_ALL_WEB_PORT:-5173}"
DOCS_PORT="${START_ALL_DOCS_PORT:-3000}"
SESSION="open-navigator"
WAIT_SECONDS="${START_ALL_WAIT_SECONDS:-90}"

echo "🚀 Starting Open Navigator"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

mkdir -p logs

# Check if dependencies are installed
echo -e "${BLUE}Checking dependencies...${NC}"

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found in $SCRIPT_DIR. Run ./install.sh first${NC}"
    exit 1
fi

if [ ! -d "web_app/node_modules" ]; then
    echo -e "${YELLOW}Installing web_app dependencies...${NC}"
    (cd web_app && npm install) || { echo -e "${RED}npm install failed in web_app${NC}"; exit 1; }
fi

if [ "$WITH_DOCS" = "1" ] && [ ! -d "web_docs/node_modules" ]; then
    echo -e "${YELLOW}Installing documentation site dependencies...${NC}"
    (cd web_docs && npm install) || { echo -e "${RED}npm install failed in web_docs${NC}"; exit 1; }
fi

echo -e "${GREEN}✅ Dependencies OK${NC}"
echo ""

has_tmux() {
    [ "${START_ALL_NO_TMUX:-0}" != "1" ] && command -v tmux >/dev/null 2>&1
}

# PIDs listening on a TCP port (lsof first, fuser as a fallback).
port_pids() {
    local port="$1" pids=""
    if command -v lsof >/dev/null 2>&1; then
        pids="$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u | tr '\n' ' ')"
    fi
    if [ -z "$pids" ] && command -v fuser >/dev/null 2>&1; then
        pids="$(fuser "$port"/tcp 2>/dev/null | tr -s ' ')"
    fi
    echo "$pids"
}

# Stop whatever holds a port: polite first, then forceful, then wait until it is really free.
free_port() {
    local port="$1" pids tries
    pids="$(port_pids "$port")"
    [ -z "$(echo "$pids" | tr -d ' ')" ] && return 0

    echo -e "${YELLOW}⚠️  Port $port is in use (PID: $pids) - stopping it${NC}"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    for tries in 1 2 3 4 5 6 7 8 9 10; do
        [ -z "$(port_pids "$port" | tr -d ' ')" ] && return 0
        sleep 0.5
    done
    # shellcheck disable=SC2046
    kill -9 $(port_pids "$port") 2>/dev/null || true
    for tries in 1 2 3 4 5 6 7 8 9 10; do
        [ -z "$(port_pids "$port" | tr -d ' ')" ] && return 0
        sleep 0.5
    done
    echo -e "${RED}❌ Port $port is still in use (PID: $(port_pids "$port")). Stop it by hand, then run this again.${NC}"
    return 1
}

# Stop this repo's own leftover dev processes even when they hold no port (#789): a Vite that hung
# during startup never binds 5173, so freeing ports alone would miss it. Only processes whose working
# directory is inside this repository are touched, and never this script.
stop_stale_processes() {
    local pattern="vite|npm run dev|npm start|main\\.py serve|uvicorn api\\.main|docusaurus"
    local pid cwd victims=""
    for pid in $(pgrep -f "$pattern" 2>/dev/null); do
        [ "$pid" = "$$" ] && continue
        cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || true)"
        case "$cwd" in
            "$SCRIPT_DIR"|"$SCRIPT_DIR"/*) victims="$victims $pid" ;;
        esac
    done
    [ -z "$(echo "$victims" | tr -d ' ')" ] && return 0

    echo -e "${YELLOW}⚠️  Stopping leftover dev processes from this repo (PID:$victims)${NC}"
    # shellcheck disable=SC2086
    kill $victims 2>/dev/null || true
    local tries alive
    for tries in 1 2 3 4 5 6 7 8 9 10; do
        alive=""
        for pid in $victims; do kill -0 "$pid" 2>/dev/null && alive="$alive $pid"; done
        [ -z "$(echo "$alive" | tr -d ' ')" ] && return 0
        sleep 0.5
    done
    # shellcheck disable=SC2086
    kill -9 $alive 2>/dev/null || true
    sleep 0.5
}

kill_port_processes() {
    echo -e "${BLUE}Clearing ports...${NC}"

    # An old tmux session from an earlier run owns its windows; end it first.
    if command -v tmux >/dev/null 2>&1; then
        tmux kill-session -t "$SESSION" 2>/dev/null || true
    fi

    stop_stale_processes

    local failed=0 port
    for port in "$DOCS_PORT" "$WEB_PORT" "$API_PORT"; do
        free_port "$port" || failed=1
    done
    if [ "$failed" = "1" ]; then
        exit 1
    fi
    echo -e "${GREEN}✅ Ports clear${NC}"
    echo ""
}

# Wait up to $3 seconds for an HTTP URL to answer with any status. Returns 0 when it does.
wait_for_url() {
    local url="$1" _name="$2" limit="$3" waited=0
    while [ "$waited" -lt "$limit" ]; do
        if curl -s -o /dev/null -m 3 "$url"; then
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    return 1
}

# Report one service; show the end of its log when it is down.
check_service() {
    local name="$1" url="$2" logfile="$3" required="$4"
    if wait_for_url "$url" "$name" "$WAIT_SECONDS"; then
        echo -e "  ${GREEN}OK${NC}      $name  $url"
        return 0
    fi
    echo -e "  ${RED}FAILED${NC}  $name  $url (no answer after ${WAIT_SECONDS}s)"
    if [ -f "$logfile" ]; then
        echo "          last lines of $logfile:"
        tail -n 8 "$logfile" | sed 's/^/          | /'
    fi
    [ "$required" = "1" ] && return 1
    return 0
}

verify_services() {
    echo ""
    echo -e "${BLUE}Checking that the services answer (up to ${WAIT_SECONDS}s each)...${NC}"
    local bad=0
    check_service "API       " "http://localhost:$API_PORT/docs" "logs/api.log" 1 || bad=1
    check_service "Web app   " "http://localhost:$WEB_PORT/"     "logs/dashboard.log" 1 || bad=1
    if [ "$WITH_DOCS" = "1" ]; then
        check_service "Docs      " "http://localhost:$DOCS_PORT/" "logs/docs.log" 0
    fi
    echo ""
    if [ "$bad" = "1" ]; then
        echo -e "${RED}❌ Not everything came up. Fix the log lines above, then run ./start-all.sh again.${NC}"
        return 1
    fi
    echo -e "${GREEN}🎉 Open Navigator is ready${NC}"
    echo ""
    echo "  • 🚀 MAIN APP:       http://localhost:$WEB_PORT"
    echo "  • 🔥 API Backend:    http://localhost:$API_PORT   (docs: http://localhost:$API_PORT/docs)"
    [ "$WITH_DOCS" = "1" ] && echo "  • 📚 Documentation:  http://localhost:$DOCS_PORT"
    echo ""
    echo "  Logs:      tail -f logs/api.log logs/dashboard.log"
    echo "  Stop all:  ./stop-all.sh"
    return 0
}

# Preferred: one detached tmux session, one window per service, output also saved to logs/.
start_with_tmux() {
    echo -e "${BLUE}Starting services in tmux session: $SESSION${NC}"
    : > logs/api.log; : > logs/dashboard.log; : > logs/docs.log

    tmux new-session -d -s "$SESSION" -n "API" "cd '$SCRIPT_DIR' && source .venv/bin/activate && echo '🔥 Starting API Backend...' && python main.py serve 2>&1 | tee -a '$SCRIPT_DIR/logs/api.log'; read"

    tmux new-window -t "$SESSION" -n "Dashboard" "cd '$SCRIPT_DIR/web_app' && echo '⚛️  Starting React Dashboard...' && npm run dev 2>&1 | tee -a '$SCRIPT_DIR/logs/dashboard.log'; read"

    if [ "$WITH_DOCS" = "1" ]; then
        tmux new-window -t "$SESSION" -n "Docs" "cd '$SCRIPT_DIR/web_docs' && echo '📚 Starting Documentation Site...' && npm start 2>&1 | tee -a '$SCRIPT_DIR/logs/docs.log'; read"
    fi

    tmux new-window -t "$SESSION" -n "Shell" "cd '$SCRIPT_DIR' && source .venv/bin/activate && bash"
    tmux select-window -t "$SESSION:0"
    echo -e "${GREEN}✅ Services launched${NC} (attach later with: tmux attach -t $SESSION)"
}

# Fallback: plain background processes that survive the terminal closing.
start_without_tmux() {
    echo -e "${BLUE}Starting services as background processes...${NC}"
    local launcher="nohup"
    command -v setsid >/dev/null 2>&1 && launcher="setsid nohup"

    # shellcheck disable=SC1091
    source .venv/bin/activate
    $launcher python main.py serve > logs/api.log 2>&1 < /dev/null &
    echo $! > logs/api.pid

    (cd web_app && exec $launcher npm run dev > ../logs/dashboard.log 2>&1 < /dev/null) &
    echo $! > logs/dashboard.pid

    if [ "$WITH_DOCS" = "1" ]; then
        (cd web_docs && exec $launcher npm start > ../logs/docs.log 2>&1 < /dev/null) &
        echo $! > logs/docs.pid
    fi
    echo -e "${GREEN}✅ Services launched${NC}"
}

kill_port_processes

if has_tmux; then
    start_with_tmux
else
    start_without_tmux
fi

if verify_services; then
    status=0
else
    status=1
fi

if [ "$ATTACH" = "1" ] && has_tmux && [ "$status" = "0" ]; then
    tmux attach -t "$SESSION"
fi

exit "$status"
