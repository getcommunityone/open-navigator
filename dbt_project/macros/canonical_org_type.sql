{% macro canonical_org_type(expr, default_type='other') -%}
    /*
        Map a raw org-type string (AI org_type, bronze_locations organization_type,
        NTEE hints, ...) onto one canonical type. Word/substring matched, most
        specific first. Pass default_type for sources with a known kind (e.g.
        'nonprofit' for NCCS).

        Canonical set: government | church | healthcare | education | nonprofit |
        political | business | other.
    */
CASE
    WHEN {{ expr }} IS NULL THEN '{{ default_type }}'
    WHEN lower({{ expr }}) ~ 'worship|church|ministr|parish|congregation|temple|mosque|synagogue|chapel|faith|diocese' THEN 'church'
    WHEN lower({{ expr }}) ~ 'police|sheriff|constable|marshal|gov|agency|municipal|township|federal|state agency|public safety|fire dep|fire dist' THEN 'government'
    WHEN lower({{ expr }}) ~ 'hospital|health|medical|clinic|hospice' THEN 'healthcare'
    WHEN lower({{ expr }}) ~ 'school|educat|universit|college|academy|institute' THEN 'education'
    WHEN lower({{ expr }}) ~ 'pac|committee|campaign|political|electioneer' THEN 'political'
    WHEN lower({{ expr }}) ~ 'non.?profit|charit|foundation|501' THEN 'nonprofit'
    WHEN lower({{ expr }}) ~ 'business|company|corp|for.?profit|llc| inc|enterprise|holdings|partners' THEN 'business'
    ELSE '{{ default_type }}'
END
{%- endmacro %}
