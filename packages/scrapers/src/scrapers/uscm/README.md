# U.S. Conference of Mayors (USCM) Data Source

Official organization representing cities with populations of 30,000+.

## 📊 Data Source

- **Website:** https://www.usmayors.org/
- **Election Results:** https://www.usmayors.org/elections/election-results-2/
- **Meet the Mayors (directory):** https://www.usmayors.org/mayors/meet-the-mayors/
- **Coverage:** 1,400+ cities with mayors
- **Update Frequency:** Ongoing as elections occur

## 🎯 Purpose

Track current and incoming mayors for U.S. cities:
- Mayor names
- Election dates
- Election winners and candidates
- Cities with upcoming elections

## 📁 Scripts

- `scrape_mayor_elections.py` — **archived** (`archive/datasources/uscm/`): wrote mayor data to the dropped `c1_jurisdiction` columns (`current_mayor`, …) post migration 048. Use the Meet the Mayors → bronze path below instead.
- `download_uscm_mayors.py` — download the Meet the Mayors directory by state (POST search); writes `data/cache/uscm/meet_the_mayors_us_YYYYMMDD.json`
- `load_uscm_mayors_to_bronze.py` — load that JSON into `bronze.bronze_jurisdictions_municipalities_uscm`
- `state_names.py` — USPS → full state name (required by the Meet the Mayors search form)
- `add_mayor_columns.sql` — add mayor-related columns to legacy tables

### Meet the Mayors → bronze

```bash
./.venv/bin/python packages/scrapers/src/scrapers/uscm/download_uscm_mayors.py
./.venv/bin/python packages/scrapers/src/scrapers/uscm/load_uscm_mayors_to_bronze.py
# Optional: ./.venv/bin/python packages/scrapers/src/scrapers/uscm/load_uscm_mayors_to_bronze.py --truncate
```

If you already had data in `bronze.bronze_jurisdictions_municipalities_mayors`, apply `packages/hosting/scripts/neon/migrations/016_rename_bronze_jurisdictions_municipalities_uscm.sql` once before relying on the new table name.

## 🚀 Usage

### First Time Setup

```bash
# Add database columns
psql -h localhost -p 5433 -U postgres -d open_navigator -f add_mayor_columns.sql
```

### Scrape Mayor Data

```bash
# Scrape all cities
python scrape_mayor_elections.py

# Dry run (preview without updating)
python scrape_mayor_elections.py --dry-run

# Filter to specific states
python scrape_mayor_elections.py --states AL,GA,IN,MA,WA,WI
```

## 📋 Data Fields

New columns added to `jurisdictions_details_search`:

- **current_mayor** (VARCHAR) - Name of current or incoming mayor
- **mayor_election_date** (DATE) - Date of most recent election
- **usmayors_last_updated** (TIMESTAMP) - Last update from USCM

## 🔄 Type of Load

**ENRICHMENT LOAD** - Updates existing city records with mayor information

## 📊 Example Data

```json
{
  "city": "Boston",
  "state": "Massachusetts",
  "population": 675647,
  "current_mayor": "Michelle Wu",
  "mayor_election_date": "2025-11-02",
  "source": "U.S. Conference of Mayors"
}
```

## 🎯 Coverage

- **Target Audience:** Cities with 30,000+ population
- **Membership:** ~1,400 U.S. cities
- **Election Tracking:** Ongoing (updates throughout the year)
- **Historical Data:** Also available for past years

## 🔗 Related Sources

- **National League of Cities (NLC)** - Broader city official data
- **Ballotpedia** - Comprehensive election results
- **WikiData** - Government official metadata

## ⚠️ Notes

- USCM represents ~1,400 larger cities (30,000+ population)
- Not all cities have direct mayoral elections (some council-appointed)
- Election results are listed chronologically by date
- Some upcoming elections may not have winners yet
- Mayor names marked in **bold** indicate newly elected mayors

## 📝 Data Quality

- **Source Authority:** Official organization of mayors
- **Accuracy:** High - directly reported by cities
- **Timeliness:** Updated as elections occur
- **Completeness:** Covers member cities only (~1,400 out of ~19,000+ cities)
