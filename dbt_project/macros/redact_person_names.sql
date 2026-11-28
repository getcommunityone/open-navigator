{% macro redact_person_names(text_expr) %}
{#-
    Private names and home addresses out of a stored excerpt (#1468), applied to the source text BEFORE ts_headline so
    the <mark> highlighting is computed on the redacted words. The SQL twin of core_lib.privacy.NameRedactor, which the
    API runs again on every excerpt it serves (with the roster officials kept); this pass covers the stored copy.

      - a street address after "I live at", "my address is", or "of / at / from <number> ... <street suffix>"
        -> "[address]";
      - a name after a strong cue ("my name is", "name's", "next speaker is", "speaker will be"): first word kept,
        middle words dropped, surname cut to its initial ("my name is Mary Ann Smith" -> "my name is Mary S.");
        lower-case captions keep a lower-case initial ("john s.");
      - a surname after Mr./Mrs./Ms./Dr./Miss -> its initial ("Mr. Smith" -> "Mr. S.").
    Function words after a cue ("my name is on the list") are left alone.
-#}
{%- set stop = "(?:and|i|from|with|of|in|on|at|to|the|a|an|is|not|going|here|there|speaking|calling|resident|live|living|spelled|listed|signed|up|for|but|so|who|that|this|uh|um)\\M" -%}
{%- set word = "[A-Za-z][A-Za-z''-]+" -%}
regexp_replace(
  regexp_replace(
    regexp_replace(
      regexp_replace(
        coalesce({{ text_expr }}, ''),
        '(\m(?:i\s+live\s+at|i\s+reside\s+at|my\s+address\s+is|lives?\s+at)[,:]?\s+)\d{1,6}[A-Za-z]?(?:\s+[A-Za-z0-9.''-]+){0,4}',
        '\1[address]', 'gi'),
      '(\m(?:of|at|from)\s+)\d{1,6}[A-Za-z]?(?:\s+[A-Za-z0-9.''-]+){0,4}\s+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|court|ct|boulevard|blvd|way|place|pl|circle|cir|parkway|pkwy|highway|hwy|terrace|trail)\M\.?',
      '\1[address]', 'gi'),
    '(\m(?:my\s+name\s+is|my\s+name''s|name\s+is|next\s+speaker\s+is|speaker\s+is|speaker\s+will\s+be)[,:]?\s+(?:(?:uh|um)[,.]?\s+)?)(?!{{ stop }})({{ word }})(?:\s+(?!{{ stop }}){{ word }}){0,2}\s+(?!{{ stop }})([A-Za-z])[A-Za-z''-]+',
    '\1\2 \3.', 'gi'),
  '(\m(?:Mr|Mrs|Ms|Dr|Miss)\.?\s+)([A-Z])[A-Za-z''-]+\.?',
  '\1\2.', 'g')
{% endmacro %}
