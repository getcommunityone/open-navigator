# Databricks notebook source
# MAGIC %md
# MAGIC # Sync: Unity Catalog Delta → Lakebase synced tables
# MAGIC
# MAGIC For each UC Delta serving table, create a Lakebase **synced table**
# MAGIC (UC Delta → Lakebase Postgres). Uses the Autoscaling Postgres REST API
# MAGIC (`/api/2.0/postgres/...`) directly via the workspace client — the stable
# MAGIC surface the `databricks postgres create-synced-table` CLI wraps. (DABs
# MAGIC `synced_database_tables` targets the *Provisioned* API and must not be
# MAGIC used for Autoscaling projects.)
# MAGIC
# MAGIC Idempotent: a table that already exists is left in place and its pipeline
# MAGIC is refreshed (best-effort) so re-runs pick up the freshly-ingested data.

# COMMAND ----------
# MAGIC %run ./serving_tables

# COMMAND ----------
dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("serving_schema", "open_navigator_serving")
dbutils.widgets.text("lakebase_catalog", "opennav_lakebase")
dbutils.widgets.text("lakebase_project_id", "opennav-serving")
dbutils.widgets.text("lakebase_branch", "production")
dbutils.widgets.text("lakebase_postgres_database", "databricks_postgres")
dbutils.widgets.text("sync_schema", "public")
dbutils.widgets.text("sync_mode", "SNAPSHOT")

catalog = dbutils.widgets.get("catalog")
serving_schema = dbutils.widgets.get("serving_schema")
lakebase_catalog = dbutils.widgets.get("lakebase_catalog")
project_id = dbutils.widgets.get("lakebase_project_id")
branch = dbutils.widgets.get("lakebase_branch")
pg_database = dbutils.widgets.get("lakebase_postgres_database")
sync_schema = dbutils.widgets.get("sync_schema")
sync_mode = dbutils.widgets.get("sync_mode").upper()

branch_resource = f"projects/{project_id}/branches/{branch}"

# COMMAND ----------
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
api = w.api_client


def _already_exists(exc: Exception) -> bool:
    s = str(exc).lower()
    return "already" in s or "exist" in s


# COMMAND ----------
# Register the Lakebase database as a UC catalog (one-time, idempotent). This is
# what binds {lakebase_catalog} -> (project, branch, postgres_database); the
# synced-table calls below need only the catalog name as a result.
try:
    api.do(
        "POST",
        "/api/2.0/postgres/catalogs",
        query={"catalog_id": lakebase_catalog},
        body={
            "spec": {
                "postgres_database": pg_database,
                "branch": branch_resource,
            }
        },
    )
    print(f"registered UC catalog '{lakebase_catalog}' -> {branch_resource}/{pg_database}")
except Exception as exc:
    if _already_exists(exc):
        print(f"UC catalog '{lakebase_catalog}' already registered")
    else:
        raise

# COMMAND ----------
created, existed, failed = [], [], []

for table, pk in TABLES.items():
    # UC Delta + Lakebase use the serving name (browse_* → transcript_* relabel);
    # the PK is keyed by the source name in TABLES.
    dest_name = serving_name(table)
    synced_id = f"{lakebase_catalog}.{sync_schema}.{dest_name}"
    spec = {
        "source_table_full_name": f"{catalog}.{serving_schema}.{dest_name}",
        "primary_key_columns": pk,
        "scheduling_policy": sync_mode,
        "create_database_objects_if_missing": True,
        # The CreateSyncedTable REST API requires the Lakebase target (branch +
        # postgres_database) in the spec — the registered catalog alone is not
        # enough ("Field spec.postgres_database must be defined").
        "branch": branch_resource,
        "postgres_database": pg_database,
        # storage_catalog MUST be a regular UC catalog (not the Lakebase one) —
        # it holds the managed sync pipeline's metadata.
        "new_pipeline_spec": {
            "storage_catalog": catalog,
            "storage_schema": serving_schema,
        },
    }
    try:
        api.do(
            "POST",
            "/api/2.0/postgres/synced_tables",
            query={"synced_table_id": synced_id},
            body={"spec": spec},
        )
        created.append(table)
        print(f"CREATE {synced_id}  (pk={pk}, {sync_mode})")
    except Exception as exc:
        if not _already_exists(exc):
            failed.append((table, str(exc)))
            print(f"FAIL   {synced_id}: {exc}")
            continue
        existed.append(table)
        print(f"EXISTS {synced_id} — refreshing")
        # Best-effort refresh so a re-run reflects the new ingest. The synced
        # table's managed pipeline is what we trigger.
        try:
            st = api.do("GET", f"/api/2.0/postgres/synced_tables/{synced_id}")
            status = st.get("status") or {}
            pipeline_id = (
                status.get("pipeline_id")
                or (status.get("provisioning_status") or {}).get("pipeline_id")
                or (st.get("spec") or {}).get("existing_pipeline_id")
            )
            if pipeline_id:
                w.pipelines.start_update(pipeline_id=pipeline_id)
                print(f"  started pipeline update {pipeline_id}")
            else:
                print("  no pipeline id found — relies on the synced-table schedule")
        except Exception as exc2:
            print(f"  refresh skipped: {exc2}")

# COMMAND ----------
print(
    f"synced tables — created={len(created)} existed={len(existed)} failed={len(failed)}"
)
if failed:
    raise Exception(f"synced-table failures: {failed}")
