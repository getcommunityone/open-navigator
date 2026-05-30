---
sidebar_position: 8
---

# Census American Community Survey (ACS)

Add demographic, economic, housing, and social data from the U.S. Census Bureau's American Community Survey to enrich your civic engagement analysis.

## Overview

The **American Community Survey (ACS)** is the premier source for detailed population and housing information about America. It provides data for communities across the United States, Puerto Rico, and Island Areas.

### What's Included

- **Demographics**: Age, race, ethnicity, language, citizenship
- **Economics**: Income, poverty, employment, occupation
- **Housing**: Occupancy, value, rent, housing costs
- **Education**: School enrollment, educational attainment
- **Health**: Health insurance coverage by age and type
- **Social**: Disability status, veteran status, commuting

### ACS vs. Census of Governments

| Dataset | Purpose | What it Measures |
|---------|---------|------------------|
| **Census of Governments** | Jurisdiction discovery | Lists all government entities (cities, counties, districts) |
| **American Community Survey (ACS)** | Community demographics | Population characteristics, economics, housing |

**Use both together**: Census of Governments tells you *which* jurisdictions exist, ACS tells you *about the people* who live there.

## 🚀 Quick Start

### 1. Get a Census API Key (Recommended)

While optional, an API key increases your rate limit from 500 to 5,000 requests per day.

1. Visit: https://api.census.gov/data/key_signup.html
2. Enter your email and organization
3. Check email for API key
4. Add to `.env` file:

```bash
CENSUS_API_KEY=your_key_here
```

### 2. Run the ACS Ingestion Script

```bash
# Activate virtual environment
source .venv/bin/activate

# Navigate to script directory
cd scripts/datasources/census

# Run the example (downloads sample data)
python acs_ingestion.py
```

This will:
- Download median household income for all U.S. counties
- Download health insurance data for California
- Cache data to `data/cache/acs/`

## 📊 Available Data Tables

### Demographics

| Table Code | Description | Use Case |
|------------|-------------|----------|
| B01001 | Sex by Age | Identify communities with children (dental screening priority) |
| B02001 | Race | Analyze health equity across racial groups |
| B03002 | Hispanic or Latino Origin by Race | Understand demographic composition |
| B05001 | Nativity and Citizenship Status | Language access planning |
| B16001 | Language Spoken at Home | Multilingual outreach needs |

### Economics

| Table Code | Description | Use Case |
|------------|-------------|----------|
| B19013 | Median Household Income | Target low-income communities for programs |
| B17001 | Poverty Status | Medicaid eligibility analysis |
| B23025 | Employment Status | Economic health assessment |
| C24010 | Sex by Occupation | Workforce composition |

### Health Insurance ⭐ **Critical for Oral Health Policy**

| Table Code | Description | Use Case |
|------------|-------------|----------|
| B27001 | Health Insurance Coverage Status by Age | Overall insurance coverage rates |
| B27010 | Health Insurance Coverage (Under 19) | **Child dental insurance coverage** |
| C27007 | Medicaid/Means-Tested Public Coverage | Medicaid enrollment by community |

### Education

| Table Code | Description | Use Case |
|------------|-------------|----------|
| B15003 | Educational Attainment | Community education levels |
| B14001 | School Enrollment by Age | Number of school-aged children |

## 💻 Usage Examples

### Example 1: Download Data for All Counties

```python
import asyncio
from pathlib import Path
from scripts.datasources.census.acs_ingestion import ACSDataIngestion

async def download_county_data():
    # Initialize with default cache directory
    acs = ACSDataIngestion()
    
    # Download median household income for all U.S. counties
    income_df = await acs.download_acs_data_api(
        table="B19013",        # Median household income
        geography="county",    # County level
        state="*"             # All states
    )
    
    print(f"Downloaded {len(income_df)} counties")
    print(income_df.head())

asyncio.run(download_county_data())
```

### Example 2: Child Health Insurance Coverage

**Critical for oral health policy analysis!**

```python
async def analyze_child_insurance():
    acs = ACSDataIngestion()
    
    # Download health insurance for children under 19
    child_insurance_df = await acs.download_acs_data_api(
        table="B27010",        # Health insurance (Under 19)
        geography="county",
        state="*"
    )
    
    # This table includes:
    # - With health insurance
    # - With public coverage (Medicaid/CHIP)
    # - With private coverage
    # - No health insurance
    
    return child_insurance_df

df = asyncio.run(analyze_child_insurance())
```

### Example 3: Download Multiple Tables at Once

```python
async def download_comprehensive_data():
    acs = ACSDataIngestion()
    
    # Download all key demographic tables for California
    ca_data = await acs.download_all_demographics(
        geography="county",
        state="06"  # California FIPS code
    )
    
    # Returns dictionary with multiple DataFrames
    for table_code, df in ca_data.items():
        print(f"{table_code}: {len(df)} counties")

asyncio.run(download_comprehensive_data())
```

### Example 4: Use Cached Data

```python
acs = ACSDataIngestion()

# First call downloads from API
df1 = await acs.download_acs_data_api("B19013", "county", "*")

# Subsequent calls use cached Parquet file (instant!)
df2 = acs.get_cached_data("B19013", "county", "*")

print(f"Same data: {df1.equals(df2)}")  # True
```

## 🗄️ Data Storage Options

### Option 1: Default Cache (Recommended for Development)

```python
# Uses data/cache/acs/ in project directory
acs = ACSDataIngestion()
```

**Location**: `/home/developer/projects/open-navigator/data/cache/acs/`

### Option 2: D Drive (Windows)

```python
from pathlib import Path

# Store all ACS data on D drive
acs = ACSDataIngestion(data_dir=Path("D:/open-navigator-data/acs"))
```

**Location**: `D:\open-navigator-data\acs\`

### Option 3: External Drive (Linux/Mac)

```python
# Mount external drive first, then:
acs = ACSDataIngestion(data_dir=Path("/mnt/external/acs-data"))
```

**Location**: `/mnt/external/acs-data/`

### Option 4: Network Storage

```python
# For shared team access
acs = ACSDataIngestion(data_dir=Path("//server/shared/acs"))
```

## 📁 Data File Format

Downloaded data is cached as **Parquet files** for fast loading:

```
data/cache/acs/
├── B19013_county_*_2022.parquet   # Median income, all counties
├── B27010_county_06_2022.parquet  # Child insurance, CA only
├── B01001_place_*_2022.parquet    # Age/sex, all cities
└── acs_2022_ALL/                  # Bulk download (if used)
```

**Parquet advantages**:
- 10x smaller than CSV
- 100x faster to load
- Preserves data types
- Columnar storage (efficient queries)

## 🌍 Geography Levels

ACS data is available at multiple geographic levels:

| Level | Code | Example | Records (approx.) |
|-------|------|---------|-------------------|
| **National** | `us` | United States | 1 |
| **State** | `state` | California, Texas | 50 |
| **County** | `county` | Los Angeles County | 3,200 |
| **Place** | `place` | San Francisco city | 19,500 |
| **Tract** | `tract` | Neighborhood-level | 85,000 |
| **County Subdivision** | `cousub` | Townships | 36,000 |

**Choose based on your analysis needs**:
- **State-level**: Policy comparison across states
- **County-level**: Regional analysis
- **Place-level**: City-specific programs
- **Tract-level**: Neighborhood targeting (large datasets!)

## 🔗 Integration with Open Navigator

### Enriching Jurisdiction Data

Combine ACS demographics with jurisdiction discovery:

```python
from discovery.census_ingestion import CensusGovernmentIngestion
from scripts.datasources.census.acs_ingestion import ACSDataIngestion

# Step 1: Get list of all counties
census = CensusGovernmentIngestion()
counties_df = await census.download_census_data("counties")

# Step 2: Add demographic data from ACS
acs = ACSDataIngestion()
demographics = await acs.download_acs_data_api("B19013", "county", "*")

# Step 3: Join on FIPS code
enriched = counties_df.merge(demographics, on="fips", how="left")

# Now you have: county name, URL, population, AND median income!
```

### Targeting High-Need Communities

Identify counties for oral health program targeting:

```python
async def find_high_need_counties():
    acs = ACSDataIngestion()
    
    # Get poverty data
    poverty_df = await acs.download_acs_data_api("B17001", "county", "*")
    
    # Get child health insurance
    child_insurance_df = await acs.download_acs_data_api("B27010", "county", "*")
    
    # Combine datasets
    combined = poverty_df.merge(child_insurance_df, on=["state", "county"])
    
    # Filter for high poverty + low insurance coverage
    high_need = combined[
        (combined["poverty_rate"] > 0.15) &  # > 15% poverty
        (combined["uninsured_children"] > 100)  # > 100 uninsured kids
    ]
    
    return high_need
```

## ⚡ Performance Tips

### 1. Use State Filters

```python
# ❌ Slow: Downloads all 3,200 counties
all_counties = await acs.download_acs_data_api("B19013", "county", "*")

# ✅ Fast: Downloads only California's 58 counties
ca_counties = await acs.download_acs_data_api("B19013", "county", "06")
```

### 2. Leverage Caching

```python
# First run: Downloads from API (slow)
df1 = await acs.download_acs_data_api("B19013", "county", "*")

# Second run: Loads from Parquet cache (instant!)
df2 = acs.get_cached_data("B19013", "county", "*")
```

### 3. Download Multiple Tables in Parallel

```python
async def parallel_download():
    acs = ACSDataIngestion()
    
    # Download 3 tables simultaneously
    results = await asyncio.gather(
        acs.download_acs_data_api("B19013", "county", "*"),
        acs.download_acs_data_api("B27010", "county", "*"),
        acs.download_acs_data_api("B17001", "county", "*"),
    )
    
    income_df, insurance_df, poverty_df = results
```

### 4. Avoid Bulk Downloads (Unless Necessary)

The Census Bureau offers bulk downloads of ALL ACS data:

```python
# ⚠️ WARNING: This downloads 15 GB!
await acs.download_bulk_files(state="ALL")
```

**Use bulk downloads only if**:
- You need 100+ tables
- You need tract-level data for entire U.S.
- You're doing large-scale research

**Otherwise**: Use targeted API downloads (much faster!)

## 📚 Resources

### Official Documentation

- **ACS Homepage**: https://www.census.gov/programs-surveys/acs
- **Table Shells**: https://www.census.gov/programs-surveys/acs/technical-documentation/table-shells.html
- **API Documentation**: https://www.census.gov/data/developers/data-sets/acs-5year.html
- **Data Profiles**: https://www.census.gov/acs/www/data/data-tables-and-tools/data-profiles/

### Understanding ACS Data

- **ACS 101**: https://www.census.gov/programs-surveys/acs/about.html
- **When to Use ACS vs. Decennial Census**: https://www.census.gov/programs-surveys/acs/guidance.html
- **Margin of Error**: ACS is a sample survey, all estimates have MOE
- **5-Year vs. 1-Year Estimates**: Use 5-year for small areas (more reliable)

### State FIPS Codes

Common state codes for API queries:

| State | FIPS | State | FIPS |
|-------|------|-------|------|
| Alabama | 01 | Montana | 30 |
| Alaska | 02 | Nebraska | 31 |
| Arizona | 04 | Nevada | 32 |
| Arkansas | 05 | New Hampshire | 33 |
| California | 06 | New Jersey | 34 |
| Colorado | 08 | New Mexico | 35 |
| Connecticut | 09 | New York | 36 |
| Delaware | 10 | North Carolina | 37 |
| Florida | 12 | Ohio | 39 |
| Georgia | 13 | Oklahoma | 40 |
| Hawaii | 15 | Oregon | 41 |
| Illinois | 17 | Pennsylvania | 42 |
| Indiana | 18 | Texas | 48 |
| Iowa | 19 | Utah | 49 |
| Kansas | 20 | Virginia | 51 |
| Louisiana | 22 | Washington | 53 |
| Massachusetts | 25 | Wisconsin | 55 |
| Michigan | 26 | | |

**Full list**: https://www.census.gov/library/reference/code-lists/ansi/ansi-codes-for-states.html

## 🆘 Troubleshooting

### "API request failed: 403"

**Cause**: Rate limit exceeded (500 requests/day without API key)

**Fix**: Get a Census API key (see Quick Start above)

### "Module 'config.settings' has no attribute 'CENSUS_API_KEY'"

**Cause**: API key not set in configuration

**Fix**: Add to `.env` file:
```bash
CENSUS_API_KEY=your_key_here
```

### "No data returned for this geography"

**Cause**: Not all tables are available at all geography levels

**Fix**: Check Census API documentation for table availability by geography

### Downloads are slow

**Solutions**:
1. Use state filters instead of `"*"`
2. Use cached data for repeated queries
3. Download during off-peak hours (late night/early morning EST)
4. Consider bulk downloads if you need many tables

## 🔮 Next Steps

1. **Explore Available Tables**: Run `acs.list_available_tables()`
2. **Download Sample Data**: Try the examples in this guide
3. **Join with Jurisdictions**: Combine ACS demographics with jurisdiction URLs
4. **Build Dashboards**: Create visualizations of demographic data
5. **Target Programs**: Use poverty/insurance data to prioritize outreach

## Related Documentation

- [Census of Governments](./census-governments.md) - Jurisdiction discovery
- [Data Sources Overview](./citations.md) - All data sources
- [D Drive Configuration](../deployment/d-drive-configuration.md) - External storage setup
