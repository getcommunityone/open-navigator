## OSF datasource

This datasource is hosted on OSF at:

- `https://osf.io/mv5e6/files/osfstorage`

### Download (cache + files)

Uses the Python standard library only (no `httpx`). Downloads into `data/cache/osf/osf/`
(see script help for ZIP vs folder fallback).

```bash
python3 scripts/datasources/osf/download_osf_zip.py --page-url https://osf.io/mv5e6/files/osfstorage
```

If you still see `import httpx`, your tree is out of date—pull latest or replace the script with the repo version.

### Load to bronze

Registers extracted files in Postgres (`bronze.bronze_osf_files`): path, size, mtime, sha256.

Use the same Python environment as other bronze loaders (project venv has `psycopg2-binary`):

```bash
# Prefer project venv if present
./.venv/bin/python3 scripts/datasources/osf/load_osf_to_bronze.py
# or
./.venv-dbt/bin/python3 scripts/datasources/osf/load_osf_to_bronze.py
```

System `python3` often lacks `psycopg2`; install then retry:

```bash
python3 -m pip install --user psycopg2-binary
```

Run without DB (smoke test indexing):

```bash
python3 scripts/datasources/osf/load_osf_to_bronze.py --dry-run
```

If `./scripts/datasources/osf/load_osf_to_bronze.py` says `Permission denied`, run with `python3` or `chmod +x` that file.

### Load tabular data → `bronze` schema (RDS + CSV)

Tables are created as **`bronze.bronze_osf_<name>`** (e.g. `bronze.bronze_osf_ledb_candidatelevel`), not a separate schema.

Prefer the **Python** loader (uses `pyreadr`; does not require `Rscript` on PATH). Use the project venv if your system Python blocks `pip` (PEP 668):

```bash
./.venv/bin/pip install pyreadr
./.venv/bin/python scripts/datasources/osf/load_osf_rds_to_bronze.py --data-dir data/cache/osf/osf/Replication
```

If a few RDS files were saved with Latin-1 text and `pyreadr` errors, install R and re-run—the script will fall back to `Rscript` for those files only.

Same rules as below: all `.rds` → one table each; `.csv` only if no same-basename `.rds`.

If you previously loaded with the old layout, you may still have a separate `bronze_osf` schema; new runs use **`bronze.bronze_osf_*`** only. Drop the old schema if you no longer need it: `DROP SCHEMA IF EXISTS bronze_osf CASCADE;`

**Optional (R installed):** `load_osf_rds_to_bronze.R` does the same with `DBI` / `RPostgres`:

```bash
Rscript scripts/datasources/osf/load_osf_rds_to_bronze.R --data-dir data/cache/osf/osf/Replication
```