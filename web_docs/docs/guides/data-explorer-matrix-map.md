---
title: Data explorer Matrix map
sidebar_label: Matrix map
description: The Matrix map tab in Data explorer is one scrolling report of twelve numbered sections over the ACS bundle - tiles, share, pivot, compare, bars, trend, columns, heatmap, diverging, scatter, dot map and a table with CSV download - with a section band, data tables under every figure, seven themes and a URL for every view.
---

# Data explorer: Matrix map

The **Matrix map** tab (`/data-explorer/matrix`) sits next to Map view and Scorecard. It reads the same published
American Community Survey (ACS) 5-year bundle as the map and presents it as **one scrolling report of twelve numbered
sections**, one chart type per section. Under the page heading are the controls that apply to every section: **Metric**,
**Vintage** and **Theme**.

Each section has the same layout. On a wide screen the left column holds the eyebrow (`06 — Trend`), a large headline and a
short text, and the right column holds the figure with its controls, its `FIG. 06` caption and a **Show data table**
button, with a hairline between the two. Below about 1024 pixels the columns stack, text first. The Heatmap and Table
sections put the figure full width under the text because they are wide.

| # | Section | What it shows | Use it to |
| --- | --- | --- | --- |
| 01 | **Tiles** | One box per geography, shaded by rank. Flat, By region or By quarter regroups the boxes; each group is headed `name · count (share %)` | See every geography at once |
| 02 | **Share** | A 100% stacked bar, a 10x10 waffle and a list, for states of the U.S. or counties of a state | See each part's share of the whole |
| 03 | **Pivot** | Geographies as rows, up to 8 metrics as columns, each column shaded; click a header to sort | Compare several metrics side by side |
| 04 | **Compare** | A dumbbell per geography: hollow dot for the earliest vintage, filled dot for the selected one, the change on the right | See who moved, and by how much |
| 05 | **Bars** | One horizontal bar per geography for the metric, with region chips | Rank geographies, one region at a time |
| 06 | **Trend** | The metric across every vintage, one line per chosen geography plus the median across states | See change over time |
| 07 | **Columns** | One stacked column per vintage, stacked by Census region (counts only) | See how regions add up over time |
| 08 | **Heatmap** | Geographies by metrics, each cell shaded by that metric's rank; click a header to sort | Scan every metric at once |
| 09 | **Diverging** | Bars left or right of the median geography, sorted by value by default | See who is above or below the middle |
| 10 | **Scatter** | One metric against another, coloured by Census region, with a trend line, slope and r-squared | See whether two metrics move together |
| 11 | **Dot map** | The country as a grid of dots; click a state for its counties | Read the geography of a metric |
| 12 | **Table** | Every geography with every metric; search, sort and **Download CSV** | Take the numbers away |

## The section band

A bar under the Data explorer tabs stays at the top of the screen (just below the site header) while you scroll. It lists
the section numbers `01` to `12`, marks the one in view (the link has `aria-current`), and draws a thin progress line
along its bottom edge. Click a number, or tab to it and press Enter, to jump to that section. It is a `nav` of real links.

## Titles and figures animate in once

When a section first scrolls into view, its eyebrow fades up and the headline lines slide up one after another (80 ms
and 160 ms apart for the second and third lines). Charts start their own intro at the same moment, not when the page
loads: bars and lines grow, columns rise, dots and tiles appear. The Trend lines draw as you scroll the section into place.
Each section does this once.

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

Section 12 lists every geography with every metric. The **search** box (`q`) filters by name, state code or region without
regard to case. Column headers sort (they have `aria-sort`). **Download CSV** saves the rows exactly as filtered and sorted,
named `matrix-map-<metric>-<vintage>.csv`. The file has a header row, CRLF line ends, quotes around any value that contains a
comma, quote or line break, and an **empty cell** for a missing value. The columns are state, state code, FIPS, region, vintage
(a string such as `2023`, never `2,023`) and one column of raw numbers per metric.

## Themes

The **Theme** control offers seven themes taken from the Folio reference: Lavender Press (the default), Newsprint, Night
Edition, Gazette Mono, Swiss Poster, Forest Ochre and Riso Pastel. A theme is a set of CSS custom properties applied only
inside the Matrix workspace, so no other tab or page changes. It is kept in `theme`. Text, chart labels and the section band
meet 4.5:1 contrast in every theme, which a test checks.

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
  section in view without adding history entries.
- Opening a tile or a state name goes to the national map for that metric. The map does not yet open on that state.

## URL parameters

`layout` (section id: `tiles`, `share`, `pivot`, `dumbbell`, `bars`, `trend`, `columns`, `heatmap`, `diverging`, `scatter`, `dots`,
`table`), `metric`, `vintage`, `theme`, `cols` (pivot columns), `sort`, `dir`, `group` (`region` or `quartile`), `min`, `y`
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

- Page: `web_app/src/pages/DataExplorerMatrixPage.tsx` (data loading, shared controls, URL, band and section tracking).
  One component per section and the shared pieces are in `web_app/src/components/matrix/`: `SectionShell` (spread layout,
  animated title, data table toggle), `SectionBand`, `LegendChips`, `Tooltip`, `DivergingBars`, and `*Section.tsx` files.
  The dot map is `web_app/src/components/DotMatrixMap.tsx`.
- Pure helpers with tests: `web_app/src/utils/matrixTable.ts` (`toCsv`, `filterRows`, `stackByRegion`, legend toggles and the
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

- **Section titles** slide up line by line when the section first enters view; the eyebrow fades up.
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
