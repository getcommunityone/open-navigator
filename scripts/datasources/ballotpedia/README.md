# Ballotpedia Data Scripts

Scripts for scraping Ballotpedia ballot measures and loading them into bronze.

## Scripts

| Script | Purpose |
|--------|---------|
| `ballotpedia_integration.py` | Core scraper (`BallotpediaDiscovery`) — officials, ballot measures, external links |
| `download_ballotpedia_measures.py` | Bulk-scrape state + jurisdiction ballot-measure pages → JSON cache |
| `load_ballotpedia_measures_to_bronze.py` | Load cache JSON → `bronze.bronze_ballotpedia_measures` |

## Quick start

```bash
# Scrape (httpx first; Playwright fallback on challenge pages)
python scripts/datasources/ballotpedia/download_ballotpedia_measures.py --states AL,GA --year 2024

# Include per-city ballot-measure pages (requires NEON_DATABASE_URL_DEV)
python scripts/datasources/ballotpedia/download_ballotpedia_measures.py \
    --states AL --include-jurisdictions --limit-per-state 10

# Load into Postgres bronze
python scripts/datasources/ballotpedia/load_ballotpedia_measures_to_bronze.py --truncate

# Apply DDL (Neon)
./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/057_create_bronze_ballotpedia_measures.sql
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `BALLOTPEDIA_PLAYWRIGHT_ONLY` | `0` | Skip httpx; use Playwright for every request |
| `BALLOTPEDIA_USE_PLAYWRIGHT` | `1` | Enable Playwright fallback on challenge pages |
| `BALLOTPEDIA_PLAYWRIGHT_HEADLESS_MODE` | `new` | `new`, `legacy`, or `headed` |
| `BALLOTPEDIA_INTER_REQUEST_DELAY` | `2.0` | Seconds between httpx requests |
| `BALLOTPEDIA_PLAYWRIGHT_CONTENT_RETRIES` | `3` | Reload attempts when article body is empty |

If headless scrapes keep failing, try headed mode:

```bash
BALLOTPEDIA_PLAYWRIGHT_HEADLESS_MODE=headed \
  python scripts/datasources/ballotpedia/download_ballotpedia_measures.py --states AL
```

## Troubleshooting `challenge_blocked` / HTTP 202

Ballotpedia often returns **HTTP 202** to plain httpx requests (Cloudflare). The scraper should escalate to Playwright automatically. If you see `reason=challenge_blocked` with `statuses=[202,202,202,202]`:

1. **Install Chromium** (most common fix when `artifacts=[]`):
   ```bash
   ./.venv/bin/playwright install chromium
   ```

2. **Skip useless httpx retries** — go straight to Playwright:
   ```bash
   BALLOTPEDIA_PLAYWRIGHT_ONLY=1 \
     ./.venv/bin/python scripts/datasources/ballotpedia/download_ballotpedia_measures.py
   ```

3. **Rate limiting** — wait 10–15 minutes between bulk runs, or increase delay between states:
   ```bash
   BALLOTPEDIA_STATE_DELAY=30 \
     ./.venv/bin/python scripts/datasources/ballotpedia/download_ballotpedia_measures.py
   ```

4. **WSL / headless blocks** — use headed mode with a display, or system Chrome:
   ```bash
   BALLOTPEDIA_PLAYWRIGHT_CHANNEL=chrome BALLOTPEDIA_PLAYWRIGHT_HEADLESS_MODE=headed \
     ./.venv/bin/python scripts/datasources/ballotpedia/download_ballotpedia_measures.py --states AL
   ```

5. **Inspect failures** — check `data/cache/ballotpedia/playwright_debug/*.html` and the matching `fetch_debug/*.json` (the `error` field now includes the Playwright exception when present).

## Cache layout

```
data/cache/ballotpedia/
  AL/state/state_ballot_measures_2024_20260524T120000Z.json
  AL/municipality/municipality_0177256_ballot_measures_20260524T120000Z.json
```

## Related

- External links: `bronze.bronze_ballotpedia_external_links` (migration 055), loaded via Google Civic path
- OCD election shape: `bronze.bronze_elections_scraped` (migration 047)
- dbt: `dbt_project/models/bronze/bronze_ballot_measures_nist.sql` unions this table with VIP + AI sources
