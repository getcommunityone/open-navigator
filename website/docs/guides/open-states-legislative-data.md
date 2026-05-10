---
sidebar_position: 10
---

# Working with Open States Legislative Data

Complete guide to using the Open States PostgreSQL dump downloaded from Plural Policy.

## Scope & limitations (important)

Open States focuses on **state legislative data** — lawmakers' voting records, committee assignments, bill status, sponsors, and bill text — aggregated into a unified, machine-readable format across **all 50 states**, plus **Washington, D.C.** and **Puerto Rico**.

It **does not** cover local government offices or elections. In particular, you should **not** expect Open States to have data on:

- **County commissioners**
- **County elections**
- **School boards**
- **Municipal offices**

Open States was built specifically for **state legislatures**. The project was adopted by **Plural Policy** in 2021 and is now accessible via [Plural Policy](https://www.pluralpolicy.com/), which adds AI-powered tracking on top of the original dataset while staying in the state-legislative lane.

For **county/local ballot information**, good starting points are:

- [Ballotpedia](https://ballotpedia.org/)
- [VOTE411](https://www.vote411.org/)
- Directly from **county election administrator** websites

## � Quick Start (Complete Setup)

**Prerequisites:**
- PostgreSQL 15+ installed ([Download](https://www.postgresql.org/download/))
- Python 3.12+ with venv
- ~15 GB free disk space

**Full Setup (20-30 minutes):**

```bash
# 1. Download BOTH schema and data files (~10 GB total, takes 5-10 min)
python scripts/bulk_legislative_download.py --postgres --month 2026-04

# This downloads TWO files:
#   - 2026-04-schema.pgdump  (~50 MB) - creates tables
#   - 2026-04-public.pgdump  (~10 GB) - contains data

# 2. Create database
createdb openstates

# 3. Restore schema first (creates all tables, ~30 seconds)
pg_restore \
  --dbname=openstates \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  data/cache/legislation_bulk/postgres/2026-04-schema.pgdump

# 4. Restore data (takes 10-15 minutes for 9.8 GB)
pg_restore \
  --dbname=openstates \
  --data-only \
  --disable-triggers \
  --no-owner \
  --no-privileges \
  data/cache/legislation_bulk/postgres/2026-04-public.pgdump

# 5. Verify tables loaded
psql openstates -c "\dt" | grep opencivicdata

# 6. Test query
psql openstates -c "SELECT COUNT(*) FROM opencivicdata_person;"

# 7. Add to .env file
echo "OPENSTATES_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/openstates" >> .env

# 8. Test Python connection
python -c "
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine
load_dotenv()
engine = create_engine(os.getenv('OPENSTATES_DATABASE_URL'))
with engine.connect() as conn:
    from sqlalchemy import text
    result = conn.execute(text('SELECT COUNT(*) FROM opencivicdata_person'))
    print(f'✅ Connected! Total people: {result.scalar()}')
"
```

**Expected Output:**
```
✅ Connected! Total people: 7342
```

You're ready to query legislative data!

## �📥 Download the Data

The PostgreSQL dump requires **TWO separate files** from OpenStates:

1. **Schema file** (~50 MB): Creates all database tables, indexes, and constraints
2. **Data file** (~10 GB): Contains all the actual legislative data

```bash
# Download both files for the latest month
python scripts/bulk_legislative_download.py --postgres --month 2026-04

# Files saved to:
# data/cache/legislation_bulk/postgres/2026-04-schema.pgdump (schema)
# data/cache/legislation_bulk/postgres/2026-04-public.pgdump (data)
```

**Why two files?**

OpenStates separates schema and data for flexibility:
- **Schema file**: Small, updates rarely, creates table structure
- **Data file**: Large, updated monthly, contains all records

This allows you to update data without recreating the schema each time.

**What's Included:**
- **7,300+ state legislators** with complete profiles
- **100,000+ bills** with full text (2020+)
- **Committee assignments** and memberships
- **Roll call votes** with individual legislator positions
- **Bill sponsorships** and co-sponsors
- **Bill actions** (timeline of committee/floor activity)
- **Multiple bill versions** (as introduced, amended, enrolled)
- **Legislator contact information** (district and capitol offices)

## 🗄️ Load Data into PostgreSQL

### Option 1: Local PostgreSQL (Recommended for Development)

**Prerequisites:**
- PostgreSQL 15+ installed ([Download here](https://www.postgresql.org/download/))
- Both schema and data files downloaded (see above section)

**Setup Steps (Two-Step Restore):**

```bash
# 1. Create database
createdb openstates

# 2. Restore SCHEMA first (creates tables, indexes, constraints)
pg_restore \
  --dbname=openstates \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  data/cache/legislation_bulk/postgres/2026-04-schema.pgdump

# This takes ~30 seconds and creates all tables

# 3. Restore DATA (loads all records into tables)
pg_restore \
  --dbname=openstates \
  --data-only \
  --disable-triggers \
  --no-owner \
  --no-privileges \
  data/cache/legislation_bulk/postgres/2026-04-public.pgdump

# This takes 10-15 minutes for 9.8 GB of data

# 4. Verify restoration
psql openstates -c "\dt"  # List all tables (should see 30+ opencivicdata_* tables)

# 5. Test query
psql openstates -c "SELECT COUNT(*) FROM opencivicdata_person;"
# Expected: ~7,300+ legislators
```

**Add to `.env`:**
```bash
OPENSTATES_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/openstates
```

**Automated Script:**

For convenience, use the provided setup script that does both steps:

```bash
./scripts/setup_openstates_db.sh
```

This script:
- ✅ Checks that both schema and data files exist
- ✅ Creates the database if needed
- ✅ Restores schema first, then data
- ✅ Verifies the restore was successful
- ✅ Shows table counts

**Troubleshooting:**
```bash
# If you need to set PostgreSQL password
psql -U postgres -c "ALTER USER postgres PASSWORD 'postgres';"

# If port 5432 is busy, use different port
psql -p 5433  # Then update .env accordingly
```

### Option 2: Docker PostgreSQL (Clean Isolation)

**Use a different port (5433) to avoid conflicts with main database:**

```bash
# Start PostgreSQL container
docker run -d \
  --name openstates-db \
  -e POSTGRES_PASSWORD=openstates \
  -e POSTGRES_DB=openstates \
  -p 5433:5432 \
  -v $(pwd)/data/cache/legislation_bulk/postgres:/dumps \
  postgres:15

# Restore SCHEMA first
docker exec -i openstates-db \
  pg_restore \
  --dbname=openstates \
  --username=postgres \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  /dumps/2026-04-schema.pgdump

# Restore DATA second
docker exec -i openstates-db \
  pg_restore \
  --dbname=openstates \
  --username=postgres \
  --data-only \
  --disable-triggers \
  --no-owner \
  --no-privileges \
  /dumps/2026-04-public.pgdump

# Test connection
docker exec -it openstates-db psql -U postgres -d openstates -c "SELECT COUNT(*) FROM opencivicdata_person;"
```

**Add to `.env`:**
```bash
OPENSTATES_DATABASE_URL=postgresql://postgres:openstates@localhost:5433/openstates
```

**Stop/Start Container:**
```bash
docker stop openstates-db    # Stop container
docker start openstates-db   # Start container
docker rm openstates-db      # Remove container
```

## 📊 Database Schema

### Core Tables

The Open States database follows the [Popolo Project](https://www.popoloproject.com/) standard for representing political data.

#### `opencivicdata_person` - Legislators

```sql
SELECT 
  id,                    -- OCD-ID: ocd-person/{uuid}
  name,                  -- Full name
  given_name,            -- First name
  family_name,           -- Last name
  gender,                -- Male/Female/Other
  email,                 -- Official email
  biography,             -- Bio text
  birth_date,            -- Date of birth
  image,                 -- Photo URL
  created_at,
  updated_at
FROM opencivicdata_person
LIMIT 5;
```

#### `opencivicdata_personmembership` - Legislator Roles

```sql
SELECT 
  person_id,             -- Links to opencivicdata_person.id
  organization_id,       -- Legislature ID
  post_id,              -- District/position
  label,                -- "Senator"/"Representative"
  role,                 -- "upper"/"lower"
  start_date,           -- Term start
  end_date              -- Term end
FROM opencivicdata_personmembership
WHERE end_date > CURRENT_DATE  -- Active legislators
LIMIT 5;
```

#### `opencivicdata_bill` - Legislation

```sql
SELECT 
  id,                    -- OCD-ID: ocd-bill/{uuid}
  identifier,            -- HB 123, SB 456
  title,                 -- Bill title
  classification,        -- bill/resolution/concurrent_resolution
  subject,              -- Array of topics
  from_organization_id, -- Legislature
  legislative_session_id,
  created_at,
  updated_at
FROM opencivicdata_bill
WHERE subject @> ARRAY['Health']::varchar[]  -- Health-related bills
LIMIT 5;
```

#### `opencivicdata_billabstract` - Bill Summaries

```sql
SELECT 
  bill_id,
  abstract,              -- Summary text
  note,                  -- "Official Summary"
  date
FROM opencivicdata_billabstract
LIMIT 5;
```

#### `opencivicdata_billsponsorship` - Bill Sponsors

```sql
SELECT 
  bill_id,
  person_id,             -- Links to opencivicdata_person.id
  classification,        -- "primary"/"cosponsor"
  primary_sponsorship,   -- Boolean
  entity_type            -- "person"/"organization"
FROM opencivicdata_billsponsorship
LIMIT 5;
```

#### `opencivicdata_voteevent` - Roll Call Votes

```sql
SELECT 
  id,                    -- OCD-ID: ocd-vote/{uuid}
  bill_id,
  organization_id,       -- Chamber
  motion_text,           -- "Passage of HB 123"
  motion_classification, -- "passage"/"amendment"
  result,               -- "pass"/"fail"
  start_date,           -- Vote date
  created_at,
  updated_at
FROM opencivicdata_voteevent
LIMIT 5;
```

#### `opencivicdata_personvote` - Individual Legislator Votes

```sql
SELECT 
  vote_event_id,
  voter_id,              -- Links to opencivicdata_person.id
  option,                -- "yes"/"no"/"abstain"/"absent"
  voter_name,            -- Name at time of vote
  note
FROM opencivicdata_personvote
LIMIT 5;
```

#### `opencivicdata_organization` - Committees

```sql
SELECT 
  id,                    -- OCD-ID: ocd-organization/{uuid}
  name,                  -- "Committee on Health and Human Services"
  classification,        -- "committee"/"subcommittee"/"legislature"
  parent_id,            -- Parent committee (for subcommittees)
  jurisdiction_id,
  created_at,
  updated_at
FROM opencivicdata_organization
WHERE classification = 'committee'
LIMIT 5;
```

## 🔍 Useful Queries

### Find All Health-Related Bills in Alabama (2024)

```sql
SELECT 
  b.identifier,
  b.title,
  b.subject,
  p.name AS sponsor,
  b.created_at
FROM opencivicdata_bill b
LEFT JOIN opencivicdata_billsponsorship bs ON bs.bill_id = b.id AND bs.primary_sponsorship = true
LEFT JOIN opencivicdata_person p ON p.id = bs.person_id
LEFT JOIN opencivicdata_legislativesession ls ON ls.id = b.legislative_session_id
WHERE ls.jurisdiction_id = 'ocd-jurisdiction/country:us/state:al/government'
  AND ls.identifier LIKE '2024%'
  AND (
    b.subject @> ARRAY['Health']::varchar[]
    OR b.title ILIKE '%dental%'
    OR b.title ILIKE '%oral health%'
    OR b.title ILIKE '%medicaid%'
  )
ORDER BY b.created_at DESC;
```

### List Active Legislators with Committee Assignments

```sql
SELECT 
  p.name,
  p.party_name,
  pm.role AS chamber,
  pm.label AS position,
  o.name AS committee
FROM opencivicdata_person p
JOIN opencivicdata_personmembership pm 
  ON pm.person_id = p.id 
  AND pm.end_date > CURRENT_DATE
LEFT JOIN opencivicdata_personmembership cm 
  ON cm.person_id = p.id 
  AND cm.end_date > CURRENT_DATE
LEFT JOIN opencivicdata_organization o 
  ON o.id = cm.organization_id 
  AND o.classification = 'committee'
WHERE pm.organization_id LIKE 'ocd-organization%/legislature'
ORDER BY p.name;
```

### Track Bill Progress Through Legislature

```sql
SELECT 
  b.identifier,
  b.title,
  ba.date AS action_date,
  ba.description AS action,
  ba.classification,
  o.name AS organization
FROM opencivicdata_bill b
JOIN opencivicdata_billaction ba ON ba.bill_id = b.id
LEFT JOIN opencivicdata_organization o ON o.id = ba.organization_id
WHERE b.identifier = 'HB 123'
  AND b.from_organization_id LIKE '%state:al%'
ORDER BY ba.date;
```

### Count Bills by Legislator (Top Sponsors)

```sql
SELECT 
  p.name,
  COUNT(DISTINCT bs.bill_id) AS bills_sponsored
FROM opencivicdata_person p
JOIN opencivicdata_billsponsorship bs ON bs.person_id = p.id
WHERE bs.primary_sponsorship = true
GROUP BY p.id, p.name
ORDER BY bills_sponsored DESC
LIMIT 20;
```

### Find Roll Call Votes on Health Bills

```sql
SELECT 
  b.identifier,
  b.title,
  v.motion_text,
  v.result,
  v.start_date,
  COUNT(CASE WHEN pv.option = 'yes' THEN 1 END) AS yes_votes,
  COUNT(CASE WHEN pv.option = 'no' THEN 1 END) AS no_votes,
  COUNT(CASE WHEN pv.option = 'abstain' THEN 1 END) AS abstain_votes
FROM opencivicdata_bill b
JOIN opencivicdata_voteevent v ON v.bill_id = b.id
LEFT JOIN opencivicdata_personvote pv ON pv.vote_event_id = v.id
WHERE b.subject @> ARRAY['Health']::varchar[]
GROUP BY b.id, b.identifier, b.title, v.id, v.motion_text, v.result, v.start_date
ORDER BY v.start_date DESC;
```

## 🐍 Python Integration with SQLAlchemy

### Using Environment Variables

**Setup `.env` file first (see above), then:**

```python
import os
from sqlalchemy import create_engine, text
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Connect using OPENSTATES_DATABASE_URL from .env
engine = create_engine(os.getenv('OPENSTATES_DATABASE_URL'))

# Test connection
with engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM opencivicdata_person"))
    print(f"Total people in database: {result.scalar()}")

# Query legislators
legislators_df = pd.read_sql_query("""
    SELECT 
        p.name,
        p.email,
        p.party_name,
        pm.role AS chamber,
        pm.label AS position,
        j.name AS state
    FROM opencivicdata_person p
    JOIN opencivicdata_personmembership pm ON pm.person_id = p.id
    JOIN opencivicdata_jurisdiction j ON j.id LIKE '%' || pm.organization_id || '%'
    WHERE pm.end_date > CURRENT_DATE
    LIMIT 100
""", engine)

print(f"Active legislators: {len(legislators_df)}")
print(legislators_df.head())

# Query health bills
health_bills_df = pd.read_sql_query("""
    SELECT 
        b.identifier,
        b.title,
        b.subject,
        ls.identifier AS session
    FROM opencivicdata_bill b
    JOIN opencivicdata_legislativesession ls ON ls.id = b.legislative_session_id
    WHERE b.subject @> ARRAY['Health']::varchar[]
        AND ls.identifier LIKE '2024%'
    LIMIT 50
""", engine)

print(f"Health bills in 2024: {len(health_bills_df)}")
```

### Complete Example Script

Save as `scripts/query_openstates.py`:

```python
#!/usr/bin/env python3
"""
Query Open States PostgreSQL database for legislative data.

Usage:
    python scripts/query_openstates.py --state al --topic health
"""
import os
import argparse
from sqlalchemy import create_engine
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

def get_engine():
    """Create database engine from environment variable."""
    db_url = os.getenv('OPENSTATES_DATABASE_URL')
    if not db_url:
        raise ValueError(
            "OPENSTATES_DATABASE_URL not set in .env file. "
            "See website/docs/guides/open-states-legislative-data.md for setup."
        )
    return create_engine(db_url)

def query_legislators(engine, state_code=None):
    """Get active legislators, optionally filtered by state."""
    where_clause = ""
    if state_code:
        where_clause = f"AND j.id LIKE '%state:{state_code}%'"
    
    query = f"""
        SELECT 
            p.name,
            p.email,
            p.party_name,
            pm.role AS chamber,
            pm.label AS position,
            j.name AS state
        FROM opencivicdata_person p
        JOIN opencivicdata_personmembership pm ON pm.person_id = p.id
        JOIN opencivicdata_jurisdiction j ON j.id LIKE '%' || pm.organization_id || '%'
        WHERE pm.end_date > CURRENT_DATE
        {where_clause}
        ORDER BY p.name
    """
    
    return pd.read_sql_query(query, engine)

def query_bills_by_topic(engine, topic, state_code=None, year=2024):
    """Get bills by topic (Health, Education, etc.)."""
    where_clause = ""
    if state_code:
        where_clause = f"AND ls.jurisdiction_id LIKE '%state:{state_code}%'"
    
    query = f"""
        SELECT 
            b.identifier,
            b.title,
            b.subject,
            ls.identifier AS session,
            ls.jurisdiction_id
        FROM opencivicdata_bill b
        JOIN opencivicdata_legislativesession ls ON ls.id = b.legislative_session_id
        WHERE b.subject @> ARRAY['{topic}']::varchar[]
            AND ls.identifier LIKE '{year}%'
            {where_clause}
        ORDER BY b.created_at DESC
    """
    
    return pd.read_sql_query(query, engine)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query Open States database")
    parser.add_argument("--state", help="State code (e.g., al, ca, ny)")
    parser.add_argument("--topic", default="Health", help="Bill topic")
    parser.add_argument("--year", type=int, default=2024, help="Legislative year")
    
    args = parser.parse_args()
    
    engine = get_engine()
    
    print(f"\n📊 Querying Open States Database...")
    print(f"   State: {args.state or 'All'}")
    print(f"   Topic: {args.topic}")
    print(f"   Year: {args.year}")
    
    # Get legislators
    legislators = query_legislators(engine, args.state)
    print(f"\n👥 Active Legislators: {len(legislators)}")
    print(legislators.head())
    
    # Get bills
    bills = query_bills_by_topic(engine, args.topic, args.state, args.year)
    print(f"\n📜 {args.topic} Bills in {args.year}: {len(bills)}")
    print(bills.head())
    
    # Save to CSV
    output_dir = "output/openstates_queries"
    os.makedirs(output_dir, exist_ok=True)
    
    legislators.to_csv(f"{output_dir}/legislators_{args.state or 'all'}.csv", index=False)
    bills.to_csv(f"{output_dir}/bills_{args.topic}_{args.year}.csv", index=False)
    
    print(f"\n✅ Results saved to {output_dir}/")
```

**Run it:**
```bash
# Query all health bills in Alabama for 2024
python scripts/query_openstates.py --state al --topic Health --year 2024

# Query all education bills nationwide
python scripts/query_openstates.py --topic Education
```

## 📊 Export to Parquet for HuggingFace

### Complete Export Script

Save as `scripts/export_openstates_parquet.py`:

```python
#!/usr/bin/env python3
"""
Export Open States PostgreSQL data to Parquet files for HuggingFace.

Usage:
    python scripts/export_openstates_parquet.py --output data/gold/legislation/
"""
import os
import argparse
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

def get_engine():
    """Get database engine from environment."""
    db_url = os.getenv('OPENSTATES_DATABASE_URL')
    if not db_url:
        raise ValueError("OPENSTATES_DATABASE_URL not set in .env")
    return create_engine(db_url)

def export_legislators(engine, output_dir):
    """Export active legislators."""
    logger.info("Exporting legislators...")
    
    df = pd.read_sql_query("""
        SELECT 
            p.id AS legislator_id,
            p.name AS full_name,
            p.given_name,
            p.family_name,
            p.gender,
            p.email,
            p.biography,
            p.birth_date,
            p.death_date,
            p.image,
            p.party[1]->>'name' AS party_name,
            p.created_at,
            p.updated_at
        FROM opencivicdata_person p
        WHERE id IN (
            SELECT DISTINCT person_id 
            FROM opencivicdata_personmembership 
            WHERE end_date > CURRENT_DATE
        )
    """, engine)
    
    output_path = os.path.join(output_dir, 'legislation_legislators.parquet')
    df.to_parquet(output_path, index=False, compression='snappy')
    logger.success(f"✅ Exported {len(df)} legislators to {output_path}")
    return len(df)

def export_legislator_roles(engine, output_dir):
    """Export legislator roles/terms."""
    logger.info("Exporting legislator roles...")
    
    df = pd.read_sql_query("""
        SELECT 
            pm.id AS role_id,
            pm.person_id AS legislator_id,
            pm.organization_id AS legislature_id,
            pm.post_id,
            pm.label AS position,
            pm.role AS chamber,
            pm.start_date AS term_start,
            pm.end_date AS term_end,
            pm.created_at,
            pm.updated_at
        FROM opencivicdata_personmembership pm
        WHERE pm.organization_id LIKE 'ocd-organization%'
    """, engine)
    
    output_path = os.path.join(output_dir, 'legislation_legislator_roles.parquet')
    df.to_parquet(output_path, index=False, compression='snappy')
    logger.success(f"✅ Exported {len(df)} roles to {output_path}")
    return len(df)

def export_bills(engine, output_dir):
    """Export bills from 2020+."""
    logger.info("Exporting bills (2020+)...")
    
    df = pd.read_sql_query("""
        SELECT 
            b.id AS bill_id,
            b.identifier,
            b.title,
            b.classification,
            b.subject,
            b.from_organization_id AS legislature_id,
            b.legislative_session_id,
            b.created_at,
            b.updated_at
        FROM opencivicdata_bill b
        WHERE b.created_at >= '2020-01-01'
    """, engine)
    
    output_path = os.path.join(output_dir, 'legislation_bills.parquet')
    df.to_parquet(output_path, index=False, compression='snappy')
    logger.success(f"✅ Exported {len(df)} bills to {output_path}")
    return len(df)

def export_bill_sponsors(engine, output_dir):
    """Export bill sponsorships."""
    logger.info("Exporting bill sponsors...")
    
    df = pd.read_sql_query("""
        SELECT 
            bs.id AS sponsor_id,
            bs.bill_id,
            bs.person_id AS legislator_id,
            bs.classification AS sponsor_type,
            bs.primary AS is_primary_sponsor,
            bs.entity_type
        FROM opencivicdata_billsponsorship bs
    """, engine)
    
    output_path = os.path.join(output_dir, 'legislation_bill_sponsors.parquet')
    df.to_parquet(output_path, index=False, compression='snappy')
    logger.success(f"✅ Exported {len(df)} sponsorships to {output_path}")
    return len(df)

def export_vote_events(engine, output_dir):
    """Export vote events from 2020+."""
    logger.info("Exporting vote events...")
    
    df = pd.read_sql_query("""
        SELECT 
            v.id AS vote_event_id,
            v.bill_id,
            v.organization_id,
            v.motion_text,
            v.motion_classification,
            v.result,
            v.start_date AS vote_date,
            v.created_at,
            v.updated_at
        FROM opencivicdata_voteevent v
        WHERE v.start_date >= '2020-01-01'
    """, engine)
    
    output_path = os.path.join(output_dir, 'legislation_vote_events.parquet')
    df.to_parquet(output_path, index=False, compression='snappy')
    logger.success(f"✅ Exported {len(df)} vote events to {output_path}")
    return len(df)

def export_legislator_votes(engine, output_dir):
    """Export individual legislator votes."""
    logger.info("Exporting legislator votes...")
    
    df = pd.read_sql_query("""
        SELECT 
            pv.id AS legislator_vote_id,
            pv.vote_event_id,
            pv.voter_id AS legislator_id,
            pv.option AS vote_position,
            pv.voter_name,
            pv.note
        FROM opencivicdata_personvote pv
    """, engine)
    
    output_path = os.path.join(output_dir, 'legislation_legislator_votes.parquet')
    df.to_parquet(output_path, index=False, compression='snappy')
    logger.success(f"✅ Exported {len(df)} legislator votes to {output_path}")
    return len(df)

def export_committees(engine, output_dir):
    """Export committees."""
    logger.info("Exporting committees...")
    
    df = pd.read_sql_query("""
        SELECT 
            o.id AS committee_id,
            o.jurisdiction_id,
            o.name,
            o.classification,
            o.parent_id,
            o.created_at,
            o.updated_at
        FROM opencivicdata_organization o
        WHERE o.classification IN ('committee', 'subcommittee')
    """, engine)
    
    output_path = os.path.join(output_dir, 'legislation_committees.parquet')
    df.to_parquet(output_path, index=False, compression='snappy')
    logger.success(f"✅ Exported {len(df)} committees to {output_path}")
    return len(df)

def export_committee_memberships(engine, output_dir):
    """Export committee memberships."""
    logger.info("Exporting committee memberships...")
    
    df = pd.read_sql_query("""
        SELECT 
            pm.id AS membership_id,
            pm.organization_id AS committee_id,
            pm.person_id AS legislator_id,
            pm.role,
            pm.start_date,
            pm.end_date,
            pm.created_at,
            pm.updated_at
        FROM opencivicdata_personmembership pm
        WHERE pm.organization_id IN (
            SELECT id FROM opencivicdata_organization 
            WHERE classification IN ('committee', 'subcommittee')
        )
    """, engine)
    
    output_path = os.path.join(output_dir, 'legislation_committee_memberships.parquet')
    df.to_parquet(output_path, index=False, compression='snappy')
    logger.success(f"✅ Exported {len(df)} memberships to {output_path}")
    return len(df)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Open States data to Parquet")
    parser.add_argument(
        "--output", 
        default="data/gold/legislation/",
        help="Output directory for Parquet files"
    )
    
    args = parser.parse_args()
    os.makedirs(args.output, exist_ok=True)
    
    logger.info(f"📊 Exporting Open States data to {args.output}")
    
    engine = get_engine()
    
    # Export all tables
    stats = {
        'legislators': export_legislators(engine, args.output),
        'legislator_roles': export_legislator_roles(engine, args.output),
        'bills': export_bills(engine, args.output),
        'bill_sponsors': export_bill_sponsors(engine, args.output),
        'vote_events': export_vote_events(engine, args.output),
        'legislator_votes': export_legislator_votes(engine, args.output),
        'committees': export_committees(engine, args.output),
        'committee_memberships': export_committee_memberships(engine, args.output),
    }
    
    logger.success("\n✅ Export complete!")
    logger.info("\n📊 Summary:")
    for table, count in stats.items():
        logger.info(f"   {table}: {count:,} records")
```

**Run the export:**
```bash
# Export all tables to Parquet
python scripts/export_openstates_parquet.py --output data/gold/legislation/

# Verify files were created
ls -lh data/gold/legislation/

# Output:
# legislation_legislators.parquet
# legislation_legislator_roles.parquet
# legislation_bills.parquet
# legislation_bill_sponsors.parquet
# legislation_vote_events.parquet
# legislation_legislator_votes.parquet
# legislation_committees.parquet
# legislation_committee_memberships.parquet
```

### Upload to HuggingFace

```bash
# Install huggingface-hub if not already installed
pip install huggingface-hub

# Upload datasets
python scripts/upload_to_huggingface.py \
    --dataset CommunityOne/open-navigator-data \
    --folder data/gold/legislation/
```

## 🔗 Related Resources

- **Open States Documentation:** https://docs.openstates.org/
- **Popolo Project Schema:** https://www.popoloproject.com/
- **Open Civic Data IDs:** https://opencivicdata.readthedocs.io/
- **Plural Policy Data Portal:** https://open.pluralpolicy.com/data/
- **PostgreSQL Monthly Dumps:** https://data.openstates.org/postgres/monthly/

## 🎯 Oral Health Policy Use Cases

### Finding Water Fluoridation Legislation

```sql
SELECT 
  b.identifier,
  b.title,
  ls.jurisdiction_id,
  b.subject,
  b.created_at
FROM opencivicdata_bill b
JOIN opencivicdata_legislativesession ls ON ls.id = b.legislative_session_id
WHERE (
    b.title ILIKE '%fluorid%'
    OR b.title ILIKE '%water treatment%'
    OR EXISTS (
        SELECT 1 FROM opencivicdata_billabstract ba
        WHERE ba.bill_id = b.id 
        AND ba.abstract ILIKE '%fluorid%'
    )
)
ORDER BY b.created_at DESC;
```

### Tracking Medicaid Dental Coverage Expansion

```sql
SELECT 
  b.identifier,
  b.title,
  p.name AS sponsor,
  v.result AS vote_outcome,
  v.start_date AS vote_date
FROM opencivicdata_bill b
LEFT JOIN opencivicdata_billsponsorship bs ON bs.bill_id = b.id AND bs.primary_sponsorship = true
LEFT JOIN opencivicdata_person p ON p.id = bs.person_id
LEFT JOIN opencivicdata_voteevent v ON v.bill_id = b.id
WHERE (
    b.title ILIKE '%medicaid%' AND b.title ILIKE '%dental%'
    OR b.title ILIKE '%medicaid%' AND b.title ILIKE '%oral health%'
)
ORDER BY b.created_at DESC;
```

### School-Based Dental Screening Programs

```sql
SELECT 
  b.identifier,
  b.title,
  ls.identifier AS session,
  j.name AS state
FROM opencivicdata_bill b
JOIN opencivicdata_legislativesession ls ON ls.id = b.legislative_session_id
JOIN opencivicdata_jurisdiction j ON j.id = ls.jurisdiction_id
WHERE (
    b.title ILIKE '%school%' AND b.title ILIKE '%dental%'
    OR b.title ILIKE '%school%' AND b.title ILIKE '%oral health%'
    OR b.title ILIKE '%school nurse%' AND b.title ILIKE '%screening%'
)
ORDER BY b.created_at DESC;
```
