{#
  One-time repair for #514 / #515: write the hand-reviewed YouTube attribution
  (seed youtube_channel_attribution_override -> int_youtube__attribution_override)
  into the tables a normal `dbt run` cannot rewrite.

  Why a run-operation (same reasoning as repair_id_shaped_jurisdiction_names, #506):
  bronze_event_youtube, the channel catalogs and civic_event are written by Python
  loaders; the AI-extraction event marts (event_meeting + its event_* children) are
  `incremental, append, full_refresh=false` and keep the geography they copied
  from civic_event at build time; event_documents is a 35-minute table rebuild, so
  its few affected rows are patched in place with the same values a rebuild would
  produce (it reads event_youtube_with_jurisdiction for event-orphan transcripts).

  Steps (each counts first; writes only when dry_run=false):
    1. bronze.bronze_event_youtube   geo columns per video (the source of truth for
                                     the Python promote / analyze steps).
    2. bronze.bronze_events_channels jurisdictions array -> the reviewed channel
                                     default ('[]' when the channel has no single
                                     government); a channel_title that is empty or
                                     only a jurisdiction-name fallback is replaced by
                                     the LocalView channel title, or NULL.
    3. bronze_jurisdictions_{counties,municipalities}_scraped: clear the channel from
                                     rows of other jurisdictions; set it on the
                                     reviewed jurisdiction's row when that row has
                                     no channel id yet.
    4. intermediate.int_events_channels: repoint the wrong row to the reviewed
                                     jurisdiction when it has none, delete the rest.
    5. civic_event                   geo columns by dedupe_key = 'youtube|<video_id>'.
                                     (civic_event.state is varchar(2): it holds the
                                     state code, so it takes state_code.)
    6. each append-only event mart   geo columns from the override, joined through
                                     c1_event_id = civic_event.id.
    7. event_documents               geo columns for event-orphan transcripts.
    8. bronze_question_instance      (LLM clustering output) local_decision rows
                                     re-copy state/name/city from the repaired
                                     event_decision they point at.
  Afterwards rebuild the table marts that read these (see the #514 PR).

  Usage:
    dbt run-operation repair_youtube_channel_attribution                     # dry run: counts only
    dbt run-operation repair_youtube_channel_attribution --args '{dry_run: false}'
#}
{% macro repair_youtube_channel_attribution(dry_run=true) %}
    {%- set ov = ref('int_youtube__attribution_override') -%}
    {%- set seed = ref('youtube_channel_attribution_override') -%}
    {%- set juris = ref('int_jurisdictions') -%}
    {%- set yt = source('bronze', 'bronze_event_youtube') -%}
    {%- set channels = source('bronze', 'bronze_events_channels') -%}
    {%- set counties_scraped = source('bronze', 'bronze_jurisdictions_counties_scraped') -%}
    {%- set munis_scraped = source('bronze', 'bronze_jurisdictions_municipalities_scraped') -%}
    {%- set golden = source('intermediate_runtime', 'int_events_channels') -%}
    {%- set civic_event = source('civic_core', 'civic_event') -%}
    {%- set event_marts = [
        'event_meeting', 'event_decision', 'event_bill', 'event_person',
        'event_place', 'event_financial_item', 'event_topic',
    ] -%}

    {#- Channel-wide reviewed default, one row per channel, with canonical names. -#}
    {%- set channel_default -%}
        (select
            nullif(trim(s.channel_id), '')      as channel_id,
            nullif(trim(s.jurisdiction_id), '') as jurisdiction_id,
            j.name                              as jurisdiction_name,
            j.jurisdiction_type,
            j.geoid,
            coalesce(j.state_code, upper(nullif(trim(s.state_code), ''))) as state_code,
            j.state
         from {{ seed }} s
         left join {{ juris }} j on j.jurisdiction_id = nullif(trim(s.jurisdiction_id), '')
         where nullif(trim(s.video_id), '') is null)
    {%- endset -%}

    {#- 1. bronze_event_youtube -#}
    {%- set yt_diff -%}
        from {{ ov }} o
        where y.video_id = o.video_id
          and (y.jurisdiction_id is distinct from o.jurisdiction_id
            or y.jurisdiction_name is distinct from o.jurisdiction_name
            or y.jurisdiction_type is distinct from o.jurisdiction_type
            or y.state_code is distinct from o.state_code
            or y.state is distinct from o.state
            or y.city is distinct from o.city)
    {%- endset -%}
    {%- do _repair_attribution_step(dry_run, 'bronze_event_youtube',
        'select count(*) from ' ~ yt ~ ' y where exists (select 1 ' ~ yt_diff ~ ')',
        'update ' ~ yt ~ ' y set jurisdiction_id = o.jurisdiction_id, jurisdiction_name = o.jurisdiction_name,'
        ~ ' jurisdiction_type = o.jurisdiction_type, state_code = o.state_code, state = o.state,'
        ~ ' city = o.city, last_updated = now() ' ~ yt_diff) -%}

    {#- 2. bronze_events_channels: jurisdictions array + fallback title -#}
    {%- set ch_new -%}
        (select cd.channel_id,
                case when cd.jurisdiction_id is null then '[]'::jsonb
                     else jsonb_build_array(jsonb_build_object(
                        'jurisdiction_id', cd.jurisdiction_id,
                        'jurisdiction_name', cd.jurisdiction_name,
                        'jurisdiction_type', cd.jurisdiction_type,
                        'geoid', cd.geoid,
                        'state_code', cd.state_code,
                        'state', cd.state)) end as jurisdictions,
                {#- runtime-owned video->channel map (read by literal name in
                    int_events_localview / int_youtube__events too) -#}
                (select max(m.channel_title)
                   from intermediate.int_localview_youtube_video_channels m
                  where m.channel_id = cd.channel_id) as localview_title
         from {{ channel_default }} cd)
    {%- endset -%}
    {%- set ch_title_is_fallback -%}
        exists (select 1 from jsonb_array_elements(coalesce(c.jurisdictions, '[]'::jsonb)) e
                where e->>'jurisdiction_name' = c.channel_title)
    {%- endset -%}
    {%- do _repair_attribution_step(dry_run, 'bronze_events_channels',
        'select count(*) from ' ~ channels ~ ' c join ' ~ ch_new ~ ' n on n.channel_id = c.channel_id'
        ~ ' where c.jurisdictions is distinct from n.jurisdictions'
        ~ ' or (c.channel_title is null and n.localview_title is not null)',
        'update ' ~ channels ~ ' c set'
        ~ ' channel_title = case when c.channel_title is null or ' ~ ch_title_is_fallback
        ~ ' then n.localview_title else c.channel_title end,'
        ~ ' jurisdictions = n.jurisdictions, last_updated = now()'
        ~ ' from ' ~ ch_new ~ ' n where n.channel_id = c.channel_id'
        ~ ' and (c.jurisdictions is distinct from n.jurisdictions'
        ~ ' or (c.channel_title is null and n.localview_title is not null))') -%}

    {#- 3. scraped jurisdiction rows -#}
    {%- for tbl in [counties_scraped, munis_scraped] -%}
        {%- set wrong -%}
            from {{ channel_default }} cd
            where nullif(trim(s.youtube_channel_id), '') = cd.channel_id
              and s.jurisdiction_id is distinct from cd.jurisdiction_id
        {%- endset -%}
        {%- do _repair_attribution_step(dry_run, tbl.identifier ~ ' (clear wrong channel)',
            'select count(*) from ' ~ tbl ~ ' s where exists (select 1 ' ~ wrong ~ ')',
            'update ' ~ tbl ~ ' s set youtube_channel_url = null, youtube_channel_id = null,'
            ~ ' youtube_channel_selection_method = null, youtube_channel_selection_confidence = null'
            ~ ' where exists (select 1 ' ~ wrong ~ ')') -%}
        {%- set target -%}
            from {{ channel_default }} cd
            where s.jurisdiction_id = cd.jurisdiction_id
              and nullif(trim(s.youtube_channel_id), '') is null
        {%- endset -%}
        {%- do _repair_attribution_step(dry_run, tbl.identifier ~ ' (set reviewed channel)',
            'select count(*) from ' ~ tbl ~ ' s where exists (select 1 ' ~ target ~ ')',
            'update ' ~ tbl ~ ' s set youtube_channel_id = cd.channel_id,'
            ~ " youtube_channel_url = 'https://www.youtube.com/channel/' || cd.channel_id,"
            ~ " youtube_channel_selection_method = 'manual_review',"
            ~ ' youtube_channel_selection_confidence = 0.95 ' ~ target) -%}
    {%- endfor -%}

    {#- 4. int_events_channels (runtime-owned golden channel table) -#}
    {%- set repoint -%}
        from {{ channel_default }} cd
        where g.youtube_channel_id = cd.channel_id
          and cd.jurisdiction_id is not null
          and g.jurisdiction_id is distinct from cd.jurisdiction_id
          and not exists (select 1 from {{ golden }} g2
                          where g2.jurisdiction_id = cd.jurisdiction_id
                            and g2.youtube_channel_id = cd.channel_id)
          and g.id = (select min(g3.id) from {{ golden }} g3
                      where g3.youtube_channel_id = cd.channel_id
                        and g3.jurisdiction_id is distinct from cd.jurisdiction_id)
    {%- endset -%}
    {%- do _repair_attribution_step(dry_run, 'int_events_channels (repoint to reviewed jurisdiction)',
        'select count(*) from ' ~ golden ~ ' g where exists (select 1 ' ~ repoint ~ ')',
        'update ' ~ golden ~ ' g set jurisdiction_id = cd.jurisdiction_id,'
        ~ ' jurisdiction_type = cd.jurisdiction_type, state_code = cd.state_code,'
        ~ " channel_title = null, discovery_method = 'manual_review',"
        ~ " source = 'manual', loaded_at = now() " ~ repoint) -%}
    {%- set stale -%}
        from {{ channel_default }} cd
        where g.youtube_channel_id = cd.channel_id
          and g.jurisdiction_id is distinct from cd.jurisdiction_id
    {%- endset -%}
    {%- do _repair_attribution_step(dry_run, 'int_events_channels (delete wrong jurisdiction)',
        'select count(*) from ' ~ golden ~ ' g where exists (select 1 ' ~ stale ~ ')',
        'delete from ' ~ golden ~ ' g where exists (select 1 ' ~ stale ~ ')') -%}

    {#- 5. civic_event -#}
    {%- set ce_diff -%}
        from {{ ov }} o
        where ce.dedupe_key = 'youtube|' || o.video_id
          and (ce.jurisdiction_id is distinct from o.jurisdiction_id
            or ce.jurisdiction_name is distinct from o.jurisdiction_name
            or ce.jurisdiction_type is distinct from o.jurisdiction_type
            or ce.state is distinct from o.state_code
            or ce.city is distinct from o.city)
    {%- endset -%}
    {%- do _repair_attribution_step(dry_run, 'civic_event',
        'select count(*) from ' ~ civic_event ~ ' ce where exists (select 1 ' ~ ce_diff ~ ')',
        'update ' ~ civic_event ~ ' ce set jurisdiction_id = o.jurisdiction_id,'
        ~ ' jurisdiction_name = o.jurisdiction_name, jurisdiction_type = o.jurisdiction_type,'
        ~ ' state = o.state_code, city = o.city, updated_at = now() ' ~ ce_diff) -%}

    {#- 6. append-only event marts, through civic_event -#}
    {%- for m in event_marts -%}
        {%- set rel = ref(m) -%}
        {%- set diff -%}
            from {{ civic_event }} ce
            join {{ ov }} o on ce.dedupe_key = 'youtube|' || o.video_id
            where ce.id = t.c1_event_id
              and (t.jurisdiction_name is distinct from o.jurisdiction_name
                or t.jurisdiction_type is distinct from o.jurisdiction_type
                or t.state_code is distinct from o.state_code
                or t.state is distinct from o.state
                or t.city is distinct from o.city)
        {%- endset -%}
        {%- do _repair_attribution_step(dry_run, m,
            'select count(*) from ' ~ rel ~ ' t where exists (select 1 ' ~ diff ~ ')',
            'update ' ~ rel ~ ' t set jurisdiction_name = o.jurisdiction_name,'
            ~ ' jurisdiction_type = o.jurisdiction_type, state_code = o.state_code,'
            ~ ' state = o.state, city = o.city ' ~ diff) -%}
    {%- endfor -%}

    {#- 7. event_documents: event-orphan transcripts take the YouTube geography -#}
    {%- set docs = ref('event_documents') -%}
    {%- set doc_diff -%}
        from {{ ov }} o
        where d.video_id = o.video_id
          and d.event_id is null
          and (d.jurisdiction_name is distinct from o.jurisdiction_name
            or d.jurisdiction_type is distinct from o.jurisdiction_type
            or d.state_code is distinct from o.state_code
            or d.state is distinct from o.state
            or d.city is distinct from o.city)
    {%- endset -%}
    {%- do _repair_attribution_step(dry_run, 'event_documents',
        'select count(*) from ' ~ docs ~ ' d where exists (select 1 ' ~ doc_diff ~ ')',
        'update ' ~ docs ~ ' d set jurisdiction_name = o.jurisdiction_name,'
        ~ ' jurisdiction_type = o.jurisdiction_type, state_code = o.state_code,'
        ~ ' state = o.state, city = o.city ' ~ doc_diff) -%}

    {#- 8. policy-question instances copied from event_decision at clustering time -#}
    {%- set pqi = source('pq_bronze', 'bronze_question_instance') -%}
    {%- set pqi_diff -%}
        from {{ ref('event_decision') }} d
        join {{ civic_event }} ce on ce.id = d.c1_event_id
        join {{ ov }} o on ce.dedupe_key = 'youtube|' || o.video_id
        where q.source_type = 'local_decision'
          and q.source_id = d.event_decision_id
          and (q.jurisdiction_name is distinct from o.jurisdiction_name
            or q.state_code is distinct from o.state_code
            or q.city is distinct from o.city)
    {%- endset -%}
    {%- do _repair_attribution_step(dry_run, 'bronze_question_instance',
        'select count(*) from ' ~ pqi ~ ' q where exists (select 1 ' ~ pqi_diff ~ ')',
        'update ' ~ pqi ~ ' q set jurisdiction_name = o.jurisdiction_name,'
        ~ ' state_code = o.state_code, city = o.city ' ~ pqi_diff) -%}

    {%- if not dry_run -%}
        {%- do run_query('commit') -%}
    {%- endif -%}
{% endmacro %}

{#- One counted step of repair_youtube_channel_attribution: log the count; run the
    write only when dry_run is false and there is something to change. -#}
{% macro _repair_attribution_step(dry_run, label, count_sql, update_sql) %}
    {%- set n = run_query(count_sql).columns[0].values()[0] -%}
    {{ log(label ~ ': ' ~ n ~ ' rows to change', info=true) }}
    {%- if not dry_run and n | int > 0 -%}
        {%- do run_query(update_sql) -%}
        {{ log(label ~ ': repaired', info=true) }}
    {%- endif -%}
{% endmacro %}
