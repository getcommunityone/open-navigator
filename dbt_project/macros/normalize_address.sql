{% macro normalize_address(expr) -%}
    /*
        Normalize a street-address string into a canonical match string.

          - unaccent + lowercase + trim
          - punctuation -> spaces
          - expand common USPS abbreviations (st->street, ave->avenue,
            n->north, ...) using word boundaries so "1st" / "first" survive
          - drop unit/suite designators and everything after them
          - collapse whitespace; empty result -> NULL

        Word-level deterministic only — this is the cheap key for exact/near
        blocking. Hard parses (street_number vs street_name) come from the
        usaddress/libpostal enrichment. See entity-resolution-mdm.md (Layer 1).

        The abbreviation table is a Jinja loop so adding a mapping is one line
        rather than another nested REGEXP_REPLACE.
    */
{%- set abbreviations = [
    ('street',    'st|str'),
    ('avenue',    'ave|av'),
    ('boulevard', 'blvd'),
    ('road',      'rd'),
    ('drive',     'dr'),
    ('lane',      'ln'),
    ('court',     'ct'),
    ('place',     'pl'),
    ('circle',    'cir'),
    ('terrace',   'ter'),
    ('highway',   'hwy'),
    ('parkway',   'pkwy'),
    ('northeast', 'ne'),
    ('northwest', 'nw'),
    ('southeast', 'se'),
    ('southwest', 'sw'),
    ('north',     'n'),
    ('south',     's'),
    ('east',      'e'),
    ('west',      'w')
] -%}
{%- set ns = namespace(sql="LOWER(TRIM(UNACCENT(" ~ expr ~ ")))") -%}
{%- set ns.sql = "REGEXP_REPLACE(" ~ ns.sql ~ ", '[^a-z0-9]+', ' ', 'g')" -%}
{%- for full, abbrs in abbreviations -%}
{%- set ns.sql = "REGEXP_REPLACE(" ~ ns.sql ~ ", '\\y(" ~ abbrs ~ ")\\y', '" ~ full ~ "', 'g')" -%}
{%- endfor -%}
{%- set ns.sql = "REGEXP_REPLACE(" ~ ns.sql ~ ", '\\y(apt|apartment|suite|ste|unit|rm|room|fl|floor|bldg|building)\\y.*$', '', 'g')" -%}
{%- set ns.sql = "REGEXP_REPLACE(" ~ ns.sql ~ ", '\\s+', ' ', 'g')" -%}
NULLIF(TRIM({{ ns.sql }}), '')
{%- endmacro %}
