---
sidebar_position: 5
---

# Census Bureau Shapefiles

Geographic boundary data from the U.S. Census Bureau TIGER/Line program.

## Overview

The Census Bureau provides comprehensive geographic boundary files (shapefiles) for all U.S. administrative divisions. These are essential for mapping, spatial analysis, and geographic visualization.

**Data Source:** [U.S. Census Bureau TIGER/Line Files](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html)

**Update Frequency:** Annual (typically released in summer)

**Latest Vintage:** 2023

## Available Boundary Types

### 1. States
- **File:** `cb_{year}_us_state_500k.zip`
- **Features:** 50 states + DC + territories (56 total)
- **Use Cases:** State-level aggregation, choropleth maps, jurisdiction lookup
- **Size:** ~3 MB

### 2. Counties
- **File:** `cb_{year}_us_county_500k.zip`
- **Features:** 3,143 counties and county equivalents
- **Use Cases:** County-level analysis, regional mapping, jurisdiction boundaries
- **Size:** ~15 MB

### 3. ZIP Code Tabulation Areas (ZCTAs)
- **File:** `cb_{year}_us_zcta520_500k.zip`
- **Features:** ~33,000 ZIP Code Tabulation Areas
- **Use Cases:** Postal code mapping, demographic analysis, service area definition
- **Size:** ~350 MB
- **Note:** ZCTAs are statistical approximations of ZIP codes, not exact postal routes

## Cartographic vs. Full TIGER Files

We use **Cartographic Boundary Files** (cb_* prefix) instead of full TIGER/Line files because:

| Feature | Cartographic (cb_) | Full TIGER (tl_) |
|---------|-------------------|------------------|
| **Detail** | Simplified 1:500k | High detail 1:100k |
| **File Size** | Smaller (faster downloads) | Larger (slower) |
| **Rendering** | Faster (optimized for maps) | Slower |
| **Water Boundaries** | Clipped at shoreline | Include water features |
| **Use Case** | Web mapping, visualization | Detailed GIS analysis |

**Recommendation:** Use cartographic files for Open Navigator's web-based mapping.

## Installation & Setup

### Prerequisites

```bash
# Shapefile processing requires geopandas
pip install geopandas pyogrio
```

### Download Script

```bash
# Download all shapefiles for 2023
python scripts/datasources/census/download_shapefiles.py --year 2023

# Download only states and counties
python scripts/datasources/census/download_shapefiles.py --year 2023 --types states counties

# Download and extract automatically
python scripts/datasources/census/download_shapefiles.py --year 2023 --extract

# Download only ZIP codes
python scripts/datasources/census/download_shapefiles.py --year 2023 --types zcta
```

## Data Storage

Downloaded shapefiles are cached in:
```
data/cache/census/shapefiles/{year}/
├── cb_2023_us_state_500k.zip
├── cb_2023_us_county_500k.zip
└── cb_2023_us_zcta520_500k.zip
```

Extracted files (if `--extract` used):
```
data/cache/census/shapefiles/{year}/
├── cb_2023_us_state_500k/
│   ├── cb_2023_us_state_500k.shp       # Geometry
│   ├── cb_2023_us_state_500k.shx       # Shape index
│   ├── cb_2023_us_state_500k.dbf       # Attributes
│   ├── cb_2023_us_state_500k.prj       # Projection
│   └── cb_2023_us_state_500k.xml       # Metadata
├── cb_2023_us_county_500k/
└── cb_2023_us_zcta520_500k/
```

## Loading Shapefiles

### GeoPandas (Recommended)

```python
import geopandas as gpd
from pathlib import Path

# Load from ZIP (no extraction needed!)
states = gpd.read_file("data/cache/census/shapefiles/2023/cb_2023_us_state_500k.zip")

# Or from extracted directory
states = gpd.read_file("data/cache/census/shapefiles/2023/cb_2023_us_state_500k/cb_2023_us_state_500k.shp")

# View data
print(states.head())
print(f"Total states: {len(states)}")
print(f"CRS: {states.crs}")  # Should be EPSG:4269 (NAD83)
```

### Key Attributes

#### States
- `STATEFP` - State FIPS code (2 digits)
- `STUSPS` - State postal abbreviation (2 letters)
- `NAME` - State name
- `ALAND` - Land area (square meters)
- `AWATER` - Water area (square meters)

#### Counties  
- `STATEFP` - State FIPS code
- `COUNTYFP` - County FIPS code (3 digits)
- `GEOID` - Combined state+county FIPS (5 digits)
- `NAME` - County name
- `NAMELSAD` - Full name with legal/statistical designation

#### ZCTAs
- `ZCTA5CE20` - 5-digit ZCTA code
- `ALAND` - Land area (square meters)
- `AWATER` - Water area (square meters)

## Conversion to Other Formats

### GeoJSON (for web mapping)

```python
import geopandas as gpd

# Load shapefile
states = gpd.read_file("data/cache/census/shapefiles/2023/cb_2023_us_state_500k.zip")

# Convert to Web Mercator for web maps
states_web = states.to_crs("EPSG:3857")

# Save as GeoJSON
states_web.to_file("data/gold/boundaries/states.geojson", driver="GeoJSON")
```

### GeoParquet (for efficient storage)

```python
import geopandas as gpd

# Load shapefile
counties = gpd.read_file("data/cache/census/shapefiles/2023/cb_2023_us_county_500k.zip")

# Save as GeoParquet (smaller, faster than GeoJSON)
counties.to_parquet("data/gold/boundaries/counties.parquet")

# Load back
counties = gpd.read_parquet("data/gold/boundaries/counties.parquet")
```

### Simplified Geometries (for faster rendering)

```python
import geopandas as gpd

# Load and simplify
zcta = gpd.read_file("data/cache/census/shapefiles/2023/cb_2023_us_zcta520_500k.zip")

# Simplify to 100m tolerance (reduces file size)
zcta_simple = zcta.copy()
zcta_simple['geometry'] = zcta_simple.geometry.simplify(tolerance=100)

# Save simplified version
zcta_simple.to_file("data/gold/boundaries/zcta_simplified.geojson", driver="GeoJSON")
```

## Integration with Open Navigator

### 1. Jurisdiction Boundary Lookup

Match jurisdiction names to their geographic boundaries:

```python
import geopandas as gpd
import pandas as pd

# Load jurisdictions from Open Navigator
jurisdictions = pd.read_parquet("data/gold/jurisdictions_deduplicated.parquet")

# Load county boundaries
counties = gpd.read_file("data/cache/census/shapefiles/2023/cb_2023_us_county_500k.zip")

# Merge on name + state
merged = jurisdictions.merge(
    counties[['GEOID', 'NAME', 'STATEFP', 'geometry']],
    left_on=['jurisdiction_name', 'state_code'],
    right_on=['NAME', 'STATEFP'],
    how='left'
)

# Save with geometries
merged_gdf = gpd.GeoDataFrame(merged, geometry='geometry')
merged_gdf.to_parquet("data/gold/jurisdictions_with_boundaries.parquet")
```

### 2. Choropleth Mapping

Create interactive maps colored by data values:

```python
import geopandas as gpd
import folium

# Load state boundaries
states = gpd.read_file("data/cache/census/shapefiles/2023/cb_2023_us_state_500k.zip")

# Example: Count of jurisdictions per state
jurisdiction_counts = jurisdictions.groupby('state_code').size().reset_index(name='count')

# Merge with geometries
states_data = states.merge(
    jurisdiction_counts,
    left_on='STUSPS',
    right_on='state_code',
    how='left'
)

# Create choropleth map
m = folium.Map(location=[39.8, -98.5], zoom_start=4)
folium.Choropleth(
    geo_data=states_data,
    data=states_data,
    columns=['STUSPS', 'count'],
    key_on='feature.properties.STUSPS',
    fill_color='YlOrRd',
    legend_name='Jurisdiction Count'
).add_to(m)

m.save('jurisdiction_heatmap.html')
```

### 3. Spatial Joins

Find which jurisdictions overlap with which ZIP codes:

```python
import geopandas as gpd

# Load data
counties = gpd.read_file("data/cache/census/shapefiles/2023/cb_2023_us_county_500k.zip")
zcta = gpd.read_file("data/cache/census/shapefiles/2023/cb_2023_us_zcta520_500k.zip")

# Spatial join (find which county each ZCTA is in)
zcta_counties = gpd.sjoin(
    zcta[['ZCTA5CE20', 'geometry']],
    counties[['GEOID', 'NAME', 'geometry']],
    how='left',
    predicate='intersects'
)

# Save mapping
zcta_counties.to_parquet("data/gold/zcta_to_county_mapping.parquet")
```

## Use Cases in Open Navigator

### 1. Policy Heatmap Enhancement
- Add actual geographic boundaries to policy heatmap
- Show exact county/state shapes instead of markers
- Enable click-to-zoom on boundary

### 2. Geographic Search
- "Find all nonprofits in ZIP code 35401"
- "Show meetings within 50 miles of this location"
- Point-in-polygon lookups for jurisdiction detection

### 3. Service Area Visualization
- Display coverage areas for advocacy organizations
- Show legislative district boundaries
- Map nonprofit service regions

### 4. Data Validation
- Verify jurisdiction names against official boundaries
- Detect geocoding errors (city in wrong state)
- Fill missing location data using boundaries

## File Size Considerations

**Full Downloads:**
- States: ~3 MB
- Counties: ~15 MB  
- ZCTAs: ~350 MB
- **Total: ~368 MB**

**Recommendations:**
- Store in `data/cache/` (excluded from git)
- Convert to GeoParquet for 50-70% size reduction
- Simplify geometries for web display
- Consider only downloading needed regions (e.g., priority states)

## License & Attribution

**License:** Public Domain (U.S. Government Work)

**Attribution (recommended):**
```
Boundary data from U.S. Census Bureau TIGER/Line Shapefiles
https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
```

## Troubleshooting

### Installation Issues

If GeoPandas install fails:
```bash
# Use conda (easier for spatial packages)
conda install geopandas

# Or use pyogrio instead of fiona
pip install geopandas pyogrio
```

### CRS/Projection Issues

TIGER files use NAD83 (EPSG:4269). For web maps, convert to Web Mercator (EPSG:3857):
```python
gdf_web = gdf.to_crs("EPSG:3857")
```

### Large File Handling

For ZCTAs (350 MB), consider:
```python
# Load only needed columns
zcta = gpd.read_file("cb_2023_us_zcta520_500k.zip", columns=['ZCTA5CE20', 'geometry'])

# Filter to specific states
zcta_al = zcta[zcta['ZCTA5CE20'].str.startswith('35')]  # Alabama ZCTAs
```

## Related Data Sources

- [Census ACS Data](./census-acs.md) - Demographic data for these boundaries
- [Jurisdiction Discovery](./jurisdiction-discovery.md) - Finding local governments
- [NCES Data](./census-data.md) - School district boundaries (separate)

## Next Steps

After downloading shapefiles:
1. Convert to GeoParquet for efficient storage
2. Join with Open Navigator jurisdiction data
3. Integrate into PolicyMap component for boundary display
4. Add spatial search capabilities to API
