{#-
    Body member roles and roster name keys (#1443). SQL twin of packages/ingestion/src/ingestion/governance/roles.py;
    pytest pins the Python on real roster titles and names. Change both together.
-#}

{#- The first body_role_rule (by priority) whose pattern matches the normalized title. -#}
{% macro body_role(title) -%}
coalesce((
    select _brr.role
    from {{ ref('body_role_rule') }} as _brr
    where btrim(regexp_replace(regexp_replace(lower(coalesce({{ title }}, '')), '[^a-z0-9 -]+', ' ', 'g'), ' +', ' ', 'g'))
          ~ _brr.pattern
    order by _brr.priority, _brr.rule_id
    limit 1
), 'member')
{%- endmacro %}

{#- "first last" for exact roster matching: suffixes, honorifics and middle initials dropped. -#}
{% macro person_name_key(name) -%}
(
    select case when array_length(_pnw.words, 1) >= 2 then _pnw.words[1] || ' ' || _pnw.words[array_length(_pnw.words, 1)] end
    from (
        select array(
            select _pnk.word
            from unnest(string_to_array(
                btrim(regexp_replace(regexp_replace(btrim(regexp_replace(regexp_replace(
                    replace(replace(lower(coalesce({{ name }}, '')), '''', ''), '’', ''),
                    '[^a-z ]+', ' ', 'g'), ' +', ' ', 'g')),
                    '(^| )(jr|sr|ii|iii|iv|dr|mr|mrs|ms|hon|honorable|rev)(?= |$)', ' ', 'g'), ' +', ' ', 'g')),
                ' ')) with ordinality as _pnk(word, o)
            where length(_pnk.word) > 1
            order by _pnk.o
        ) as words
    ) as _pnw
)
{%- endmacro %}
