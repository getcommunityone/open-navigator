---
sidebar_position: 32
title: Decision place and company rules
description: When the question dashboard names a decision's address, a company, or a nearby tracked data center site, and when it stays silent.
---

# Decision place and company rules

Decided November 17, 2026, for [#508](https://github.com/getcommunityone/open-navigator/issues/508), the readable
"View dashboard" modal on Browse Questions.

Each decision row on the dashboard can say **where** (an address), **who** (a company) and which tracked data center
sites are **nearby**. All three are built in dbt, with no LLM, and a row shows nothing rather than a guess
(CLAUDE.md, "No Fabricated Data").

## Where: `decision_place_label`

The place comes from the decision's own reference graph: its `primary_place_id`, resolved in `event_place_geocoded`
within the same analysis. A decision with no primary place uses a non-primary reference only when that's its single
street-level reference. That way an address read out in public comment is never shown as the subject.

A place is shown only when all four checks pass:

1. **It is street-level.** A `street_address` must start with a house number and name a road. An `intersection` or
   `corridor` must name a road (`named_road_regex`: Road, Avenue, Parkway, Highway, I-70 and the like). Jurisdiction-wide
   places, facilities and vague text like "industrial corridor" never pass. This check keeps speech-to-text county
   names such as "Dicab County" (DeKalb), "Brooks County" and "Sum County" off the page.
2. **Its state agrees** with the state of the decision's own government. That government is the `jurisdiction_id` on
   the meeting's `civic_event` (`int_event_decision__jurisdiction`), not a name match.
3. **Its city doesn't contradict that government.** The city is empty, is that government, or (for a county) is a
   place inside it according to `jurisdiction_county_crosswalk`.
4. **Its address positively agrees** (`agreement_basis`):
   - `place_city`: the address's city is the government.
   - `city_in_county`: the city lies inside the county.
   - `address_names_jurisdiction`: one comma-separated part of the address is the government's name.

The warehouse holds no jurisdiction boundary polygons, so there's no "geocode inside the boundary" test. The check
reads the address text alone.

## Who: `decision_company_mention`

A company is named for a data center decision from one of two places, and `evidence_source` says which:

- **`decision_text`:** the decision's own `headline` or `decision_statement` says it.
- **`meeting_passage`:** a passage of the decision's own meeting says it ([#525](https://github.com/getcommunityone/open-navigator/issues/525)).
  The dashboard labels this one "Named in the meeting" and links to the recording. The rules are in the
  "Named in the meeting" section below.

Two lists are matched:

- **The seed `data_center_operators.csv`** holds real operators and developers with their aliases. A brand that is
  also an ordinary word (Switch, Stack, Compass, Aligned, Vantage, Meta, Oracle, Tract) is listed only in a company form.
  Examples are "Switch, Inc.", "Stack Infrastructure", "Compass Datacenters", "Meta Platforms", "Meta's" and "Oracle
  Cloud". The bare word is never listed.
- **The Epoch AI names on `data_center_site`** are the `owner`, `users` and `project` values. The "(likely)" and
  "(speculative)" tags are removed and lists are split on commas.
  - A project name such as "Hyperion" counts only in its site's state, and it is credited to that site's owner.
  - An Epoch name that is a seed operator or one of its aliases is skipped, so the seed's company-form rule governs it.
    Epoch's bare "Meta" therefore never matches.
  - Names shorter than four characters are skipped.

Matching is **case-sensitive, on a whole word or phrase** (`phrase_regex`). A non-alphanumeric character or the edge
of the text must sit on both sides. So lower-case "switch" or "stack" never match, and "AWS" doesn't match inside
"LAWS". Each row keeps `matched_text`, the exact words matched, and `evidence`, a verbatim excerpt with the match in
`<mark>`. The dashboard shows both. To add a company, add a row to the seed, using only real company names.

### Named in the meeting

A decision's meeting is its analysis: `event_decision.analysis_id` is `event_meeting.event_meeting_id`, and that row
holds the recording's `video_id`. The passages are the rows of `data_center_meeting_mention` for that `video_id`, the
~3-minute windows of the transcript that say "data center". A company counts from a passage only when **all three**
hold:

1. **Same meeting.** The passage is from the decision's own `video_id`. A company named in another government's
   meeting is never carried over.
2. **Inside the discussion window, when there is one.** The analysis can give each decision a `media_anchor` with start
   and end seconds. When both are clean numbers and in order, the passage's window (`passage_index * 180` to `+180`)
   must overlap them, and an untimed passage never passes. When the analysis gave no window, the whole meeting is used.
   **No decision in the warehouse has a window today** (the extraction leaves `media_anchor` empty on every data center
   decision), so today this is meeting-level: [#559](https://github.com/getcommunityone/open-navigator/issues/559).
3. **The passage says the company is the applicant or developer, next to the name.** The cues are `on behalf of X`,
   `teamed up with X`, `the applicant is X` / `the applicant, X`, `the developer is X` / `the developer, X`, and
   `X is a ... developer` (or `operator`, `owner`, up to 40 characters between, none of them a sentence end). They live
   in `cue_before_regex` and `cue_after_regex` in `macros/decision_text_match.sql`. Without a cue the company is
   named in passing, as another site's owner ("a Meta data center in Newton County") or as a hypothetical ("if Google
   is like, let's build a data center"), and it does not count.

Captions are mostly lower case, so a passage matches case-insensitively and the cue is what stops an ordinary word from
matching. The seed's `meeting_aliases` hold a bare word that is also ordinary English ("Powerhouse") and are matched
only here, never in a headline or statement. When a company is found in both places, `decision_text` wins.

Each row keeps the passage it came from (`data_center_meeting_mention_id`) and `start_seconds`, the passage's first data
center cue. That is the moment to jump to, **not the exact second of the quote**: the quote is somewhere in the
passage's 3 minutes. For `meeting_passage` the `evidence` is ~120 characters either side of the match, so the cue is in
the quote, and a test (`assert_decision_company_passage_evidence_is_verbatim`) checks that every quote is a substring of
the passage's own words.

### Adding a developer from a meeting

A developer or project code name goes in `data_center_operators.csv` only with the passage that names it: set
`source_kind` to `meeting_passage`, `source_url` to the recording at that moment, and `source_passage` to the verbatim
words. A test fails on a `meeting_passage` row with either one empty. Use the company's real name for `operator_name`;
`PowerHouse Data Centers` is shown for the word "Powerhouse" in the Spalding County meeting, which describes it as a
developer "wholly owned subsidiary of American real estate partners", matching PowerHouse Data Centers' own description
of itself as a wholly owned subsidiary of American Real Estate Partners. A name the meeting says but that cannot be
tied to a real company this way (the Birmingham mayor's "Neveah's data center") is not added.

## Nearby: `decision_nearby_data_center_site`

This table holds the Epoch AI sites whose governments (`int_data_center_site__jurisdiction`, #445) include the
decision's own government. The dashboard labels each one `Nearby tracked site: <site> (<owner>)`. It means the site
is near that government, and **not** that the decision is about it.

## Tested

The dbt unit tests in `_schema_decision_context.yml` check both rules:

- **Companies:** company forms match, while ordinary words, "LAWS" and an out-of-state project don't.
- **Companies from a meeting:** a company named with a developer cue in the decision's own meeting matches. Passing
  mentions with no cue, a passage outside the decision's window, and an untimed passage under a window don't. A
  company in the decision's own headline keeps `decision_text`.
- **Places:** "Dicab County", a state-contradicting corridor and an Atlanta address on a Spalding decision get no label.
  A Spalding road and a Griffin address do.
