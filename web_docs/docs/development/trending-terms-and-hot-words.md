---
title: Trending terms and hot words in meeting speech
description: How we find open-ended terms rising in what people say at meetings and the words that run hot in public comment, for free and the same way every time, with the thresholds, the privacy filter and the evidence behind every term.
---

# Trending terms and hot words in meeting speech

Issue: [#1399](https://github.com/getcommunityone/open-navigator/issues/1399). Decided 2026-11-27. Builds on
#1352 (Browse all topics, share of recorded meetings), #1387 (public-comment speaker turns and heat) and #1140
(recorded meetings per year).

## The question

The owner asked: "Are we tracking other trending keywords and trending hot words that have a lot of heat in
discussion?" Before this change we tracked only curated topics and the major meeting topics matched by fixed phrases
(`/api/topics/yoy`). Nothing found a term nobody had listed in advance.

## What we built

A "Trending in meetings" row of term chips on **Browse all topics** (`/browse-topics/all`), with two sorts:

- **↑ Rising.** Terms whose share of recorded meetings went up most from last year to this year so far.
- **🔥 Most heated.** Terms said far more often by people speaking at heated moments than by other public
  commenters.

Tapping a chip shows the meetings and verbatim quotes that use the term. The term is highlighted, and the speaker
appears as "First L." or "Speaker not identified".

Everything is computed in dbt from our own transcripts. It needs no LLM and no paid run, and the same inputs always
give the same list.

## Method

### 1. Meetings (the denominator)

`int_trending_term__meeting` uses the same definition of a recorded meeting as `recorded_meeting_year`, row for row.
Summed per year, it equals that mart (a test checks this). A meeting is **counted** when it meets all three of these:

- it is dated in the last full year (2025) or in this year to date (2026, through November);
- it is not a school-board meeting (see Privacy);
- its transcript has a full-text vector in `event_documents` (about 99% of meetings do).

The counted meetings are 7,066 in 2025 and 15,558 in 2026.

### 2. Candidate terms come from public comment

Candidates are 1–3-word phrases said in **public-comment speaker turns** (#1387). We read segments where
`is_public_comment` is true, and never a possible minor. Each phrase is grouped by its stemmed full-text form, so "data
center" and "data centers" count as one term. The display form is the one people say most often.

Tokenizing every turn at once took the machine down, so `int_trending_term__sample_term` tokenizes a **fixed sample**:
up to 750 counted meetings with turns per year, ordered by `md5(video_id)` so that every rebuild picks the same
meetings. It processes one meeting at a time inside a `LATERAL`, and no table ever holds a row per token.

A phrase never starts or ends with a stopword, a word with an apostrophe or a word shorter than three letters.

### 3. Filters (`int_trending_term__candidate.drop_reason`)

| Reason | Rule |
|---|---|
| `excluded_word` | First or last word is filler, procedural or generic, from seed `trending_term_excluded` (`match = word`): "going", "motion", "second", "council", "people" and similar |
| `excluded_phrase` | Contains a boilerplate phrase from the seed (`match = phrase`): "public hearing", "roll call", "motion to approve", "next item", "my name", "pro tem" and similar |
| `thin_sample` | Said in fewer than 6 sampled meetings or 3 governments |
| `too_common` | Said in more than 35% of sampled meetings. A word everyone says can't trend |
| `person_name` | Privacy: see below |
| `place_name` | The name of a place with 20,000+ people. These rise when we start recording that place, not because people talk about it more |

See the pull request for the counts on the current build. On the first build, 1,185 otherwise-eligible candidates
were dropped as person names.

### 4. Counting meetings that say a term

`int_trending_term__jurisdiction_year` matches each kept term's phrase query (`phraseto_tsquery`, so no raw text is
ever parsed as a query operator) against the transcript vector of **every counted meeting**. It stores only rolled-up
counts per term, state, government and year. It never stores a row per meeting and term.

We read every meeting from its transcript, including meetings that have turns. Turn coverage more than doubled from
2025 to 2026 (970 to 2,831 counted meetings with turns). If we mixed turn text for some meetings with whole transcripts
for others, a term's share would move with turn coverage rather than with what people said. Candidates still come only
from public comment.

This is the heaviest step: about 25 minutes for roughly 10,800 terms across 22,600 meetings. The model has a
60-minute statement timeout and `work_mem = 64MB`.

### 5. Rising

`trending_term` holds one row per scope (national `US` and each state) and term:

- `share = meetings / counted meetings`, per year. This is the same idea as `/api/topics/yoy`, with school boards left
  out of both sides.
- `rise = share_2026 / share_2025` (null when the term wasn't said in 2025).
- `rise_score = ln(((m26 + 2) / r26) / ((m25 + 2) / r25))`. The +2 smoothing ranks new and rare terms sensibly.

A term is **eligible** in a scope when all of these hold:

| Scope | Meetings in 2026 | Governments in 2026 | Largest single government |
|---|---|---|---|
| National | ≥ 15 | ≥ 5 | ≤ 40% of the 2026 meetings |
| State | ≥ 5 | ≥ 3 | ≤ 40% of the 2026 meetings |

The scope must also have recorded at least 20 meetings in each year. The 40% cap means one place, or one long series
of meetings, can't carry a term.

A term isn't ranked when it is a **fragment** of a longer eligible term that is said in at least 85% as many meetings.
For example, "term rental" sits inside "short term rental". The longer phrase stands for it.

### 6. Hot words

`int_trending_term__hot` treats each speaker in a meeting as one document, built from all of that speaker's
public-comment segments. A speaker is **heated** when either of these is true:

- `heat >= 4` on `meeting_speaker_position`. Today that is the AI meeting analysis's own rating. The classifier's rating
  will land in the same column (`heat_method`) once its paid run is approved, and it is then used with no change here.
- the speaker spoke at a meeting where **both sides spoke** (`public_lean = 'mixed'`) or where **officials went against
  the public** (`officials_sided_against_public`), from `topic_meeting_lean` or `data_center_meeting_lean`.

The score is the **log-odds ratio with an informative Dirichlet prior** (Monroe, Colaresi and Quinn, 2008). It compares
heated speakers with all other speakers who said a term. The prior is the term's share of all speakers times 500, and
`hot_score` is the z-score.

A term needs at least 5 heated speakers in at least 3 meetings, and it is ranked only when `hot_score >= 1.96`. Heat is
too sparse per state, so a state's "most heated" list ranks that state's own eligible terms by the national score.

### 7. Serving

`public.trending_term` publishes only `is_served` rows, and only the columns the API reads. A served row is in the top
60 of any sort in its scope, so each scope has roughly 60 to 180 terms. That is about 6,500 rows and 1.2 MB.

`public.trending_term_evidence` holds excerpts for the terms in the top 20 of any sort in a scope. It keeps each
government's newest counted meeting that says the term, for the 5 newest governments nationally plus the newest one
per state where the term is served. That is about 6,800 rows and 1.7 MB.

Together they stay under 3 MB; a test checks this. The serving view drops the stored URL, and the API builds the
YouTube link from `video_id`. Each government's newest meeting is taken from the counting step
(`latest_meeting_date`), so building the evidence never searches every transcript again.

- `GET /api/trends/terms?state=&sort=rising|hot|volume&limit=` (default 20)
- `GET /api/trends/terms/{term_id}/evidence?state=&limit=&offset=`

A city in the URL is answered for its state, and the chip row says so ("counted per state, not per city").

## Privacy (blocking)

These rules follow AGENTS.md, Privacy and data ethics.

- **No private person's name trends.** `int_trending_term__name_lexicon` lists every word used as a first or last name
  in our name data: self-introductions in meetings, officials (`person_government`) and legislators (`legislator`). A
  single word counts as a **name word** when two conditions hold. First, two or more people use it as a given name, or
  three or more as a surname. Second, those name uses are at least 25% of the sampled meetings that say the word. So
  "john" (about 1,050 name uses, said in 298 meetings) is a name, while "budget" (3 surname uses, said in 474 meetings)
  is a word.
- A phrase with a given-name word followed by a surname word is a name too.
- A name-shaped term is kept only in two cases: it is on the reviewed allow-list `trending_term_public_figure` (U.S.
  presidents and vice presidents, a few governors and national business leaders, "Martin Luther King"), or, for a
  first-and-last name, it matches a public official in `int_trending_term__official_name`. A single surname is never
  allowed through the official rule, because it is too ambiguous.
- Common civic words that are also names ("bill", "grant", "park", "hope") are listed in `trending_term_common_word`
  and are never treated as names.
- This over-blocks some place names ("virginia", "montgomery"). We accept that in exchange for privacy.
- **Sensitive terms are counts only.** A term containing a word from `trending_term_sensitive` (health conditions such
  as "cancer", religion, immigration status, sexual orientation, disability, race or ethnicity, criminal history,
  finances) carries `is_sensitive`. Its evidence never names a speaker: the mart drops the name and the API drops it
  again.
- **Self-introductions are redacted.** In every excerpt, "my name is Jane Doe" becomes "my name is [name]".
- **Minors and school boards.** School-board meetings are left out of the counts, the denominator and the quotes.
  Possible-minor segments are never read.
- Speaker names are only ever "First L.", taken from the segment's own self-introduction (`meeting_comment`).

## Evidence (show the match)

Each excerpt is a verbatim `ts_headline` with the term in `<mark>`…`</mark>`. The page renders it with
`highlightSnippet`, which React-escapes it and never uses `dangerouslySetInnerHTML`. The excerpt comes from a
public-comment segment of that meeting when one says the term, with its speaker and a link to the moment. Otherwise it
comes from the transcript, with the speaker not identified.

## Rebuild

```bash
cd dbt_project
dbt seed --select trending_term_excluded trending_term_public_figure trending_term_sensitive trending_term_common_word
dbt run --select int_trending_term__meeting int_trending_term__name_lexicon int_trending_term__official_name \
  int_trending_term__sample_term int_trending_term__candidate int_trending_term__jurisdiction_year \
  int_trending_term__hot trending_term trending_term_evidence
```

You can also select by tag: `--select tag:trending_terms`. Changing a seed only needs the candidate and mart steps,
because new drops are filtered downstream. Adding a term to the kept set needs `int_trending_term__jurisdiction_year`
rebuilt.

## Limits

- The 2026 numbers are partial-year, and they use shares rather than counts.
- Candidates come from about 1,500 sampled meetings. A term said only outside public comment can't trend.
- Heated speakers mostly come from contentious meetings (about 385 with turns), many of them about data centers, so
  the heated list leans toward those fights. It will widen once the classifier's heat lands.
