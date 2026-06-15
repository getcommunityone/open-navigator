# agent-analysis-sync

Run the civic transcript **analysis prompts on Databricks** via batch LLM
inference (`ai_query`), layered **bronze → silver → gold in dbt**. Replaces the
Gemini/GPU per-row analyze loop. Fully **Databricks-resident at run time** — no
local machine, no Neon, no secret — so it runs anywhere the workspace does
(judges included). Cost-optimized to stay **well under $200**.

```
ONE-TIME BOOTSTRAP (run once from a machine with local-warehouse access):
  ingestion.databricks.load_transcripts_to_uc
    local gold.event_documents (unanalyzed) ──parquet→UC Volume→MERGE──▶ UC tables:
      {work_schema}.transcript_to_analyze   (video_id, transcript_text)
      {work_schema}.analysis_prompt          (the active prompt)

JUDGE-RUNNABLE (the bundle — dbt only, re-runnable, all in Databricks):
  dbt_build
    bronze  bronze_transcript_analysis    ai_query (gpt-oss-120b, escalate→llama-4-maverick)
                                           incremental on video_id + batched (analysis_batch_size)
    silver  silver_meeting_analysis        JSON → typed meeting rows
            silver_decision_analysis       decisions[] exploded → typed rows
    gold    gold_event_meeting_analysis    shaped to the event_meeting contract
            gold_event_decision_analysis   shaped to the event_decision contract
```

**Layering follows CLAUDE.md:** the only Python is *ingestion* (the one-time
loader); **dbt owns every transformation and all JSON extraction**. The bronze
`ai_query` model is incremental on `video_id` and capped by `analysis_batch_size`,
so **re-running the job catches up the backlog a batch at a time** — and never
re-pays for an already-analyzed transcript.

## Why the transcripts must be loaded first

No Databricks catalog carries transcript *text* — the serving layer
(`open_navigator_serving`, Lakebase) holds analyzed *outputs* only, and full-text
search is served from Neon, not UC. The unanalyzed transcripts live only in the
local `gold` warehouse. So a one-time loader pushes them into a UC Delta table;
after that the analysis pipeline is self-contained in Databricks. Re-run the
loader anytime to top up with newly-scraped transcripts (idempotent MERGE).

## Cost

| Model (lead) | per 150-transcript batch | full ~14.8k backlog | notes |
|---|---|---|---|
| `databricks-gpt-oss-120b` ✅ | ~$0.05–0.40 | ~$10–40 across runs | default; cheap, solid extraction |
| `databricks-llama-4-maverick` | similar | similar | escalation target for invalid rows |
| `databricks-claude-opus-4-8` | higher | ~$340 ❌ | only Claude hosted here; reserve for a subset |

`analysis_batch_size` (default **150**) caps per-run volume — keep it small for a
live demo, set `--var analysis_batch_size=0` to drain the whole backlog in one run.
The prompt is identical across rows, so endpoint prompt caching helps automatically.

## Run it

```bash
# 1. ONE-TIME (machine with local gold access): load transcripts + prompt into UC
python -m ingestion.databricks.load_transcripts_to_uc --dry-run --limit 150   # count
python -m ingestion.databricks.load_transcripts_to_uc --limit 150            # load
#    re-run later (idempotent) to add more, or --limit 0 for all in scope

# 2. Deploy + run the dbt analysis (repeat step 2 to catch up the backlog)
./setup.sh                                                   # validate + deploy (paused)
databricks bundle run agent_analysis_sync -t dev --profile opennav-prod

# inspect
#   open_navigator_analysis.bronze_transcript_analysis  (raw ai_query JSON)
#   open_navigator_analysis.silver_{meeting,decision}_analysis
#   open_navigator_analysis.gold_event_{meeting,decision}_analysis
```

## Returning results to the warehouse (production path, NOT needed for the demo)

The UC serving tables are a Neon-overwritten mirror, so analysis results flow back
to local `gold` (source of truth) and re-serve via the normal path — pull the
`gold_*` tables with `python -m ingestion.databricks.pull_analysis_from_uc`, then
merge into `gold` via the existing promote/dbt. Judges don't need this.

## Knobs (`--var name=value` at deploy)

| var | default | purpose |
|-----|---------|---------|
| `primary_model` | `databricks-gpt-oss-120b` | lead inference endpoint |
| `escalate_model` | `databricks-llama-4-maverick` | re-run invalid rows (== primary disables) |
| `analysis_batch_size` | `150` | not-yet-analyzed transcripts per run (0 = all) |
| `max_output_tokens` | `8000` | per-row output cap (policy JSON is large) |
| `warehouse_id` | `89382a58d0c1c6aa` | SQL warehouse running the dbt/ai_query SQL |
| `schedule_cron` | `0 0 6 * * ?` | daily 06:00 ET |
| `schedule_pause` | `PAUSED` | unpause once verified |

## Files

- `databricks.yml` — bundle config + variables + targets.
- `resources/analysis.job.yml` — single dbt_task job.
- `dbt/` — dbt-databricks project (all analysis + JSON extraction):
  - `models/bronze/bronze_transcript_analysis.sql` — incremental, batched `ai_query`.
  - `macros/escalate_invalid.sql` — post-hook re-run of invalid rows.
  - `models/silver/*` — JSON → typed meeting/decision rows.
  - `models/gold/*` — writeback-shaped marts.
- `setup.sh` — validate + deploy.

> Loader lives in `packages/ingestion/src/ingestion/databricks/` (`load_transcripts_to_uc`,
> `pull_analysis_from_uc`). The local Neon loaders in `packages/hosting` remain for
> the production Neon/Lakebase path but are not used by this demo pipeline.
