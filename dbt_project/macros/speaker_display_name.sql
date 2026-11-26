{% macro speaker_display_name(speaker_id_expr, speaker_role_expr) %}
{#-
    A speaker's display name, "First L." (#1036), from the meeting analysis's speaker_id: a slug of the name heard in the
    meeting plus a role ("audra_taylor_resident", "andrea_varela_chief_of_staff"). The trailing role words (the row's own
    speaker_role, or a common role) are dropped. Exactly two name words left -> "Audra T."; more (a middle name, a place
    such as "cynthia_jones_arizona_city") -> the first name only, so a middle name is never shown as the surname; a slug
    that is only a role ("resident_2", "speaker_3") -> null. Never the full surname; nothing invented.
-#}
(
    with base as (
        select regexp_replace(
            regexp_replace(lower(coalesce({{ speaker_id_expr }}, '')), '[^a-z0-9_]', '', 'g'),
            '_(' || coalesce(nullif(regexp_replace(lower(coalesce({{ speaker_role_expr }}, '')), '[^a-z0-9]+', '_', 'g'), ''), 'zzzz')
                || '|former_council_member|council_member|chief_of_staff|business_owner|property_owner|not_stated'
                || '|resident|applicant|organizer|advocate|counsel|attorney|developer|representative|member|other'
                || '|engineer|consultant|staff|owner|neighbor|citizen|speaker)(_[0-9]+)?$',
            ''
        ) as b
    ),
    parts as (select string_to_array(b, '_') as a from base)
    select case
        when a is null or a[1] is null or a[1] !~ '^[a-z]{2,}$'
             or a[1] in ('speaker', 'unidentified', 'unknown', 'unnamed', 'resident', 'public', 'member', 'male',
                         'female', 'man', 'woman', 'citizen', 'caller', 'commenter', 'audience', 'person', 'mr', 'ms',
                         'mrs', 'dr', 'not', 'other', 'council', 'mayor', 'commissioner', 'chair')
        then null
        when array_length(a, 1) = 2 and a[2] ~ '^[a-z]{2,}$'
        then initcap(a[1]) || ' ' || upper(left(a[2], 1)) || '.'
        else initcap(a[1])
    end
    from parts
)
{% endmacro %}
