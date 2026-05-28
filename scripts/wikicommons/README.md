# Wikimedia Commons (reference assets)

Scripts here download **attribution-friendly** imagery from [Wikimedia Commons](https://commons.wikimedia.org/) into `data/cache/wikicommons/` (gitignored).

## What gets cached

| Pattern | Role |
|--------|------|
| `{USPS}_colors_hero.svg` | State / territory **flag** (canonical `Flag of …` SVG from per-state “SVG flags of …” categories). |
| `{USPS}_{year}.{ext}` | **License plate** images from the U.S. by-state category tree (recursive). |
| `{USPS}_latest.{ext}` | Copy of the most recent plate (by parsed year, then upload time). |
| `_manifest.json` | URLs, Commons file pages, and notes. |

## Run

The downloader was ported to `packages/ingestion` on `core_lib.http.BaseAsyncClient`
(retries, rate limiting, structured logs). Run the module from the **repository root**:

```bash
python -m ingestion.wikicommons.download
# or the thin wrapper (now just exec's the module):
./scripts/wikicommons/download_wikicommons_assets.sh
```

Options:

```text
--only AL TX …   Limit to these USPS codes (handy for testing)
--skip-flags     Only license plates
--skip-plates    Only state flags
--force          Re-download even if a fresh cache exists (per-file freshness reuse otherwise)
```

Requirements: the `communityone-ingestion` package and its deps (`core-lib`, `httpx`).
Output: `data/cache/wikicommons/` (cache dir is fixed; per-file cache-freshness reuse).

The former `scripts/state_symbols/` flow (State Symbols USA) has been **removed**; all assets here are Commons-only.
