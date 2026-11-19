/*
#593 — AI meeting.jurisdiction must not keep the Tuscaloosa demo label when the
warehouse place for that meeting is somewhere else (and bare id/slug forms are
never a display jurisdiction).
*/
select
    em.event_meeting_id,
    em.video_id,
    em.jurisdiction,
    em.jurisdiction_name,
    em.city
from {{ ref('event_meeting') }} em
where em.jurisdiction is not null
  and (
        (
            em.jurisdiction ~* 'tuscaloosa'
            and coalesce(em.jurisdiction_name, '') !~* 'tuscaloosa'
            and coalesce(em.city, '') !~* 'tuscaloosa'
        )
        or em.jurisdiction ~* '^[[:space:]]*tuscaloosa(_|[[:space:]])?0*[0-9]+[[:space:]]*$'
        or em.jurisdiction ~* '^[[:space:]]*city_of_tuscaloosa'
      )
