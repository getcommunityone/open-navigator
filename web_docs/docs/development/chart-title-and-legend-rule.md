---
sidebar_position: 40
title: Every map and chart needs a title and a legend
description: The site-wide rule that each map and chart leads with a takeaway title and carries a compact colour legend, the shared ChartFrame component that enforces it, and the tests that check it.
---

# Every map and chart needs a title and a legend

Rule from the owner (#1409): "We always need a colour legend to indicate what this means, and a title to say clearly what the chart or map is saying."

## What every visual shows

- **A takeaway title.** It says the most interesting, impactful thing the real data supports for the scope and topic, not a description.
  Descriptions ("Short-term rental meetings by county · Florida") go in the one-line caption under the title.
- **A compact colour legend**, directly under or beside the visual, for every colour and shape drawn: stance colours in the topic's own
  position words, grey for "meetings, no stance on record", darker meaning more meetings, a ring for a town on record, hatched for proposed.
  It wraps to one or two lines on a phone and is never behind a "More" control.
- Legend colours come from the same palette constants the visual draws with (`BOX_COLORS`, `MEETING_GREYS`, `PHASE_COLOR`, `TONE_COLOR`,
  the CSS variables of `storyCharts.css`), so the two cannot drift.
- Real numbers only. When a figure is missing, the title falls back to a plain description; nothing is made up.

## How it is enforced

- `web_app/src/components/chart/ChartFrame.tsx`: `title` and `legend` are required TypeScript props. Every map and chart is drawn inside it
  (DOM hooks `[data-chart-frame]`, `[data-chart-title]`, `[data-chart-legend]`).
- `web_app/src/components/chart/ChartFrame.test.tsx` (vitest) renders each chart with fixture data and asserts a title and a legend.
- `web_app/e2e/chart-legends.check.mjs` (Playwright) opens the home page (national, Florida, Alabama; data centers and short-term rentals)
  and story screens at Pixel 7 and 1440 wide, and asserts that every chart `<svg>`/`<canvas>` has a visible title and a legend that fits.

## Picking the title

`web_app/src/utils/chartInsight.ts` (`pickInsight`, unit-tested in `chartInsight.test.ts`) scores the findings the data supports and leads with
the most impactful one:

1. A change in heat over time (needs at least 20 rated speakers in each of two consecutive years, and a clear rise).
2. Officials siding against the public (at least 5 meetings).
3. A sharp rise in attention (at least +30% as a share of recorded meetings, at least 5 meetings in each year; shares, because the current year is partial).
4. A clear public lean (at least 5 meetings or 20 speakers, at least half on one side). The top concern is added ("noise leads the complaints") only
   when it is the top cue in at least 30% of the opposing or heated turns read, and at least 5 of them. No title claims a cause without that evidence.
5. Volume and geography as the fallback, then a plain description.

Titles stay near 90 characters. The numbers behind a title are one tap away on the title's "i" button.

## Known gaps

- Per-year speaker heat and the top concern are served per topic and scope since #1418 (below). A topic with no concern list
  (today only data centers has one, `comment_concern_terms`) never gets the "leads the complaints" clause.

## Heat by year and top concern (#1418)

- `topic_heat_year` (dbt mart, `public.topic_heat_year`): one row per topic x scope (`national`, `state`, `city`) x calendar year.
  Mean heat (1-5), share of speakers with heat 4 or 5 and the count of rated speakers, from the classifier's reading of each
  public speaker's own words (`meeting_speaker_topic_side`, #1391). A year with fewer than `heat_year_min_speakers` (20) rated
  speakers has no row.
- `topic_top_concern` (dbt mart, `public.topic_top_concern`): one row per topic x basis x scope. Among the turns of speakers
  who opposed (`opposing`: side against) or were heated (`heated`: heat 4 or 5) on the topic, the concern named in the most
  turns, from the free keyword concern list (`comment_concern_terms`), with its turn count, the turns read and its share. No row
  under `top_concern_min_turns` (20) turns read. The stance-shape cue texts are verbatim phrases, not categories, so they are not
  counted here.
- `GET /api/topics/{slug}/heat-by-year?state=&city=` returns `{years: [{year: "2026", mean, speakers_rated, share_heated}]}`;
  `GET /api/topics/{slug}/top-concern?state=&city=` returns `{label, count, of, basis, share}` (the opposing basis, else heated;
  all null when there is no row).
- The picker still applies its own thresholds (20 rated speakers in each of two consecutive years and a clear rise; the
  concern in at least 30% and 5 of the turns read), so a finding fires only when both the server and the picker agree.
