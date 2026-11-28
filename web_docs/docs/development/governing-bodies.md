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

## Officials heard most recently (body_recent_speaker)

Captions carry no speaker labels, and officials almost never say "my name is", so the speaker layer (#1387) names
residents but hardly ever an official (4 of 152k speaker rows were `official_roster_match`). The chair and the clerk do
name officials at the moment they speak, so `python -m ingestion.youtube.official_mentions` (regex, no model) looks
for a title plus a roster surname of the meeting place's members and keeps only three shapes:

| Pattern | Real caption text (Tuscaloosa City Council, 2026) |
|---|---|
| roll_call | "voting with councelor Howard. >> Yes. >> Yes." / "voting on the application, Mr. Lanier. No. No." |
| chair_call | "Thank you, Zach. Mayor Maddox. >> Yes, sir." / "Councilman Busby. >> Yeah, I'll do these two." |
| self_intro | "this is Councilor Howard" |

A plain mention ("Mr. Henry will be here at 2:00") is not counted. Only names on the place's roster can match, so a
name heard in a meeting never makes anyone an official; a surname two members share needs the first name too. Caption
misspellings of a surname ("Laneir") are missed rather than guessed. The rows land in
`bronze.bronze_meeting_official_mention` with the seconds from the timed caption segments.

`body_recent_speaker` has one row per body × member heard in that body's meetings in the last 18 months: meetings
heard, moments, the last date and a YouTube link three seconds before the latest moment. Official self-introductions
already matched in `meeting_speaker_intro` count too. A member is shown with their seat on the place's primary body
(so a council member heard in a committee keeps their council role). Residents never appear: every row joins a
`body_membership` row.

On 2026-11-28: 3,812 recent transcripts in 482 places with a roster were scanned; 540 had a moment (5,474 moments);
212 body × member rows across 92 bodies in 46 places. Tuscaloosa: the mayor, Raevan Howard, Cassius Lanier, Lee Busby
and Richard Henry, across the council, its committees and Planning and Zoning.

## API and place page

- `GET /api/jurisdictions/{id}/bodies` (id = jurisdiction_id or Census geoid): each body with meeting count and date
  range, member count (distinct people with a current seat), members and roles (current, plus seats that ended in
  the last year so a vacancy reads as one), and officials heard recently. 404 for an unknown place; an empty list when
  we know no bodies.
- `GET /api/bodies/{id}?limit=`: the body with its place, members, officials heard and recent meetings.
- The four marts are on the `publish_public_serving` list with ODCS contracts. Their routes live in `api/main.py`, so
  `api.types.ts` (generated from `api.app`) does not change.
- The place home `/jurisdiction/:jurisdictionId/meetings` shows "Who governs `<place>`" (the heading names the place in
  the URL, the scope label) and "Officials heard most recently" with a play link to the YouTube moment and a link to
  the official's person page. `/bodies/:bodyId` shows the body with its place as the scope label, members and roles,
  ended seats, officials heard and recent meetings; the Close comes from Layout like every sub-page. Empty states say
  "not on file" instead of showing a number. Checked at Pixel 7 and 1440 by `web_app/e2e/who-governs.check.mjs`.

## Coverage (local warehouse, 2026-11-28)

Places are jurisdictions other than states. "Member with a role" = a current seat from a roster source (officials data,
council roster or Legistar; OpenStates chamber seats are counted separately: 7,387 seats on 100 chamber bodies in 50
states).

| State | Places with meetings | Places with ≥1 body | Places with ≥1 member with a role | Places with officials heard |
|---|---|---|---|---|
| AL | 100 | 104 | 13 | 4 |
| CA | 161 | 214 | 78 | 6 |
| NC | 138 | 139 | 5 | 2 |
| IL | 137 | 159 | 36 | 3 |
| OH | 155 | 160 | 11 | 1 |
| MA | 62 | 68 | 9 | 2 |
| TX | 149 | 175 | 41 | 1 |
| MN | 91 | 95 | 9 | 1 |
| MI | 91 | 103 | 13 | 0 |
| WI | 119 | 125 | 9 | 1 |
| NJ | 108 | 123 | 18 | 2 |
| **All** | 2,628 | 2,949 | 483 | 46 |

Rows after AL are the ten states with the most meetings on file.

What is missing:

- **Council members.** Most places' only member is a mayor from OpenStates. Only 23 places have three or more seated
  members on their primary body; in Alabama, Tuscaloosa (mayor + 6 seated, District 5 vacant since 2026-09-18) and
  Northport. The Alabama places with the most meetings (Mobile, Scottsboro, Homewood, Montgomery, Fairhope) have no
  roster. Follow-up: [#1472](https://github.com/getcommunityone/open-navigator/issues/1472).
- **Committee members.** Committees get members only from Legistar; elsewhere a committee shows "Members not on file".
- **Legistar people pages.** 2 of 2,197 Legistar members match a `person_government` row by exact name, so most have
  no person page yet (#1472).
- **Renamed bodies** appear twice (Tuscaloosa "Public Projects Committee" in 2020-2026 agendas and "Projects
  Committee" on YouTube since 2024) until an alias seed merges them (#1472).
- **Officials heard** depends on captions naming members; misspelled surnames are missed by design.

Sources blocked by terms or robots: none in this run. All 24 Legistar portals answered through the polite client
(Dallas, Atlanta and Minneapolis publish bodies but no current office records). The Legistar agenda/minutes PDF hosts
disallow crawlers in robots.txt and were not touched. No city roster page was fetched in this work; the council roster
scraper's existing curated rosters (Tuscaloosa, Northport, Boston, Kingsport) flow in through the officials data.

## Publish set

The API reads these through `public` (publish_public_serving). Nothing was written to Neon. When the owner publishes,
the relations to add to the Neon set are `governing_body`, `meeting_body`, `body_membership` and
`body_recent_speaker` (local sizes: 10,667, 168,227, 10,121 and 212 rows).
