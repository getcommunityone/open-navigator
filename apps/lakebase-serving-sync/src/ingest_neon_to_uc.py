# Databricks notebook source
# MAGIC %md
# MAGIC # Ingest: prod Neon `public` → Unity Catalog Delta
# MAGIC
# MAGIC Reads each civic-serving table from **prod Neon** over Spark JDBC and
# MAGIC writes it as a UC Delta table in `${catalog}.${serving_schema}` (full
# MAGIC overwrite each run). Those Delta tables are the **source** for the
# MAGIC Lakebase synced tables created by the next task.
# MAGIC
# MAGIC Neon is reachable from Databricks (public internet); the connection URL
# MAGIC comes from a Databricks secret so no credentials live in the bundle.

# COMMAND ----------
# MAGIC %run ./serving_tables

# COMMAND ----------
dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("serving_schema", "open_navigator_serving")
dbutils.widgets.text("neon_secret_scope", "open-navigator")
dbutils.widgets.text("neon_secret_key", "neon-prod-url")
dbutils.widgets.text("sync_mode", "SNAPSHOT")

catalog = dbutils.widgets.get("catalog")
serving_schema = dbutils.widgets.get("serving_schema")
neon_secret_scope = dbutils.widgets.get("neon_secret_scope")
neon_secret_key = dbutils.widgets.get("neon_secret_key")
sync_mode = dbutils.widgets.get("sync_mode").upper()

# COMMAND ----------
import re
from urllib.parse import urlparse


def redact(msg) -> str:
    """Strip any user:password@ credentials from text before it is logged."""
    return re.sub(r"(://[^:/@\s]+:)[^@/\s]+(@)", r"\1***\2", str(msg))


# Strip stray surrounding quotes/whitespace — a secret stored from a quoted
# .env line (NEON_DATABASE_URL="...") would otherwise break URL parsing AND, on
# a parse failure, leak the whole URL (incl. password) into the JDBC error.
raw_url = dbutils.secrets.get(scope=neon_secret_scope, key=neon_secret_key).strip().strip("\"'").strip()
u = urlparse(raw_url)
host, port = u.hostname, (u.port or 5432)
dbname = (u.path or "/").lstrip("/")
if not host or not dbname:
    # Never echo raw_url — it contains the password.
    raise ValueError(
        f"Secret '{neon_secret_scope}/{neon_secret_key}' is not a valid "
        f"postgresql:// URL (host/dbname did not parse — check for stray quotes)."
    )
# jdbc_url deliberately carries only host:port/db (NO credentials) — user and
# password are passed as separate options so they can't land in error text.
jdbc_url = f"jdbc:postgresql://{host}:{port}/{dbname}?sslmode=require"
neon_user, neon_pwd = u.username, u.password
print(f"Neon source: {host}:{port}/{dbname} (sslmode=require)")

# COMMAND ----------
from pyspark.sql import functions as F

spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{serving_schema}`")

# Non-SNAPSHOT synced tables refresh via Change Data Feed — enable it on the
# UC source so TRIGGERED/CONTINUOUS modes work.
enable_cdf = sync_mode != "SNAPSHOT"

results = []
for t in TABLES:
    # Read from Neon under the SOURCE name; write the UC Delta under the serving
    # name (most tables: unchanged; the browse_* → transcript_* set is relabeled).
    dest_name = serving_name(t)
    fq = f"`{catalog}`.`{serving_schema}`.`{dest_name}`"
    try:
        df = (
            spark.read.format("jdbc")
            .option("url", jdbc_url)
            .option("dbtable", f'public."{t}"')
            .option("user", neon_user)
            .option("password", neon_pwd)
            .option("driver", "org.postgresql.Driver")
            .option("fetchsize", "10000")
            .load()
        )
        # Tables with no natural PK get a stable, null-safe surrogate over their
        # (verified-unique) grain so they can be synced — see DERIVED_PK.
        grain = DERIVED_PK.get(t)
        if grain:
            df = df.withColumn(
                "sync_key",
                F.sha2(
                    F.concat_ws(
                        "||", *[F.coalesce(F.col(c).cast("string"), F.lit("")) for c in grain]
                    ),
                    256,
                ),
            )
        df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
            f"{catalog}.{serving_schema}.{dest_name}"
        )
        if enable_cdf:
            spark.sql(
                f"ALTER TABLE {fq} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)"
            )
        n = spark.table(f"{catalog}.{serving_schema}.{dest_name}").count()
        results.append((t, n, "ok"))
        print(f"OK   {t}: {n:,} rows -> {catalog}.{serving_schema}.{dest_name}")
    except Exception as exc:  # isolate per-table failures, fail the run at the end
        results.append((t, -1, redact(exc)))
        print(f"FAIL {t}: {redact(exc)}")

# COMMAND ----------
ok = [r for r in results if r[2] == "ok"]
fails = [r for r in results if r[2] != "ok"]
print(f"ingested {len(ok)}/{len(results)} tables; {len(fails)} failed")
for t, _, err in fails:
    print(f"FAIL {t}: {err}")
if fails:
    # Surface the first real error in the raised message so it shows in the run
    # output even when notebook stdout isn't captured.
    raise Exception(
        f"{len(fails)} table(s) failed. First: {fails[0][0]} -> {fails[0][2]}"
    )
