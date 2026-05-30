---
displayed_sidebar: developersSidebar
---

# Census Bureau Data URL Fix

## Problem
The original Census Bureau data URLs were returning 404 errors because the data structure changed.

## Solution

### Updated URLs (2022 Census of Governments)

The Census Bureau publishes data as **ZIP files containing Excel spreadsheets**, not direct CSV files.

**New URLs:**
- **Counties**: https://www2.census.gov/programs-surveys/gus/tables/2022/cog2022_cg2200org05.zip
- **Municipalities**: https://www2.census.gov/programs-surveys/gus/tables/2022/cog2022_cg2200org06.zip  
- **School Districts**: https://www2.census.gov/programs-surveys/gus/tables/2022/cog2022_cg2200org09.zip
- **Special Districts**: https://www2.census.gov/programs-surveys/gus/tables/2022/cog2022_cg2200org08.zip

### Required Dependencies

To process Excel files from Census Bureau:

```bash
pip install openpyxl
```

### How It Works

1. **Downloads ZIP file** from Census Bureau
2. **Extracts Excel file** (.xlsx) from ZIP
3. **Converts to CSV** using pandas
4. **Caches locally** (7-day cache)

### Installation

```bash
source venv/bin/activate
pip install pyspark delta-spark openpyxl
```

### Usage

```bash
python main.py discover-jurisdictions --limit 10
```

The system will:
- Download Census ZIP files automatically
- Extract and convert Excel → CSV
- Cache for 7 days to avoid re-downloading
- Process jurisdiction data into Delta Lake

---

## Data Source Reference

**Official Page**: https://www.census.gov/data/tables/2022/econ/gus/2022-governments.html

**Available Tables:**
- Table 2: Local Governments by Type and State
- Table 5: County Governments by Population-Size Group
- Table 6: Subcounty General-Purpose Governments
- Table 8: Special District Governments by Function
- Table 9: Public School Systems by Type

**Update Frequency**: Census of Governments runs every 5 years (2017, 2022, 2027...)

**Next Update**: 2027 Census of Governments

---

## Troubleshooting

### Missing openpyxl
```
ModuleNotFoundError: No module named 'openpyxl'
```
**Fix**: `pip install openpyxl`

### ZIP Extraction Fails
Check disk space in `data/cache/census/` directory

### Still Getting 404
The Census Bureau may have moved files. Check:
https://www.census.gov/programs-surveys/gus/data/datasets.html

---

## Alternative: Manual Download

If automated download fails:

1. Visit: https://www.census.gov/data/tables/2022/econ/gus/2022-governments.html
2. Download ZIP files manually
3. Extract Excel files
4. Place in `data/cache/census/` as:
   - `counties_20260421.csv`
   - `municipalities_20260421.csv`
   - etc.

The system will use cached files automatically.
