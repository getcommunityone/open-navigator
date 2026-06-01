# Neon YouTube Tables Setup

Automated script to set up YouTube data tables in Neon cloud database.

## What It Does

This script automates the complete setup process:

1. ✅ Creates `bronze` schema in Neon
2. ✅ Creates required tables using dbt:
   - `bronze.bronze_event_youtube`
   - `bronze.bronze_event_youtube_transcript`
3. ✅ Syncs data from local PostgreSQL to Neon
4. ✅ Verifies the setup

## Prerequisites

1. **Neon connection string** in `.env`:
   ```bash
   NEON_DATABASE_URL=postgresql://user:password@ep-xxxx.neon.tech/open_navigator?sslmode=require
   ```

2. **dbt profiles** configured at `~/.dbt/profiles.yml`
   - Script will create from example if missing
   - You'll need to add your Neon credentials

3. **Local database** with bronze tables populated:
   - `bronze.bronze_event_youtube` (your local data)
   - `bronze.bronze_event_youtube_transcript`

## Usage

### Quick Start

```bash
# From project root
./packages/hosting/scripts/neon/setup_youtube_tables.sh
```

The script will:
- Check your environment
- Create schema and tables in Neon
- Ask which tables to sync (minimum or recommended)
- Sync the data
- Verify everything worked

### Options

When asked which tables to sync:

**Option 1: Minimum (recommended for Colab)**
- `bronze_event_youtube` (4,759 rows, ~7.5 MB)
- `bronze_event_youtube_transcript` (2 rows, ~168 KB)
- `bronze_events_channels` (344 rows, ~368 KB)
- **Total:** ~8 MB, takes 10-30 seconds

**Option 2: Recommended (includes LocalView)**
- All minimum tables, plus:
- `bronze_events_localview` (185,037 rows, ~65 MB)
- **Total:** ~73 MB, takes 1-2 minutes

**Option 3: Custom**
- Choose specific tables yourself

## After Setup

Once the script completes, your Neon database is ready!

**In Google Colab:**

1. Add Neon URL to Colab Secrets:
   - Click the 🔑 key icon in left sidebar
   - Add secret: `NEON_DATABASE_URL`
   - Paste your Neon connection string

2. Run the YouTube events loader:
   - Open `packages/scrapers/src/scrapers/youtube/load_youtube_events_colab.ipynb`
   - Run the cells to fetch new YouTube videos

## Troubleshooting

### Error: "NEON_DATABASE_URL not set"

Add it to your `.env` file:
```bash
echo 'NEON_DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/open_navigator?sslmode=require' >> .env
```

### Error: "dbt profiles not found"

The script will create `~/.dbt/profiles.yml` from the example.

Edit it and add your Neon credentials:
```yaml
prod:
  type: postgres
  host: ep-xxxx.us-west-2.aws.neon.tech  # Your Neon host
  user: your_user                         # Your Neon user
  password: your_password                 # Your Neon password
  dbname: open_navigator
  schema: public
```

### Error: "Table already exists"

That's okay! The script will skip existing tables and continue.

### Manual Verification

Check what's in Neon:
```bash
psql "$NEON_DATABASE_URL" -c "
SELECT tablename, pg_size_pretty(pg_total_relation_size('bronze.'||tablename))
FROM pg_tables 
WHERE schemaname = 'bronze';
"
```

## Alternative: Manual Setup

If you prefer to run each step manually:

```bash
# 1. Create schema
psql "$NEON_DATABASE_URL" -c "CREATE SCHEMA IF NOT EXISTS bronze;"

# 2. Create tables with dbt
cd dbt_project
dbt run --select bronze_event_youtube --target prod
dbt run --select bronze_event_youtube_transcript --target prod

# 3. Sync data
source .venv/bin/activate
python -m hosting.neon.sync_bronze_tables \
  bronze_event_youtube \
  bronze_event_youtube_transcript \
  bronze_events_channels
```

## What Gets Created

### In Neon Database

```
open_navigator (database)
└── bronze (schema)
    ├── bronze_event_youtube         # Video metadata
    ├── bronze_event_youtube_transcript         # Video transcripts
    ├── bronze_events_channels        # Channel tracking
    └── bronze_events_localview       # Optional: LocalView events
```

### Table Sizes

- **Small deployment** (minimum): ~8 MB
- **Medium deployment** (with LocalView): ~73 MB
- **Disk usage:** Minimal (well within Neon free tier)

## Related Scripts

- `sync_bronze_tables.py` - Flexible table sync (used by this script)
- `sync_youtube_to_neon.py` - Legacy YouTube-only sync
- `migrate.py` - Sync gold parquet files to Neon
