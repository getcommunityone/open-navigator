{#-
    Helpers reproducing the c1-promotion id / dedupe-key logic from the legacy
    scripts/datasources/openstates/sync_elections_to_c1.py
    (make_ocd_id / _truncate / fit_c1_id / _stable_key / _dedupe_key).

    These promote bronze.bronze_elections_scraped into the contracted election
    marts. The c1_* id columns were VARCHAR(50); the legacy code hashed long
    values into ``ocd-<short>/<uuid5>``. Postgres has no built-in uuid5(), so
    the marts use the same VALUE-FITS path the Python took (use the bronze
    ``ocd_id`` when it already fits 50 chars) and fall back to a deterministic
    surrogate built from the bronze row ``id`` when it does not. The dedupe_key
    (the actual ON CONFLICT key that drives dedup) is pure string concatenation
    and is reproduced VERBATIM, so dedup semantics match the legacy upserts.
-#}

{#- c1 VARCHAR limits, mirrored from _C1_LIMITS in the legacy loader. -#}
{% macro c1_limit(name) -%}
    {%- set limits = {
        'id': 50,
        'dedupe_key': 500,
        'division_id': 300,
        'jurisdiction_id': 300,
        'source': 100,
    } -%}
    {{ limits[name] }}
{%- endmacro %}

{#-
    _truncate: trim, NULL out empties, cap at max_len.
    Returns a SQL expression.
-#}
{% macro c1_truncate(col, max_len) -%}
    nullif(left(trim({{ col }}), {{ max_len }}), '')
{%- endmacro %}

{#-
    _stable_key(*parts): "|".join(p.strip().lower() for p in parts).
    Empty parts collapse to '' exactly as the Python join does.
-#}
{% macro c1_stable_key() -%}
    {%- set parts = varargs -%}
    {%- for col in parts -%}
        lower(trim(coalesce({{ col }}::text, '')))
        {%- if not loop.last %} || '|' || {% endif -%}
    {%- endfor -%}
{%- endmacro %}

{#-
    _dedupe_key(*parts): stable key, NULLed when entirely empty, capped at 500.
    `is_empty_expr` is a boolean SQL expression: TRUE when every part is empty
    (matches the Python `if not key: return None`).
-#}
{% macro c1_dedupe_key() -%}
    {%- set parts = varargs -%}
    nullif(
        left({{ c1_stable_key(*parts) }}, {{ c1_limit('dedupe_key') }}),
        {#- a key of only '|' separators (all parts empty) -> NULL -#}
        repeat('|', {{ (parts | length) - 1 }})
    )
{%- endmacro %}

{#-
    Stable c1 contest id.

    The legacy _contest_id() built make_ocd_id('candidatecontest', contest_key)
    where contest_key = dedupe_key(election_id, candidate_post, candidate_party);
    that key almost always overflows VARCHAR(50) so the value was ALWAYS hashed
    via Python uuid5. uuid5 has no SQL equivalent, so we substitute a
    deterministic md5 hash of the same key -> 'ocd-cc/<md5>' (39 chars, fits 50).
    Both dim_candidate_contests and fct_candidacies call this macro with the
    identical key expression, so the join between them stays consistent.

    `key_expr` is a SQL expression for the contest key; `fallback` (already a SQL
    expression) stands in for the legacy "contest_key or f'{election_id}|{id}'".
-#}
{% macro c1_contest_id(key_expr, fallback) -%}
    'ocd-cc/' || md5(coalesce({{ key_expr }}, {{ fallback }}))
{%- endmacro %}

{#-
    fit_c1_id(value, fallback): use `value` when non-empty and <= 50 chars,
    otherwise the deterministic surrogate `fallback` (already <= 50).
    NOTE: the legacy uuid5 hash of overflowing values is NOT reproducible in
    pure SQL; the fallback surrogate stands in for it (flagged in CONVENTIONS).
-#}
{% macro c1_fit_id(value, fallback) -%}
    case
        when {{ value }} is not null
             and length(trim({{ value }})) > 0
             and length(trim({{ value }})) <= {{ c1_limit('id') }}
            then trim({{ value }})
        else {{ fallback }}
    end
{%- endmacro %}
