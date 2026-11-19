{{ config(severity='error', tags=['data_centers']) }}

/*
#472: a data center meeting mention never carries a meeting_date later than the load date. A video whose source
date is in the future (a wrong YouTube date such as 2029-10-12) gets a NULL date, which sorts after dated rows,
instead of sorting first under "Said in meetings".

Output: one row per offending mention.
*/

select data_center_meeting_mention_id, video_id, meeting_date
from {{ ref('data_center_meeting_mention') }}
where meeting_date > current_date
