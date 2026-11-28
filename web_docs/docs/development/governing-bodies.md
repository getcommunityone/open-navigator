---
title: Governing bodies, members and roles
description: How a place page shows who governs it, which body held each meeting, who sits on each body in what role, and which officials were heard most recently, from meeting titles, platform body fields, rosters and roster-matched speaker turns.
---

# Governing bodies, members and roles

Issues: parent [#1441](https://github.com/getcommunityone/open-navigator/issues/1441); bodies
[#1442](https://github.com/getcommunityone/open-navigator/issues/1442), members
[#1443](https://github.com/getcommunityone/open-navigator/issues/1443), officials heard
[#1444](https://github.com/getcommunityone/open-navigator/issues/1444), API
[#1445](https://github.com/getcommunityone/open-navigator/issues/1445), UI
[#1446](https://github.com/getcommunityone/open-navigator/issues/1446). Decided 2026-11-28.

## The problem

The owner asked for "a feature for organizing the council or committee for all cities, and what person or role each
person is". A place page should say which bodies govern the place (city council, planning and zoning, board of
adjustment, committees), how many of their meetings we hold, who sits on each and in what role, and which officials
were heard most recently with a link to the moment. A peer product shows this; it is listed in citations as
reference only, and nothing of theirs is fetched, copied or reused.

## Bodies come from what the meetings say

A meeting's title or body field names the body that met, in many spellings: "Tuscaloosa Zoning Board of
Adjustments", "Zoning Board of Adjustment Meeting - Oct 26, 2026", "BOC Business Session". `int_meeting_body__matched`
reads three meeting sources:

| Source | Text tried, in order |
|---|---|
| YouTube videos with a jurisdiction (`event_youtube_with_jurisdiction`, minus videos the meeting-kind screen says are not public meetings) | the title, then the AI body name on `event_meeting` |
| Legistar / Granicus (`platform_meeting`) | the platform's body name, then the title |
| Scraped agendas and minutes (`event_meeting_document`) | the body name, then the meeting title |

Each text is cleaned (`clean_meeting_title_for_body`: dates, times, brackets, the place's own name, a state name or
code after it, and filler such as "meeting", "regular", "livestream" go) and then tried against the ordered pattern
seed `seeds/governing_body_pattern.csv`. The first pattern whose `applies_to` (any, municipal, county,
school_district) fits the place wins:

- curated bodies: school board, planning and zoning, zoning board of adjustment or appeals, planning commission or
  board, zoning commission, historic preservation, board of health, and the place's own governing body (city/town/
  village/common/borough council, aldermen, select board, village board, county commission, board of supervisors,
  commissioners court, fiscal court, county council);
- council sessions ("Pre-Council Briefing", "Council Work Session", "Committee of the Whole") count as meetings of the
  governing body but do not vote on its name;
- `__skip__`: a county body named in a city's video ("Tuscaloosa County Commission" stamped on the city) is not
  the city's, so the meeting gets no body rather than a wrong one;
- generic rules build a key from the cleaned name for anything ending in committee, commission, authority, board,
  council, task force, district or agency ("Finance Committee" becomes `committee:finance_committee`).

A title that names no body (a ceremony, a news clip, "Community Development Meeting") stays unlinked. On the
2026-11-28 warehouse, 72% of 229k meetings matched a body.

### Why a seed and a Python twin

Transformations live in dbt (CLAUDE.md), so the warehouse resolves titles in SQL. The same regexes live in
`ingestion.governance.body_titles` so pytest can pin the behaviour on real titles in CI, where there is no warehouse.
Both read the one pattern seed, and both are checked against the one example seed
(`seeds/governing_body_title_example.csv`): pytest for Python, `tests/assert_governing_body_title_examples.sql` for
SQL. Patterns use only syntax both engines read the same way (no `\b`; word edges are `(^| )` and `( |$)` over the
single-spaced cleaned text), and an alternative that is a prefix of another comes after it, because Postgres prefers
the longest alternative and Python the first. A parity run over 41k real titles found no differences in the cleaned
text.

## governing_body and meeting_body

- `governing_body`: one row per jurisdiction × body. PK `governing_body_id` = md5(jurisdiction_id | body_key); FK
  `jurisdiction_id`. `body_name` is the name most of its meetings use (else a default for its type); `meeting_count`
  counts distinct meeting dates on file, so a re-upload or the same meeting from two sources counts once (a council
  meeting and its pre-council briefing on the same day count as one date). A place whose officials include a mayor or
  council members gets its governing body even with no meetings (`sources` includes `roster`, `meeting_count` 0).
- `meeting_body`: one row per matched meeting, with FKs to `governing_body`, `jurisdictions`, `platform_meeting` and
  `event_meeting`, the title, date, recording URL and which text and pattern matched.

## Members and roles (body_membership)

`body_membership` has one row per body × member × role (a council member who is also president pro tem has two
rows). Sources, in order of trust; when two give the same member the same role on the same body, the first wins:

| Source | What it gives | How it is tied to a body |
|---|---|---|
| Officials data (`person_government` + `person_government_term`) | mayors and council members, district, start/end dates from terms (a seed term beats a roster snapshot; a term with no end beats an ended one) | the place's own governing body |
| Council roster scraper (`scrapers.municipal.council_roster`, rows `ocd-membership/scraped-...`) | council members a city's own site lists | the place's own governing body; `source = council_roster` |
| Legistar office records (`scrapers.platforms.legistar_people`) | current seats on every Legistar body (council, committees, boards) with title and dates | the body name is resolved with the same title rules as meetings; the member is tied to a `person_government` row only on an exact name key in the same place |
| OpenStates chamber memberships (`stg_openstates__chamber_member`) | state senators and representatives with district | two chamber bodies at the state jurisdiction (`legislature_upper`, `legislature_lower`), FK to `legislator` |

Roles come from the title through the ordered seed `seeds/body_role_rule.csv` (mayor, president, president_pro_tem,
vice_mayor, chair, vice_chair, council_member, alderman, commissioner, supervisor, member, legislator, clerk, staff).
Name keys for matching are "first last" with suffixes, honorifics and middle initials dropped, and must be equal: there
is no fuzzy matching. Python twins (`ingestion.governance.roles`) are pinned by pytest; a parity run over 14,865 real
titles and names found no differences.

A past member stays with `is_current = false` and the end date the term gives (Tuscaloosa District 5 after
2026-09-18), so a vacancy shows as a vacancy and nobody is invented to fill it.

### Legistar, politely

The reader uses the same `PoliteClient` as the meeting reader: robots.txt honoured (webapi.legistar.com serves none,
which RFC 9309 reads as no rules), the open-navigator User-Agent, one request a second, and a 403/429 or challenge
page stops that portal as `blocked` with no retry. Office records carry a public office email, but no feature needs
it, so it is not stored. On 2026-11-28 all 24 portals we read meetings from answered; Dallas, Atlanta and
Minneapolis publish bodies but no current office records. The API returned server errors for about 20 minutes during
the run; the reader records those as `error` and a later run picks them up.

## Publish set

The API reads these through `public` (publish_public_serving). Nothing is written to Neon by this work; the relations
to add to the Neon publish list when the owner runs a publish are listed in each pull request.
