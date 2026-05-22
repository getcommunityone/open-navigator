---
sidebar_position: 6
---

# Partitioned Datasets

Partitioned datasets provide the best of both worlds: efficient state-level queries **and** the ability to query the full national dataset.

## Why Partitioning?

### Problem with Separate Files
```python
# ❌ Must know which files to load
df_al = pd.read_parquet('data/gold/by_state/nonprofits_organizations_AL.parquet')
df_ga = pd.read_parquet('data/gold/by_state/nonprofits_organizations_GA.parquet')
df = pd.concat([df_al, df_ga])  # Manual combining
```

### Solution: Partitioned Datasets
```python
# ✅ Single dataset, automatic filtering
df = pd.read_parquet('data/gold/nonprofits_organizations',
                     filters=[('state', 'in', ['AL', 'GA'])])
# Only reads AL and GA partitions - efficient!
```

## Benefits

1. **Partition Pruning**: Only reads relevant data
   - Query Alabama → Only reads AL partition (1 MB)
   - Query California → Only reads CA partition (8 MB)
   - Not entire 72 MB file!

2. **Single Logical Table**: Query like a database
   ```python
   # Filter, aggregate, join - just like SQL
   df = pd.read_parquet('data/gold/nonprofits_organizations',
                        filters=[('state', '=', 'AL')])
   ```

3. **Works with Analytics Tools**:
   - Apache Spark (built-in partition pruning)
   - DuckDB (automatic partition detection)
   - AWS Athena (S3 partitioning)
   - Pandas (filter pushdown)

4. **Easy Updates**: Update one state without touching others
   ```python
   # Update only Alabama data
   df_new = pd.read_parquet('data/gold/nonprofits_organizations',
                            filters=[('state', '!=', 'AL')])
   df_al_updated = get_updated_alabama_data()
   df = pd.concat([df_new, df_al_updated])
   df.to_parquet('data/gold/nonprofits_organizations',
                 partition_cols=['state'])
   ```

## Directory Structure

```
data/gold/
├── nonprofits_organizations/          # Partitioned dataset (207 MB)
│   ├── state=AL/
│   │   └── part-0.parquet (1 MB)
│   ├── state=AK/
│   │   └── part-0.parquet (0.5 MB)
│   ├── state=CA/
│   │   └── part-0.parquet (8 MB)
│   └── ... (63 states)
├── nonprofits_locations/              # Partitioned dataset (99 MB)
├── nonprofits_financials/             # Partitioned dataset (78 MB)
├── nonprofits_programs/               # Partitioned dataset (67 MB)
├── jurisdictions_cities/              # Partitioned dataset (2.9 MB)
├── jurisdictions_counties/            # Partitioned dataset (1.1 MB)
├── jurisdictions_school_districts/    # Partitioned dataset (1.8 MB)
├── jurisdictions_townships/           # Partitioned dataset (3.3 MB)
├── domains_gsa_domains/               # Partitioned dataset (1.4 MB)
├── causes_everyorg_causes.parquet     # Lookup table (no partitioning)
└── causes_ntee_codes          # Lookup table (no partitioning)
```

**Note**: All datasets with state information are now partitioned. Lookup tables and non-state data remain as single files.

### State Column Handling

Different datasets get their state information in different ways:

- **Direct state column**: `nonprofits_organizations`, `nonprofits_locations`
- **State via EIN join**: `nonprofits_financials`, `nonprofits_programs` (joined with organizations by EIN)
- **USPS column**: `jurisdictions_cities`, `jurisdictions_counties`, etc. (renamed to `state`)
- **State column**: `domains_gsa_domains` (capitalized, normalized to `state`)

The partitioning script automatically handles these differences, ensuring all datasets use a consistent `state` partition column.

## Creating Partitioned Datasets

```bash
# Create all partitioned datasets
python scripts/create_partitioned_datasets.py --all

# Create specific dataset
python scripts/create_partitioned_datasets.py --file nonprofits_organizations.parquet

# Dry run (see what would be created)
python scripts/create_partitioned_datasets.py --all --dry-run
```

## Query Examples

### Pandas

```python
import pandas as pd

# Read single state (only reads 1 MB, not 72 MB!)
df = pd.read_parquet('data/gold/nonprofits_organizations',
                     filters=[('state', '=', 'AL')])
print(f"Alabama nonprofits: {len(df):,}")

# Read multiple states
df = pd.read_parquet('data/gold/nonprofits_organizations',
                     filters=[('state', 'in', ['AL', 'GA', 'FL', 'MS', 'TN'])])
print(f"Southeast nonprofits: {len(df):,}")

# Read all states (reads all partitions)
df = pd.read_parquet('data/gold/nonprofits_organizations')
print(f"All nonprofits: {len(df):,}")

# Complex filters (still efficient!)
df = pd.read_parquet('data/gold/nonprofits_organizations',
                     filters=[
                         ('state', '=', 'AL'),
                         ('ntee_code', '=', 'E')  # Health orgs only
                     ])
```

### DuckDB

```python
import duckdb

# DuckDB automatically detects partitions
con = duckdb.connect()

# Query with partition pruning
result = con.execute("""
    SELECT state, COUNT(*) as org_count
    FROM 'data/gold/nonprofits_organizations/**/*.parquet'
    WHERE state IN ('AL', 'GA', 'FL')
    GROUP BY state
""").fetchdf()

print(result)
```

### PySpark

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

# Spark automatically uses partition pruning
df = spark.read.parquet('data/gold/nonprofits_organizations')

# Only reads AL partition
al_orgs = df.filter(df.state == 'AL')
print(f"Alabama nonprofits: {al_orgs.count():,}")

# Join partitioned datasets efficiently
cities = spark.read.parquet('data/gold/jurisdictions_cities')
nonprofits = spark.read.parquet('data/gold/nonprofits_organizations')

# Both filter to AL before join - very efficient!
result = nonprofits.filter(nonprofits.state == 'AL') \
                   .join(cities.filter(cities.state == 'AL'), 
                         on='city_name')
```

## Performance Comparison

### Query: Alabama Nonprofits

| Method | Data Read | Time | Memory |
|--------|-----------|------|--------|
| **Full file** | 72 MB | 2.5s | 400 MB |
| **Separate file** | 1 MB | 0.1s | 8 MB |
| **Partitioned (filtered)** | 1 MB | 0.1s | 8 MB |

### Query: All Nonprofits

| Method | Data Read | Time | Memory |
|--------|-----------|------|--------|
| **Full file** | 72 MB | 2.5s | 400 MB |
| **Separate files** | 72 MB (62 files) | 3.2s | 400 MB |
| **Partitioned** | 72 MB | 2.5s | 400 MB |

### Query: 5 Southeastern States

| Method | Data Read | Time | Memory |
|--------|-----------|------|--------|
| **Full file** | 72 MB | 2.5s | 400 MB |
| **Separate files** | 5 MB (5 files) | 0.2s | 35 MB |
| **Partitioned (filtered)** | 5 MB | 0.2s | 35 MB |

**Winner: Partitioned datasets** - Same efficiency as separate files with full dataset queryability!

## Available Partitioned Datasets

All files with state information can be partitioned:

- `nonprofits_organizations/` (62 state partitions)
- `nonprofits_locations/` (62 state partitions)
- `nonprofits_financials/` (62 state partitions)
- `nonprofits_programs/` (62 state partitions)
- `jurisdictions_cities/` (52 state partitions)
- `jurisdictions_counties/` (52 state partitions)
- `jurisdictions_school_districts/` (52 state partitions)
- `jurisdictions_townships/` (52 state partitions)
- `domains_gsa_domains/` (56 state partitions)

## Uploading to HuggingFace

Partitioned datasets work great with HuggingFace:

```python
from datasets import Dataset
import pandas as pd

# Read partitioned data
df = pd.read_parquet('data/gold/nonprofits_organizations',
                     filters=[('state', '=', 'AL')])

# Upload state-specific subset
dataset = Dataset.from_pandas(df)
dataset.push_to_hub("CommunityOne/one-data-AL")
```

Or upload the entire partitioned structure:

```bash
# Upload partitioned directory to HuggingFace
# Each state becomes a separate shard
huggingface-cli upload CommunityOne/one-nonprofits \
  data/gold/nonprofits_organizations \
  --repo-type dataset
```

## Best Practices

1. **Always use filters** when reading partitioned data for specific states
   ```python
   # ✅ Efficient
   df = pd.read_parquet('path', filters=[('state', '=', 'AL')])
   
   # ❌ Inefficient (reads all partitions then filters)
   df = pd.read_parquet('path')
   df = df[df['state'] == 'AL']
   ```

2. **Use `in` operator for multiple states**
   ```python
   df = pd.read_parquet('path', 
                        filters=[('state', 'in', ['AL', 'GA', 'FL'])])
   ```

3. **Combine with other filters** for maximum efficiency
   ```python
   df = pd.read_parquet('path', 
                        filters=[
                            ('state', '=', 'AL'),
                            ('revenue', '>', 1000000)
                        ])
   ```

## Migration from Separate Files

If you have code using separate files:

```python
# Old approach
df = pd.read_parquet('data/gold/by_state/nonprofits_organizations_AL.parquet')

# New approach (equivalent)
df = pd.read_parquet('data/gold/nonprofits_organizations',
                     filters=[('state', '=', 'AL')])
```

Both work identically! The partitioned approach is recommended for new code.
