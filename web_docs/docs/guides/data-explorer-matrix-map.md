---
title: Data explorer Matrix map
sidebar_label: Matrix map
description: The Matrix map tab in Data explorer is one scrolling report over the ACS bundle, told as a public meeting in five chapters and twelve numbered sections, each with a story sentence computed from the data in view, a chapter and section band, data tables under every figure, the Open Navigator house theme plus seven reference themes, and a URL for every view.
---

# Data explorer: Matrix map

The **Matrix map** tab (`/data-explorer/matrix`) sits next to Map view and Scorecard. It reads the same published
American Community Survey (ACS) 5-year bundle as the map and presents it as **one scrolling report of twelve numbered
sections**, one chart type per section, grouped into **five chapters**. Under the page heading are the controls that apply
to every section: **Metric**, **Vintage** and **Theme**.

## Five chapters, told as a public meeting

This product is about local government meetings, so the report follows the order of one. Each chapter opens with a full-width
**chapter card**: a small monospaced eyebrow (`Chapter 1 of 5 · Call to order`), a very large title, one sentence computed from
the metric, vintage and geographies in view, and a thin rule that draws under the title.

| Chapter | Meeting item | Story | Sections |
| --- | --- | --- | --- |
| 1 `problem` | Call to order | The problem: where things stand | 01 Tiles, 02 Dot map, 03 Share |
| 2 `decision` | The motion | The decision: what changed and who sits above or below | 04 Compare, 05 Diverging, 06 Bars |
| 3 `challenge` | Public comment | The challenge: what complicates the picture | 07 Scatter, 08 Heatmap |
| 4 `implementation` | The vote and the work | Implementation: how it played out across the years | 09 Trend, 10 Columns, 11 Pivot |
| 5 `action` | New business | The call to action | 12 Table, then the action block |

The last chapter ends with an **action block** of large square buttons that carry the scope in view: **See decisions in
(state)** (the decisions browse page with `?state=`) when one state is in scope, **See decisions nationwide** otherwise,
**Download this table (CSV)** (the same file as the Table section) and **Open the map view**. One state is in scope when the
Dot map is drilled into it (`dot`) or the Share section shows its counties (`part=county`, `st`). A "Play" button will be added
when its route exists (issue 852); no button points at a page that does not exist.

### How the sentences are written

Every section's headline and its one supporting sentence, and every chapter card's sentence, are produced by pure functions in
`web_app/src/utils/matrixStory.ts` from the data the section already computed, and they change with the metric, vintage and
filters (the entrance animation does not replay). The rules, which the unit tests check:

- **Only what the data shows:** rankings, counts, shares, changes, and a correlation's direction and strength with its r-squared
  ("rises with ... moderately; r² is 0.32"). Never a cause, a forecast, a judgment ("should", "worrying", "good") or a claim
  about people.
- **Lower-is-better metrics** still read "highest" and "lowest"; the copy never says "best" or "worst".
- **Nothing is filled in.** When a needed figure is missing, the headline names the chart and its scope ("Poverty rate, 2023: no
  tile values are available.") and there is no supporting sentence.
- **Ties are named** ("Alabama and Puerto Rico share the lowest ..."), a single geography is said plainly, and numbers come from
  the same formatters as the charts, so a sentence matches the chart beside it. Years are plain strings.

Each section has the same layout. On a wide screen the left column holds the eyebrow (`06 — Trend`), a large headline and a
short text, and the right column holds the figure with its controls, its `FIG. 06` caption and a **Show data table**
button, with a hairline between the two. Below about 1024 pixels the columns stack, text first. The Heatmap and Table
sections put the figure full width under the text because they are wide.

| # | Section | What it shows | Use it to |
| --- | --- | --- | --- |
| 01 | **Tiles** | One box per geography, shaded by rank. Flat, By region or By quarter regroups the boxes; each group is headed `name · count (share %)` | See every geography at once |
| 02 | **Dot map** | The country as a grid of dots; click a state for its counties | Read the geography of a metric |
| 03 | **Share** | A 100% stacked bar with labelled segments, a 10x10 waffle and a list, for states of the U.S. or counties of a state | See each part's share of the whole |
| 04 | **Compare** | A dumbbell per geography: hollow dot for the earliest vintage, filled dot for the selected one, the change on the right | See who moved, and by how much |
| 05 | **Diverging** | Bars left or right of the median geography, sorted by value by default | See who is above or below the middle |
| 06 | **Bars** | One horizontal bar per geography for the metric, with region chips | Rank geographies, one region at a time |
| 07 | **Scatter** | One metric against another, coloured by Census region, with a trend line, slope and r-squared | See whether two metrics move together |
| 08 | **Heatmap** | Geographies by metrics, each cell shaded by that metric's rank; click a header to sort | Scan every metric at once |
| 09 | **Trend** | The metric across every vintage, one line per chosen geography plus the median across states | See change over time |
| 10 | **Columns** | One stacked column per vintage, stacked by Census region (counts only) | See how regions add up over time |
| 11 | **Pivot** | Geographies as rows, up to 8 metrics as columns, each column shaded, a Share column and a Total row for count metrics; click a header to sort | Compare several metrics side by side |
| 12 | **Table** | Every geography with every metric, bars, change and trend; search, sort and **Download CSV** | Take the numbers away |

## The chapter and section band

A bar under the Data explorer tabs stays at the top of the screen (just below the site header) while you scroll. It lists
the five chapters by short name (Problem, Decision, Challenge, Implementation, Action) with the section numbers `01` to `12`
under each, marks the chapter and the section in view (both links have `aria-current`), shows the meeting item and section
name on the right, and draws a thin progress line along its bottom edge. Click a name or a number, or tab to it and press
Enter, to jump there. It is a `nav` of real links.

## Titles and figures animate in once

Chapter titles and section headlines use the Folio reference's masked line rise: each line of the title sits behind its own
overflow-hidden mask and rises into place over 900 ms (the `--d-4` duration, `--ease-out` curve), the second line 80 ms after
the first and the third and later lines 160 ms after, with the eyebrow fading in first and a rule drawing under chapter titles.
It plays once, when the title block first has 20% of itself in view above the bottom 10% of the viewport (the reference's
trigger numbers). The lines are the lines the browser really sets the text in (measured from a hidden copy, and re-measured
when the width or the web font changes), so the stagger reads line by line at any width. A filter change swaps the words in
place and a resize re-flows them, but neither replays the animation. Under reduced motion the titles are simply there. The
full title text is available to screen readers through a visually hidden copy; the masked lines are hidden from them.
Charts start their own intro when their section comes into view: bars and lines grow, columns rise, dots and tiles appear. The
Trend lines draw as you scroll the section into place. Each section does this once.

## Legends you can click

Charts with a legend use square chips with a colour swatch. **Click a chip** to switch that series off or on; an off chip is
dimmed with a lighter border, and the chart re-lays out with animation (columns re-stack, lines fade, bars and points hide,
the other share segments re-share the remaining total). **Hover or focus** a chip to highlight its series and dim the
others. At least one series always stays on; a click that would turn off the last one is ignored. The chips are real
buttons (`aria-pressed`) with a visible focus ring. This applies to Columns (regions), Trend (each geography and the median),
Scatter (regions), Share (segments) and Diverging (below and above the median). The hidden series are kept in the address
bar as `off=section:series,...`. Bars region chips are a filter instead (`region`).

## Show data table

Under every figure's caption, **Show data table** opens a real HTML table (`th scope`) of exactly the rows and values the chart
draws, in the same scope and with the same formatting. It follows the chart: switch a legend chip off and the column goes from
the table too. One table is open at a time and is kept in the address bar (`table=trend`). The Dot map's table lists the
states; while a state's counties are open it says no data table is available, because county values are read by the map.

## Table and CSV

Section 12 lists every geography with every metric. The header stays fixed while the body scrolls. The **search** box (`q`)
filters by name, state code or region without regard to case. Column headers sort (they have `aria-sort`): State, Region, each
metric and Change. `sort=change` orders by the change column, `sort=region` by Census region; the other values are `name` or a
metric slug, and `dir` is `asc` or `desc`. Rows glide to their new places when the sort changes (not under reduced motion).

- **Bars.** Each metric cell shows its formatted value and a thin bar. The bar's length is the value's position between that
  metric's lowest and highest value among the rows currently shown, so searching rescales the bars. A missing value has no bar.
- **Change.** The selected metric from the earliest vintage in the bundle to the selected vintage, in the metric's unit
  (`+5.3 pp` for percentage metrics, a signed formatted number otherwise). It reads `—` when either value is missing, and is never
  computed from a missing value. The colour follows Compare: good is violet, bad is vermilion, and for lower-is-better metrics a
  fall is good.
- **Trend.** A sparkline of the selected metric across every vintage in the bundle, ending in a dot at the selected vintage. The
  line breaks where a vintage has no value instead of bridging it, and a geography with fewer than two values shows `—`. Every bar
  and sparkline has a text equivalent (the cell text, and for the sparkline each vintage's value, read by screen readers).

**Download CSV** saves the rows exactly as filtered and sorted, named `matrix-map-<metric>-<vintage>.csv`. The file has a header
row, CRLF line ends, quotes around any value that contains a comma, quote or line break, and an **empty cell** for a missing
value. The columns are state, state code, FIPS, region, vintage (a string such as `2023`, never `2,023`), one column of raw
numbers per metric, then `Change` (the selected metric's difference, in its own unit) and one column per vintage for the selected
metric, headed by the year (`2019`, `2021`, ...). The file holds values only.

## Share and Pivot

**Share** labels each segment of the 100% bar above it with a thin leader line to the segment's centre, on a second or third row
when neighbours would collide. The whole-number percentage sits inside a segment that has room, in whichever of ink or white
reads better on its colour; a segment too narrow for its number carries the percentage in its label instead (`Maine 2%`).
Percentages are rounded by largest remainder, so they add up to 100. Hovering or focusing a segment highlights it and its row in
the list; the legend chips still switch segments off.

**Pivot** has heavy rules above and below the header, hairline row rules and sort arrows (`↕` unsorted, `↓` / `↑` sorted). When the
selected metric is a count it adds a **Share** column: each row's share of that metric's total across all rows, with a thin bar.
The **Total** row adds up count columns over the rows shown (per region when grouped); a metric that cannot be summed, such as a
rate, reads `—`. Hovering or focusing a Pivot row picks out that geography's tile in Tiles (section 01) and dims the others.

## Themes

The **Theme** control offers eight themes. **Open Navigator** is the default (it is used whenever `theme` is absent): it is
built from the product's own colours, a warm off-white page, near-black ink, the slate of the site's primary colour for the
band, and a ramp that runs from a light teal tint through the teal of the logo to dark slate. The opposite pole (below the
median, alerts) is amber, and a muted red is kept for "worse" in better and worse colouring. Series are teal, amber, red and
a light blue, never red against green. The seven themes of the Folio reference stay selectable: Lavender Press, Newsprint,
Night Edition, Gazette Mono, Swiss Poster, Forest Ochre and Riso Pastel.

A theme is a set of CSS custom properties applied only inside the Matrix workspace, so no other tab or page changes. It is kept
in `theme`. Text, chart labels and the section band meet 4.5:1 contrast in every theme, bars and sparklines 3:1, and the
Open Navigator series stay apart for protan, deutan and tritan colour vision; tests check all of it.

## Reading the colours

Tiles, Pivot, Heatmap and Dot map use six shade steps. Darker means a better rank; for metrics where lower is better (for
example poverty) the scale is flipped. The **Highlight** slider grays out every cell below a chosen point on the scale and says
how many cells remain highlighted. In the Dot map, a state's counties are scaled within that state, so county shades are not
comparable with the national view. The Heatmap ranks each column on its own.

## Things to know

- **Share and Columns work only on counts** (population, housing units, labor force and similar). In Columns, a metric that is a
  rate, median or percentage shows a "can't be stacked" message with a button to switch to a count; in Share the first count
  metric is used and the text says so. The Share whole is the 50 states plus the District of Columbia; Puerto Rico is left out,
  as in the ACS definition of the United States.
- **Columns sum only what exists.** A region with no value in a vintage is left out of that column and is never counted as
  zero. The number of states behind each segment is in the tooltip. A vintage whose file is missing leaves an empty slot.
- **Compare needs two vintages.** The base is the earliest vintage in the bundle, the other end is the selected vintage. With only
  one vintage, or the earliest selected, the section says so. The change column reads `+13 pp` for percentage metrics, a signed
  formatted number otherwise, and `—` when either reading is missing. For lower-is-better metrics the line is coloured by better
  or worse, and the legend says so.
- **Diverging is sorted by value by default** (`Sort by value` or `Alphabetical`). The lighter step of a bar is the distance up to
  the nearest quartile, the middle half of geographies; the stronger step is the distance beyond it. The number at the end of
  each bar is the real distance from the median in the metric's own unit.
- **Trend** lines are the geographies in `geo` (state FIPS, up to 8; by default the four highest in the selected vintage) plus
  the median across states. There are no event markers: the bundle has no event data.
- **Scatter shows association between places, not cause.**
- **Sorting is shared** by Pivot, Heatmap and Table (`sort`, `dir`), and Compare and Diverging read the same parameters.
- **Missing data is shown as missing.** A geography with no value is gray and reads `—`. A section with nothing to draw says "No
  data available" instead of drawing a chart.
- **The view is in the address bar.** Everything that shapes the data is a URL parameter, so a link or a refresh returns the same
  view. `layout=<section>` is a deep link: the page scrolls to that section on load, and as you scroll the address updates to the
  section in view without adding history entries. `chapter=<id>` does the same for a chapter card; while a chapter card is in
  view the address carries `chapter` (and no `layout`), and while a section is in view it carries `layout` (and no `chapter`).
- Opening a tile or a state name goes to the national map for that metric. The map does not yet open on that state.

## URL parameters

`chapter` (chapter id: `problem`, `decision`, `challenge`, `implementation`, `action`), `layout` (section id: `tiles`, `dots`,
`share`, `dumbbell`, `diverging`, `bars`, `scatter`, `heatmap`, `trend`, `columns`, `pivot`, `table`), `metric`, `vintage`, `theme`, `cols` (pivot columns), `sort`, `dir`, `group` (`region` or `quartile`), `min`, `y`
(scatter), `part` and `st` (share), `dot` (dot map drill), `region` (bars), `geo` (trend), `q` (table search), `table` (open data
table), `off` (hidden legend series). The Columns Absolute / Share toggle is not in the address bar.

## When the Data explorer shows no data

Map view and Matrix map both read the census bundle from `/data/census-map/` (in the repository,
`web_app/public/data/census-map/`). The bundle is generated and git-ignored, so a fresh checkout, or a machine where
that folder was cleaned, does not have it. Both tabs then say **No map data available** and name the command that
creates the files:

```bash
python -m ingestion.census.export_census_map_static --all-years
```

Reload the page afterwards. A missing file comes back from the dev server as the app's own page with a success status, not
as an error, which is why the page checks for it explicitly.

## For developers

- Page: `web_app/src/pages/DataExplorerMatrixPage.tsx` (data loading, shared controls, URL, band and position tracking).
  One component per section and the shared pieces are in `web_app/src/components/matrix/`: `SectionShell` (spread layout,
  data table toggle), `TitleBlock` (the measured, masked title entrance), `ChapterCard`, `ActionBlock`, `SectionBand`, `LegendChips`, `Tooltip`, `DivergingBars`, and `*Section.tsx` files.
  The dot map is `web_app/src/components/DotMatrixMap.tsx`.
- Story copy: `web_app/src/utils/matrixStory.ts` (`CHAPTERS` and one pure function per section, tested in `matrixStory.test.ts`).
- Pure helpers with tests: `web_app/src/utils/matrixTable.ts` (`toCsv`, `filterRows`, `stackByRegion`, `barFraction`, `signedChange`, `sparklinePath`, `layoutLabels`, legend toggles and the
  `off` parameter), `matrixMapMath.ts` (scales, median, quantiles, regression), `folioThemes.ts` and `folioRamp.ts`
  (themes and contrast).
- Data: `/data/census-map/manifest.json`, `{vintage}/state_metrics.json`, `{vintage}/county_metrics.json`, written by
  `python -m ingestion.census.export_census_map_static`. Every vintage's state file is loaded so Compare, Trend and Columns
  can draw. Shapes come from the us-atlas Albers topologies.
- `DivergingBars` takes generic rows, `{label, segments: [{key, value, side}]}`, with any number of ordered segments per side.
  A true five-category stack (for example public-comment stance: For, Against, Asked questions, Mixed or neutral) is
  **a follow-up**, to build on the same component once that data is loaded. The census data is not survey data, so no
  categories are invented here.
- Plan for showing meeting and decision metrics in the same sections:
  [Meeting metrics for the Matrix map](../development/meeting-metrics-matrix-map-design.md).

## Look and motion

The Matrix map uses the "Folio" look: flat paper background, hairline rules, square corners, no shadows, large light
numerals and small monospaced captions. The design tokens (paper, ink, violet, vermilion, neutral data colour, type,
durations and easings) are CSS custom properties in `web_app/src/styles/folio.css`, scoped to the `.folio` wrapper class and
set per theme from `folioThemes.ts`. Fonts are Geist and Geist Mono, self-hosted from the `@fontsource-variable` packages and
loaded only with this page. The four figures under the heading (geographies with data, median, highest, lowest) are computed
from the state values already loaded for the selected metric.

### Motion rule

What moves, and when:

- **Chapter and section titles** slide up line by line (behind a mask) when the title first enters view; the eyebrow fades up and a chapter rule draws.
- **Tiles** appear on a diagonal wave the first time the section is seen. When the sort or grouping changes, each tile glides
  to its new place and its colour fades to the new shade.
- **Rows** (Pivot, Bars, Compare, Diverging) appear in a short stagger and glide when the sort, filter or grouping changes. The
  stagger is capped so a 52-row chart finishes in about 1.2 seconds.
- **Bars, share segments and dumbbell lines** grow from their origin; **columns** rise one after another; **Trend lines** draw
  as you scroll the section into place; **scatter points, waffle squares and dot-map dots** fade and scale in.
- **Legend toggles** re-stack, fade or shrink the affected series over about 0.6 seconds.
- **Key figures** count up to their value over about 0.9 seconds whenever the value changes.

Rules that always hold:

- **Reduced motion.** When the visitor's system asks for reduced motion, nothing animates: titles, strokes, bars, tiles,
  count-ups and scrolling all show their final state at once.
- **Numbers never animate to anything but the real value.** A count-up always ends on the exact formatted value from the
  data. If a value is missing, the figure shows a dash and does not count at all.
- Motion never changes what is shown: the scope label, the URL parameters and the data are the same with or without it.

## If the page does not load (#856)

The Matrix map's code and fonts load only when its tab is opened. If they fail to load, the tab shows "Matrix map
could not be loaded" with the error and a Reload button, and the rest of the site keeps working. On a developer
machine the usual cause is a pull that added a package: run `npm install` in `web_app` and reload.
