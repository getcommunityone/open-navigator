{#-
    Local concern categories (DC-4.3, #251): one shared word list, used by area_concern
    (what residents object to) and data_center_agenda_item.concerns (what an agenda
    item touches), so the two always mean the same thing.

    Case-insensitive Postgres regexes; \y is a word boundary. Deliberately narrow:
    "power" alone or "zoning" alone are too common to mean a concern.
-#}

{% macro local_concern_patterns() -%}
{{ return([
    ('water',       '\\y(water|wells?|aquifers?|groundwater|wastewater|drought|cooling)\\y'),
    ('electricity', '\\y(electric (bills?|rates?|costs?)|electricity (bills?|rates?|costs?|prices?)|utility (bills?|rates?)|power (bills?|rates?)|the grid|power grid|energy (bills?|costs?))\\y'),
    ('noise',       '\\y(noise|noisy|humming|decibels?|loud)\\y'),
    ('land',        '\\y(farmland|farm land|property values?|home values?|rural character|green ?space|open space|wetlands?|trees)\\y'),
    ('taxes',       '\\y(tax (breaks?|abatements?|incentives?)|abatements?|incentives?|pilot agreements?|payments? in lieu)\\y'),
    ('traffic',     '\\y(traffic|trucks?|congestion)\\y'),
    ('pollution',   '\\y(pollution|emissions?|diesel|generators?|air quality|exhaust|smog)\\y'),
]) }}
{%- endmacro %}
