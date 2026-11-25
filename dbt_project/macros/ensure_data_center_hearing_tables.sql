{#
    The bronze tables the data center hearing models read (#955, #956), created empty when
    missing so data_center_hearing and data_center_hearing_verified still build in a fresh
    warehouse (no leads fetched yet: every lead reads not_fetched, nothing is verified).
    The loaders create the same tables with the same columns:
      ingestion.data_centers.fetch_hearing_sources      -> bronze_data_center_hearing_source
      ingestion.data_centers.load_hearing_tracker_leads -> bronze_data_center_hearing_tracker_lead
    Keep the columns in step with those loaders.
#}
{% macro ensure_data_center_hearing_tables() -%}
create schema if not exists bronze;
create table if not exists bronze.bronze_data_center_hearing_source (
    lead_id      text primary key,
    source_url   text not null,
    final_url    text,
    fetched_at   timestamptz not null,
    http_status  integer,
    content_type text,
    page_text    text,
    error        text
);
create table if not exists bronze.bronze_data_center_hearing_tracker_lead (
    tracker      text not null,
    record_id    text not null,
    feed_url     text not null,
    attribution  text not null,
    fetched_at   timestamptz not null,
    record       jsonb not null,
    primary key (tracker, record_id)
)
{%- endmacro %}
