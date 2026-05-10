#!/usr/bin/env Rscript
#
# If R is not installed, use the Python equivalent instead (no R required):
#   python3 scripts/datasources/osf/load_osf_rds_to_bronze.py --data-dir data/cache/osf/osf/Replication
#
# Load OSF replication .rds into schema bronze with table names bronze_osf_<stem>, and load .csv only
# when there is no same-basename .rds / .RDS (e.g. load ledb_candidatelevel.rds,
# skip ledb_candidatelevel.csv).
#
# Requires: DBI, RPostgres
#   install.packages(c("DBI", "RPostgres"))
#
# Environment (defaults match scripts/datasources/osf/load_osf_to_bronze.py):
#   POSTGRES_PASSWORD  (default: password)
#   PGHOST             (default: localhost)
#   PGPORT             (default: 5433)
#   PGDATABASE         (default: open_navigator)
#   PGUSER             (default: postgres)
#
# Usage:
#   Rscript scripts/datasources/osf/load_osf_rds_to_bronze.R
#   Rscript scripts/datasources/osf/load_osf_rds_to_bronze.R --data-dir data/cache/osf/osf/Replication
#   Rscript scripts/datasources/osf/load_osf_rds_to_bronze.R --dry-run

suppressPackageStartupMessages({
  if (!requireNamespace("DBI", quietly = TRUE)) {
    stop("Install DBI: install.packages('DBI')", call. = FALSE)
  }
  if (!requireNamespace("RPostgres", quietly = TRUE)) {
    stop("Install RPostgres: install.packages('RPostgres')", call. = FALSE)
  }
})

args <- commandArgs(trailingOnly = TRUE)
dry_run <- "--dry-run" %in% args
args <- args[args != "--dry-run"]

data_dir <- "data/cache/osf/osf/Replication"
if ("--data-dir" %in% args) {
  i <- which(args == "--data-dir")
  if (length(i) && length(args) > i) {
    data_dir <- args[i + 1L]
    args <- args[-c(i, i + 1L)]
  }
}

if (!dir.exists(data_dir)) {
  stop("Data directory not found: ", data_dir, call. = FALSE)
}

pg_password <- Sys.getenv("POSTGRES_PASSWORD", "password")
pg_host <- Sys.getenv("PGHOST", "localhost")
pg_port <- as.integer(Sys.getenv("PGPORT", "5433"))
pg_db <- Sys.getenv("PGDATABASE", "open_navigator")
pg_user <- Sys.getenv("PGUSER", "postgres")

# pg identifier max 63; "bronze_osf_" is 11 chars -> suffix max 52
.suffix_max <- 52L

.safe_suffix <- function(stem) {
  stem <- tolower(gsub("[^a-zA-Z0-9_]", "_", stem))
  stem <- gsub("_+", "_", stem)
  stem <- gsub("^_+|_+$", "", stem)
  if (!nzchar(stem)) {
    stem <- "unnamed_table"
  }
  if (nchar(stem) > .suffix_max) {
    stem <- substring(stem, 1L, .suffix_max)
  }
  stem
}

.bronze_osf_table_name <- function(stem) {
  paste0("bronze_osf_", .safe_suffix(stem))
}

.list_rds <- function(root) {
  all <- list.files(root, full.names = TRUE, recursive = TRUE)
  all[grepl("\\.rds$", basename(all), ignore.case = TRUE)]
}

.list_csv <- function(root) {
  list.files(
    root,
    pattern = "\\.csv$",
    full.names = TRUE,
    recursive = TRUE,
    ignore.case = TRUE
  )
}

.basename_stem <- function(path) {
  tools::file_path_sans_ext(basename(path))
}

.connect <- function() {
  DBI::dbConnect(
    RPostgres::Postgres(),
    host = pg_host,
    port = pg_port,
    dbname = pg_db,
    user = pg_user,
    password = pg_password
  )
}

.write_table <- function(conn, tbl, df, label) {
  if (dry_run) {
    message("[dry-run] would write ", nrow(df), " rows -> bronze.", tbl, " (", label, ")")
    return(invisible(NULL))
  }
  DBI::dbWriteTable(
    conn,
    DBI::Id(schema = "bronze", table = tbl),
    df,
    overwrite = TRUE,
    row.names = FALSE
  )
  message("OK bronze.", tbl, " (", nrow(df), " rows) ", label)
}

message("Data dir: ", normalizePath(data_dir, mustWork = TRUE))

rds_paths <- .list_rds(data_dir)
if (length(rds_paths) == 0) {
  stop("No .rds files found under ", data_dir, call. = FALSE)
}

stems_rds <- unique(vapply(rds_paths, .basename_stem, ""))
names(stems_rds) <- stems_rds

conn <- if (!dry_run) {
  .connect()
} else {
  NULL
}
on.exit(if (!is.null(conn)) DBI::dbDisconnect(conn), add = TRUE)

if (!is.null(conn)) {
  DBI::dbExecute(conn, "CREATE SCHEMA IF NOT EXISTS bronze")
}

for (p in rds_paths) {
  stem <- .basename_stem(p)
  tbl <- .bronze_osf_table_name(stem)
  message("RDS ", basename(p), " -> ", tbl)
  df <- readRDS(p)
  if (!is.data.frame(df)) {
    warning(
      "Skipping non-data.frame RDS: ", p,
      " (class: ", paste(class(df), collapse = ", "), ")"
    )
    next
  }
  .write_table(conn, tbl, df, basename(p))
}

csv_paths <- .list_csv(data_dir)
for (p in csv_paths) {
  stem <- .basename_stem(p)
  if (stem %in% stems_rds) {
    message("CSV skip (RDS exists): ", basename(p))
    next
  }
  tbl <- .bronze_osf_table_name(stem)
  message("CSV ", basename(p), " -> ", tbl)
  df <- utils::read.csv(p, stringsAsFactors = FALSE, check.names = FALSE, fileEncoding = "UTF-8")
  .write_table(conn, tbl, df, basename(p))
}

message("Done.")
