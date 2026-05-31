-- Every tag must have its own self-row in tag_closure at depth 0
-- (the closure-table convention that makes a subtree query include its root).
-- Returns offending tags; the test passes when zero rows are returned.

select t.tag_id
from {{ ref('tag') }} as t
left join {{ ref('tag_closure') }} as c
    on c.ancestor_tag_id = t.tag_id
   and c.descendant_tag_id = t.tag_id
   and c.depth = 0
where c.descendant_tag_id is null
