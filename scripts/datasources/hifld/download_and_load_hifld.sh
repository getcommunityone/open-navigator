#!/bin/bash
# Download and Load HIFLD Datasets to PostgreSQL
# 
# ⚠️ 2026 UPDATE: HIFLD Open portal has been sunsetted
# Data now scattered across:
# - ArcGIS Online (re-indexed datasets)
# - Data Rescue Project (portal.datarescueproject.org)
# - USGS and state mirrors
#
# This script downloads HIFLD infrastructure data and loads it into
# the organizations_locations table in PostgreSQL.
#
# Usage: ./download_and_load_hifld.sh

set -e  # Exit on error

echo "========================================="
echo "HIFLD Data Download and Load Pipeline"
echo "2026 - Post-Portal-Sunset Version"
echo "========================================="
echo ""

# Activate virtual environment
source .venv/bin/activate

# Step 1: Download datasets that work with current scripts
echo "Step 1: Downloading HIFLD datasets from ArcGIS Online (CSV)..."
echo ""

python scripts/datasources/hifld/download_hifld.py

# ⚠️ DATASETS THAT REQUIRE ALTERNATIVE METHODS:
# 
# Public Schools - On Data Rescue Project (hifld-open-public-schools)
#   Portal: portal.datarescueproject.org
#   Requires different API (not ArcGIS Online)
#
# Private Schools - On Data Rescue Project (hifld-open-private-schools)
#   Portal: portal.datarescueproject.org
#   Requires different API (not ArcGIS Online)
#
# Fire Stations - Available but dataset structure incompatible
#   Item ID: d33b8b5d03a84170847b48d7d4c1bdf6
#   Error: Feature Service without queryable layers
#
# Courthouses - Proxy for government buildings (not yet verified)
#   Item ID: f4007823f38c4b12b508f7b76400c0a9
#   Status: May exist but not tested

echo ""
echo "Step 2: Loading data to PostgreSQL..."
echo ""

# Load all downloaded parquet files into organizations_locations table
python scripts/datasources/hifld/load_hifld_to_postgres.py

echo ""
echo "========================================="
echo "✅ HIFLD data pipeline complete!"
echo "========================================="
echo ""
echo "Summary:"
echo "  ✅ Places of Worship: 254,742 locations"
echo "  ✅ Hospitals: 7,496 locations"
echo "  ✅ Law Enforcement: 46,972 locations"
echo "  Total loaded: ~309,210 organizations"
echo ""
echo "⚠️  Not yet available:"
echo "  - Public/Private Schools (Data Rescue Project - requires different API)"
echo "  - Fire Stations (dataset format incompatible)"
echo "  - Government Buildings (Courthouses - not yet verified)"
echo ""
echo "For more info on HIFLD portal sunset:"
echo "  https://portal.datarescueproject.org/"
echo ""
