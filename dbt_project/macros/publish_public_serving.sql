{% macro publish_public_serving() %}
{#-
    Publish the PUBLIC serving layer: the full warehouse lives in `gold`; the
    public API reads ONLY the relations below, exposed as thin views over gold
    ("public = all the serving data and nothing else"). A plain
    (non-security_barrier) view is inlined by the planner, so each view reuses the
    gold base table's indexes (FTS GIN / trigram) — no perf regression — and a
    SELECT * view auto-tracks additive columns.

    This is the SINGLE SOURCE OF TRUTH for what the public API may read. To
    add/remove a public relation, edit `served` (or `projections`) below. Fired
    from on-run-end after every `dbt run` (idempotent CREATE OR REPLACE), and
    runnable on demand:

        dbt run-operation publish_public_serving

    Privacy posture:
      * The person-graph PII (mdm_person, mdm_bridge_person_*, organization_
        nonprofit_compensation) is deliberately ABSENT — it is gold-only / private.
      * `contact_official` ("leaders") is published PII/PHI-LIGHT: the per-person
        contact fields (email, phone) are REDACTED to NULL in the public view.
        Officials' name/title/office/jurisdiction/party/district/photo/bio remain
        (public-figure role data). Column shape is preserved (NULL::text aliases)
        so API queries that select email/phone keep working — they just get NULL.
        See projections['contact_official'] below.
-#}
{%- if not execute -%}{{ return('') }}{%- endif -%}

{%- set served = [
    'event', 'event_meeting', 'event_documents', 'event_meeting_document',
    'meeting_document', 'event_decision', 'event_decision_place',
    'event_place_geocoded', 'event_financial_item', 'event_bill', 'event_topic',
    'contact_official', 'person_government', 'jurisdictions', 'civic_jurisdiction',
    'jurisdiction_document', 'jurisdiction_mapping_analysis',
    'jurisdiction_state_aggregate', 'jurisdiction_minutes_publish_lag',
    'grant', 'tag', 'rpt_bill_map_aggregate', 'item_interestingness',
    'nonprofit_sector_revenue',
    'mdm_organization', 'mdm_organization_nonprofit', 'mdm_bridge_org_jurisdiction'
] -%}

{#- Per-relation column projections. Anything not listed here is published as a
    full SELECT * pass-through. Use this to drop/redact PII before it reaches the
    public API. -#}
{%- set projections = {
    'contact_official':
        'select id, full_name, title, jurisdiction, state_code, state, party, '
        'district, office, null::text as email, null::text as phone, photo_url, '
        'biography, is_current, website_url from gold.contact_official'
} -%}

{%- set created = [] -%}
{%- set redacted = [] -%}
{%- set skipped = [] -%}
{%- for name in served -%}
  {%- set q = '"' ~ name ~ '"' -%}
  {%- set chk = run_query("select to_regclass('gold." ~ q ~ "') as r") -%}
  {%- if chk and chk.rows and chk.rows[0][0] is not none -%}
    {%- set body = projections.get(name, "select * from gold." ~ q) -%}
    {%- do run_query("create or replace view public." ~ q ~ " as " ~ body) -%}
    {%- if name in projections -%}{%- do redacted.append(name) -%}{%- else -%}{%- do created.append(name) -%}{%- endif -%}
  {%- else -%}
    {%- do skipped.append(name) -%}
  {%- endif -%}
{%- endfor -%}

{{ log("publish_public_serving: published " ~ (created | length + redacted | length) ~ " public view(s)" ~ (" | PII-light projection: " ~ (redacted | join(', ')) if redacted else '') ~ (" | skipped (gold relation absent): " ~ (skipped | join(', ')) if skipped else ''), info=true) }}
{%- do return('') -%}
{% endmacro %}
