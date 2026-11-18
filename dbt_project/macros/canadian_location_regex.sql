{#
  canadian_location_regex() — POSIX regex matching a CivicSearch `location`
  ("Toronto, Ontario") that ends in a Canadian province or territory (#533).
  CivicSearch indexes Canadian municipal meetings; they have no US jurisdiction,
  so event_documents excludes them. Use as `location ~ '{{ canadian_location_regex() }}'`.
#}
{% macro canadian_location_regex() -%}
, *(Ontario|Quebec|Québec|Nova Scotia|New Brunswick|Prince Edward Island|Newfoundland and Labrador|Newfoundland|Manitoba|Saskatchewan|Alberta|British Columbia|Yukon|Northwest Territories|Nunavut)$
{%- endmacro %}
