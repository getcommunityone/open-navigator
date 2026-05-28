# Parcel attribute extraction (Esri REST)

There is **no single free public Esri endpoint** for all ~150M U.S. land parcels with owner and assessed value. Esri’s nationwide Living Atlas parcel layer is a **paid** product (Regrid). To replicate Regrid-style ingestion for free, you query **each county or state GIS** that publishes tax parcels on ArcGIS FeatureServer/MapServer.

This folder implements:

1. **Seed discovery** — OpenAddresses source tree + ArcGIS Hub catalog API  
2. **Validation** — `?f=json` layer probe (Query capability)  
3. **Attribute harvest** — `returnGeometry=false` paginated `query` → CSV  

## Pipeline overview

```text
OpenAddresses clone          ArcGIS Hub API
        │                            │
        ▼                            ▼
 parse_openaddresses_sources    scout_arcgis_hub
        │                            │
        └──────────┬─────────────────┘
                   ▼
         validate_parcel_seeds  (?f=json, Query cap)
                   ▼
      extract_parcel_attributes  (returnGeometry=false)
                   ▼
              flat CSV per county
```

## Strategy 1: OpenAddresses source tree (recommended)

The [OpenAddresses](https://github.com/openaddresses/openaddresses) repo lists thousands of `sources/us/**/*.json` files with Esri `layers.parcels[].data` URLs.

```bash
# Sparse-clone sources/us only (~fast), parse parcel layers, validate first 30
python scripts/datasources/parcels/parse_openaddresses_sources.py \
  --clone \
  --layer-types parcels \
  --validate --validate-limit 30 \
  --output data/cache/parcels/openaddresses_esri_seeds.csv

# Re-run after you already have a checkout at data/cache/openaddresses/openaddresses
python scripts/datasources/parcels/parse_openaddresses_sources.py \
  --repo-path data/cache/openaddresses/openaddresses
```

Output columns include `state`, `county`, `layer_type`, `esri_endpoint`, `source_id` (e.g. `us/al/jefferson.json`).

## Strategy 2: ArcGIS Hub catalog API

Discover layers not yet in OpenAddresses via [Hub datasets API](https://hub.arcgis.com/api/v3/datasets):

```bash
python scripts/datasources/parcels/scout_arcgis_hub.py \
  --pages 10 \
  --query parcels \
  --output data/cache/parcels/hub_discovered_endpoints.csv

python scripts/datasources/parcels/scout_arcgis_hub.py \
  --pages 3 --validate --validate-limit 25
```

Non-Esri Hub items (Experience pages, vector tile-only entries) are skipped automatically.

## Validate seeds before full pulls

Government endpoints go offline often. Validation hits the layer root with `?f=json` and requires `Query` in `capabilities`:

```bash
python scripts/datasources/parcels/validate_parcel_seeds.py \
  --input data/cache/parcels/openaddresses_esri_seeds.csv \
  --url-column esri_endpoint \
  --queryable-only \
  --output data/cache/parcels/openaddresses_queryable.csv
```

## Attribute extraction

```bash
python scripts/datasources/parcels/extract_parcel_attributes.py \
  --url "https://jccgis.jccal.org/server/rest/services/Basemap/Parcels/MapServer/0" \
  --output data/cache/parcels/jefferson_al_parcels.csv

python scripts/datasources/parcels/extract_parcel_attributes.py \
  --url "https://..." \
  --max-records 100 \
  --list-fields \
  --normalize-fields
```

## Schema standardization

County field names differ (`OWNER_NAME` vs `Owner1` vs `M_OWNER`). Use `--normalize-fields` or extend `field_mappings.py` (`CANONICAL_ALIASES`).

| Raw examples | Canonical |
|--------------|-----------|
| `IMPR_VAL`, `BLDG_APPRAISAL` | `appraised_improvement_value` |
| `PROP_ADR`, `SITUS_ADDRESS` | `situs_address` |
| `OWNER1`, `PR_OWNER` | `owner_primary` |

## Related code

- `scripts/datasources/hifld/download_hifld.py` — same ArcGIS pagination pattern  
- Citations: [CITATIONS.md](../../../CITATIONS.md) (OpenAddresses)

## Load to Postgres (`bronze.bronze_addresses`)

Migration: `scripts/deployment/neon/migrations/074_create_bronze_addresses.sql`

```bash
./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/074_create_bronze_addresses.sql

.venv/bin/python scripts/datasources/parcels/load_parcel_addresses_to_bronze.py \
  --csv data/cache/parcels/al/tuscaloosa_county_attrs.csv \
  --state AL --county-fips 01125 --county-name Tuscaloosa \
  --dataset al_tuscaloosa_county_parcels \
  --esri-endpoint "https://services.arcgis.com/AWzSDaKZ41uuVges/ArcGIS/rest/services/Parcels/FeatureServer/0" \
  --truncate
```

Typed columns: `owner_name`, `situs_full`, `appraised_value`, `parcel_number_formatted`, `jurisdiction_id` (`county_01125`), plus full county fields in `raw_attributes` JSONB.

### Batch all counties in a state (e.g. Alabama)

Uses OpenAddresses `sources/us/al/*.json` parcel layers plus `seeds/al_manual_overrides.json` (Tuscaloosa).

```bash
.venv/bin/python scripts/datasources/parcels/batch_state_parcels.py --state AL
```

Progress log: `data/cache/parcels/al/_batch_run.log` — manifest: `data/cache/parcels/al/_batch_manifest.json`.

~37 AL counties have public Esri parcel endpoints; **33 counties** have no entry in OpenAddresses/manual overrides (listed in the log at start).

## Not in scope

- Geometry download, paid nationwide Regrid/Esri layers
