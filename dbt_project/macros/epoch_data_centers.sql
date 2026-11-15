{#-
    Helpers for Epoch AI data center rows (DC-4.1, #249).
-#}

{#- Epoch tags uncertain names: "Amazon #confident", "OpenAI #likely", "xAI #speculative".
    Drop #confident; turn the others into a visible "(likely)" / "(speculative)"; tidy
    spaces; blank -> null. -#}
{% macro epoch_confidence_text(expr) -%}
nullif(btrim(regexp_replace(regexp_replace(regexp_replace(
    coalesce({{ expr }}, ''),
    '\s*#confident\y', '', 'gi'),
    '\s*#(likely|speculative)\y', ' (\1)', 'gi'),
    '\s+', ' ', 'g')), '')
{%- endmacro %}

{#- A US state code from a free-text address: the address ends in ", XX" or ", <State name>",
    optionally followed by a ZIP and ", USA". Only real states match; anything else -> null.
    The match is anchored at the comma, so "West Virginia" can't be read as "Virginia". -#}
{% macro us_state_code_from_address(expr) -%}
{%- set us_states = [
    ('AL','Alabama'),('AK','Alaska'),('AZ','Arizona'),('AR','Arkansas'),('CA','California'),
    ('CO','Colorado'),('CT','Connecticut'),('DE','Delaware'),('DC','District of Columbia'),
    ('FL','Florida'),('GA','Georgia'),('HI','Hawaii'),('ID','Idaho'),('IL','Illinois'),
    ('IN','Indiana'),('IA','Iowa'),('KS','Kansas'),('KY','Kentucky'),('LA','Louisiana'),
    ('ME','Maine'),('MD','Maryland'),('MA','Massachusetts'),('MI','Michigan'),('MN','Minnesota'),
    ('MS','Mississippi'),('MO','Missouri'),('MT','Montana'),('NE','Nebraska'),('NV','Nevada'),
    ('NH','New Hampshire'),('NJ','New Jersey'),('NM','New Mexico'),('NY','New York'),
    ('NC','North Carolina'),('ND','North Dakota'),('OH','Ohio'),('OK','Oklahoma'),('OR','Oregon'),
    ('PA','Pennsylvania'),('RI','Rhode Island'),('SC','South Carolina'),('SD','South Dakota'),
    ('TN','Tennessee'),('TX','Texas'),('UT','Utah'),('VT','Vermont'),('VA','Virginia'),
    ('WA','Washington'),('WV','West Virginia'),('WI','Wisconsin'),('WY','Wyoming'),
    ('PR','Puerto Rico')
] -%}
{%- set tail = "(\\s+[0-9]{5}(-[0-9]{4})?)?\\s*(,\\s*(USA|US|United States))?\\s*$" -%}
(
    case
    {%- for code, name in us_states %}
        when {{ expr }} ~ ',\s*{{ code }}{{ tail }}' then '{{ code }}'
        when {{ expr }} ~* ',\s*{{ name }}{{ tail }}' then '{{ code }}'
    {%- endfor %}
    end
)
{%- endmacro %}
