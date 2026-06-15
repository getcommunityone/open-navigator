{% macro publish_public_serving() %}
{#-
    Publish the PUBLIC serving layer. The full warehouse lives in `gold`; the
    public API reads ONLY the relations below.

    TWO MODES (var: public_serving_mode, default 'view'):

      * 'view' (DEFAULT — dev / unchanged):
        Each served relation is a thin view over gold
        (CREATE OR REPLACE VIEW public.x AS SELECT ... FROM gold.x). A plain
        (non-security_barrier) view is inlined by the planner, so each view reuses
        the gold base table's indexes (FTS GIN / trigram) — no perf regression —
        and a SELECT * view auto-tracks additive columns. The public schema stays
        tiny (~1 MB) but the public API TRANSITIVELY reads gold.

      * 'materialize' (Neon-scoped self-contained TABLES):
        Each served relation becomes a standalone TABLE in public, populated with
        the SAME Neon serving scope the `neon` dbt target / sync loaders enforce
        (analyzed-only event/event_documents; top-2-per-jurisdiction org graph;
        org-linked grants; transcript full-text dropped). public no longer
        references gold at all, so an API running with search_path=public is a
        self-contained, Neon-sized serving layer. Essential serving indexes
        (FTS GIN / trigram / PK) are recreated on the public tables because, as
        standalone tables, they can no longer borrow gold's indexes.

        Build it:
            dbt run-operation publish_public_serving \
                --vars '{public_serving_mode: materialize}'

    This macro is the SINGLE SOURCE OF TRUTH for what the public API may read. To
    add/remove a public relation, edit `served` (or `projections`) below. Fired
    from on-run-end after every `dbt run` in the default 'view' mode (idempotent
    CREATE OR REPLACE), and runnable on demand:

        dbt run-operation publish_public_serving

    Privacy posture (identical in both modes):
      * The person-graph PII (mdm_person, mdm_bridge_person_*, organization_
        nonprofit_compensation) is deliberately ABSENT — it is gold-only / private.
      * `contact_official` ("leaders") and `person_government` are published
        PII/PHI-LIGHT: the per-person contact fields (email, phone) are REDACTED
        to NULL. Officials' name/title/office/jurisdiction/party/district/photo/bio
        remain (public-figure role data). Column shape is preserved (NULL::text
        aliases) so API queries selecting email/phone keep working — they get NULL.
        See projections[...] below.
-#}
{%- if not execute -%}{{ return('') }}{%- endif -%}

{%- set mode = var('public_serving_mode', 'view') -%}

{#- ===================================================================
    LAUNCH SCOPE (var: public_serving_launch_scope, default false).

    The product launches in 4 counties only. When this var is OFF the macro
    behaves EXACTLY as before (regression-safe). When ON, every served
    relation's computed body is WRAPPED:

        select * from (<body>) _s where <predicate>

    Because both the view and materialize modes compute a `body` string, the
    wrap applies uniformly to both. The wrap is layered ON TOP of the
    neon_bodies slimming, so e.g. grant = (top-2-org-graph) ∩ launch states.

    The geoid IN-list (95 launch places + 4 county FIPS + 4 state FIPS, all
    confirmed present in jurisdictions.geoid) is resolved ONCE at macro start
    from bronze and inlined as SQL literals — public views never depend on
    bronze. Launch states / county FIPS are overridable vars.

    Relations whose predicate map entry is absent are left UNFILTERED (small
    national reference tables, or tables already slimmed by a neon body and
    carrying no usable geo key). See launch_predicates below.
    =================================================================== -#}
{%- set launch_scope = var('public_serving_launch_scope', false) -%}
{%- set launch_states = var('launch_states', ['AL', 'GA', 'MA', 'WA']) -%}
{%- set launch_county_fips = var('launch_county_fips', ['01125', '13121', '25025', '53033']) -%}

{#- Built only when scope is on: literal IN-list fragments. -#}
{%- set geoid_in_list = '' -%}
{%- set state_in_list = '' -%}

{%- if launch_scope and execute -%}
  {#- State-code literal list: ('AL','GA',...) -#}
  {%- set _sc = [] -%}
  {%- for s in launch_states -%}{%- do _sc.append("'" ~ s ~ "'") -%}{%- endfor -%}
  {%- set state_in_list = '(' ~ (_sc | join(', ')) ~ ')' -%}

  {#- State FIPS = first 2 chars of each county FIPS (e.g. 01125 -> 01). -#}
  {%- set _state_fips = [] -%}
  {%- for cf in launch_county_fips -%}
    {%- set sf = cf[:2] -%}
    {%- if sf not in _state_fips -%}{%- do _state_fips.append(sf) -%}{%- endif -%}
  {%- endfor -%}

  {#- Resolve the 95 launch place geoids from bronze, ONCE. -#}
  {%- set _cf_lits = [] -%}
  {%- for cf in launch_county_fips -%}{%- do _cf_lits.append("'" ~ cf ~ "'") -%}{%- endfor -%}
  {%- set _geo_q -%}
    select geoid from bronze.bronze_jurisdictions_county_fips_enriched
    where county_fips_code in ({{ _cf_lits | join(', ') }})
  {%- endset -%}
  {%- set _geo_res = run_query(_geo_q) -%}
  {%- set _geoids = [] -%}
  {%- if _geo_res and _geo_res.rows -%}
    {%- for r in _geo_res.rows -%}
      {%- if r[0] is not none -%}{%- do _geoids.append(r[0]) -%}{%- endif -%}
    {%- endfor -%}
  {%- endif -%}
  {#- geoid set = places + county FIPS + state FIPS (so county/state-level
      jurisdiction rows survive the place-strict geoid filter). -#}
  {%- for cf in launch_county_fips -%}{%- if cf not in _geoids -%}{%- do _geoids.append(cf) -%}{%- endif -%}{%- endfor -%}
  {%- for sf in _state_fips -%}{%- if sf not in _geoids -%}{%- do _geoids.append(sf) -%}{%- endif -%}{%- endfor -%}
  {%- set _geo_lits = [] -%}
  {%- for g in _geoids -%}{%- do _geo_lits.append("'" ~ g ~ "'") -%}{%- endfor -%}
  {%- set geoid_in_list = '(' ~ (_geo_lits | join(', ')) ~ ')' -%}
  {{ log("publish_public_serving: launch scope ON — " ~ (_geoids | length) ~ " geoids, states " ~ state_in_list, info=true) }}
{%- endif -%}

{#- Per-relation launch-scope predicate map. The VALUE is a boolean SQL
    expression evaluated against the wrapped body alias `_s`. Placeholders
    {{geoids}} and {{states}} are substituted with the inlined literal lists.
    Every column referenced below was verified to exist in the gold relation
    via information_schema. Relations NOT listed here are left unfiltered.

    Tiers:
      * PLACE  (strict geoid set): jurisdictions, civic_jurisdiction.
      * CIVIC  (state_code IN states): all event_* / jurisdiction_* / browse /
               item / officials relations that carry state_code.
      * NATIONAL graph (state_code IN states): grant (either endpoint),
               mdm_organization, bills.

    jurisdiction_finance_category has no state column but FK-references
    jurisdiction_finance; it is scoped via jurisdiction_finance_id to the
    state-scoped finance set (see entry below).

    Left UNFILTERED (no usable geo column / already slimmed by neon body, noted
    in summary): mdm_organization_nonprofit and mdm_bridge_org_jurisdiction
    (already inner-joined to the top-2 kept-org set by their neon bodies),
    jurisdiction_document (jurisdiction_id is a slug, tiny seed table), and all
    national reference tables (cpi_annual, state_sales_tax_rate, tag,
    opportunity_atlas_*national, nonprofit_sector_revenue, grant_opportunity,
    etc.). -#}
{%- set launch_predicates = {
    'jurisdictions':                       "_s.geoid in {{geoids}}",
    'civic_jurisdiction':                  "_s.geoid in {{geoids}}",
    'event':                               "_s.state_code in {{states}}",
    'event_meeting':                       "_s.state_code in {{states}}",
    'event_decision':                      "_s.state_code in {{states}}",
    'event_documents':                     "_s.state_code in {{states}}",
    'event_meeting_document':              "_s.state_code in {{states}}",
    'event_bill':                          "_s.state_code in {{states}}",
    'event_financial_item':                "_s.state_code in {{states}}",
    'event_place_geocoded':                "_s.state_code in {{states}}",
    'event_topic':                         "_s.state_code in {{states}}",
    'item_interestingness':                "_s.state_code in {{states}}",
    'item_flags':                          "_s.state_code in {{states}}",
    'contact_official':                    "_s.state_code in {{states}}",
    'person_government':                    "_s.state_code in {{states}}",
    'jurisdiction_state_aggregate':        "_s.state_code in {{states}}",
    'jurisdiction_finance':                "_s.state_code in {{states}}",
    'jurisdiction_finance_category':
        "_s.jurisdiction_finance_id in (select jurisdiction_finance_id "
        "from gold.jurisdiction_finance where state_code in {{states}})",
    'jurisdiction_mapping_analysis':       "_s.state_code in {{states}}",
    'jurisdiction_property_tax_rate':      "_s.state_code in {{states}}",
    'jurisdiction_minutes_publish_lag':    "_s.state_code in {{states}}",
    'rpt_bill_map_aggregate':              "_s.state_code in {{states}}",
    'topic_money_and_talk':                "_s.state_code in {{states}}",
    'browse_transcript_count':             "_s.state_code in {{states}}",
    'browse_directory_summary':            "_s.state_code in {{states}}",
    'browse_entity_state_transcript_count':"_s.state_code in {{states}}",
    'meeting_browse':                      "_s.state_code in {{states}}",
    'meeting_topic_link':                  "_s.state_code in {{states}}",
    'meeting_question_link':               "_s.state_code in {{states}}",
    'question_instance':                   "_s.state_code in {{states}}",
    'question_transcript_link':            "_s.state_code in {{states}}",
    'grant':                               "(_s.grantee_state_code in {{states}} or _s.grantor_state_code in {{states}})",
    'mdm_organization':                    "_s.state_code in {{states}}",
    'bills':                               "_s.state_code in {{states}}"
} -%}
{#- bill_sponsorship is DROPPED from serving entirely (removed from `served`):
    it has no state column and even scoped to the kept-bill set it is ~53 MB,
    which the under-500 MB budget can't afford. The sponsorship graph stays in
    gold (private warehouse); the public API does not read it. -#}


{%- set served = [
    'event', 'event_meeting', 'event_documents', 'event_meeting_document',
    'meeting_document', 'event_decision', 'event_decision_place', 'decision_speakers',
    'event_place_geocoded', 'event_financial_item', 'event_bill', 'event_topic',
    'contact_official', 'person_government', 'jurisdictions', 'civic_jurisdiction',
    'jurisdiction_document', 'jurisdiction_finance', 'jurisdiction_finance_category',
    'jurisdiction_property_tax_rate', 'state_sales_tax_rate',
    'opportunity_atlas_mobility', 'opportunity_atlas_mobility_national',
    'jurisdiction_mapping_analysis',
    'jurisdiction_state_aggregate', 'jurisdiction_minutes_publish_lag',
    'grant', 'grant_opportunity', 'tag', 'rpt_bill_map_aggregate',
    'bills',
    'cpi_annual',
    'item_interestingness', 'item_flags', 'nonprofit_sector_revenue',
    'topic_money_and_talk', 'civicsearch_topic',
    'browse_transcript_count', 'browse_directory_summary',
    'browse_entity_state_transcript_count',
    'mdm_organization', 'mdm_organization_nonprofit', 'mdm_bridge_org_jurisdiction',
    'mdm_bridge_event_analysis',
    'policy_question', 'canonical_argument', 'question_instance', 'instance_argument',
    'policy_question_relation', 'policy_question_trend', 'question_transcript_link',
    'meeting_browse', 'meeting_topic_link', 'meeting_question_link'
] -%}

{#- Per-relation column projections. Anything not listed here is published as a
    full SELECT * pass-through. Use this to drop/redact PII before it reaches the
    public API. Applies to BOTH modes (view body / table body). -#}
{%- set projections = {
    'contact_official':
        'select id, full_name, title, jurisdiction, state_code, state, party, '
        'district, office, null::text as email, null::text as phone, photo_url, '
        'biography, is_current, website_url from gold.contact_official',
    'person_government':
        'select person_id, master_person_id, full_name, title, jurisdiction, '
        'jurisdiction_id, office, state_code, state, party, district, '
        'null::text as email, null::text as phone, photo_url, biography, '
        'website_url, is_current from gold.person_government'
} -%}

{#- ===================================================================
    NEON SERVING SCOPE (materialize mode only). These bodies reproduce, in
    plain SQL against gold, the EXACT `target.name == 'neon'` predicates in
    the dbt models / sync loaders — DO NOT invent new filters here:

      * event                -> models/marts/event.sql (analyzed_video_ids from
                                event_meeting; video_id parsed from video_url /
                                datasource_id exactly as mdm_bridge_event_analysis).
      * event_documents      -> models/marts/event_documents.sql (analyzed-scoped;
                                content + content_tsv NULLed, segments slimmed) and
                                hosting/neon/sync_event_documents_to_neon.py
                                (_ANALYZED_SCOPE_SQL).
      * mdm_organization     -> models/marts/serving_mdm_organization.sql
                                (top-2 orgs per jurisdiction by revenue).
      * mdm_organization_nonprofit / mdm_bridge_org_jurisdiction
                             -> serving_mdm_organization_nonprofit.sql /
                                serving_mdm_bridge_org_jurisdiction.sql
                                (inner-joined to the kept org set).
      * grant                -> serving_grant.sql (keep if either endpoint is a
                                kept org).

    A shared CTE chain is defined once (analyzed video ids; the kept-org set) and
    referenced by the bodies that need it.
    =================================================================== -#}

{%- set analyzed_cte -%}
with analyzed_video_ids as (
    select distinct nullif(trim(video_id), '') as video_id
    from gold.event_meeting
    where nullif(trim(video_id), '') is not null
)
{%- endset -%}

{#- kept-org CTE: top-2 orgs per jurisdiction by revenue/income/assets. -#}
{%- set kept_org_cte -%}
with org_revenue as (
    select
        b.jurisdiction_id,
        b.master_org_id,
        coalesce(np.revenue, np.income, np.assets, 0) as size_metric
    from gold.mdm_bridge_org_jurisdiction b
    left join gold.mdm_organization_nonprofit np
        on np.master_org_id = b.master_org_id
),
ranked as (
    select
        jurisdiction_id,
        master_org_id,
        row_number() over (
            partition by jurisdiction_id
            order by size_metric desc, master_org_id
        ) as juris_rank
    from org_revenue
),
kept_org_ids as (
    -- top-2 orgs per jurisdiction (was 10): shrinks grant + the 3 org-graph
    -- tables (mdm_organization, mdm_organization_nonprofit,
    -- mdm_bridge_org_jurisdiction) together to fit the serving layer under the
    -- Neon 512 MB free-tier cap. Measured launch-scoped total: ~498 MB at top-2
    -- (grant ~189 MB, the single largest table, is dominated by a handful of
    -- mega-grant orgs that survive any top-N cut — top-1 saves only ~34 MB while
    -- over-thinning the org graph to a single org per jurisdiction, so top-2 is
    -- the best size/coverage balance).
    select distinct master_org_id from ranked where juris_rank <= 2
)
{%- endset -%}

{#- Neon-scoped table bodies. Keys present here override the default
    `select * from gold.x` / the projection for materialize mode only. -#}
{%- set neon_bodies = {
    'event':
        analyzed_cte ~ "
select c.*
from gold.event c
where coalesce(
        case
            when c.video_url like '%youtube.com%' or c.video_url like '%youtu.be%'
            then regexp_replace(
                     regexp_replace(c.video_url, '.*[?&]v=([^&]+).*', '\\1'),
                     '.*youtu\\.be/([^?]+).*', '\\1')
        end,
        case
            when c.source in ('youtube', 'localview')
            then nullif(trim(c.datasource_id), '')
        end
      ) in (select video_id from analyzed_video_ids)",
    'event_documents':
        analyzed_cte ~ "
select
    event_document_id, event_id, document_type, document_source, video_id,
    -- Transcript full-text search MUST work on the serving layer. We KEEP the raw
    -- `content` (the document search leg matches with
    -- to_tsvector('english', content) @@ websearch_to_tsquery(...) and builds its
    -- match-evidence snippet with ts_headline('english', content, ...)), but DROP
    -- the materialized `content_tsv` column (~85 MB): the FTS GIN index is now an
    -- EXPRESSION index over to_tsvector('english', content) (see
    -- table_indexes['event_documents']), so the planner still index-matches and
    -- ts_headline snippets are unchanged. content_excerpt stays as the cheap
    -- display field. Affordable because launch+analyzed scope cuts this to a few
    -- thousand rows — see the launch_predicates wrap.
    content,
    left(content, 300) as content_excerpt,
    content_length, word_count, language, is_auto_generated,
    -- segments DROPPED on the serving layer (~94 MB): the slimmed {s,t} array
    -- still carries the full transcript text, duplicating `content`. FTS +
    -- ts_headline snippets run off content, so search is unaffected; only
    -- transcript-grain timestamp scrubbing is lost in the served copy.
    null::jsonb as segments,
    event_title, event_date, jurisdiction_name, jurisdiction_type,
    state_code, state, city, video_url, created_at
from gold.event_documents
where nullif(trim(video_id), '') in (select video_id from analyzed_video_ids)",
    'mdm_organization':
        kept_org_cte ~ "
select o.* from gold.mdm_organization o
inner join kept_org_ids k on k.master_org_id = o.master_org_id",
    'mdm_organization_nonprofit':
        kept_org_cte ~ "
select np.* from gold.mdm_organization_nonprofit np
inner join kept_org_ids k on k.master_org_id = np.master_org_id",
    'mdm_bridge_org_jurisdiction':
        kept_org_cte ~ "
select b.* from gold.mdm_bridge_org_jurisdiction b
inner join kept_org_ids k on k.master_org_id = b.master_org_id",
    'grant':
        kept_org_cte ~ "
select g.* from gold.\"grant\" g
where exists (select 1 from kept_org_ids k where k.master_org_id = g.grantor_master_org_id)
   or exists (select 1 from kept_org_ids k where k.master_org_id = g.grantee_master_org_id)",
    'bills':
        "select bill_uid, ocd_bill_id, identifier, title, session_identifier, session_name, ocd_jurisdiction_id, state_code, jurisdiction_id, latest_action_date, latest_action_description, year from gold.bills where year >= 2023"
} -%}

{#- Essential serving indexes to recreate on the standalone public tables
    (materialize mode). These exist on the gold base tables today and the API
    relies on them; a SELECT * view borrows gold's, but a standalone table must
    own its own. PK first (named *_pkey), then secondary / FTS / trigram. -#}
{%- set table_indexes = {
    'event': [
        'create unique index if not exists event_pkey on public.event (event_id)',
        "create index if not exists event_event_date_idx on public.event (event_date)",
        "create index if not exists event_state_code_idx on public.event (state_code, state)",
        "create index if not exists event_jurisdiction_id_idx on public.event (jurisdiction_id)",
        "create index if not exists event_video_url_idx on public.event (video_url)",
        "create index if not exists event_title_fts_idx on public.event using gin (to_tsvector('english', event_title))",
        "create index if not exists event_jurisdiction_trgm_idx on public.event using gin (jurisdiction_name gin_trgm_ops)"
    ],
    'event_documents': [
        'create unique index if not exists event_documents_pkey on public.event_documents (event_document_id)',
        'create index if not exists event_documents_video_id_idx on public.event_documents (video_id)',
        'create index if not exists event_documents_event_id_idx on public.event_documents (event_id)',
        'create index if not exists event_documents_state_code_idx on public.event_documents (state_code)',
        "create index if not exists event_documents_content_fts_idx on public.event_documents using gin (to_tsvector('english', content))"
    ],
    'event_decision': [
        'create index if not exists event_decision_state_code_idx on public.event_decision (state_code)',
        'create index if not exists event_decision_search_tsv_idx on public.event_decision using gin (search_tsv)'
    ],
    'mdm_organization': [
        'create unique index if not exists mdm_organization_pkey on public.mdm_organization (master_org_id)',
        "create index if not exists mdm_organization_org_name_fts_idx on public.mdm_organization using gin (to_tsvector('english', org_name))",
        'create index if not exists mdm_organization_org_name_norm_idx on public.mdm_organization (org_name_norm)',
        'create index if not exists mdm_organization_state_code_idx on public.mdm_organization (state_code)'
    ],
    'mdm_organization_nonprofit': [
        'create index if not exists mdm_organization_nonprofit_master_org_id_idx on public.mdm_organization_nonprofit (master_org_id)'
    ],
    'mdm_bridge_org_jurisdiction': [
        'create index if not exists mdm_bridge_org_jurisdiction_jurisdiction_id_idx on public.mdm_bridge_org_jurisdiction (jurisdiction_id)',
        'create index if not exists mdm_bridge_org_jurisdiction_master_org_id_idx on public.mdm_bridge_org_jurisdiction (master_org_id)'
    ],
    'grant': [
        'create index if not exists grant_grantor_master_org_id_idx on public."grant" (grantor_master_org_id)',
        'create index if not exists grant_grantee_master_org_id_idx on public."grant" (grantee_master_org_id)',
        'create index if not exists grant_grantee_state_code_idx on public."grant" (grantee_state_code)',
        'create index if not exists grant_grantee_name_trgm_idx on public."grant" using gin (grantee_name gin_trgm_ops)',
        'create index if not exists grant_grantor_name_trgm_idx on public."grant" using gin (grantor_name gin_trgm_ops)'
    ],
    'item_interestingness': [
        'create index if not exists item_interestingness_event_decision_id_idx on public.item_interestingness (event_decision_id)',
        'create index if not exists item_interestingness_jurisdiction_id_idx on public.item_interestingness (jurisdiction_id)'
    ],
    'bills': [
        'create unique index if not exists bills_pkey on public.bills (bill_uid)',
        'create index if not exists bills_state_code_idx on public.bills (state_code)',
        "create index if not exists bills_title_fts_idx on public.bills using gin (to_tsvector('english', coalesce(title, '')))"
    ],
    'contact_official': [
        "create index if not exists contact_official_full_name_trgm_idx on public.contact_official using gin (full_name gin_trgm_ops)"
    ],
    'person_government': [
        "create index if not exists person_government_full_name_trgm_idx on public.person_government using gin (full_name gin_trgm_ops)"
    ]
} -%}

{%- set created = [] -%}
{%- set redacted = [] -%}
{%- set skipped = [] -%}

{%- if mode == 'materialize' -%}
  {#- Standalone Neon-scoped TABLES. public no longer references gold. -#}
  {%- do run_query("create extension if not exists pg_trgm") -%}
  {%- for name in served -%}
    {%- set q = '"' ~ name ~ '"' -%}
    {%- set chk = run_query("select to_regclass('gold." ~ q ~ "') as r") -%}
    {%- if chk and chk.rows and chk.rows[0][0] is not none -%}
      {%- set body = neon_bodies.get(name, projections.get(name, "select * from gold." ~ q)) -%}
      {#- Launch-scope wrap (on top of the neon body). No-op when scope off. -#}
      {%- if launch_scope and (name in launch_predicates) -%}
        {%- set pred = launch_predicates[name] | replace('{{geoids}}', geoid_in_list) | replace('{{states}}', state_in_list) -%}
        {%- set body = "select * from (" ~ body ~ "\n) _s where " ~ pred -%}
      {%- endif -%}
      {#- Idempotent: drop any prior view OR table, then rebuild. -#}
      {%- do run_query("drop view if exists public." ~ q ~ " cascade") -%}
      {%- do run_query("drop table if exists public." ~ q ~ " cascade") -%}
      {%- do run_query("create table public." ~ q ~ " as " ~ body) -%}
      {%- for idx in table_indexes.get(name, []) -%}
        {%- do run_query(idx) -%}
      {%- endfor -%}
      {%- do run_query("analyze public." ~ q) -%}
      {%- if name in projections -%}{%- do redacted.append(name) -%}{%- else -%}{%- do created.append(name) -%}{%- endif -%}
    {%- else -%}
      {%- do skipped.append(name) -%}
    {%- endif -%}
  {%- endfor -%}
  {{ log("publish_public_serving[materialize]: built " ~ (created | length + redacted | length) ~ " standalone public table(s), Neon-scoped, no gold dependency" ~ (" | PII-light projection: " ~ (redacted | join(', ')) if redacted else '') ~ (" | skipped (gold relation absent): " ~ (skipped | join(', ')) if skipped else ''), info=true) }}
{%- else -%}
  {#- DEFAULT: thin views over gold (dev). -#}
  {%- for name in served -%}
    {%- set q = '"' ~ name ~ '"' -%}
    {%- set chk = run_query("select to_regclass('gold." ~ q ~ "') as r") -%}
    {%- if chk and chk.rows and chk.rows[0][0] is not none -%}
      {%- set body = projections.get(name, "select * from gold." ~ q) -%}
      {#- Launch-scope wrap. No-op when scope off. -#}
      {%- if launch_scope and (name in launch_predicates) -%}
        {%- set pred = launch_predicates[name] | replace('{{geoids}}', geoid_in_list) | replace('{{states}}', state_in_list) -%}
        {%- set body = "select * from (" ~ body ~ "\n) _s where " ~ pred -%}
      {%- endif -%}
      {#- Idempotent: a prior materialize run may have left a TABLE here. Only
          DROP TABLE when the public relation is actually a base table — issuing
          `drop table` against an existing VIEW raises
          "<x> is not a table. HINT: Use DROP VIEW to remove a view." and aborts
          the on-run-end hook. A pre-existing view is handled by the subsequent
          CREATE OR REPLACE VIEW (no drop needed). -#}
      {%- set kind = run_query("select c.relkind from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relname = '" ~ name ~ "'") -%}
      {%- if kind and kind.rows and kind.rows[0][0] in ('r', 'p') -%}
        {%- do run_query("drop table if exists public." ~ q ~ " cascade") -%}
      {%- endif -%}
      {%- do run_query("create or replace view public." ~ q ~ " as " ~ body) -%}
      {%- if name in projections -%}{%- do redacted.append(name) -%}{%- else -%}{%- do created.append(name) -%}{%- endif -%}
    {%- else -%}
      {%- do skipped.append(name) -%}
    {%- endif -%}
  {%- endfor -%}
  {{ log("publish_public_serving[view]: published " ~ (created | length + redacted | length) ~ " public view(s)" ~ (" | PII-light projection: " ~ (redacted | join(', ')) if redacted else '') ~ (" | skipped (gold relation absent): " ~ (skipped | join(', ')) if skipped else ''), info=true) }}
{%- endif -%}

{%- do return('') -%}
{% endmacro %}
