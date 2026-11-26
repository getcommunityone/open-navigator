-- #1089: quote_text is plain verbatim text cut to about 300 characters (no <mark> tags; those are added at render time).
select business_mention_id, length(quote_text) as quote_length
from {{ ref('business_mention') }}
where quote_text is null
   or btrim(quote_text) = ''
   or length(quote_text) > 320
   or quote_text like '%<mark>%'
