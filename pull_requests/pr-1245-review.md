---
pr: 1245
branch: feat/1231-speaker-names-self-intros
title: "feat(stories): speaker names on meeting quotes from public-comment self-introductions"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: general-purpose read-only subagent and coordinator
verdict: approve-with-nits
---

# PR Review: feat(stories): speaker names on meeting quotes from public-comment self-introductions

## Summary

The PR names who is speaking on story-map quote cards. A regex extractor reads public-comment self-introductions
("my name is …", "I'm … and I live …", the chair's "next speaker is …") from the bronze transcripts. It doesn't use
any model and doesn't add any data from outside the record.

- dbt assigns each topic or data-center passage the nearest preceding introduction in the same recording.
- A resident is shown as "First L.". An official of that government is shown by name and title.
- No name is shown for students, minors, residents at school board meetings, or a first word that isn't a known
  given name.
- The API and the topic quote cards carry `speaker_display_name` and `speaker_role`.

The first review round found one critical and several important issues: an official's name could be taken from a
resident's greeting, ordinary words could pass as names, the student check missed some cases, school boards could be
missed, and repeated phrases could place a passage wrongly. All are fixed in `8c2dee9f` and `0000284f`, with tests.
Required CI was green on `d95f38ca`, and the local dbt build passed (35/35). The verdict is approve-with-nits. The
nits are known limits, documented in the design note.

## Scope of Change
- Files changed: 19 (+1,726 / -5, excluding the generated `api.types.ts` and ODCS contracts)
- Areas touched: api / web_app / web_docs / dbt_project / packages
- Commits:
  - 61609c6b feat(stories): speaker names on meeting quotes from public-comment self-introductions
  - 8c2dee9f fix(stories): tighter speaker-intro matching from review
  - 7c41fc80 chore(contracts): ODCS contract for meeting_passage_speaker
  - cc7e8c0e docs(contracts): list the gold-only meeting_speaker_intro key
  - 0000284f fix(stories): only known given names become speaker names, and a single ordered pass assigns passages
  - d95f38ca chore: merge origin/main (keeps #1230's stance-first selection and public_stance)
- Range reviewed: `725cde56..d95f38ca`

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | pass (run 46020355545, `d95f38ca`) |
| Documentation Build (Docusaurus) | pass |
| Backend Tests (Python) | pass (it failed earlier on a missing ODCS contract, fixed in 7c41fc80 / cc7e8c0e) |
| API Types (OpenAPI -> TypeScript) | pass |
| PR conventions | pass |
| Docker Build Test | skipped (no Docker files changed) |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean. The extractor reads the DSN from the environment. There are no credentials in the diff or in
  this file.
- **Fabricated data:** clean. A name is served only when the transcript says it. Every unknown case is `null`
  (no intro, intro out of window, suppressed, unrecognized first word, repeated needle). Test rows are only in tests.
- **Personal data:** clean. Bronze and staging keep the raw tokens heard, in the private warehouse.
  `meeting_speaker_intro` (gold) has no full private name column. `meeting_passage_speaker` (public) carries only
  the display form. The given-name gate uses an aggregate of first names (count ≥ 4) from `mdm_person`, and nothing
  about any person is joined or exposed.
- **Privacy and data ethics:**
  - No enrichment.
  - No sensitive traits: the role is only "Resident", an official's title, or null.
  - Minors and students are suppressed when the 200 characters before or the 300 after the intro mention a student,
    a grade, a school or an age under 18.
  - Every resident at a school board meeting is suppressed.
  - No scraping and no contact.
- **Destructive changes:** none. The bronze table is created with `CREATE TABLE IF NOT EXISTS`. Re-runs replace rows
  only for the videos scanned. Nothing touches `data/cache/`.

## Strengths
- Deterministic and free. The extractor is pure (`find_intros`), with 23 unit tests built from realistic caption
  snippets, including negative cases.
- The helpers `find_intros` and `clean_name_tokens` are importable. #1262 can reuse them in the comment segmenter.
- The privacy cut is applied twice: once in SQL, and again at the API (`speaker_fields`, `first_l`).
- The nearest-introduction lookup is a single ordered window pass. The first version scanned per passage and ran for
  more than 20 minutes.
- Every API lookup degrades to null when `meeting_passage_speaker` is missing.

## Findings
### 🔴 Blocking (Critical)

None remaining.

- **Fixed in 8c2dee9f.** `greeting_name` turned "good evening Mayor Walt Maddox, I live …" into an official
  attribution. Now greetings, chair calls and "this is" introductions never produce an official, and are dropped
  when a title comes before the name. Tested in `test_greeting_an_official_is_not_the_speakers_name`.

### 🟡 Should fix (Important, non-blocking)

All are fixed:

- **Ordinary words as names** ("my name is spelled wrong" became "Spelled W."). Fixed by:
  - rejecting suffixes (-ed, -ly, -ing, -ful, -ous, -ness);
  - extra stopwords;
  - requiring two tokens for weak patterns;
  - the dbt given-name gate (`unrecognized` → no name).

  Tested in `test_ordinary_words_are_not_names`.
- **A student mentioned before the name, or a bare age** ("I'm 16"): the window now includes the 200 characters
  before the intro, and the age pattern accepts a bare age. Tested in two tests.
- **School-board titles missed** ("Tuscaloosa City Schools Board Meeting", BOE, USD): fixed with a broader title and
  jurisdiction-name regex wrapped in `coalesce(…, false)`, plus `jurisdiction_type = school_district`.
- **Repeated phrases placed a passage wrongly:** a needle that occurs twice gets no speaker.
- **Two intros in one anchor window:** the window now uses `finditer`. Tested in
  `test_two_short_intros_in_one_window`.

### 🔵 Nits / suggestions (Minor)
- `meeting_speaker_intro.sql`: a resident who shares an official's first and last name, in that same government,
  would be shown as the official. This is rare: only 5 introductions matched an official, and none is near a story
  quote. It is documented as a limit.
- Attribution is by position, not by voice. A council reply inside three minutes of a resident's introduction would
  carry the resident's name. The 2,500-character window and the two-fragment rule limit this, and the limit is
  documented. Diarization (GPU, on hold) is the real fix.
- Coverage is low but honest: 5.1% of topic passages and 11.0% of data-center passages.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | #1231 has all four parts; branch `feat/1231-…`; `Closes #1231` |
| Conventional Commits | ✅ | All commits typed with a co-author trailer (merge commits excepted) |
| No fabricated data | ✅ | Names only from the transcript; null otherwise |
| New Python in `packages/` | ✅ | `python -m ingestion.youtube.speaker_intros`; nothing in `scripts/` |
| dbt for transformations | ✅ | Python extracts into bronze only; assignment, matching and display form are in dbt |
| Naming | ✅ | `state_code` carried; no dim/fact |
| Keys | ✅ | PK on both marts; FKs to `meeting_speaker_intro`, `topic_transcript_link`, `data_center_meeting_mention`, `person_government`; the left-out key is documented in data-contracts.md |
| Calendar years | n/a | |
| Scope label matches filter | n/a | Card content only |
| Match evidence on filtered tiles | ✅ | Unchanged; the passage stays the ts_headline excerpt |
| Docs | ✅ | New `development/speaker-names-from-self-introductions.md`; `guides/data-stories.md`; `data-contracts.md` |
| Telemetry and logging | ✅ | `topics.newest_with_speaker` span attribute; loguru in the extractor |
| Tests | ✅ | 23 extractor tests and 8 API tests |
| Shared libraries | ✅ | ingestion package tests: 718 pass, 10 collection errors from local `aiolimiter` absence (CI has it); datamodels 38 pass |

## Test Coverage

Run locally:

- `pytest packages/ingestion/tests/test_speaker_intros.py`: 23 passed.
- `pytest tests/test_api_data_center*.py tests/test_api_topic*.py tests/test_api_passage_speakers.py`: 169 passed.
- `pytest packages/datamodels/tests`: 38 passed.
- `python -m models.odcs --check`: current.
- `npx tsc --noEmit`: clean.
- `npx vitest run`: 717 passed.
- Docs build succeeded. Its broken-link warnings were already there before this PR.
- `dbt ls --select stg_bronze_meeting_speaker_intro+` lists only the three new models.
- `dbt build` of those three models: PASS=35.

Extractor run (`--story-passages`):

- 18,090 transcripts scanned, 10,660 with an introduction, 51,221 introductions, 4,494 flagged student or minor.

Coverage (served view `public.meeting_passage_speaker`):

| | Named | Residents | Officials | Withheld (student, minor, school board) | Unrecognized |
|---|---|---|---|---|---|
| Topic passages (of 16,459) | 847 | 847 | 0 | 98 | 122 |
| Data-center passages (of 6,323) | 696 | 696 | 0 | 40 | 118 |

Playwright, headless Chromium with `--use-gl=swiftshader`, own API on :8051 and Vite on :5251. Hovering map boxes
showed named quote cards:

- `/stories/pickleball`: "Alex F.", "Henry H.", "Steve Y.", "Bill B."
- `/stories/guns`: "Walt A.", "Bethany C."
- `/stories/data-centers`: "Leanne O.", "Jeremy H.", "Pat", …
- the home data-center map: "Brad M.", "Amanda K.", …

Every name shown was "First L." or a first name only.

## Verdict

Approve with nits. Nothing is blocking. Merge once the required checks are green on the head commit.
