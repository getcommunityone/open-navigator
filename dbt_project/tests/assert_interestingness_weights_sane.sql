-- Sanity-check the interestingness_weights seed: the weight set must sum to ~1.0
-- (the score normalizes by the sum, but a wildly off total signals a typo), every
-- weight in [0,1], and all seven components present exactly once. Returns failing
-- rows (test passes when empty).

with agg as (
    select
        sum(weight)                          as total_weight,
        count(*)                             as n_components,
        count(distinct component)            as n_distinct,
        min(weight)                          as min_w,
        max(weight)                          as max_w
    from {{ ref('interestingness_weights') }}
)
select *
from agg
where total_weight not between 0.99 and 1.01
   or n_components <> 7
   or n_distinct <> 7
   or min_w < 0
   or max_w > 1
