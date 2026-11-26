{#
    The bronze tables of the open data center inventories (#958), created empty when missing so
    data_center_site and the inventory marts still build in a fresh warehouse (no registry rows
    yet: data_center_site holds the Epoch sites only). The loader creates the same tables:
      python -m ingestion.data_centers.facility_inventories
    Keep the columns in step with ingestion.data_centers.facility_inventories.create_sql.
#}
{% macro ensure_data_center_inventory_tables() -%}
create schema if not exists bronze;
{%- for t in ['bronze_data_center_facility_registry', 'bronze_data_center_facility_public_evidence', 'bronze_data_center_state_count_greencalculus'] %}
create table if not exists bronze.{{ t }} (
    record_id      text primary key,
    feed_url       text not null,
    attribution    text not null,
    record         jsonb not null,
    first_seen_at  timestamptz not null,
    last_seen_at   timestamptz not null
);
{%- endfor %}
{%- endmacro %}
