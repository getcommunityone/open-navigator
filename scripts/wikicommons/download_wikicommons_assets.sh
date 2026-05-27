#!/usr/bin/env bash
# Download Wikimedia Commons reference assets into data/cache/wikicommons/.
# SVG state flags as {USPS}_colors_hero.svg and U.S. license plates by state/year (+ _latest).
# See scripts/wikicommons/README.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
# Ported to packages/ingestion (BaseAsyncClient). Run the module form.
exec python3 -m ingestion.wikicommons.download "$@"
