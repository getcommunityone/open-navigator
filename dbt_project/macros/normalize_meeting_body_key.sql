{% macro normalize_meeting_body_key(column) %}
{#
  Map a free-text meeting body label to a CANONICAL body-category token so a
  SuiteOne agenda/minutes title (e.g. '3:00 p.m. Finance Committee') and the
  AI-extracted event_meeting.body_name (e.g. 'Tuscaloosa Finance Committee
  Meeting') collapse to the same key ('finance') for matching.

  Normalization before keying:
    - lowercase
    - strip a leading meeting time ('3:00 p.m. ' / '5:00 a.m. ')
    - strip the trailing ' meeting' filler and a ' - canceled' suffix

  The CASE ordering is significant: more specific phrases ('public projects',
  'community development', 'zoning board') are tested before the broad fallbacks
  ('projects', 'planning/zoning', 'council') so e.g. a Zoning Board of Adjustments
  does not collapse into the generic planning bucket.

  Returns NULL when nothing meaningful is recognized (the document then stays an
  orphan rather than mis-attaching).
#}
{% set t %}
    regexp_replace(
        regexp_replace(
            regexp_replace(
                lower(coalesce({{ column }}, '')),
                '^\s*\d{1,2}:\d{2}\s*[ap]\.?m\.?\s*', '', 'i'
            ),
            '\s*-\s*canceled\s*$', '', 'i'
        ),
        '\s+meeting\s*$', '', 'i'
    )
{% endset %}
    case
        when {{ t }} ~ 'work session'          then 'work_session'
        when {{ t }} ~ 'canvass|election'      then 'election'
        when {{ t }} ~ 'community development' then 'community_development'
        when {{ t }} ~ 'public safety|safety'  then 'public_safety'
        when {{ t }} ~ 'public projects|projects' then 'projects'
        when {{ t }} ~ 'litigation|insurance'  then 'litigation_insurance'
        when {{ t }} ~ 'administration'        then 'administration'
        when {{ t }} ~ 'finance'               then 'finance'
        when {{ t }} ~ 'properties'            then 'properties'
        when {{ t }} ~ 'historic'              then 'historic'
        when {{ t }} ~ 'riverfront'            then 'riverfront'
        when {{ t }} ~ 'zoning board'          then 'zoning_board'
        when {{ t }} ~ 'planning|zoning'       then 'planning'
        when {{ t }} ~ 'city council|council'  then 'council'
        else null
    end
{% endmacro %}
