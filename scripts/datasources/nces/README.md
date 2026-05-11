# National Center for Education Statistics (NCES) Data Source

School district data from the Common Core of Data (CCD).

## 📊 Data Source

- **Website:** https://nces.ed.gov/ccd/
- **Files Page:** https://nces.ed.gov/ccd/files.asp
- **Coverage:** 13,000+ local education agencies (school districts)
- **Update Frequency:** Annual

## 🎯 Purpose

Track school districts for educational civic engagement:
- School district names and locations
- Physical addresses and phone numbers  
- NCES IDs for standardized identification
- Enrollment and demographic data
- District websites

## 📁 Scripts

- `download_nces.py` — download CCD LEA zips to ``data/cache/nces/`` and optional partitioned Parquet under ``data/lake/bronze/`` (pandas + pyarrow, no Spark)
- `load_nces_school_districts_to_bronze.py` — upsert CSV cache into ``bronze.bronze_jurisdictions_school_districts_nces_*`` (incremental by district PK / optional ``--states``)

## 🚀 Usage

### Manual Download (Recommended)

Since NCES URLs change frequently, manual download is most reliable:

1. **Visit:** https://nces.ed.gov/ccd/files.asp

2. **Select:**
   - Fiscal/Nonfiscal: **Nonfiscal**
   - Level: **Local Education Agency (LEA)**
   - School Year: **Latest available** (e.g., 2024-25)

3. **Download:**
   - Find "Directory" section
   - Click "Flat and SAS Files" (ZIP file, ~2-3 MB)

4. **Extract:**
   - Unzip the downloaded file
   - Find the CSV file (e.g., `ccd_lea_029_2425_l_1a_mmddyy.csv`)

5. **Place file:**
   ```bash
   mkdir -p data/cache/nces
   cp <downloaded_file>.csv data/cache/nces/nces_school_districts.csv
   ```

6. **Run ingestion:**
   ```bash
   python scripts/datasources/nces/nces_ingestion.py
   ```

### Automatic Download (If URL Known)

If you have the direct download URL, update the script:

```python
# In nces_ingestion.py
DIRECTORY_URL = "https://nces.ed.gov/ccd/data/zip/ccd_lea_029_2425_l_1a_080824.zip"
```

Then run:
```bash
python scripts/datasources/nces/nces_ingestion.py
```

## 📋 Data Fields

NCES Directory includes:

- **LEAID** - Local Education Agency ID (NCES unique identifier)
- **LEA_NAME** - School district name
- **STATE_ABBR** - State code (2-letter)
- **COUNTY_NAME** - County name
- **LSTREET1** - Physical street address
- **LCITY** - City
- **LZIP** - ZIP code
- **PHONE** - Main phone number
- **WEBSITE** - Official district website URL
- **ENROLLMENT** - Total student enrollment
- **TYPE** - District type (regular, charter, etc.)

## 🔄 Type of Load

**CREATE/ENRICHMENT LOAD** - Creates new school district records or enriches existing jurisdictions

## 📊 Integration with Other Sources

School districts can be matched to:
- **WikiData** via NCES ID (`P6545` property)
- **Census** via state + county + city
- **Government Websites** via official URLs

## ⚠️ Notes

- NCES updates data annually (typically August/September)
- Directory files are ~2-3 MB (manageable size)
- Membership files are much larger (62 MB) - use only if needed
- CSV files may use tab-delimited format (not comma-separated)
- Some districts may have missing website URLs

## 🔗 Related Data Files

From the same NCES page, you can also get:

- **Membership** - Student counts by grade, race/ethnicity, sex
- **Staff** - Teacher and staff counts
- **School** - Individual school-level data

These are useful for deeper educational analysis but not required for basic district identification.
