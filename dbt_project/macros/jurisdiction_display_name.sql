{#
  jurisdiction_name is the human display name ("Chilton County"), never an id (#501).

  Older YouTube loads stored the jurisdiction id as the name when the loader's join
  to int_jurisdictions missed: `COALESCE(j.name, s.jurisdiction_id)`. Two id shapes
  reached bronze:
    - the canonical slug id   `{place_slug}_{geoid}`  e.g. chilton_01021
    - the legacy county code  `c-{USPS}-{geoid}`      e.g. c-AL-01021
  These macros detect an id-shaped name and swap in the authoritative name.
#}

{#- Postgres regexes for an id-shaped jurisdiction_name (shared with the #501 test). -#}
{% macro jurisdiction_slug_id_regex() -%}
    '^[a-z0-9_]+_[0-9]{5,10}$'
{%- endmacro %}

{% macro jurisdiction_county_code_regex() -%}
    '^c-[A-Z]{2}-[0-9]+$'
{%- endmacro %}

{#- TRUE when `name` looks like a jurisdiction id. NULL-safe: NULL -> FALSE. -#}
{% macro jurisdiction_name_is_id_shaped(name) -%}
    coalesce(
        {{ name }} ~ {{ jurisdiction_slug_id_regex() }}
        or {{ name }} ~ {{ jurisdiction_county_code_regex() }},
        false
    )
{%- endmacro %}

{#-
  Display name with id-shaped values healed.

  name            : the stored name expression
  jurisdiction_id : the row's jurisdiction_id expression (or none when the row has none)
  canonical_name  : the authoritative name (int_jurisdictions.name joined on the id)

  Uses canonical_name when the stored name is NULL/blank, equals the id, or looks
  like an id. When no canonical name is available the result is NULL: an id is
  never surfaced as a name.
-#}
{% macro heal_jurisdiction_name(name, jurisdiction_id, canonical_name) -%}
    case
        when nullif(trim({{ name }}), '') is null
            {%- if jurisdiction_id %}
          or trim({{ name }}) = trim({{ jurisdiction_id }})
            {%- endif %}
          or {{ jurisdiction_name_is_id_shaped('trim(' ~ name ~ ')') }}
            then {{ canonical_name }}
        else trim({{ name }})
    end
{%- endmacro %}
