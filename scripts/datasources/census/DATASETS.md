# Census Datasets Downloaded by `download_bronze.py`

This file documents every Census Bureau dataset the project downloads, the
source URL, the on-disk cache layout, and **which geographic granularities
each dataset reaches** (with a city-level summary at the bottom).

All downloaders are orchestrated by:

```bash
python scripts/download_bronze.py            # download everything
python scripts/download_bronze.py --only acs # one downloader at a time
```

Each step writes its files under `data/cache/census/...` (and a few write
gold-layer parquet to `data/gold/`).

---

## 1. Gazetteer files — `download_census_gazetteer.py`

**Source**: U.S. Census Bureau Gazetteer (2024 vintage)
<https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html>

**What it is**: Tab-delimited reference tables listing every named
geographic entity of a given type, with FIPS/GEOID codes, name, state,
land/water area, internal point lat/lon. Lightweight (~few MB each), no
geometry — just the attributes.

| Sub-type                  | Records | Description                                      |
| ------------------------- | ------- | ------------------------------------------------ |
| `counties`                | ~3.2k   | All US counties + county-equivalents             |
| `municipalities`          | ~32k    | **All incorporated places + CDPs (city-level)**  |
| `townships`               | ~36k    | County subdivisions (MCDs / townships)           |
| `zcta`                    | ~33k    | ZIP Code Tabulation Areas                        |
| `school_districts_unified`| ~10k    | K-12 unified school districts                    |
| `school_districts_elem`   | ~1.7k   | Elementary-only districts                        |
| `school_districts_sec`    | ~600    | Secondary-only districts                         |

**Cache**: `data/cache/census/gazetteer/<sub-type>.csv`
**Gold output**: `data/gold/jurisdictions_{cities,counties,townships,postal_codes,school_districts}.parquet`

---

## 2. Boundary shapefiles — `download_census_shapefiles.py`

**Source**: TIGER/Line **Cartographic Boundary** files (1:500k scale, suitable for mapping)
<https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html>

**What it is**: ZIP archives containing `.shp` / `.shx` / `.dbf` / `.prj`
files with polygon geometry for each entity. Use with GeoPandas:
`geopandas.read_file(zip_path)`.

| Sub-type   | URL pattern                                                         | Notes                                                |
| ---------- | ------------------------------------------------------------------- | ---------------------------------------------------- |
| `states`   | `cb_{year}_us_state_500k.zip`                                       | 56 entities (50 states + DC + territories)           |
| `counties` | `cb_{year}_us_county_500k.zip`                                      | ~3.2k counties                                       |
| `places`   | `cb_{year}_us_place_500k.zip`                                       | **~32k places — city-level boundaries**              |
| `zcta`     | `tl_{year}_us_zcta520.zip` (full TIGER, not CB; CB only exists 2020)| ~33k ZCTAs                                           |

**Cache**: `data/cache/census/shapefiles/{year}/<file>.zip`
Pass `--extract` (or set `supports_extract=True` in the orchestrator step) to also unzip into `<file>/` next to the zip.

---

## 3. School-district shapefiles — `download_census_school_districts.py`

**Source**: TIGER/Line CB (2023+; CB school-district files were not published earlier)

| Sub-type     | URL pattern                          |
| ------------ | ------------------------------------ |
| `unified`    | `cb_{year}_us_unsd_500k.zip`         |
| `elementary` | `cb_{year}_us_elsd_500k.zip`         |
| `secondary`  | `cb_{year}_us_scsd_500k.zip`         |

**Cache**: `data/cache/census/school_districts/{year}/<file>.zip`

Key fields after extraction: `GEOID` (7-digit), `NAME`, `STATEFP`, `LOGRADE`, `HIGRADE`, `ALAND`, `AWATER`.

> **Geography level**: school district. Districts do **not** align with city
> boundaries — a city may span multiple districts and a district may serve
> multiple cities or only part of one.

---

## 4. Geographic relationship files — `download_census_relationships.py`

**Source**: 2020 Census Geographic Relationship Files
<https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.html>

**What it is**: Tab-delimited crosswalks showing which entities of one type
overlap which entities of another type, with land-area measurements (so you
can compute weighted overlaps).

| Sub-type      | Size  | Rows  | What it crosswalks                        |
| ------------- | ----- | ----- | ----------------------------------------- |
| `zcta_county` | ~6.5 MB | ~60k  | ZIP → county overlap (with land area)     |
| `zcta_place`  | ~13 MB  | ~270k | **ZIP → place (city) overlap**            |

**Cache**: `data/cache/census_relationships/<sub-type>.txt`

> ZCTAs aren't true ZIP codes — they're the Census's tabulation
> approximation. One ZCTA frequently spans multiple cities and counties.

---

## 5. Municipalities CSV — `download_census_municipalities.py`

**Source**: Same `2024_Gaz_place_national.zip` as the Gazetteer step's
`municipalities` sub-type. This is essentially a thin standalone fetch of
just the places file, predating the unified gazetteer downloader.

**Cache**: `data/cache/census/municipalities_YYYYMMDD.csv`

> **Note**: This overlaps with `gazetteer.municipalities`. Kept as a
> separate orchestrator step for backwards compat with downstream loaders
> that read the timestamp-suffixed filename.

---

## 6. ACS demographic tables — `download_census_acs_data.py`

**Source**: American Community Survey 5-year estimates via the Census API
<https://api.census.gov/data/{year}/acs/acs5>

**What it is**: Survey-derived estimates (counts, medians) for demographic,
economic, housing, and social indicators. Each "table" (e.g. `B19013`) is a
group of related variables — `B19013` is just median household income;
`B27001` is health-insurance coverage broken out by sex × age bands.

**Default tables downloaded** (12, configurable):

| Table  | Description                                          |
| ------ | ---------------------------------------------------- |
| B01001 | Sex by Age                                           |
| B02001 | Race                                                 |
| B03002 | Hispanic or Latino Origin by Race                    |
| B19013 | Median Household Income                              |
| B17001 | Poverty Status (Individual)                          |
| B23025 | Employment Status                                    |
| B27001 | Health Insurance Coverage Status by Age              |
| B27010 | Health Insurance Coverage by Age (Under 19)          |
| B15003 | Educational Attainment                               |
| B14001 | School Enrollment by Age                             |
| B25077 | Median Home Value                                    |
| B25064 | Median Gross Rent                                    |

For the full table inventory open `scripts/datasources/census/load_acs.py`
(`ACSDataIngestion.ACS_TABLES`) or run:

```bash
python scripts/datasources/census/download_census_acs_data.py --list-tables
```

**Cache**: `data/cache/census/acs/{table}_{geography}_{state}_{year}.parquet`

**Geography options** (set via `--geography` when calling the script directly):

| Option   | What it produces                                           |
| -------- | ---------------------------------------------------------- |
| `county` | One row per county (~3.2k rows per table). **Default.**    |
| `place`  | **One row per incorporated place / CDP — city-level data.**|
| `tract`  | One row per Census tract (~84k tracts; finer than county). |
| `cousub` | One row per county subdivision (township).                 |

> **API key note**: Without `CENSUS_API_KEY` in the environment, the public
> Census API allows ~500 requests/day. A free key (signup at
> <https://api.census.gov/data/key_signup.html>) raises the cap.

> **API limitation**: Some tables (e.g. detailed ones with hundreds of
> variables) cannot be requested for very fine geographies in a single
> call. The script doesn't currently chunk by state for such cases.

---

## What's available at the city level?

Five of the six datasets reach city-level granularity:

| Dataset                              | City-level? | How                                                        |
| ------------------------------------ | :---------: | ---------------------------------------------------------- |
| **Gazetteer — municipalities**       | ✅ Yes      | Reference table of all ~32k places (incorporated + CDPs)   |
| **Boundary shapefiles — places**     | ✅ Yes      | Polygon geometry for all ~32k places                       |
| **Relationship — `zcta_place`**      | ✅ Yes      | ZIP-to-city crosswalk with land-area overlap               |
| **Municipalities CSV (legacy)**      | ✅ Yes      | Same data as Gazetteer's `municipalities` sub-type         |
| **ACS demographic tables**           | ✅ Yes      | Run with `--geography place` for per-city demographics     |
| Boundary shapefiles — states/counties/zcta | ❌ No (coarser geographies) | |
| School-district shapefiles           | ❌ No       | School-district boundaries don't align with city limits    |
| Relationship — `zcta_county`         | ❌ No       | County granularity                                         |

### City-level recipes

**"Give me all the demographics for Tuscaloosa, AL"**

```bash
python scripts/datasources/census/download_census_acs_data.py \
    --geography place \
    --state 01           # Alabama FIPS
```

This downloads each ACS table at place granularity for Alabama
(`{table}_place_01_2022.parquet`). Tuscaloosa's row will have GEOID
`0177256` (state `01` + place `77256`). Cross-reference the place GEOID
using `data/gold/jurisdictions_cities.parquet` (from the Gazetteer step).

**"Give me a polygon I can map for every California city"**

```bash
python scripts/download_bronze.py --only shapefiles --extract
# then in Python:
import geopandas as gpd
places = gpd.read_file("data/cache/census/shapefiles/2025/cb_2025_us_place_500k/cb_2025_us_place_500k.shp")
ca_places = places[places["STATEFP"] == "06"]
```

**"Map ZIP 35401 to the cities it covers"**

```bash
python scripts/download_bronze.py --only relationships
# then load data/cache/census_relationships/zcta_place.txt and filter on ZCTA5CE20 == "35401"
```

---

---

## Bronze tables built from the downloaded files

After `python scripts/load_bronze.py` runs, these tables exist in the
`bronze` schema of the `open_navigator` Postgres database. The two
place-centric crosswalks below are the ones that answer "what county is
this city in?" and "what's this city's primary ZIP?".

### `bronze.bronze_jurisdictions_place_county`

> **What county does this city/town belong to?**

Built by `scripts/datasources/census/load_place_crosswalks.py` via a
GeoPandas spatial overlay of the place and county polygons (reprojected to
EPSG:5070, NAD83 / Conus Albers, for accurate area math). Census 2020 does
not publish a direct place→county relationship file, so we derive it from
the cartographic boundary shapefiles. One row per (place, county) pair —
when a city straddles a county line, it appears multiple times.

| Column           | Type        | Notes                                              |
| ---------------- | ----------- | -------------------------------------------------- |
| `place_geoid`    | varchar(7)  | State FIPS + place FIPS (e.g., `0177256`)          |
| `place_name`     | varchar     | e.g., `Tuscaloosa city`                            |
| `place_state`    | varchar(2)  | State FIPS of the place                            |
| `county_geoid`   | varchar(5)  | State FIPS + county FIPS (e.g., `01125`)           |
| `county_name`    | varchar     | e.g., `Tuscaloosa`                                 |
| `state_fips`     | varchar(2)  | State FIPS of the county                           |
| `overlap_area_m2`| bigint      | Land area of (place ∩ county) in m²                |
| `place_area_m2`  | bigint      | Total land area of the place in m²                 |
| `overlap_pct`    | numeric     | `100 * overlap_area / place_area`                  |
| `is_primary`     | bool        | TRUE for the county with the largest overlap       |
| `vintage_year`   | smallint    | Census shapefile vintage used                      |

**Lookup query**:

```sql
-- Primary county for a given city
SELECT county_geoid, county_name, overlap_pct
FROM bronze.bronze_jurisdictions_place_county
WHERE place_geoid = '0177256' AND is_primary;

-- All counties a place spans, ordered by share
SELECT county_name, overlap_pct
FROM bronze.bronze_jurisdictions_place_county
WHERE place_geoid = '0177256'
ORDER BY overlap_pct DESC;
```

### `bronze.bronze_jurisdictions_place_zcta`

> **What is the primary postal code (ZCTA) for this city/town?**

Built from the Census 2020 `zcta_place.txt` relationship file by rotating
it into a place-centric view. One row per (place, ZCTA) pair, with
`is_primary=TRUE` on the ZCTA whose land overlap with the place is the
largest.

| Column            | Type        | Notes                                                |
| ----------------- | ----------- | ---------------------------------------------------- |
| `place_geoid`     | varchar(7)  | State FIPS + place FIPS                              |
| `place_name`      | varchar     | NAMELSAD of the place                                |
| `zcta`            | varchar(10) | 5-digit ZCTA                                         |
| `state_fips`      | varchar(2)  | First two digits of `place_geoid`                    |
| `arealand_part`   | bigint      | Land area of (place ∩ ZCTA) in m² (Census `AREALAND_PART`) |
| `areawater_part`  | bigint      | Water area of (place ∩ ZCTA) in m²                   |
| `is_primary`      | bool        | TRUE for the ZCTA with the largest land overlap      |

**Lookup query**:

```sql
-- Primary ZIP for a given city
SELECT zcta
FROM bronze.bronze_jurisdictions_place_zcta
WHERE place_geoid = '0177256' AND is_primary;

-- All ZIPs a place covers, biggest overlap first
SELECT zcta, arealand_part
FROM bronze.bronze_jurisdictions_place_zcta
WHERE place_geoid = '0177256'
ORDER BY arealand_part DESC NULLS LAST;
```

---

## What's *not* downloaded by this project (but is available from Census)

For completeness — these are commonly asked for and would be straightforward
follow-up additions if needed:

- **Block-group and block-level shapefiles / ACS tables** (sub-tract granularity).
- **Population estimates (PEP)** — annual non-decennial population by county/place.
- **Decennial Census P/H/PCT tables** — exact counts (not estimates) at finer granularity than ACS.
- **Business Patterns (CBP/ZBP)** — employer counts by industry per county/ZIP.
- **Migration flows** — county-to-county migration estimates.

If you want any of these, drop a request and we can add a downloader step
following the same pattern as the existing ones.
