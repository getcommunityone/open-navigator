#!/bin/bash
# Load OpenCivicData jurisdictions into bronze_jurisdiction_ocd via Python generator
# This generates SQL INSERT statements from the OCD CSV files

python3 << 'PYTHON'
import csv
from pathlib import Path

ocd_cache = Path(__file__).parent.parent.parent / "data" / "cache" / "opencivicdata"

print("BEGIN;")

# Load from country-us.csv
country_csv = ocd_cache / "identifiers" / "country-us.csv"
if country_csv.exists():
    with open(country_csv, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            ocd_id, name = row[0], row[1]
            if not ocd_id or not name or "state:" not in ocd_id:
                continue

            state_code = None
            jtype = None
            parent_ocd = None

            for part in ocd_id.split("/"):
                if "state:" in part:
                    state_code = part.split(":")[1].upper()
                elif "county:" in part:
                    jtype = "county"
                elif "place:" in part:
                    jtype = "place"
                elif "school_district:" in part:
                    jtype = "school_district"
                    if "county:" in ocd_id:
                        parts = ocd_id.split("county:")
                        if len(parts) > 1:
                            county_part = parts[1].split("/")[0]
                            parent_ocd = f"ocd-division/country:us/state:{state_code.lower()}/county:{county_part}"

            if not state_code or not jtype:
                continue

            name_escaped = name.replace("'", "''")
            parent_val = f"'{parent_ocd}'" if parent_ocd else "NULL"
            print(f"INSERT INTO bronze.bronze_jurisdiction_ocd (ocd_id, state_code, jurisdiction_type, name, parent_ocd_id) VALUES ('{ocd_id}', '{state_code}', '{jtype}', '{name_escaped}', {parent_val}) ON CONFLICT DO NOTHING;")

# Load from state-specific local_gov.csv
identifiers_dir = ocd_cache / "identifiers" / "country-us"
if identifiers_dir.exists():
    for state_csv in sorted(identifiers_dir.glob("state-*-local_gov.csv")):
        state_code = state_csv.name.split("-")[1].upper()
        with open(state_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue
                ocd_id, name = row[0], row[1]
                if not ocd_id or not name:
                    continue

                jtype = None
                parent_ocd = None

                if "place:" in ocd_id:
                    jtype = "place"
                elif "council_district:" in ocd_id:
                    jtype = "council_district"
                    if "place:" in ocd_id:
                        parts = ocd_id.split("place:")
                        if len(parts) > 1:
                            place_part = parts[1].split("/")[0]
                            parent_ocd = f"ocd-division/country:us/state:{state_code.lower()}/place:{place_part}"
                elif "ward:" in ocd_id:
                    jtype = "ward"
                    if "place:" in ocd_id:
                        parts = ocd_id.split("place:")
                        if len(parts) > 1:
                            place_part = parts[1].split("/")[0]
                            parent_ocd = f"ocd-division/country:us/state:{state_code.lower()}/place:{place_part}"

                if not jtype:
                    continue

                name_escaped = name.replace("'", "''")
                parent_val = f"'{parent_ocd}'" if parent_ocd else "NULL"
                print(f"INSERT INTO bronze.bronze_jurisdiction_ocd (ocd_id, state_code, jurisdiction_type, name, parent_ocd_id) VALUES ('{ocd_id}', '{state_code}', '{jtype}', '{name_escaped}', {parent_val}) ON CONFLICT DO NOTHING;")

print("COMMIT;")
PYTHON

