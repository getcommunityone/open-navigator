{% macro stance_shape_sql(units) %}
{#-
    The stance-shape rules (#1383) over any relation `units` with columns unit_id, unit_text, concern_count.
    Used on one segment (int_meeting_comment__stance_shape) and on all of a speaker's text joined together
    (int_meeting_speaker__stance_shape), so the two never drift. Cue rules: seed comment_stance_shape_terms.
    Returns unit_id, stance_shape, shape_cue_text, both_side_cues.
-#}
with c as (
    select unit_id, unit_text as comment_text, concern_count from {{ units }}
),

rules as (
    select cue_kind, pattern, priority from {{ ref('comment_stance_shape_terms') }}
),

hits as (
    select
        c.unit_id,
        r.cue_kind,
        left(regexp_replace((regexp_match(c.comment_text, '(' || r.pattern || ')', 'i'))[1], '\s+', ' ', 'g'), 160) as cue
    from c
    cross join rules as r
),

per as (
    select
        unit_id,
        max(cue) filter (where cue_kind = 'support')                      as support_cue,
        max(cue) filter (where cue_kind = 'oppose')                       as oppose_cue,
        max(cue) filter (where cue_kind = 'for_concept_against_project')  as site_cue,
        max(cue) filter (where cue_kind = 'condition')                    as condition_cue,
        max(cue) filter (where cue_kind = 'open_terms')                   as open_cue
    from hits
    where cue is not null
    group by unit_id
)

select
    c.unit_id,
    (case
        when p.site_cue is not null                                         then 'for_concept_against_project'
        when p.condition_cue is not null
             and (p.support_cue is not null or p.oppose_cue is not null)    then 'conditional'
        when p.open_cue is not null and p.oppose_cue is not null            then 'against_concept_open_to_terms'
        when p.support_cue is not null and p.oppose_cue is null             then 'clear_for'
        when p.oppose_cue is not null and p.support_cue is null             then 'clear_against'
        when p.support_cue is null and p.oppose_cue is null
             and c.concern_count > 0                                        then 'concerns_only'
        else 'unclear'
    end)::text as stance_shape,
    (case
        when p.site_cue is not null                                         then p.site_cue
        when p.condition_cue is not null
             and (p.support_cue is not null or p.oppose_cue is not null)    then p.condition_cue
        when p.open_cue is not null and p.oppose_cue is not null            then p.open_cue
        when p.support_cue is not null and p.oppose_cue is null             then p.support_cue
        when p.oppose_cue is not null and p.support_cue is null             then p.oppose_cue
        else null
    end)::text as shape_cue_text,
    (p.support_cue is not null and p.oppose_cue is not null)::boolean       as both_side_cues
from c
left join per as p on p.unit_id = c.unit_id
{% endmacro %}
