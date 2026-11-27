---
title: How organizations are tied to topics
description: How the topic_organization mart ties curated topics to nonprofits (named in a meeting, 990 mission, name, IRS NTEE category), the curated rules, which rules were dropped as noisy after a spot-check, the counts, and what the API and story show (#1345).
---

# How organizations are tied to topics

**Issue:** [#1345](https://github.com/getcommunityone/open-navigator/issues/1345) · **Parent:**
[#1344](https://github.com/getcommunityone/open-navigator/issues/1344)

Owner, 27 Nov 2026: "We also need to better integrate nonprofits that are tied to topics and any upcoming events they
may have." A topic story now says which nonprofits in the place are working on the topic. This page records how an
organization is tied to a topic and why. Events: [Upcoming events of nonprofits](organization-events.md).

## The decision

An organization is tied to a topic only by something in the record, never by a guess or a model's opinion. Four ways,
strongest first (`evidence_rank`):

| Rank | `match_method` | The record says | Source |
|---|---|---|---|
| 1 | `named_in_meeting` | Its full name is said, word for word, within about 250 characters of the topic's words in one of the topic's recorded meetings in its own state | `topic_transcript_link` → `event_documents` |
| 2 | `keyword_in_mission` | Its latest Form 990 mission names the topic | GivingTuesday 990 missions (`stg_givingtuesday__990_missions`) |
| 3 | `keyword_in_name` | Its name names the topic | `mdm_organization` |
| 4 | `ntee_code` | Its IRS NTEE category is the topic's field | `mdm_organization_nonprofit.ntee_code` |

`cause_tag` is reserved in the contract but has no rows: the EveryOrg cause tags in `tag` have no organization linkage
in the warehouse, and `tag_organization` is NTEE-only, so a cause rule would only repeat the NTEE rule.

The rules for ranks 2 to 4 are a curated seed, `dbt_project/seeds/topic_organization_rule.csv` (topic slug, rule type,
a Postgres regex or an NTEE prefix, an optional side, a label). It is keyed by slug, not id, so a topic added later
(the crime and safety topics of #1128) picks up its rows when it reaches `civicsearch_topic`.

### Sides

A side is shown only when the organization's own words state it, and labelled neutrally: a name or mission saying
"Second Amendment", "right to bear arms" or "rifle association" is `gun rights`; "gun violence", "Moms Demand Action",
"Brady Campaign", "Everytown", "Giffords" or "Sandy Hook Promise" is `gun violence prevention`; "Fluoride Action Network"
`opposes fluoridation`. A rifle or gun club, a dental society or a bicycle coalition gets no side: what it does is not a
stated position on the policy. An organization that matches rules for both sides gets none.

### Named in a meeting: kept high precision

A first try, matching any nonprofit's name anywhere in a topic meeting's transcript, was mostly noise in a spot-check
of Alabama: "People Place", "All Hours of the Day", "Health Services" and "Team Confidence" matched ordinary speech,
and named organizations (a food bank, a museum) were only in the same three-hour meeting as the topic. So:

1. Only passages near the topic's words count (its `keyword_stats` phrases, 250 characters each side).
2. A candidate's cleaned name (Inc, Corp, The dropped) is at least 12 characters and two words, is held by no other
   nonprofit in the state, and has a word that occurs in 2% of topic passages or fewer.
3. It is based in the meeting's city, or already tied to the topic by a rule (a statewide advocacy group).
4. The passage holds the whole name: a full-text phrase match, then a regex on the passage's own words.

## Rules dropped after the spot-check

About 20 random rows per topic and method were read (27 Nov 2026, local warehouse).

| Topic | Rule | Why dropped |
|---|---|---|
| Data centers | Name contains "data center" | Mostly data repositories ("Geologic Data Center", "Travel Data Center", "Hospital Data Center") |
| Data centers | NTEE C35 (energy) | Energy co-ops and fuel-cell groups: the field, not data centers |
| Pickleball | NTEE N66 (racquet sports) | Coded on lacrosse, hockey and cricket clubs as well as tennis |
| Guns | NTEE I21 (youth violence prevention) | Soccer clubs, boot camps, family services |
| Guns | Name "Brady" (bare) | "Brady Cemetery Association"; now only "Brady Campaign / Center / United" |
| Guns | "Gun owners" as gun rights | "Gun Owners for Responsible Ownership" is a safety group; a name does not state a side |
| License plate readers | NTEE R60 (civil liberties) | Death-penalty, religious-liberty and gun groups |
| License plate readers | Name "Crime Stoppers" | Tip lines, not about plate readers |
| Violent crime | NTEE I21 | as for guns |
| Immigration | NTEE P84 (ethnic and immigrant centers) | Cultural and home-town associations, not immigration policy |
| Traffic safety | Name "MADD" (bare) | "Madd Skillz Society"; now "Mothers Against Drunk Driving" |
| Homelessness | Mission "homeless" | "Homeless pets": now excludes pets and animals |
| Water fluoridation | Name "dental" | Dental benefit plans and trusts excluded |
| Short-term rentals | Mission "vacation rental" | Community centers and unrelated missions; mission rule is "short-term rental" only |
| Bike lanes | Name "bike", "cycling" | Racing teams, BMX and mountain-bike clubs; now bicycle coalitions, alliances, advocates and "bike walk" |

What stayed reads well in the samples: pickleball clubs and associations by name or mission, dental societies and
oral-health groups for fluoridation (stakeholders in the debate, no side stated), short-term rental alliances, gun and
rifle clubs and gun-policy groups by mission, bicycle coalitions, civil liberties unions, and for the crime topics the
NTEE fields that name the work (family violence shelters, homeless services, animal shelters, fire departments).

## Counts

See the table below, from the build of 27 Nov 2026.
