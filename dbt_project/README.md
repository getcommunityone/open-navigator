# Open Navigator dbt Project

Transforms bronze AI extractions into production-ready search tables.

## 🎯 Purpose

This dbt project handles:
- **Bronze → Production transformations** (AI extracted data)
- **Data quality testing**
- **Incremental processing** (only new records)
- **Entity deduplication**
- **Documentation generation**

## 📁 Project Structure

```
dbt_project/
├── dbt_project.yml           # Project configuration
├── profiles.yml.example      # Database connection template
├── models/
│   ├── staging/              # Clean bronze data
│   │   ├── _staging.yml
│   │   ├── stg_bronze_contacts.sql
│   │   ├── stg_bronze_organizations_meetings.sql
│   │   └── stg_bronze_bills.sql
│   ├── intermediate/         # Deduplicate
│   │   ├── _intermediate.yml
│   │   └── int_contacts_deduped.sql
│   └── marts/               # Production tables
│       ├── _marts.yml
│       └── contacts_search_ai.sql
├── macros/                  # Reusable SQL functions
│   ├── calculate_confidence.sql
│   ├── normalize_bill_number.sql
│   └── normalize_name.sql
├── tests/                   # Custom data quality tests
└── README.md               # This file
```

## 🚀 Quick Start

### 1. Install dbt

```bash
# Install dbt-postgres
pip install dbt-postgres

# Verify installation
dbt --version
```

### 2. Configure Database Connection

```bash
# Copy example profiles
cp profiles.yml.example ~/.dbt/profiles.yml

# Edit with your database credentials
nano ~/.dbt/profiles.yml
```

Or set environment variables:
```bash
export POSTGRES_PASSWORD=your_password
export NEON_HOST=your-neon-host.neon.tech
export NEON_USER=your_user
export NEON_PASSWORD=your_password
```

### 3. Test Connection

```bash
# Check dbt can connect
dbt debug

# Should show:
# ✓ Connection test: [OK connection ok]
```

### 4. Run Models

```bash
# Run all models
dbt run

# Run specific model
dbt run --select stg_bronze_contacts

# Run with full refresh (rebuild everything)
dbt run --full-refresh

# Run tests
dbt test

# Generate documentation
dbt docs generate
dbt docs serve  # Opens in browser
```

## 📊 Model Layers

### Staging (`models/staging/`)

**Purpose:** Clean and normalize bronze data

- `stg_bronze_contacts.sql` - Clean contact names, filter invalid records
- `stg_bronze_organizations_meetings.sql` - Normalize org names, clean EINs
- `stg_bronze_bills.sql` - Standardize bill numbers

**Materialization:** `view` (no storage, computed on-the-fly)

### Intermediate (`models/intermediate/`)

**Purpose:** Deduplicate and prepare for production

- `int_contacts_deduped.sql` - One record per person per org

**Materialization:** `table` (stored, fast to query)

### Marts (`models/marts/`)

**Purpose:** Production-ready tables for API

- `contacts_search_ai.sql` - AI-extracted contacts (incremental)

**Materialization:** `incremental` (only processes new records)

## 🧪 Testing

### Run Tests

```bash
# Run all tests
dbt test

# Run tests for specific model
dbt test --select contacts_search_ai

# Run specific test type
dbt test --select test_type:unique
dbt test --select test_type:not_null
```

### Available Tests

1. **Schema tests** (in `.yml` files)
   - `unique` - No duplicates
   - `not_null` - No NULL values
   - `accepted_values` - Value in allowed list
   - `relationships` - Foreign key exists

2. **Custom tests** (in `tests/` folder)
   - Custom SQL assertions

## 🔄 Incremental Processing

Models marked `materialized='incremental'` only process new records:

```sql
{% if is_incremental() %}
WHERE extracted_at > (SELECT MAX(last_updated) FROM {{ this }})
{% endif %}
```

### Full Refresh

To rebuild everything from scratch:

```bash
dbt run --full-refresh --select contacts_search_ai
```

## 🎨 Macros

Reusable SQL functions in `macros/`:

### `calculate_confidence(datasource)`
```sql
SELECT {{ calculate_confidence('datasource') }} as score
-- Returns 1.0 for authoritative, 0.60 for AI extraction
```

### `normalize_bill_number(column)`
```sql
SELECT {{ normalize_bill_number('official_number') }} as bill_num
-- 'HB 123' → 'HB123'
```

### `normalize_name(column)`
```sql
SELECT {{ normalize_name('full_name') }} as name_clean
-- Lowercase, trim, remove special chars
```

## 📋 Workflow Integration

### Combined with Python ETL

```bash
#!/bin/bash
# Full ETL pipeline

# 1. Python: Load bronze data
python scripts/datasources/gemini/load_meeting_transcripts_bronze.py

# 2. dbt: Transform to production
cd dbt_project
dbt run --select staging+
dbt run --select intermediate+
dbt run --select marts+
dbt test

# 3. Python: Export to parquet (if needed)
cd ..
python scripts/data/export_to_gold_parquet.py
```

## 🐛 Troubleshooting

### "relation does not exist"

**Problem:** Source table not found

**Solution:** Check you're connected to the right database
```bash
dbt debug
# Look at "target" database
```

### "Compilation Error: macro 'dbt_utils' is not defined"

**Problem:** Missing dbt packages

**Solution:** Install packages
```bash
# Create packages.yml
cat > packages.yml << EOF
packages:
  - package: dbt-labs/dbt_utils
    version: 1.1.1
EOF

# Install
dbt deps
```

### "Incremental model not updating"

**Problem:** New records not being processed

**Solution:** Check timestamp logic
```bash
# Full refresh to rebuild
dbt run --full-refresh --select contacts_search_ai
```

## 📚 Resources

- [dbt Documentation](https://docs.getdbt.com/)
- [dbt Best Practices](https://docs.getdbt.com/guides/best-practices)
- [SQL Style Guide](https://github.com/dbt-labs/corp/blob/main/dbt_style_guide.md)

## 🔗 Related Documentation

- [dbt ETL Strategy](../website/docs/development/dbt-etl-strategy.md) - Full architecture guide
- [Bronze to Production Merge](../website/docs/development/bronze-to-production-merge.md) - Merge strategy
- [Data Sources](../docs/DATA_SOURCES.md) - All data sources

## ⏭️ Next Steps

1. **Install packages:** `dbt deps`
2. **Run models:** `dbt run`
3. **Run tests:** `dbt test`
4. **Generate docs:** `dbt docs generate && dbt docs serve`
5. **Iterate:** Add more models incrementally
