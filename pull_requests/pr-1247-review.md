---
pr: 1247
branch: feat/1233-dc-comment-segments
title: "feat(data-centers): segment public comments once per meeting and flag concerns, companies, AI and places (phase 1)"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: claude (/pr-review, read-only reviewer subagent + verification)
head_sha: af8ef740212c2cdbabe6227635151203c9760918
verdict: approve-with-nits
---

# PR Review: comment-level data-center dataset, phase 1 (#1233, epic #1232)

## Summary

Adds a topic-agnostic comment segmenter (`python -m ingestion.meetings.comment_segments`). It writes local bronze and
scrubs home addresses before storing. dbt adds staging → private flags intermediate → `segmented_meeting`,
`meeting_comment`, `data_center_comment` and `data_center_comment_place`, with four keyword seeds. There is
`GET /api/data-centers/comment-metrics`, a hand-counted label plus caption counts in Who spoke up, and the design doc with
the theirs-vs-ours table. No paid run and no Neon write.

## Scans

- Secrets: the automated scan flagged a credential-shaped default DSN; removed in 7f3c6168 (now requires
  `OPEN_NAVIGATOR_DATABASE_URL` or `--dsn`). Clean.
- Fabricated data: none. Unknown stance metrics are `null` with a reason. The UI shows a quiet "not available" line
  instead of zeros.
- Personal data / privacy: no comment text in any mart, public view or API. Names are served only as "First L." and
  are null for possible minors. Home addresses and street of residence are scrubbed before storage. Places are
  extracted after blanking the introduction and the heard name.
- Destructive: none. The segmenter replaces only its own rows per meeting; dbt built only the six new models.

## Findings (read-only reviewer, each verified; all blocking and should-fix items fixed in the "review fixes" commit)

### 🔴 Blocking (fixed)
1. A place name could reveal a surname ("Jackson" from the gazetteer, "John Park" as a neighborhood). Fixed: the
   introduction sentence and heard-name words are blanked before place matching (`data_center_comment_place.sql`).
2. The address scrub missed "we live on", "right on", "my home on", lowercase and unpunctuated streets. Fixed: the
   scrub is wider, cuts at a clause boundary or after 5 words, and has tests for each case.

### 🟡 Should fix (fixed)
3. Staff/applicant rule dropped residents who mention "the applicant" or "consultants". Now needs first-person framing.
4. Minor detection missed ordinal grades and age words. Added.
5. Quarterly trend ignored `year` without saying so. Now documented in the field description (a trend by design).

### 🔵 Nit
6. AI pattern "a. i" now needs both dots (fixed).
7. `CommentMetricsBlock` defaults to 2026. Acceptable while the story is the 2026 story; pass the year through when
   the story gains a year selector.
8. Year filter is now a date range so the index applies (fixed).

## Checks

- pytest: segmenter (12), seeds (6), API (4), plus existing data-center API tests: 52 passed. `ruff check` clean on
  changed Python.
- dbt: `dbt ls --select stg_meeting_comment_segment+` lists only the six new models. `dbt build` of exactly those:
  PASS=39, ERROR=0. `models.odcs --check`: current.
- Web: `npx tsc --noEmit` clean, vitest 3 passed, `npm run build` OK. Docs: `npm run build` SUCCESS.
- Local run: 47,578 comments in 13,682 of 18,260 meetings. 2026 data-center: 2,300 comments at 230 governments.
- CI on the previous head: all required checks green.

## Compliance

Issue first (#1233, Refs #1232) ✓ · Conventional Commits ✓ · new Python in packages/ with a `python -m` CLI ✓ · SQL logic
in dbt ✓ · PK/FK declared for all public models ✓ · `state_code` + `state` ✓ · scope label follows `?state=&city=` ✓ ·
no dim_/fact_ ✓ · follow-ups filed (#1260, #1261, #1262) ✓.

## Verdict

**approve-with-nits**
