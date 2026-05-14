# eBoard Platform Manual Download Guide

## Issue: Incapsula Bot Protection

eBoard Solutions (https://simbli.eboardsolutions.com) uses **Incapsula** anti-bot protection that blocks automated scraping, even with advanced tools like Playwright. The platform requires manual interaction to access meeting documents.

## Affected School Districts

| District (AL) | `jurisdiction_id` | Public hub / board page | Simbli agendas & minutes |
| --- | --- | --- | --- |
| **Tuscaloosa City School District** | `school_district_0103360` | [Board of Education](https://www.tuscaloosacityschools.com/about-us/board-of-education) (Finalsite) | [Simbli meeting listing `S=2088`](https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=2088) · [index `s=2088`](https://simbli.eboardsolutions.com/index.aspx?s=2088) |
| **Tuscaloosa County School District (TCSS)** | `school_district_0103390` | [Board of Education](https://www.tcss.net/board-of-education) (Finalsite; links to Simbli) | [Simbli meeting listing `S=2092`](https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=2092) · [index `s=2092`](https://simbli.eboardsolutions.com/index.aspx?s=2092) |

Seed overrides for the Tuscaloosa **city** (`school_district_0103360`) and **county** (`school_district_0103390`) board hubs + Simbli URLs live in [`dbt_project/seeds/jurisdiction_website_url_overrides.csv`](../../dbt_project/seeds/jurisdiction_website_url_overrides.csv). NCES only carries the district homepage, so **`%simbli%` rows appear only after these seeds** are loaded. Reload with `dbt seed --select jurisdiction_website_url_overrides` then `dbt run --select int_jurisdiction_websites` (see [Query from Postgres](#query-from-postgres)).

## Query from Postgres

After `dbt seed` and `dbt run --select int_jurisdiction_websites`, URLs (including overrides) are in **`intermediate.int_jurisdiction_websites`** — not necessarily under `public` (see comment in `dbt_project/models/intermediate/int_jurisdiction_websites.sql`).

**If a Simbli filter returns zero rows:** confirm the seed is loaded (`SELECT * FROM seeds.jurisdiction_website_url_overrides WHERE jurisdiction_id = 'school_district_0103360'`), then re-run `dbt seed` and `dbt run --select int_jurisdiction_websites`. List every URL for the district with `SELECT website_source, website_url FROM intermediate.int_jurisdiction_websites WHERE jurisdiction_id = 'school_district_0103360' ORDER BY website_source, website_url` — you should see `website_source = override` rows including Simbli after a successful rebuild.

**If you only see `nces_directory` and no `override` rows:** dbt was probably using **`~/.dbt/profiles.yml`** (wrong DB) while your SQL client uses Neon. From the repo root run **`export DBT_PROFILES_DIR="$(pwd)/dbt_project"`** before `dbt seed` / `dbt run`, or use **`./scripts/dbt-root.sh`** / **`./scripts/dbt.sh`** so `dbt_project/profiles.yml` (same host as Neon) is used.

**Tuscaloosa County School District (`school_district_0103390`) — hub + Simbli:**

```sql
SELECT
  jurisdiction_id,
  organization_name,
  website_source,
  website_url
FROM intermediate.int_jurisdiction_websites
WHERE jurisdiction_id = 'school_district_0103390'
  AND (
    website_url ILIKE '%tcss.net%'
    OR website_url ILIKE '%simbli.eboardsolutions.com%'
  )
ORDER BY website_url;
```

**Tuscaloosa City School District (`school_district_0103360`) — board hub + Simbli:**

```sql
SELECT
  jurisdiction_id,
  organization_name,
  website_source,
  website_url
FROM intermediate.int_jurisdiction_websites
WHERE jurisdiction_id = 'school_district_0103360'
  AND (
    website_url ILIKE '%tuscaloosacityschools.com%'
    OR website_url ILIKE '%simbli.eboardsolutions.com%'
  )
ORDER BY website_url;
```

**Simbli URLs only (Tuscaloosa City)** — use `trim` and match the meeting-listing path (not only the substring `simbli`, which is easy to typo-filter):

```sql
SELECT
  jurisdiction_id,
  organization_name,
  website_source,
  trim(website_url) AS website_url
FROM intermediate.int_jurisdiction_websites
WHERE jurisdiction_id = 'school_district_0103360'
  AND (
    trim(website_url) ILIKE '%simbli%'
    OR trim(website_url) ILIKE '%SB_MeetingListing.aspx%'
    OR trim(website_url) ILIKE '%/SB_Meetings/%'
  )
ORDER BY website_url;
```

If this still returns no rows, the Simbli row is not in `intermediate` yet — check `seeds.jurisdiction_website_url_overrides` for `school_district_0103360`, then `dbt seed` + `dbt run --select int_jurisdiction_websites`.

**All websites for either district (debug):**

```sql
SELECT jurisdiction_id, organization_name, website_source, website_url
FROM intermediate.int_jurisdiction_websites
WHERE jurisdiction_id IN ('school_district_0103360', 'school_district_0103390')
ORDER BY jurisdiction_id, website_url;
```

**Raw seed rows:**

```sql
SELECT jurisdiction_id, website_url
FROM seeds.jurisdiction_website_url_overrides
WHERE jurisdiction_id IN ('school_district_0103360', 'school_district_0103390')
ORDER BY jurisdiction_id, website_url;
```

## Manual Download Steps

### 1. Access Meeting Listings
1. Visit the meetings URL above in your browser
2. You'll see a calendar or list of board meetings
3. Each meeting shows the date and has document links

### 2. Download Documents
For each meeting:
- Click on the meeting date to view details
- Look for:
  - **Agenda** (usually PDF)
  - **Minutes** (usually PDF)
  - **Packets** (supporting materials)
- Right-click each document → "Save As"

### 3. Organize Downloads
Save files with naming pattern:
```
tuscaloosa_city_schools_YYYY-MM-DD_agenda.pdf
tuscaloosa_city_schools_YYYY-MM-DD_minutes.pdf
```

### 4. Import into System

Once downloaded, you can import them manually:

```python
from pipeline.delta_lake import DeltaLakePipeline
from agents.scraper import ScraperAgent
import asyncio

async def import_manual_pdfs(pdf_directory: str):
    """Import manually downloaded PDFs into the system."""
    scraper = ScraperAgent()
    async with scraper:
        documents = []
        
        for pdf_path in Path(pdf_directory).glob("*.pdf"):
            # Extract content from PDF
            content = await scraper._scrape_pdf_document(str(pdf_path))
            
            if content:
                # Parse filename for metadata
                parts = pdf_path.stem.split('_')
                date_str = parts[2] if len(parts) > 2 else ""
                doc_type = parts[3] if len(parts) > 3 else "document"
                
                doc = {
                    'document_id': hashlib.md5(str(pdf_path).encode()).hexdigest(),
                    'source_url': f'file://{pdf_path}',
                    'municipality': 'Tuscaloosa City Schools',
                    'state': 'AL',
                    'meeting_date': date_str,
                    'meeting_type': 'Board Meeting',
                    'title': pdf_path.stem,
                    'content': content,
                    'metadata': {'source': 'manual_download', 'platform': 'eboard'}
                }
                documents.append(doc)
        
        # Write to Delta Lake
        pipeline = DeltaLakePipeline()
        pipeline.write_raw_documents(documents)
        
        return documents

# Usage:
# asyncio.run(import_manual_pdfs('/path/to/downloaded/pdfs'))
```

## Alternative: RSS Feeds

Some eBoard installations offer RSS feeds or calendar exports:
1. Look for RSS icon on meetings page
2. Look for "Subscribe" or "Export to Calendar" options
3. These may bypass the web interface restrictions

## Future Enhancement Ideas

1. **Browser Extension**: Create a Chrome extension that scrapes while you browse
2. **API Discovery**: Research if eBoard has any undocumented APIs
3. **Selenium Grid**: Use residential proxy services for more sophisticated bot evasion
4. **Contact District**: Request bulk export of meeting documents directly

## Why Automation Fails

eBoard's Incapsula protection includes:
- Browser fingerprinting (detects headless browsers)
- IP reputation checking
- JavaScript challenges (requires full browser execution)
- Session tracking (blocks rapid sequential requests)
- Rate limiting per IP address

Even with Playwright running in visible mode, subsequent page navigations get blocked once the system detects automated patterns.

## Recommended Approach

For comprehensive school district data:
1. **Prioritize**: Focus on city government data (working well)
2. **Manual collection**: Download key school board meetings manually
3. **Selective import**: Import only the most relevant documents
4. **Direct contact**: Reach out to school district IT for data sharing agreement

## Status

- ✅ **Tuscaloosa City Government**: Automated scraping works (SuiteOne Media platform)
- ❌ **Tuscaloosa City Schools**: Manual download required (eBoard + Incapsula)
- ❌ **Tuscaloosa County Schools**: Manual download required (eBoard + Incapsula)
