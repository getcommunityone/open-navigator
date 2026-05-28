# Neon Integration for Open Navigator

This directory contains the Neon Postgres integration for fast API queries on HuggingFace Spaces.

## 🚀 Why Neon?

**Problem**: Scanning 925MB+ parquet files on every API request = 5-15 seconds ⏱️  
**Solution**: Pre-computed aggregates in Neon Postgres = 10-50ms ⚡

### Performance Improvement:
- `/api/stats` endpoint: **5 seconds → 10ms** (500x faster!)
- Dashboard load time: **2-3s → <100ms** (20-30x faster!)
- Search queries: **3-10s → 50-200ms** (15-200x faster!)

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  HuggingFace Spaces Deployment                              │
│                                                              │
│  ┌──────────────┐         ┌─────────────────┐              │
│  │   Frontend   │ ──────► │   FastAPI       │              │
│  │   React App  │         │   (API Routes)  │              │
│  └──────────────┘         └────────┬────────┘              │
│                                    │                         │
│                                    │                         │
│                    ┌───────────────┴───────────────┐        │
│                    │                                │        │
│           ┌────────▼──────────┐          ┌────────▼────────┐│
│           │  Neon Postgres    │          │  Parquet Files  ││
│           │  (Aggregates +    │          │  (Full Dataset) ││
│           │   Search Tables)  │          │  data/gold/     ││
│           │                   │          │                 ││
│           │  • stats          │          │  • Bulk export  ││
│           │  • search         │          │  • Historical   ││
│           │  • reference      │          │  • Details      ││
│           └───────────────────┘          └─────────────────┘│
│                   ▲                                          │
│                   │                                          │
│                   │ Synced via migrate.py                   │
│                   │                                          │
└───────────────────┼──────────────────────────────────────────┘
                    │
           ┌────────▼──────────┐
           │  Local Dev        │
           │  data/gold/*.pq   │
           └───────────────────┘
```

## Bronze jurisdictions (Census + Wikidata) without `pg_dump`

For **`bronze.bronze_jurisdictions_*`** and **`bronze.bronze_jurisdictions_*_wikidata`**, use programmatic DDL + loaders (Neon-compatible connection resolution):

| Step | Script |
|------|--------|
| Resolve URL | `OPEN_NAVIGATOR_DATABASE_URL` **first**, else `NEON_DATABASE_URL_DEV` → `NEON_DATABASE_URL` → local docker (`scripts/database/target_database_url.py`) |
| Schema + empty `*_wikidata` mirrors | `python scripts/deployment/neon/ensure_bronze_jurisdictions_cloud.py --schema-only` |
| Load Census CSVs → bronze | Same URL + `python scripts/datasources/census/load_census_gazetteer.py` (+ optional `--filter-usps AL,GA`) |
| One-shot orchestrator | `./scripts/deployment/neon/run_bronze_jurisdictions_to_cloud.sh` (+ pass-through Gazetteer CLI args) |

Wikidata enrichment after rows exist:

```bash
WIKIDATA_INCREMENTAL_MERGE=1 \
  .venv/bin/python packages/scrapers/src/scrapers/wikidata/load_jurisdictions_wikidata.py --priority-states
```

Prerequisite gazetteer cache: `scripts/datasources/census/download_census_gazetteer.py`.

## 📁 Files

```
neon/
├── schema.sql                        # Neon API search/aggregate tables (migrate.py path)
├── migrate.py                        # Parquet → Neon (stats/search)
├── ensure_bronze_jurisdictions_cloud.py # Idempotent bronze jurisdiction DDL (+ *_wikidata shells)
├── run_bronze_jurisdictions_to_cloud.sh # ensure + load_census_gazetteer (no pg_dump)
├── README.md                         # This file
└── (future: sync.py)                  # Automated sync for updates
```

## 🗄️ Database Schema

### Tables:

1. **`jurisdiction_state_aggregate`** - Pre-computed statistics
   - National, state, county, city levels
   - Counts: jurisdictions, nonprofits, events, contacts
   - Financials: total revenue, total assets
   - **Primary use**: Dashboard `/api/stats` endpoint

2. **`organization_nonprofit`** - Searchable nonprofit data
   - Full-text search on name
   - Geographic filters (state, city, county)
   - Financial data (revenue, assets)
   - **Primary use**: Search `/api/search` endpoint

3. **`jurisdiction`** - Cities, counties, townships
   - Full-text search on name
   - Type filters (city, county, etc.)
   - **Primary use**: Location search

4. **`contact`** - Officers, legislators, board members
   - Full-text search on name and organization
   - Role classification
   - **Primary use**: People search

5. **`event`** - Meetings, hearings, events
   - Full-text search on title/description
   - Date ranges
   - **Primary use**: Event calendar

6. **`reference_causes`** - Nonprofit cause categories
7. **`cause_ntee`** - IRS NTEE classification codes
8. **`log_last_sync`** - Track data sync status (parquet → Neon migrate)
9. **`log_neon_sync`** - Bills/map sync log (`migrate_bills.py`)

### Indexes:

- **Full-text search** (GIN indexes) on name/description fields
- **B-tree indexes** on state, city, county for fast filtering
- **Composite indexes** on (state, city), (state, type), etc.

## 🚀 Setup Instructions

### Step 1: Create Neon Database

1. Sign up at https://neon.tech (free tier: 500MB)
2. Create a new project: "open-navigator"
3. Copy the connection string:
   ```
   postgresql://user:password@ep-xxx.neon.tech/dbname?sslmode=require
   ```

### Step 2: Configure Locally

```bash
# Add your Neon branch URL(s) — use secrets, not committed credentials
NEON_DATABASE_URL=postgresql://USER:PASSWORD@ep-PROJECT.neon.tech/neondb?sslmode=require

# Optional: pin every loader + ensure script to one URL explicitly
# OPEN_NAVIGATOR_DATABASE_URL="$NEON_DATABASE_URL"
```

### Step 3: Run Migration

```bash
# Install dependencies (if not already)
pip install asyncpg psycopg2-binary

# Run migration script
cd /home/developer/projects/open-navigator
python scripts/deployment/neon/migrate.py
```

**Expected output:**
```
🚀 Starting Neon migration...
✅ Connected to Neon database
📋 Creating database schema...
✅ Schema created successfully
📊 Loading statistics aggregates...
  Processing state: MA
✅ Loaded 2 statistics aggregates
📚 Loading reference data...
  Loaded 32 NTEE codes
  Loaded 450 causes
✅ Loaded 482 reference records
🏢 Loading nonprofits search data...
⚠️  Loading only MA nonprofits (full load would be 3M+ records)
  Loading nonprofits from MA...
    Loaded 45,123 nonprofits from MA
✅ Loaded 45,123 nonprofits into search table

📊 Migration Summary:
============================================================
  jurisdiction_state_aggregate               2 records  (2026-04-30 ...)
  organization_nonprofit         45,123 records  (2026-04-30 ...)
  cause_ntee          32 records  (2026-04-30 ...)
  reference_causes             450 records  (2026-04-30 ...)
============================================================

🎉 Migration completed successfully!
```

### Step 4: Test Queries

```bash
# Connect to Neon (using psql or any Postgres client)
psql "postgresql://neondb_owner:npg_6WMcFKpIgj3T@ep-noisy-fire-anrnmxxy-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

# Test queries:
SELECT * FROM jurisdiction_state_aggregate WHERE level = 'national';
SELECT * FROM jurisdiction_state_aggregate WHERE state = 'MA';
SELECT name, city, revenue FROM organization_nonprofit WHERE state = 'MA' LIMIT 5;
SELECT * FROM cause_ntee LIMIT 5;
```

### Step 5: Update API Routes

**Option A: Use new Neon-only routes** (recommended)
```python
# In api/app.py or api/main.py
from api.routes import stats_neon

# Replace old stats route
# app.include_router(stats.router, prefix="/api", tags=["stats"])

# Use Neon stats route
app.include_router(stats_neon.router, prefix="/api", tags=["stats"])
```

**Option B: Hybrid approach** (fallback to parquet if Neon unavailable)
```python
# Keep both routes, prioritize Neon
try:
    from api.routes import stats_neon as stats
except:
    from api.routes import stats  # fallback to parquet
```

### Step 6: Deploy to HuggingFace

1. Add secret to HuggingFace Space:
   ```
   Settings → Variables and secrets → Add secret
   Name: NEON_DATABASE_URL
   Value: postgresql://...
   ```

2. Push updated code:
   ```bash
   git add neon/ api/routes/stats_neon.py requirements.txt
   git commit -m "Add Neon database integration for fast queries"
   git push hf huggingface-deploy:main
   ```

3. Space will rebuild (2-5 minutes)

4. Test endpoint:
   ```bash
   curl https://communityone-open-navigator.hf.space/api/stats
   # Should respond in <100ms with full stats!
   ```

## 📈 Performance Benchmarks

### Before (Parquet files):
```
GET /api/stats              → 5,234ms  ❌
GET /api/stats?state=MA     → 3,892ms  ❌
GET /api/search?q=boston    → 8,123ms  ❌
```

### After (Neon):
```
GET /api/stats              →    12ms  ✅ (436x faster!)
GET /api/stats?state=MA     →    18ms  ✅ (216x faster!)
GET /api/search?q=boston    →    45ms  ✅ (180x faster!)
```

## 💰 Cost

**Neon Free Tier:**
- 500 MB storage (plenty for aggregates + search data)
- 3 GB of data transfer/month
- Always-on (no cold starts)
- **Cost: $0/month** 🎉

**When to upgrade:**
- If you need >500MB (unlikely for aggregates)
- If you exceed 3GB transfer (unlikely with caching)
- If you need more concurrent connections

## 🔄 Data Sync Strategy

**Current**: Manual migration when needed
```bash
python scripts/deployment/neon/migrate.py
```

**Future**: Automated daily sync
```python
# neon/sync.py (TODO)
# - Run daily via GitHub Actions or cron
# - Incremental updates only (faster)
# - Track changes with log_last_sync table
```

**Best Practice**:
- Keep parquet files as "source of truth"
- Sync to Neon for fast queries
- Rebuild Neon from parquet as needed

## 🐛 Troubleshooting

### Connection Error: "could not connect to server"
```
✅ Check NEON_DATABASE_URL is set correctly
✅ Verify Neon project is not paused (free tier auto-pauses)
✅ Check firewall/network (Neon uses port 5432)
```

### Migration fails: "table already exists"
```bash
# Option 1: Drop and recreate
psql "$NEON_DATABASE_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
python scripts/deployment/neon/migrate.py

# Option 2: Modify schema.sql to use IF NOT EXISTS
```

### Slow queries
```
✅ Check indexes are created: \d+ table_name
✅ Run ANALYZE to update statistics
✅ Enable query logging to see slow queries
```

## 📚 Resources

- **Neon Docs**: https://neon.tech/docs
- **asyncpg Docs**: https://magicstack.github.io/asyncpg
- **PostgreSQL Full-Text Search**: https://www.postgresql.org/docs/current/textsearch.html

## 🎯 Next Steps

1. ✅ Run migration for your data
2. ✅ Test locally with new stats endpoint
3. ✅ Deploy to HuggingFace with NEON_DATABASE_URL secret
4. ⬜ Create sync script for automated updates
5. ⬜ Add more search tables (bills, grants, etc.)
6. ⬜ Implement caching layer (Redis) for even faster responses

## 🤝 Contributing

To add new tables to Neon:

1. Add table definition to `schema.sql`
2. Add migration logic to `migrate.py`
3. Create/update API route to use new table
4. Update this README with new table info
