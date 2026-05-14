# Vendor meeting portal search

Script: `vendor_meeting_portal_search.py`  
Writes: `data/cache/vendorsearch/_manifest.json` and `data/cache/vendorsearch/hits.jsonl`

This tool runs **DuckDuckGo-style metasearch** (`ddgs`, same as the jurisdiction website enrichment script) to collect **raw URL candidates** on CivicPlus, Legistar, Granicus, PrimeGov, and Swagit. It does **not** download official vendor client lists; hits are for manual or downstream triangulation.

---

## The three `--mode` options

These control **which search queries** run, not a different API.

### 1. `global` (default)

**What it does:** Runs a **fixed set of nationwide queries**—mostly `site:civicplus.com`, `site:legistar.com`, `site:granicus.com`, etc.—plus a few vendor-agnostic phrases.

**When to use:** Quick pass to surface many example portals and common URL shapes in one short run (on the order of **16** search requests if `--vendor all`).

**Tradeoff:** Strong for “big” sites that rank well everywhere; weaker for a small county that only shows up when the query mentions **that state or region**.

---

### 2. `per-state`

**What it does:** For **each USPS code** (default: all **50 states + DC**), runs **10** tailored queries that embed the full state name, for example:

- “Texas county … site:legistar.com”
- “Texas city council … site:civicplus.com”
- “Texas state legislature … site:legistar.com”
- …and similar rows for Granicus, PrimeGov, Swagit, and state-level CivicPlus.

So the search engine gets **geographic context**, which often surfaces different hits than the global pass.

**When to use:** Building coverage **by state**, or when global mode missed jurisdictions you care about.

**Tradeoff:** Many more requests. With `--vendor all` and all states, that is about **51 × 10 ≈ 510** searches before deduplication—use **`--states TX,CA`** while developing, and a comfortable **`--sleep`** (seconds between queries) to stay polite.

---

### 3. `both`

**What it does:** Runs **`global` first**, then **all `per-state` tasks** (for the states you selected—default still all 51).

**When to use:** One batch job where you want **maximum recall**: broad vendor-wide hits **plus** state-scoped hits.

**Tradeoff:** Highest runtime and the most metasearch traffic; prefer **`--states`** or **`--vendor`** to narrow scope.

---

## Other useful flags (short)

| Flag | Purpose |
|------|--------|
| `--vendor` | Limit to one family, e.g. `legistar`, `civicplus`, `primegov` (Legistar and Granicus share one query set in the script). |
| `--states` | Comma-separated USPS codes; only affects **`per-state`** and **`both`** (which states get the 10-query loop). |
| `--max-results` | Cap hits returned **per** search query. |
| `--sleep` | Seconds to wait **after** each query (reduces rate-limit / blocking risk). |
| `--out-dir` | Alternate output directory instead of `data/cache/vendorsearch/`. |

---

## Examples

```bash
# Understand the tool: one cheap run
.venv/bin/python scripts/datasources/vendorsearch/vendor_meeting_portal_search.py --mode global

# Per-state, only a few states
.venv/bin/python scripts/datasources/vendorsearch/vendor_meeting_portal_search.py --mode per-state --states VT,IA --sleep 2.5

# Only Legistar/Granicus family, global queries
.venv/bin/python scripts/datasources/vendorsearch/vendor_meeting_portal_search.py --mode global --vendor legistar
```

---

## Reading the output

- **`hits.jsonl`**: Each line is JSON. `kind` is usually `hit` (a search result); sometimes `query_error` if a query failed. `vendor_inferred_from_url` is a **hostname guess**, not a verified product classification.
- **`_manifest.json`**: Run metadata: mode, vendor filter, `task_count`, and row counts.
