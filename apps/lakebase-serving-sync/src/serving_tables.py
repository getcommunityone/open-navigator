# Databricks notebook source
# MAGIC %md
# MAGIC # serving_tables — single source of truth
# MAGIC
# MAGIC The civic-serving objects to sync, each with its **primary key**.
# MAGIC `%run` this notebook from the ingest + sync tasks to share the list.
# MAGIC
# MAGIC - The set mirrors the Neon serving allow-list (`CIVIC_SERVING` in
# MAGIC   `hosting.neon.sync_public_to_neon`) so Lakebase serves the same data.
# MAGIC - Primary keys were read from the local `gold` marts (the dbt-declared,
# MAGIC   enforced PKs that `public` is a 1:1 view over), verified 2026-06-14.
# MAGIC   Synced tables REQUIRE a primary key and we never invent one.
# MAGIC - `EXCLUDED_NO_PK` lists civic objects whose `gold` mart has no PK — they
# MAGIC   are intentionally NOT synced until a real unique key is added here.

# COMMAND ----------

# table_name -> [primary key column(s)]
TABLES = {
    # events & AI analysis
    "event_decision": ["event_decision_id", "extracted_at"],
    "event_decision_place": ["event_decision_place_id"],
    "event_place_geocoded": ["event_place_id"],  # /api/decision/map
    "event_financial_item": ["event_financial_item_id", "extracted_at"],
    "event_bill": ["event_bill_id", "extracted_at"],
    "event_topic": ["event_topic_id", "extracted_at"],
    "event_meeting": ["event_meeting_id"],
    "event_meeting_document": ["event_meeting_document_id"],
    "meeting_document": ["jurisdiction_jid", "meeting_date", "doc_kind"],
    # people & officials
    "contact_official": ["id"],
    "person_government": ["person_id"],
    # jurisdictions
    "jurisdictions": ["jurisdiction_id"],
    "civic_jurisdiction": ["legacy_id"],
    "jurisdiction_minutes_publish_lag": ["jurisdiction_id"],
    "jurisdiction_mapping_analysis": ["jurisdiction_id"],  # admin /api/jurisdiction-mapping/*
    "jurisdiction_state_aggregate": ["sync_key"],  # /api/stats — derived PK (see DERIVED_PK)
    # bills, grants opportunities, feed, taxonomy
    "grant_opportunity": ["opportunity_id"],
    "item_interestingness": ["event_decision_id"],
    "item_flags": ["item_flag_id"],
    "tag": ["tag_id"],
    # policy-question registry
    "policy_question": ["question_id"],
    "policy_question_relation": ["relation_id"],
    "canonical_argument": ["argument_id"],
    "question_instance": ["instance_id"],
    # reference series
    "cpi_annual": ["series_id", "year"],
    # browse counts + directory
    "browse_directory_summary": ["entity_type", "state_code_key"],
    "browse_transcript_count": ["entity_type", "entity_id"],
    "browse_entity_state_transcript_count": ["entity_type", "entity_id", "state_code"],
    # meeting-grain browse + topic/question linkage
    "meeting_browse": ["event_meeting_id"],
    "meeting_question_link": ["meeting_question_link_id"],
    "civicsearch_topic": ["topic_id"],
    "topic_money_and_talk": ["topic_money_and_talk_id"],
    "policy_question_trend": ["trend_id"],
    # decision detail + arguments
    "decision_speakers": ["event_decision_id"],
    # finance / money lenses
    "jurisdiction_finance": ["jurisdiction_finance_id"],
    "jurisdiction_property_tax_rate": ["jurisdiction_property_tax_rate_id"],
}

# Tables whose gold mart has no PK get a stable surrogate computed at ingest time
# (sha2 of the listed grain columns, null-safe) → a `sync_key` column the synced
# table uses as its PK. The grain MUST be unique (verified) — this is a derived
# key over real columns, not a fabricated one. event_place_geocoded and
# jurisdiction_mapping_analysis have clean natural keys, so they're not here.
DERIVED_PK = {
    # grain is unique (0 dup rows) but (level,state_code,county,city) has NULLs,
    # which synced tables would drop — so hash the null-coalesced grain instead.
    "jurisdiction_state_aggregate": ["level", "state_code", "county", "city"],
}

# Civic-serving objects with no usable key at all — not synced (none currently;
# the former entries now have natural or derived keys above).
EXCLUDED_NO_PK = []

# Tables RENAMED in the Databricks/Lakebase serving layer ONLY. The Neon SOURCE
# keeps its original name (the API reads Neon by the original name); we relabel
# only the UC Delta + Lakebase copies. Maps source table name -> serving name.
# The ingest writes the Delta table under the serving name, and the Lakebase
# synced table is created under it too; the PK lookup in TABLES stays keyed by
# the source name.
RENAME_IN_SERVING = {
    "browse_directory_summary": "transcript_directory_summary",
    "browse_transcript_count": "transcript_count",
    "browse_entity_state_transcript_count": "transcript_entity_state_count",
}


def serving_name(source_table: str) -> str:
    """Serving-layer (UC Delta + Lakebase) name for a source table."""
    return RENAME_IN_SERVING.get(source_table, source_table)

# Dropped from the serving layer (not used by the frontend, confirmed by API +
# web_app audit 2026-06-14): event, mdm_bridge_event_analysis, instance_argument
# (no live endpoint), jurisdiction_document (endpoint registered but UI unwired).
# Also removed from the Neon CIVIC_SERVING allow-list. Re-add here + there if a
# UI consumer appears.
#
# Dropped from the DATABRICKS/LAKEBASE serving layer ONLY 2026-06-15 (kept in Neon
# for the live API): opportunity_atlas_mobility, opportunity_atlas_mobility_national,
# question_transcript_link, rpt_bill_map_aggregate, state_sales_tax_rate. These were
# removed from TABLES above (so the sync no longer ingests/syncs them) but stay in
# sync_public_to_neon's CIVIC_SERVING because the FastAPI serves them from Neon.

# event_documents is served to Neon via a dedicated slim cues-only loader (it is
# a ~13.7 GB transcript view), so it is NOT part of this generic sync. Add a
# dedicated UC ingest if Lakebase should serve transcript search.
