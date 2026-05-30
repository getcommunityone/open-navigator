# National Association of Counties (NACo) Data Source

Source organization for county-level data from the **National Association of Counties**.

## 📊 Data Source

- **Website:** https://www.naco.org/
- **County Explorer:** https://ce.naco.org/
- **Coverage:** 3,069 counties across all U.S. states and territories

## 🎯 Purpose

Enrich county jurisdiction records with:
- County official directories (commissioners, managers, clerks)
- Contact information (emails, phone numbers)
- County government websites
- County services and departments
- Demographic and economic data

## 📁 Scripts

- `scrape_naco_counties.py` - Scrape county data from NACo County Explorer

## 🚀 Usage

**Use the project virtualenv** so `httpx`, `psycopg2-binary`, etc. are available (system `python3` often has none of them):

```bash
cd /path/to/open-navigator
./.venv/bin/python scripts/datasources/naco/scrape_naco_counties.py --states AL,GA,MA
./.venv/bin/python scripts/datasources/naco/load_naco_to_bronze.py --states AL,GA,MA
```

If `.venv` does not exist yet: `python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt`

With plain `python3`, install deps first: `pip install -r requirements.txt` (or `pip install --user httpx psycopg2-binary python-dotenv loguru`).

**Do not paste log output into the shell** (lines starting with dates, `INFO`, `__main__`, etc.); the shell will try to run them as commands and you will see `command not found` / `syntax error`. Only paste **actual shell commands**.

Scripts will **automatically re-run using `./.venv/bin/python`** once if your `python3` lacks packages but the project venv exists and differs from the current interpreter.

### Database URL (same as other loaders)

Connection strings are resolved by `core_lib.db.resolve_target_database_url`, in order:

1. **`OPEN_NAVIGATOR_DATABASE_URL`** — explicit override (any host/port)
2. **`NEON_DATABASE_URL_DEV`** — typical local / cloud dev (team convention)
3. **`NEON_DATABASE_URL`**
4. **Default** — `localhost:5433/open_navigator` (password `POSTGRES_PASSWORD` or `password`)

If your log shows **5432** but you expected the Docker mapping on **5433**, check whether `OPEN_NAVIGATOR_DATABASE_URL` or a Neon URL in `.env` points at `:5432`, or fix the URL you use for local dev.

```bash
# Scrape all dev states
python3 scripts/datasources/naco/scrape_naco_counties.py --states AL,GA,IN,MA,WA,WI

# Dry run (preview without updating)
python3 scripts/datasources/naco/scrape_naco_counties.py --states MA --dry-run

# Scrape specific state
python3 scripts/datasources/naco/scrape_naco_counties.py --states WA
```

## 📋 Data Fields

- **County officials:** Names, titles, contact info
- **Contact information:** Official emails, phone numbers
- **Websites:** County government portals
- **Services:** List of county services and departments
- **Demographics:** Population, area, economic indicators

## 🔄 Type of Load

**ENRICHMENT/UPDATE LOAD** - Updates existing county records in `jurisdictions_details_search`

## ⚠️ Notes

- Respects robots.txt and rate limits
- Caches results to avoid duplicate requests
- May require authentication or membership for full access to some data
- Check NACo terms of service before large-scale scraping
