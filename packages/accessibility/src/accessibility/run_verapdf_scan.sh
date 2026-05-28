#!/usr/bin/env bash
# Discover PDFs on jurisdiction homepages → veraPDF validate → Postgres bronze.
#
# Examples:
#   ./packages/accessibility/src/accessibility/run_verapdf_scan.sh --state AL
#   VERAPDF_FLAVOURS=ua1,ua2 ./packages/accessibility/src/accessibility/run_verapdf_scan.sh --limit 100
#   ./packages/accessibility/src/accessibility/run_verapdf_scan.sh --manifest data/cache/accessibility/pdf-urls.json --skip-discover
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
ROOT="$SCRIPT_DIR"
while [[ "$ROOT" != "/" && ! -f "$ROOT/packages/accessibility/src/accessibility/export_pdf_urls.py" ]]; do
  ROOT="$(dirname "$ROOT")"
done
cd "$ROOT"

STATE=""
LIMIT=""
OFFSET=0
BATCH_ID=""
MAX_PDFS=3
SKIP_DISCOVER=0
SKIP_PERSIST=0
MANIFEST="${ROOT}/data/cache/accessibility/pdf-urls.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --state) STATE="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --offset) OFFSET="$2"; shift 2 ;;
    --batch-id) BATCH_ID="$2"; shift 2 ;;
    --max-pdfs-per-site) MAX_PDFS="$2"; shift 2 ;;
    --manifest) MANIFEST="$2"; shift 2 ;;
    --skip-discover) SKIP_DISCOVER=1; shift ;;
    --skip-persist) SKIP_PERSIST=1; shift ;;
    -h|--help)
      grep '^#' "$0" | head -20
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3)"
fi

if [[ "$SKIP_DISCOVER" -eq 0 ]]; then
  DISC_ARGS=( -m accessibility.export_pdf_urls --out "$MANIFEST" --max-pdfs-per-site "$MAX_PDFS" )
  [[ -n "$STATE" ]] && DISC_ARGS+=( --state "$STATE" )
  [[ -n "$LIMIT" ]] && DISC_ARGS+=( --limit "$LIMIT" )
  [[ "$OFFSET" -gt 0 ]] && DISC_ARGS+=( --offset "$OFFSET" )
  [[ -n "$BATCH_ID" ]] && DISC_ARGS+=( --batch-id "$BATCH_ID" )
  "$PY" "${DISC_ARGS[@]}"
fi

BATCH_ID="${BATCH_ID:-$("$PY" -c "import json;print(json.load(open('$MANIFEST')).get('batch_id',''))" 2>/dev/null || true)}"
OUT="${ROOT}/data/cache/accessibility/verapdf-${BATCH_ID:-run}.ndjson"

SCAN_ARGS=( -m accessibility.run_verapdf_scan --manifest "$MANIFEST" --out "$OUT" )
[[ -n "$LIMIT" ]] && SCAN_ARGS+=( --limit "$LIMIT" )
[[ "$OFFSET" -gt 0 ]] && SCAN_ARGS+=( --offset "$OFFSET" )
"$PY" "${SCAN_ARGS[@]}"

if [[ "$SKIP_PERSIST" -eq 0 ]]; then
  "$PY" -m accessibility.persist_verapdf_results --input "$OUT" --ensure-ddl
fi

echo "Done. Results: $OUT"
