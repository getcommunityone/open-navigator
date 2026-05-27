#!/usr/bin/env bash
# Export int_jurisdiction_websites URLs → run axe / Pa11y / Lighthouse → persist to Postgres bronze.
#
# Examples:
#   ./packages/accessibility/src/accessibility/run_accessibility_scan.sh --engine axe --state AL
#   ./packages/accessibility/src/accessibility/run_accessibility_scan.sh --engine pa11y --limit 500
#   ./packages/accessibility/src/accessibility/run_accessibility_scan.sh --engine lighthouse --state AL
#   PA11YCI_CONCURRENCY=10 WORKER_POOL_SIZE=6 ./packages/accessibility/src/accessibility/run_accessibility_scan.sh --engine pa11y
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
ROOT="$SCRIPT_DIR"
while [[ "$ROOT" != "/" && ! -f "$ROOT/packages/accessibility/src/accessibility/export_urls.py" ]]; do
  ROOT="$(dirname "$ROOT")"
done
if [[ ! -f "$ROOT/packages/accessibility/src/accessibility/export_urls.py" ]]; then
  echo "error: could not find open-navigator repo root from $SCRIPT_DIR" >&2
  exit 1
fi
cd "$ROOT"

ENGINE="axe"
STATE=""
LIMIT=""
OFFSET=0
BATCH_ID=""
JURISDICTION_PREFIX=""
SKIP_EXPORT=0
SKIP_PERSIST=0
URLS_FILE="${ROOT}/data/cache/accessibility/urls.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --engine) ENGINE="$2"; shift 2 ;;
    --state) STATE="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --offset) OFFSET="$2"; shift 2 ;;
    --batch-id) BATCH_ID="$2"; shift 2 ;;
    --jurisdiction-id-prefix) JURISDICTION_PREFIX="$2"; shift 2 ;;
    --urls-file) URLS_FILE="$2"; shift 2 ;;
    --skip-export) SKIP_EXPORT=1; shift ;;
    --skip-persist) SKIP_PERSIST=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
else
  echo "error: need .venv/bin/python or python3" >&2
  exit 1
fi

ACC_DIR="$ROOT/packages/accessibility/src/accessibility"
mkdir -p "$(dirname "$URLS_FILE")"

if [[ "$SKIP_EXPORT" -eq 0 ]]; then
  EXPORT_ARGS=( -m accessibility.export_urls --out "$URLS_FILE" )
  [[ -n "$STATE" ]] && EXPORT_ARGS+=( --state "$STATE" )
  [[ -n "$LIMIT" ]] && EXPORT_ARGS+=( --limit "$LIMIT" )
  [[ "$OFFSET" -gt 0 ]] && EXPORT_ARGS+=( --offset "$OFFSET" )
  [[ -n "$BATCH_ID" ]] && EXPORT_ARGS+=( --batch-id "$BATCH_ID" )
  [[ -n "$JURISDICTION_PREFIX" ]] && EXPORT_ARGS+=( --jurisdiction-id-prefix "$JURISDICTION_PREFIX" )
  "$PY" "${EXPORT_ARGS[@]}"
fi

if [[ ! -d "$ACC_DIR/node_modules" ]]; then
  echo "Installing Node deps in $ACC_DIR ..."
  (cd "$ACC_DIR" && npm install)
fi

BATCH_ID="${BATCH_ID:-$(node -e "const j=require(process.argv[1]); console.log(j.batch_id||'');" "$URLS_FILE" 2>/dev/null || true)}"
CACHE_DIR="$ROOT/data/cache/accessibility"

case "$ENGINE" in
  axe)
    OUT_FILE="$CACHE_DIR/axe-${BATCH_ID:-run}.ndjson"
    AXE_ARGS=( run_axe_scan.mjs --urls "$URLS_FILE" --out "$OUT_FILE" )
    [[ -n "$LIMIT" ]] && AXE_ARGS+=( --limit "$LIMIT" )
    [[ "$OFFSET" -gt 0 ]] && AXE_ARGS+=( --offset "$OFFSET" )
    (cd "$ACC_DIR" && node "${AXE_ARGS[@]}")
    RESULT_FILE="$OUT_FILE"
    ;;
  pa11y)
    PA11Y_ARGS=( run_pa11y_workers.mjs --urls "$URLS_FILE" )
    (cd "$ACC_DIR" && node "${PA11Y_ARGS[@]}")
    RESULT_FILE="$CACHE_DIR/pa11y-${BATCH_ID:-run}/pa11y-results-merged.json"
    ;;
  lighthouse)
    OUT_FILE="$CACHE_DIR/lighthouse-${BATCH_ID:-run}.ndjson"
    LH_ARGS=( run_lighthouse_scan.mjs --urls "$URLS_FILE" --out "$OUT_FILE" )
    [[ -n "$LIMIT" ]] && LH_ARGS+=( --limit "$LIMIT" )
    [[ "$OFFSET" -gt 0 ]] && LH_ARGS+=( --offset "$OFFSET" )
    (cd "$ACC_DIR" && node "${LH_ARGS[@]}")
    RESULT_FILE="$OUT_FILE"
    ;;
  *)
    echo "error: --engine must be axe, pa11y, or lighthouse (got $ENGINE)" >&2
    exit 1
    ;;
esac

if [[ "$SKIP_PERSIST" -eq 0 ]]; then
  if [[ "$ENGINE" == "lighthouse" ]]; then
    "$PY" -m accessibility.persist_lighthouse_results \
      --input "$RESULT_FILE" \
      --ensure-ddl
  else
    "$PY" -m accessibility.persist_results \
      --scanner "$ENGINE" \
      --input "$RESULT_FILE" \
      --ensure-ddl
  fi
fi

echo "Done. Results: $RESULT_FILE"
