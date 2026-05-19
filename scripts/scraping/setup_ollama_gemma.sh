#!/usr/bin/env bash
# Install Ollama (if missing) and pull the Gemma model for local scraping extraction.
#
# Usage:
#   ./scripts/scraping/setup_ollama_gemma.sh
#   OLLAMA_MODEL=gemma3 ./scripts/scraping/setup_ollama_gemma.sh
#
set -euo pipefail

MODEL="${OLLAMA_MODEL:-${SCRAPED_MEETINGS_OLLAMA_MODEL:-gemma4}}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama not found on PATH."
  if [[ "${INSTALL_OLLAMA:-0}" == "1" ]]; then
    echo "INSTALL_OLLAMA=1 — running https://ollama.com/install.sh"
    curl -fsSL https://ollama.com/install.sh | sh
  else
    echo "Install: https://ollama.com/download"
    echo "Linux: curl -fsSL https://ollama.com/install.sh | sh"
    echo "Or re-run: INSTALL_OLLAMA=1 ./scripts/scraping/setup_ollama_gemma.sh"
    exit 1
  fi
fi

if ! curl -fsS -m 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Starting ollama serve in background (not systemd)…"
  nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
  sleep 2
fi

echo "Pulling Ollama model: ${MODEL}"
ollama pull "${MODEL}"

echo "Verifying API…"
if command -v curl >/dev/null 2>&1; then
  curl -fsS http://127.0.0.1:11434/api/tags | head -c 400 || true
  echo ""
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  "${ROOT}/.venv/bin/python" "${ROOT}/scripts/scraping/extract_page_structured.py" --check-ollama --model "${MODEL}"
else
  echo "Create .venv and run: .venv/bin/python scripts/scraping/extract_page_structured.py --check-ollama"
fi

echo "Done. Test extraction:"
echo "  .venv/bin/python scripts/scraping/extract_page_structured.py --url https://example.gov/ --out /tmp/test.json"
