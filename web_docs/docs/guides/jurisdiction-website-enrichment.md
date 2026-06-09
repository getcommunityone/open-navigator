---
title: Jurisdiction Website Enrichment
---

# Jurisdiction website enrichment (free search + dbt overrides)

This flow fills gaps in **`intermediate.int_jurisdiction_websites`** for counties whose **meetings scrape** was empty, shallow, or never run, using **DuckDuckGo text search** (no API key) plus **HTTP validation**. Curated URLs are written to the dbt seed **`jurisdiction_website_url_overrides.csv`**, which already wins first in URL priority when you rebuild **`int_jurisdiction_websites`**.

## Script

```text
scripts/enrichment/enrich_jurisdiction_websites_search.py
```

### Jurisdiction types (`--jurisdiction-type`)

- **`county`** (default): reads `data/cache/scraped_meetings/{STATE}/county/county_{GEOID}/`; **missing** in AL still uses the static 67-county FIPS list.
- **`municipality`**: `{STATE}/municipality/municipality_{7-digit place GEOID}/` (same layout as the meetings scraper).
- **`school_district`**: `{STATE}/school_district/school_district_{7-digit NCES GEOID}/`.

For **missing** cities or school districts (any state), targets are **`int_jurisdictions` GEOIDs minus folders on disk** (Postgres required).

### What it does

1. Picks GEOIDs from the local meetings cache (`failed` / `shallow` / `missing`) and optional `--geoids`, scoped by `--jurisdiction-type`.
2. Loads **`intermediate.int_jurisdictions`** names from Postgres.
3. Runs **metasearch** via the **`ddgs`** package (DuckDuckGo and other backends) for an official-site style query (with light **`-site:`** clauses to down-rank census / IRS / federal courts in the query itself).
4. Ranks **`.gov` / `.org`** hits: drops obvious junk hosts, **penalizes** census, courts, state revenue/tax portals, CDC/IRS/USA.gov-style hosts, and boosts hosts/titles that look like **county vs city vs school** as requested.
5. **`httpx` HEAD** (GET fallback on `405`/`501`) on several top-ranked URLs (up to **`--max-signal-fetches`**), then **GET**s those homepages (unless **`--no-fetch-page-signals`**) and scores visible text for **jurisdiction name**, **state**, optional **ZIP** from `int_jurisdictions`, and a simple **street-address** pattern. Picks the **best combined** DDG + page score, not the first hit. Weak matches stay **`manual_review=true`** (and are not seed-appended).
6. Optional **`--fetch-contact-hint`**: reuses the same homepage HTML when possible, or GETs once, for **title + first mailto** (audit only).
7. Optional **YouTube Data API v3** search when **`YOUTUBE_DATA_API_KEY`** is set — stores top video id/title in the **CSV** for manual review (not inserted into dbt).

### Outputs

- **CSV** (default): `data/cache/enrichment/jurisdiction_website_enrichment_{state}_{jurisdiction_type}_{timestamp}.csv`  
  Columns include `relevance_scores` (DDG + page breakdown), `manual_review`, `validation_detail`, `youtube_*`, and `notes` for a **manual review queue** when automation did not find a confident match.

- **`--apply-seed`**: appends high-confidence rows (`manual_review=false` after locality checks, HTTP ok) to  
  `dbt_project/seeds/jurisdiction_website_url_overrides.csv`.

- **`--skip-existing-seed`**: skip GEOIDs already listed in that seed for the active jurisdiction prefix.

- **`--no-fetch-page-signals`**: faster path — first HEAD-ok candidate in DDG rank order wins (old behavior).

- **`--max-signal-fetches`**: cap how many HEAD-ok URLs receive a homepage GET for scoring (default 5).

### Examples

Dry-run (no seed writes):

```bash
cd /path/to/open-navigator
source .venv/bin/activate
pip install -r requirements.txt

python scripts/enrichment/enrich_jurisdiction_websites_search.py \
  --state AL --dry-run --sleep 2.5
```

Use SOCKS proxy (see below) and append validated URLs to the dbt seed:

```bash
export WIKIDATA_HTTPS_PROXY=socks5h://127.0.0.1:9091
python scripts/enrichment/enrich_jurisdiction_websites_search.py \
  --state AL --apply-seed --skip-existing-seed --fetch-contact-hint
```

Only specific GEOIDs (still merges with `--mode` unless you pass `--mode` empty — use only geoids by setting modes that add nothing is awkward; simplest is):

```bash
python scripts/enrichment/enrich_jurisdiction_websites_search.py \
  --state AL --mode failed --geoids 01011,01127
```

### After `--apply-seed`

Rebuild the intermediate table so meetings discovery sees new URLs:

```bash
cd dbt_project
dbt seed --select jurisdiction_website_url_overrides
dbt run --select int_jurisdiction_websites
```

Then re-run meetings scrape (`--from-db` / `--geoids` as you do today).

---

## SOCKS proxy on `127.0.0.1:9091` (optional)

DuckDuckGo and some county CDNs rate-limit or block datacenter IPs. The repo already uses **`WIKIDATA_HTTPS_PROXY`** for Wikidata loaders; the enrichment script reuses it for **DDG + httpx**.

Use a scheme **`socks5h://`** when you want **DNS to resolve through the proxy** (recommended for Tor-style setups).

### Check the proxy is up

```bash
curl --socks5-hostname 127.0.0.1:9091 -sI -m 15 https://www.duckduckgo.com/ | head -5
```

If this hangs or errors, the scraper will not get a working proxy either.

### Option A — SSH dynamic SOCKS (no Docker)

If you have any SSH host with outbound web:

```bash
ssh -N -D 9091 you@your-bastion.example
export WIKIDATA_HTTPS_PROXY=socks5h://127.0.0.1:9091
```

Leave that terminal open while you run enrichment.

### Option B — Tor in Docker (example)

**Tor exposes SOCKS on port 9050 inside the container.** Map host **9091 → 9050** so it matches a typical `.env` line `socks5://127.0.0.1:9091`.

Example `docker-compose` snippet (save as `docker-compose.socks-proxy.example.yml` next to your clone and adjust):

```yaml
services:
  tor-socks:
    image: dperson/torproxy
    restart: unless-stopped
    ports:
      - "9091:9050"
```

Start and verify:

```bash
docker compose -f docker-compose.socks-proxy.example.yml up -d
docker compose -f docker-compose.socks-proxy.example.yml ps
curl --socks5-hostname 127.0.0.1:9091 -sI -m 20 https://check.torproject.org/ | head -3
```

Stop:

```bash
docker compose -f docker-compose.socks-proxy.example.yml down
```

> **Note:** Tor exit nodes are often blocked by government sites. If DDG or county sites fail through Tor, prefer **SSH `-D`**, a **residential** SOCKS, or run enrichment from a network that is not heavily blocked.

### Option C — Your existing “Wikidata” SOCKS container

If you already run a sidecar on **`127.0.0.1:9091`**, set in `.env`:

```bash
WIKIDATA_HTTPS_PROXY=socks5h://127.0.0.1:9091
```

and ensure the container is healthy (`docker ps`, port publish `9091:...`, and the `curl` test above).

---

## YouTube (optional, free quota)

Set **`YOUTUBE_DATA_API_KEY`** (Google Cloud console, YouTube Data API v3 enabled). The script logs a **top search hit** per county into the CSV for context; it does **not** write to Postgres by itself.

---

## Limitations

- DuckDuckGo HTML results can change; **false positives** (wrong `.org`) are possible — use the CSV **`manual_review`** column and your judgment before `--apply-seed`.
- Respect **`--sleep`**; bulk runs without delay may get throttled.
- **`missing`** mode is implemented for **AL** (67 FIPS list). Other states: use **`--geoids`** or extend the script.
