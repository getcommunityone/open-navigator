---
title: Data explorer Matrix map
sidebar_label: Matrix map
description: The Matrix map tab in Data explorer shows ACS values for every state as tiles, a pivot table, comparisons, a scatter plot, part-of-whole shares and a dot-matrix map with county drill-down.
---

# Data explorer: Matrix map

The **Matrix map** tab (`/data-explorer/matrix`) sits next to Map view and Scorecard. It reads the same published
American Community Survey (ACS) 5-year bundle as the map, and shows it in seven layouts. Pick a layout with the
buttons at the top of the tab.

| Layout | What it shows | Use it to |
| --- | --- | --- |
| **Tiles** | One box per state, shaded by one metric | See every state at once |
| **Pivot** | States as rows, up to 8 metrics as columns, each column shaded | Compare several metrics side by side; click a header to sort |
| **Compare** | A dumbbell per state from the earliest published year to the current one | See which states moved, and by how much |
| **Scatter** | One metric against another, a dot per state coloured by Census region, with a trend line, slope and r² | See whether two metrics move together |
| **Diverging** | Bars left or right of the median state | See who is above or below the middle |
| **Share** | A 100% bar, a 10×10 waffle and a ranked table | See each state's share of the U.S. total, or each county's share of a state |
| **Dot map** | The country drawn as a grid of dots, each coloured by its state | Click a state to see its counties the same way |

## Reading the colours

Tiles, Pivot and Dot map use six shade steps per metric, cut at 10, 25, 45, 65 and 80 percent of that metric's range.
Darker means a better rank: for metrics where lower is better (for example poverty), the scale is flipped. In
Tiles and Pivot, the **Highlight** slider grays out every cell below a chosen point on the scale and says how many
cells remain highlighted. In the Dot map, a state's counties are scaled within that state, so county shades are not
comparable with the national view.

## Things to know

- **Share works only on counts** (population, housing units, labor force and similar). Medians, rates and percentages
  have no meaningful total, so they are not offered there. The U.S. total is the 50 states plus the District of
  Columbia; Puerto Rico is left out, as in the ACS definition of the United States.
- **Scatter shows association between places, not cause**, and not anything about individual people.
- **The Dot map needs a pointer to read a dot's value.** With a keyboard, choose a state from the list above the map
  to open its counties, and use Tiles or Pivot to read the values.
- **Missing data is shown as missing.** A state or county with no value is gray and reads `—`. If a year or the
  county file has not been published, the layout says "No data available" instead of drawing a chart.
- **The view is in the address bar.** Layout, metric, columns, sort, grouping, threshold and the drilled state are URL
  parameters, so a link or a refresh returns the same view.
- Opening a tile or a state name goes to the national map for that metric. The map does not yet open on that state.

## When the Data explorer shows no data

Map view and Matrix map both read the census bundle from `/data/census-map/` (in the repository,
`web_app/public/data/census-map/`). The bundle is generated and git-ignored, so a fresh checkout, or a machine where
that folder was cleaned, does not have it. Both tabs then say **No map data available** and name the command that
creates the files:

```bash
python -m ingestion.census.export_census_map_static --all-years
```

Reload the page afterwards. Before #838 the map showed gray states and an empty metric list with no message, because a
missing file comes back from the dev server as the app's own page with a success status, not as an error.

## For developers

- Page: `web_app/src/pages/DataExplorerMatrixPage.tsx`; dot map: `web_app/src/components/DotMatrixMap.tsx`.
- Data: `/data/census-map/manifest.json`, `{vintage}/state_metrics.json`, `{vintage}/county_metrics.json`, written by
  `python -m ingestion.census.export_census_map_static`. Shapes come from the us-atlas Albers topologies.
- URL parameters: `layout`, `metric`, `cols`, `sort`, `dir`, `group`, `vintage`, `min`, `y`, `part`, `st`, `dot`.
- Plan for showing meeting and decision metrics in the same layouts:
  [Meeting metrics for the Matrix map](../development/meeting-metrics-matrix-map-design.md).

## Look and motion

The Matrix map uses the "Folio" look: flat paper background, hairline rules, square corners, no shadows, large light
numerals and small monospaced captions. Under each chart a caption reads "FIG. nn", says what the chart shows, and
names its source ("Source: ACS 5-year" plus the vintage in scope).

- **Where the look lives.** The design tokens (paper, ink, violet, vermilion, neutral data colour, type, durations and
  easings) are CSS custom properties in `web_app/src/styles/folio.css`, scoped to the `.folio` wrapper class. Only the
  Matrix page imports that file, and the whole workspace sits inside one `.folio` element, so no other tab or page
  changes. Fonts are Geist and Geist Mono, self-hosted from the `@fontsource-variable` packages and loaded only with
  this page.
- **Colour.** Ranked values use a violet ramp from tint to violet to deep violet. Vermilion marks the below-median
  side in the Diverging layout. Cells with no data, or dimmed by the Highlight slider, use the neutral data colour.
  Label text on every step is ink or white, whichever has the better contrast (at least 4.5:1, checked by a test).
- **Headline row.** A small eyebrow names the layout, the scope label is the large heading, and four figures follow:
  geographies with data, median, highest and lowest (with the state named). All four are computed from the state
  values the page already loaded. They are hidden when a county drill-down is showing, because they describe states.

### Motion rule

What moves, and when:

- **Tiles** appear on a diagonal wave on first load. When the sort, grouping or metric changes, each tile glides to its
  new place and its colour fades to the new shade.
- **Pivot rows** appear in a short stagger and glide when the sort or grouping changes.
- **Bars** (Compare, Diverging, Share) grow from their origin, one row after another. The stagger is capped so a
  52-row chart finishes in about 1.2 seconds.
- **Scatter points, waffle squares and dot-map dots** fade and scale in with a short stagger.
- **Key figures** count up to their value over about 0.9 seconds whenever the value changes.

Rules that always hold:

- **Reduced motion.** When the visitor's system asks for reduced motion, nothing animates. Content shows in its final
  state at once.
- **Numbers never animate to anything but the real value.** A count-up always ends on the exact formatted value from the
  data. If a value is missing, the figure shows a dash and does not count at all.
- Motion never changes what is shown: the scope label, the URL parameters and the data are the same with or without it.

