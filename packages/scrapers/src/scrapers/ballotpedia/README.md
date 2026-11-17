# Ballotpedia Data Scripts

Scripts for scraping Ballotpedia ballot measures and loading them into bronze.

## Scripts

| Script | Purpose |
|--------|---------|
| `ballotpedia_integration.py` | Core scraper (`BallotpediaDiscovery`) — officials, ballot measures, external links |
| `download_ballotpedia_measures.py` | Bulk-scrape state + jurisdiction ballot-measure pages → JSON cache |
| `load_ballotpedia_measures_to_bronze.py` | Load cache JSON → `bronze.bronze_ballot_measures_ballotpedia` |

## Quick start

```bash
# Scrape (defaults: 6 priority states × 2025 + 2026)
python packages/scrapers/src/scrapers/ballotpedia/download_ballotpedia_measures.py

# Load bronze (defaults: election years 2025, 2026 only)
python packages/scrapers/src/scrapers/ballotpedia/load_ballotpedia_measures_to_bronze.py --truncate

# Apply DDL (Neon)
./packages/hosting/scripts/neon/psql_resolved.sh -f packages/hosting/scripts/neon/migrations/057_create_bronze_ballot_measures_ballotpedia.sql
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `BALLOTPEDIA_PLAYWRIGHT_ONLY` | `1` | Fetch with a plain Playwright browser (default). Set `0` to use httpx instead |
| `BALLOTPEDIA_PLAYWRIGHT_HEADLESS_MODE` | `new` | `new`, `legacy`, or `headed` (headed is for local debugging) |
| `BALLOTPEDIA_INTER_REQUEST_DELAY` | `2.0` | Seconds between httpx requests |

## Blocked pages

The browser is a plain, honest browser: no `playwright-stealth`, no fingerprint spoofing, no
rotating user agents or IPs (decision recorded on issue #443, 2026-11-16). When Ballotpedia answers
with HTTP 202 / 403 / 429 or a challenge page, the fetch is logged as `reason=blocked`, a report is
written to `data/cache/ballotpedia/fetch_debug/*.json`, and the scraper moves on. It does not
reload to wait out the challenge or retry the page through httpx. If you need Ballotpedia data at
volume, ask Ballotpedia for access instead.

If every request fails with `artifacts=[]`, Chromium is probably missing:

```bash
./.venv/bin/playwright install chromium
```

## Cache layout

```
data/cache/ballotpedia/
  AL/state/state_ballot_measures_2024_20260524T120000Z.json
  AL/municipality/municipality_0177256_ballot_measures_20260524T120000Z.json
```

## Related

- External links: `bronze.bronze_websites_ballotpedia` (migration 055), loaded via Google Civic path
- OCD election shape: `bronze.bronze_elections_scraped` (migration 047)
- dbt: `dbt_project/models/bronze/bronze_ballot_measures_nist.sql` unions this table with VIP + AI sources
