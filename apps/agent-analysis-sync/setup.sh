#!/usr/bin/env bash
# Validate + deploy the agent-analysis-sync bundle (dbt-only, Databricks-resident).
#
#   ./setup.sh            # validate + deploy to dev (schedule paused)
#   ./setup.sh prod       # deploy to prod
#
# PREREQUISITE: the UC source tables must be loaded once (from a machine with
# local-warehouse access) — judges never need this step, only re-runs of the job:
#   python -m ingestion.databricks.load_transcripts_to_uc --limit 150
set -euo pipefail
cd "$(dirname "$0")"

TARGET="${1:-dev}"
PROFILE="opennav-prod"

echo "==> Validating bundle"
databricks bundle validate --strict -t "$TARGET" --profile "$PROFILE"

echo "==> Deploying bundle to '$TARGET' (schedule stays PAUSED until verified)"
databricks bundle deploy -t "$TARGET" --profile "$PROFILE"

cat <<EOF

Deployed. To run the analysis (idempotent — re-run to catch up the backlog):
  databricks bundle run agent_analysis_sync -t $TARGET --profile $PROFILE

Inspect: ${UC_CATALOG:-dbw_opennav_prod_eastus_001}.open_navigator_analysis
  bronze_transcript_analysis / silver_* / gold_event_{meeting,decision}_analysis

Scale a batch / schedule on:
  --var analysis_batch_size=0 (all)   --var schedule_pause=UNPAUSED
EOF
