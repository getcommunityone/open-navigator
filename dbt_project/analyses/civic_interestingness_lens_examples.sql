/*
Example consuming queries — one per story lens — over public.item_interestingness.
These document the lens→component mapping. Run any via `dbt compile` (analyses are
compiled, not materialized) or paste into psql. The serving layer (per-request,
with the proximity boost) is the rank_for_user() macro; see the bottom of this file.

Lens ordering:
  contested → conflict   money → money     new → novelty
  people → engagement    changed → surprise
  soon → urgency (forward window)          slipped → buried
  near → proximity (downstream / per-request only, NOT in the static score)
  default feed → interestingness_score
*/

-- default feed: overall interestingness (time-decayed composite)
select event_decision_id, jurisdiction_name, state_code, occurred_at, title,
       round(interestingness_score::numeric, 1) as score, top_signals
from {{ ref('item_interestingness') }}
order by interestingness_score desc
limit 50;

-- contested: closest votes / most competing views
-- select * from {{ ref('item_interestingness') }} where conflict > 0 order by conflict desc, interestingness_score desc limit 50;

-- money: biggest dollar impact for the jurisdiction's size tier
-- select * from {{ ref('item_interestingness') }} where money > 0 order by money desc, net_dollar_impact desc limit 50;

-- new: first time a subject came before this body
-- select * from {{ ref('item_interestingness') }} where novelty > 0 order by novelty desc, occurred_at desc limit 50;

-- people: most public-comment engagement
-- select * from {{ ref('item_interestingness') }} where engagement > 0 order by engagement desc, public_comment_speaker_count desc limit 50;

-- changed: outcome reversed vs a prior session on the same subject
-- select * from {{ ref('item_interestingness') }} where surprise >= 0.5 order by surprise desc, occurred_at desc limit 50;

-- soon: upcoming items, most urgent first (forward window; empty until scheduled_for has a source)
-- select * from {{ ref('item_interestingness') }} where scheduled_for is not null order by urgency desc limit 50;

-- slipped: high-impact items that drew little discussion
-- select * from {{ ref('item_interestingness') }} where buried > 0 order by buried desc, net_dollar_impact desc limit 50;

-- near: proximity is per-request — see rank_for_user(). Example (compile-time):
--   {{ rank_for_user('near', user_lat='42.36', user_lng='-71.06', window_days=365, limit_n=50) }}

-- default feed for one user with proximity boost:
--   {{ rank_for_user('default', user_lat='42.36', user_lng='-71.06', window_days=365, limit_n=50) }}
