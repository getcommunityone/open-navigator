-- #1089: a business exists only because a meeting or decision names it. Any row returned is a business
-- with no business_mention, so search would list it with nothing to show for it.
select b.business_id, b.business_name
from {{ ref('business') }} as b
left join {{ ref('business_mention') }} as m on m.business_id = b.business_id
where m.business_id is null
