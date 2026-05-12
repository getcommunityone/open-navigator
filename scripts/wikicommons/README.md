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

From the **repository root**:

```bash
chmod +x scripts/wikicommons/download_wikicommons_assets.sh   # once
./scripts/wikicommons/download_wikicommons_assets.sh
```

Options:

```text
--out-dir PATH   Output directory (default: data/cache/wikicommons)
--sleep SECONDS  Delay between requests (default: 0.85)
--only AL TX …   Limit to these USPS codes (handy for testing)
--skip-flags     Only license plates
--skip-plates    Only state flags
```

Requirements: **Python 3** stdlib only (`urllib`).

The former `scripts/state_symbols/` flow (State Symbols USA) has been **removed**; all assets here are Commons-only.
