---
title: Explore census figures
sidebar_label: Explore census figures
description: The Analysis tab in Data explorer (Explore census figures) is one scrolling report over the ACS bundle, in five groups and twelve screens, each headed by a sentence computed from the data in view, paged with Continue and Back or the keyboard, every screen sized to fit the window, with data tables under every figure, the Open Navigator house theme, and a URL for every view.
---

# Data explorer: Explore census figures

The **Analysis** tab (`/data-explorer/matrix`; the address keeps its old name) sits next to Map view and Scorecard. It reads the
same published American Community Survey (ACS) 5-year bundle as the map: Census Bureau figures for every state. It is **analysis,
not a story**: census figures have no video or transcripts, so nothing on this page is framed as a story, a chapter or a game.
It is **one report of twelve screens**, one chart type per screen, in **five groups**, with a closing screen of action links.

## The page heading is a sentence you complete

The page heading is **"Explore [measure] in [place]"**, built with the reusable `SentenceHeading` component
(`web_app/src/components/story/SentenceHeading.tsx`; wording in one constant, `EXPLORE_SENTENCE` in
`components/matrix/QuestionHeading.tsx`). Each blank is a button, styled as words of the sentence (accent colour, dotted
underline), that opens an inline picker anchored to it:

- a **combobox with type-to-filter** (arrow keys move, Enter chooses, Escape closes and returns focus to the blank, typing
  filters), options grouped under small headings when the bundle gives categories, each with a one-line hint (here the real median
  across the states for that measure), and the current choice marked;
- on a phone the picker is a **bottom sheet** with a large search field and 44 px rows.

Choosing sets `metric` in the address and every screen, headline and label follows. The **place** has one option, "the United
States": single-state views exist only in some screens (the Dot map and Share), so no choice is offered that would work for
only part of the page; a blank with one option shows as plain words. The **year** is a small control in the line under the
heading ("Census Bureau figures for 52 states and territories, 2023."), plain text when the bundle has one vintage.

Under the heading a **Try** row offers the other real metrics in the bundle that have data (up to eight, in bundle order; the rest
are in the picker), and **Surprise me** picks a random metric that has data and announces it through a polite live region. The
ordering lives in `web_app/src/utils/matrixSuggest.ts` and the picker helpers in `web_app/src/utils/sentenceHeading.ts`, both
unit tested. There is **no theme control**: the page always renders in the Open Navigator house theme (`?theme=<id>` still works
as a silent deep link, and the other themes and their contrast tests stay in the code). The old name of this tab no longer
appears anywhere the reader can see.

## Five groups of screens

The page never shows its own structure: no group or section numbers, and none of the words "problem", "decision", "challenge",
"implementation" or "call to action" as a title or label. Each group has a short plain phrase (its **band label**) and a title that
**states its main finding as a sentence**, computed from the measure, year and states in view.

| Group id (URL `chapter=`) | Band label | The title says | Screens |
| --- | --- | --- | --- |
| `problem` | Where things stand | The spread: highest against lowest, with both names and values, and the gap ("That is 6.4 times as much." or "A gap of 19 pp.") | Tiles, Dot map, Share |
| `decision` | What changed | How many geographies rose or fell since the earliest year and the size of the biggest change; with one year, who sits above and below the median | Compare, Diverging, Bars |
| `challenge` | What goes with it | "Do poverty rate and median age move together?" and the answer: strength, direction and r-squared, or plainly "Not in a straight line" | Scatter, Heatmap |
| `implementation` | Over time | The median's path from the first to the last year (for a count: which region holds the largest share, and whether that changed); with one year, a single-year statement | Trend, Columns, Pivot |
| `action` | Go further | An invitation that names the scope: "See what Alabama decided." or "See the decisions behind these numbers." | Table, then the action links |

The group ids stay in the URL (`?chapter=`); they are never shown.

A group opens with a **compact opener** (the band label as a small line, the title in at most two lines, a rule) directly above
the group's first screen, sharing that screen with it.

The last screen has the **action links**, large square buttons that carry the scope in view: **See decisions in (state)** (the
decisions browse page with `?state=`) when one state is in scope or **See decisions nationwide** otherwise, **Download this table
(CSV)** (the same file as the Table section) and **Open the map view**, then **Back** and **Back to the start** links. One state is
in scope when the Dot map is drilled into it (`dot`) or the Share section shows its counties (`part=county`, `st`). No link points
at a page that does not exist, and there is no game link on this page.

### How the sentences are written

Every group title, every screen headline and its one supporting sentence are produced by pure functions in
`web_app/src/utils/matrixStory.ts` from the data the screen already computed, and they change with the metric, vintage and
filters (the entrance animation does not replay). The rules, which the unit tests check:

- **Engaging, but only the facts.** Short sentences. Contrast ("22.5% in Washington. 3.5% in Alabama and Puerto Rico."), concrete
  gaps ("almost twice as much", "6.4 times as much"), counts ("17 of 52 rose") and a question that leads into the chart that
  answers it ("Which moved most?", "Who sits furthest from the middle?"). A ratio is written only when both values are
  positive and the smaller is not near zero; otherwise the difference in the metric's unit.
- **Only what the data shows:** rankings, counts, shares, changes, and a correlation's direction and strength with its r-squared.
  Never a cause ("because", "due to", "driven by"), a forecast, a judgment ("should", "worrying", "good", "best", "worst",
  "problem", "crisis") or a claim about people or motives.
- **Lower-is-better metrics** still read "highest" and "lowest".
- **Nothing is filled in.** When a needed figure is missing, the sentence names the metric and its scope ("Poverty rate, 2023: no
  tile values are available.") and there is no supporting sentence.
- **Ties name every tied geography up to three, then "and N others"**, the same way in every sentence of a screen. When a tie
  would make a headline too long (Bars, Diverging), the numbers stay in the headline and the names move to the line below. A
  single geography is said plainly. Numbers come from the same formatters as the charts, so a sentence matches the chart
  beside it. Years are plain strings.
- **One vintage.** With one vintage loaded, or the earliest selected, nothing reads "2022 against 2022": the second group
  says who sits above and below the median, and the Over time group makes a single-year statement ("Only 2023 is loaded, so
  there is no run of years yet.").
- **Length.** A screen headline must fit in three lines in the left column at 1366 px wide, a group title in two lines.

Each screen has the same layout. On a wide screen the left column holds a plain eyebrow (the screen's name in words: "At a
glance", "Then and now", "Year by year"), a headline, one supporting sentence, a **More about this chart** disclosure
(the longer explanation), and the **Continue** and **Back** controls; the right column holds the figure with its controls, its
caption and a **Show data table** button, with a hairline between the two. Below about 1024 pixels the columns stack, text first,
and the Continue and Back controls follow the figure. The Heatmap and Table screens give the figure more of the width.

| Screen | Eyebrow | What it shows | Use it to |
| --- | --- | --- | --- |
| Tiles | At a glance | One box per geography, shaded by rank. Flat, By region or By quarter regroups the boxes; each group is headed `name · count (share %)` | See every geography at once |
| Dot map | On the map | The country as a grid of dots; click a state for its counties | Read the geography of a metric |
| Share | Shares of the whole | A 100% stacked bar with labelled segments, a 10x10 waffle and a list, for states of the U.S. or counties of a state | See each part's share of the whole |
| Compare | Then and now | A dumbbell per geography: hollow dot for the earliest vintage, filled dot for the selected one, the change on the right | See who moved, and by how much |
| Diverging | Above and below the median | Bars left or right of the median geography, sorted by value by default | See who is above or below the middle |
| Bars | Side by side | One horizontal bar per geography for the metric, with region chips | Rank geographies, one region at a time |
| Scatter | Two metrics together | One metric against another, coloured by Census region, with a trend line, slope and r-squared | See whether two metrics move together |
| Heatmap | Every metric at once | Geographies by metrics, each cell shaded by that metric's rank; click a header to sort | Scan every metric at once |
| Trend | Year by year | The metric across every vintage, one line per chosen geography plus the median across states | See change over time |
| Columns | By region | One stacked column per vintage, stacked by Census region (counts only) | See how regions add up over time |
| Pivot | One grid | Geographies as rows, up to 8 metrics as columns, each column shaded, a Share column and a Total row for count metrics; click a header to sort | Compare several metrics side by side |
| Table | The full table | Every geography with every metric, bars, change and trend; search, sort and **Download CSV** | Take the numbers away |

## Every screen fits the window

Under the site header and the section bar, each screen shows its headline and its whole figure panel without scrolling the page,
at 1366 by 768 and larger (checked at 1366x768, 1440x900 and 1920x1080). The room a screen has is `100svh` minus the header and
the bar (CSS variables `--screen-h`, `--opener-size`, `--fig-chrome` in `folio.css`). How each figure fits:

| Screen | How it fits at 1366x768 |
| --- | --- |
| Tiles | By density: the 52 boxes are sized from the room the screen has (38 px high, about ten across) |
| Dot map | By density: the map keeps its proportions and shrinks to the room left |
| Share | By density: nothing to scroll |
| Scatter, Trend, Columns | By density: the chart height is computed from the window height (`useFitHeight`), never below 230 px |
| Compare, Diverging, Bars | Scrolls inside the figure: 52 rows; a shadow shows where there is more, with a thin visible scrollbar |
| Heatmap, Pivot | Scrolls inside the figure with the column headings kept at the top (sticky) |
| Table | Scrolls inside the table (rows and columns), headings sticky |

The long explanation sits under **More about this chart** so it never pushes a screen past the window. Opening the data table
makes a screen taller than the window on purpose; the page then scrolls normally until that screen's end is in view.

On a **phone** (under 768 px) the layout is one column and nothing is clamped to the window: the headline comes first, then the
chart starts under it in the first screen, tables scroll sideways inside themselves, and the page never scrolls sideways. The
section bar shows only the current phrase and a progress line; the buttons and controls are at least 44 px tall, the group
title is smaller, and the action buttons stack. A tablet (768 to 1023 px) stacks the columns and caps the figure height.

## Getting back to the top

The site header stays pinned while you scroll, but the Data explorer title and its tabs (Map view, Analysis, Scorecard, Data
quality) and the page heading scroll away. The section bar therefore carries two controls:

- **Top** (an up arrow and the word, at the left end; accessible name "Back to the top and the main menu"; at least 44 px on a
  phone): scrolls to the very top (smoothly, at once under reduced motion) and moves focus to the first link in the site header.
- **The current selection in words** at the right end ("poverty rate · United States — change"): one line, the place drops out
  first when room is tight, and on a phone only "change" remains. It scrolls back to the page heading and focuses the Measure blank
  so the reader can change it without hunting.

Keyboard: **Home** goes to the first screen; pressed again within a moment, or when you are already on the first screen, it goes to
the very top of the page. A scroll-up reveal of the site header was not added: the header is already always visible, and the
Data explorer tabs belong to `DataExplorerLayout`, which this page does not change.

## The section bar and paging

A slim bar under the Data explorer tabs stays at the top of the screen (just below the site header) while you scroll. It lists
the five band labels (Where things stand, What changed, What goes with it, Over time, Go further) as links, marks the group in
view with `aria-current`, shows one small dot per screen under it (no numbers; each dot's accessible name is the screen's plain
name), and draws a thin progress line along its bottom edge. It is a `nav` of real links. On a phone it shows only the current
phrase and the progress line.

**Continue and Back.** Every screen ends with a **Continue** button that names what comes next in words, computed from the
metric and scope ("Continue: what changed since 2019", "Continue: what goes with median age"), and from the second screen on a
quieter **Back** button that names the previous screen. They scroll to that screen (smoothly; at once under reduced motion),
move focus to its heading, and update the address bar without adding history entries. The last screen has the action buttons
and a **Back to the start** link instead of Continue. A cue at the bottom of the window invites you to the next
screen (see "Moving to the next screen" below).

**Keyboard.** When focus is not in a form field, a button, a link, a table, a slider or a figure that scrolls:

| Keys | Action |
| --- | --- |
| Page Down, Space, Down arrow | Next screen |
| Page Up, Shift+Space, Up arrow | Top of this screen if you have scrolled into it, otherwise the previous screen |
| Home, End | First screen, last screen |

Typing in the Table search, using a select or slider, or reading inside a scrolling figure is never interrupted, and a screen
taller than the window (a long open table) scrolls natively until its end is in view. The mouse wheel and touch scroll the
page as usual. Gentle `scroll-snap-type: y proximity` helps a scroll settle on a screen; it is off below 768 px and under reduced
motion. The key handler is `keepsKey` and `onKey` in `DataExplorerMatrixPage.tsx`.

## Titles and figures animate in once

Group titles and section headlines use the Folio reference's masked line rise: each line of the title sits behind its own
overflow-hidden mask and rises into place over 900 ms (the `--d-4` duration, `--ease-out` curve), the second line 80 ms after
the first and the third and later lines 160 ms after, with the eyebrow fading in first and a rule drawing under group titles.
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

Eight themes exist (there is no on-page control; `?theme=` selects one). **Open Navigator** is the default (it is used whenever `theme` is absent): it is
built from the product's own colours, a warm off-white page, near-black ink, the slate of the site's primary colour for the
band, and a ramp that runs from a light teal tint through the teal of the logo to dark slate. The opposite pole (below the
median, alerts) is amber, and a muted red is kept for "worse" in better and worse colouring. Series are teal, amber, red and
a light blue, never red against green. The seven themes of the Folio reference stay available by address: Lavender Press, Newsprint,
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
  view. `layout=<section>` is a deep link: the page scrolls to that screen on load, and as you scroll or page the address updates to the
  screen in view without adding history entries. `chapter=<id>` does the same for a chapter opener; while a chapter's first screen is in
  view the address carries `chapter` (and no `layout`), on any other screen it carries `layout` (and no `chapter`), and the closing action block is `layout=action`.
  A `layout` for a chapter's first section (for example `tiles`) lands on its chapter opener.
- Opening a tile or a state name goes to the national map for that metric. The map does not yet open on that state.

## URL parameters

`chapter` (chapter id: `problem`, `decision`, `challenge`, `implementation`, `action`), `layout` (section id: `tiles`, `dots`,
`share`, `dumbbell`, `diverging`, `bars`, `scatter`, `heatmap`, `trend`, `columns`, `pivot`, `table`, `action`), `metric`, `vintage`, `theme`, `cols` (pivot columns), `sort`, `dir`, `group` (`region` or `quartile`), `min`, `y`
(scatter), `part` and `st` (share), `dot` (dot map drill), `region` (bars), `geo` (trend), `q` (table search), `table` (open data
table), `off` (hidden legend series). The Columns Absolute / Share toggle is not in the address bar.

## When the Data explorer shows no data

Map view and the Analysis tab both read the census bundle from `/data/census-map/` (in the repository,
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
  data table toggle, More about this chart), `ScreenPager` (Continue and Back), `TitleBlock` (the measured, masked title entrance), `ChapterCard` (the compact opener), `ActionBlock`, `SectionBand` (the story bar), `LegendChips`, `Tooltip`, `DivergingBars`, and `*Section.tsx` files.
  The dot map is `web_app/src/components/DotMatrixMap.tsx`.
- Headline copy and paging: `web_app/src/utils/matrixStory.ts` (`CHAPTERS` with their band labels, `chapterTitle`, one pure function per screen headline, `SCREENS`, `adjacentScreens` and `screenLabel` for Continue and Back; tested in `matrixStory.test.ts`, which also scans every visible title, label and eyebrow for the structure words, judgments and leading numbers).
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
  [Meeting metrics for the census analysis page](../development/meeting-metrics-matrix-map-design.md).

## Look and motion

This page uses the "Folio" look: flat paper background, hairline rules, square corners, no shadows, large light
numerals and small monospaced captions. The design tokens (paper, ink, violet, vermilion, neutral data colour, type,
durations and easings) are CSS custom properties in `web_app/src/styles/folio.css`, scoped to the `.folio` wrapper class and
set per theme from `folioThemes.ts`. Fonts are Geist and Geist Mono, self-hosted from the `@fontsource-variable` packages and
loaded only with this page. The four figures under the heading (geographies with data, median, highest, lowest) are computed
from the state values already loaded for the selected metric.

### Motion rule

What moves, and when:

- **Group and section titles** slide up line by line (behind a mask) when the title first enters view; the eyebrow fades up and a group rule draws.
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

## If the page does not load (#856, #936)

This tab's code and fonts load only when its tab is opened, and the same holds for every lazily loaded page
(the Data Story, Data stories, ...). If they fail to load, the page shows "Data story could not be loaded" (with that page's name) with the
error and a Reload button, and the rest of the site keeps working.

On the public site the usual cause is a deploy since the tab was opened. Every build gives these files new
names and a deploy removes the old ones, so a tab opened before the deploy asks for a file that is gone (for
example "Unable to preload CSS for …/ScrollCue-C-uJ7YO1.css"). The app reloads the page once on its own
(`web_app/src/utils/staleDeploy.ts`, on Vite's `vite:preloadError`) and shows "Loading the latest version of
…" meanwhile. The reload picks up the new build: the server sends `index.html` no-cache, and the PWA service
worker (`skipWaiting`, `clientsClaim`) has normally swapped to the new precache already. If an old service
worker still controls the tab, the reload can land on the old page; see
[Hugging Face Spaces](../deployment/huggingface-spaces.md) on the service worker taking two visits.

It never reloads twice for the same missing file, nor twice within 30 seconds, and not while the browser says
it's offline (a network failure looks the same). When it doesn't reload, the message says "This site was
updated since this page was opened. Reload to get the latest version.", or "You appear to be offline" when
offline.

On a developer machine (`npm run dev`) the usual cause is a pull that added a package, and the message says so:
run `npm install` in `web_app` and reload.

## Moving to the next screen

A small cue at the bottom of the window ("Scroll", or "Swipe up" on a touch screen) appears when you have been still for a couple of seconds and there is another screen below. Pressing it goes to the next screen. It replaces the one-time hint that used to show on the first screen only.
