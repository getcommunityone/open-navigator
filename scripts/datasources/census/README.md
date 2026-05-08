# US Census Bureau Data Scripts

**✅ MIGRATION COMPLETE** - Gold table ready in production database!

**See [STATUS.md](./STATUS.md)** for complete details and API integration guide.

**For a reference of every Census file the project downloads** (source URLs,
cache paths, geographic granularity, what's available at city level), see
[DATASETS.md](./DATASETS.md).

## Quick Reference

**The `jurisdictions` table is ready to use in `open_navigator` database:**

```sql
-- Your API can query this right now!
SELECT 
    jurisdiction_id, 
    display_name, 
    jurisdiction_type, 
    state_code, 
    geoid
FROM jurisdictions 
WHERE display_name ILIKE '%Boston%' 
  AND state_code = 'MA';
```

**Next Step**: Update `api/routes/search_postgres.py` to use this table. See [STATUS.md](./STATUS.md#-next-steps-for-api-integration) for examples.

---

## Quick Status

- ✅ **Bronze Layer**: 19,741 jurisdictions loaded
- ✅ **Silver Layer**: Data cleaned and linked (dbt models)
- ✅ **Gold Layer**: API-ready table materialized
- ✅ **Tests**: All 15 data quality tests passing
- ✅ **DONE**: API routes use `jurisdictions` table

**See**: [COMPLETION_SUMMARY.md](./COMPLETION_SUMMARY.md) for full details

Scripts for working with [US Census Bureau](https://www.census.gov/) geographic and demographic data.

## Quick Links

- **Status Dashboard**: [STATUS.md](./STATUS.md) - What's done, what's in progress
- **Migration Guide**: [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) - Bronze migration strategy
- **dbt Models**: `../../dbt_project/models/` - Transformation layer
  - Silver: `silver/silver_jurisdictions_clean.sql`, `silver_jurisdictions_linked.sql`
  - Gold: `gold/jurisdictions.sql` ✅ **API-READY**

## Migration Status

### ✅ Completed (Use These)
- `load_census_states.py` - Loads 52 states to `bronze_jurisdictions` ✅
- `load_census_municipalities.py` - Loads **19,463 cities/towns** to `bronze_jurisdictions` ✅
- dbt silver models - Clean + link jurisdictions ✅ **TESTED**
- dbt gold model - Final API-ready table ✅ **TESTED**
- **Total: 19,741 jurisdictions in gold table** 🎉

### ⚠️ Deprecated (Migrate to dbt)
- `link_cities_counties_to_search.py` - **DEPRECATED**: Use dbt silver model instead
- `fix_geoid_format.py` - **DEPRECATED**: Replaced by `silver_jurisdictions_clean.sql`

### 📝 TODO (Need Bronze Update)
- `load_census.py` - Complex PySpark script, needs refactor for bronze DB
- `load_county_mappings.py` - Needs PostgreSQL loading logic added

## Data Source

- **Website**: https://www.census.gov/
- **API**: https://www.census.gov/data/developers.html
- **Geography**: https://www.census.gov/geographies.html
- **Coverage**: All US jurisdictions
- **Data Types**: Geographic boundaries, demographics, housing, economic data

## Scripts

### Core Scripts

- **`census_ingestion.py`** - Download Census Gazetteer files (government jurisdictions)
- **`acs_ingestion.py`** ⭐ - Download American Community Survey demographic data
- **`download_shapefiles.py`** ⭐ **NEW** - Download TIGER/Line shapefiles (states, counties, ZIP codes)
- `download_county_mappings.py` - Download Census Geographic Relationship Files
- `create_zip_county_mapping.py` - Create ZIP-to-county mapping table

### New: American Community Survey (ACS) Integration

The **`acs_ingestion.py`** script provides comprehensive demographic data download capabilities:

**Key Features:**
- Download demographic, economic, housing, and health data
- Support for multiple geography levels (county, place, tract)
- Automatic caching to D drive or custom directory
- Census API integration with rate limiting
- 20+ pre-configured key tables

**Quick Start:**
```python
from acs_ingestion import ACSDataIngestion
from pathlib import Path

# Use D drive for storage
acs = ACSDataIngestion(data_dir=Path("D:/open-navigator-data/acs"))

# Download median household income
income_df = await acs.download_acs_data_api("B19013", "county", "*")

# Download child health insurance (oral health focus!)
insurance_df = await acs.download_acs_data_api("B27010", "county", "*")
```

**See Also:**
- Full documentation: `website/docs/data-sources/census-acs.md`
- D drive setup: `website/docs/deployment/d-drive-configuration.md`
- Example script: `examples/download_acs_to_d_drive.py`

## Key Datasets

### Census of Governments (census_ingestion.py)
- Counties (3,200+)
- Municipalities/Cities (19,500+)
- Townships (36,000+)
- School Districts (13,000+)

### American Community Survey (acs_ingestion.py) ⭐
- **Demographics**: Age, race, ethnicity, language
- **Economics**: Income, poverty, employment
- **Health Insurance**: Coverage by age (critical for oral health!)
- **Education**: School enrollment, attainment
- **Housing**: Occupancy, value, rent

### TIGER/Line Shapefiles (download_shapefiles.py) ⭐ NEW
- **States**: 50 states + DC + territories (56 total boundaries)
- **Counties**: 3,143 county boundaries
- **ZIP Codes**: 33,000+ ZIP Code Tabulation Areas (ZCTAs)
- **Format**: Cartographic boundary files (optimized for mapping)
- **Use Cases**: Choropleth maps, spatial joins, jurisdiction boundaries

### Geographic Relationship Files
- ZIP Code Tabulation Area (ZCTA) to County mappings
- County to State mappings
- Place to County mappings

## Usage Examples

### Download TIGER/Line Shapefiles ⭐ NEW

```bash
# Download all shapefiles (states, counties, ZIP codes) for 2023
python scripts/datasources/census/download_shapefiles.py --year 2023

# Download only states and counties
python scripts/datasources/census/download_shapefiles.py --year 2023 --types states counties

# Download and auto-extract ZIP files
python scripts/datasources/census/download_shapefiles.py --year 2023 --extract

# Download only ZIP codes (postal codes)
python scripts/datasources/census/download_shapefiles.py --year 2023 --types zcta
```

**Output Location:** `data/cache/census/shapefiles/{year}/`

**Next Steps:**
```python
import geopandas as gpd

# Load shapefile (from ZIP, no extraction needed!)
states = gpd.read_file("data/cache/census/shapefiles/2023/cb_2023_us_state_500k.zip")

# Convert to GeoJSON for web mapping
states.to_file("data/gold/boundaries/states.geojson", driver="GeoJSON")

# Or save as GeoParquet (more efficient)
states.to_parquet("data/gold/boundaries/states.parquet")
```

**See Full Guide:** `website/docs/data-sources/census-shapefiles.md`

### Download ACS Data to D Drive

```bash
# Download all key demographic tables for all counties
python examples/download_acs_to_d_drive.py --geography county --state "*"

# Download California counties only
python examples/download_acs_to_d_drive.py --geography county --state 06

# Download health insurance data only
python examples/download_acs_to_d_drive.py --health-insurance-only

# List all available tables
python examples/download_acs_to_d_drive.py --list-tables
```

### Download County Mappings

```bash
# Download county relationship files
python download_county_mappings.py

# Create ZIP-county mapping
python create_zip_county_mapping.py
```

### Download Jurisdiction Lists

```bash
# Ingest Census API data
python census_ingestion.py --state MA --dataset acs5
```

## Data License

US Census Bureau data is public domain.
