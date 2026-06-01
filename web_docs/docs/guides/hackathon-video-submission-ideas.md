---
displayed_sidebar: developersSidebar
description: Reference patterns and a checklist for strong “Google for Good”–style hackathon demo videos (CommunityOne / Open Navigator), including flagship pitch hooks (speed-trap revenue, potholes & street repair, Gapminder-style animated charts, automated interactive annual reports, TikTok-style issue summaries, circular seasonal data storytelling inspired by Searching for Birds, integrated timeline / entity / map views (KronoGraph pattern), cross-dataset corruption investigation OSINT pipeline (Splink, Aleph, Datashare, Neo4j, NetworkX), fraud and conflict-of-interest master list, required CTA slide, 100k-meeting safety scrub, 100k-decision reasoning & bias audit, jurisdiction website accessibility), plus inspirational civic data talks and case studies.
---

# Hackathon video submission ideas (reference library)

Short guide for a **CommunityOne** (or similar civic-data) submission where the **video** has to carry the “wow” as much as the product. These notes distill reference talks and pitch formats that bridge **complex data → real-world utility**.

## Quick jump: fraud & cross-dataset investigation

- [Cross-dataset corruption investigation (OSINT pipeline)](#cross-dataset-corruption-investigation-osint-pipeline)
- [Fraud and conflict-of-interest master list](#fraud-and-conflict-of-interest-hackathon-ideas-master-list)
- [Track 1: The appraisal gap watchdog](#track-1-the-appraisal-gap-watchdog)
- [Track 2: Artificial valuation and tax evasion collusion](#track-2-artificial-valuation-and-tax-evasion-collusion)
- [Track 3: The quid pro quo policy matrix](#track-3-the-quid-pro-quo-policy-matrix)
- [Track 4: The shell game contractor audit](#track-4-the-shell-game-contractor-audit)
- [Track 5: The earmark and dark money unveiler](#track-5-the-earmark-and-dark-money-unveiler)
- [Track 6: The insider trading and land-use predictor](#track-6-the-insider-trading-and-land-use-predictor)
- [Track 7: Municipal bond and infrastructure fund auditing](#track-7-municipal-bond-and-infrastructure-fund-auditing)
- [Track 8: The healthcare phantom billing and upcoding detector](#track-8-the-healthcare-phantom-billing-and-upcoding-detector)
- [Track 9: Synthetic identity theft and credit collusion](#track-9-synthetic-identity-theft-and-credit-collusion)
- [Track 10: Greenwashing and environmental grant fraud](#track-10-greenwashing-and-environmental-grant-fraud)

## 2026 Gemma 4 Good — flagship question

**Pitch hook:** *What percentage of a small town’s revenue comes from speed traps?*

Use this as the **15-second opener** and the **reveal** your demo answers—not a tour of models or folders.

### National baseline (not every town is the same)

Governing’s [**Addicted to Fines**](https://www.governing.com/archive/gov-addicted-to-fines.html) analysis of local-government audits (primarily FY 2017–18; see [methodology](https://www.governing.com/archive/local-government-fines-revenue-methodology.html)) found:

| Share of general-fund revenue from fines & forfeitures | Approx. # of U.S. jurisdictions |
| --- | --- |
| **More than 10%** | **~600** |
| **More than 20%** | **~284** |
| **More than half** | **dozens** (extreme outliers) |

Additional context from the same project:

- **720+** localities reported **more than $100 per adult resident** per year from fines.
- Dependence is concentrated in parts of the **South** (e.g. AR, GA, LA, OK, TX) and some communities in **NY**—often places with a **weak property-tax base** where ticketing substitutes for ordinary revenue.

**How to say it on camera:** “Nationwide, hundreds of small governments get **double-digit shares** of their budget from fines—not taxes. Your town might be **5%** or **50%**—the point is we can’t see that from a headline. We need **budgets + meeting records** in one place.”

### What CommunityOne / Open Navigator adds

1. **Local answer:** Pull **fines & forfeitures** (and court/municipal fee lines) from the jurisdiction’s **annual financial report** or state audit extract.
2. **Meeting context:** Use **county commission / city council** agendas and minutes (e.g. Tuscaloosa County `county_01125`) so Gemma can tie **enforcement, courts, or revenue** discussion to the budget line—not just a static percentage.
3. **Reveal beat:** Map or one chart—**% of general fund from fines** for *this* place vs. the national “>10% / >20%” bands above.

**Demo path:** Colab `02_run_meeting_llm.ipynb` with `SCOPE = "fast"` (defaults to `AL/county/county_01125`, **2 meeting dates**, up to **6 PDFs**/jurisdiction) → Gatekeeper → budget PDF OCR / drift on any audio → flash **source + year** on screen.

**Caveats for judges:** “Speed trap” is colloquial; audits use **fines and forfeitures** (sometimes bundled with fees). Always cite **fiscal year** and **fund** (general vs. special). Extreme towns are outliers—lead with *your* jurisdiction’s number, then national context.

### Gapminder-style reveal (use this chart pattern)

**Reference video (≈4:47):** [Hans Rosling — *200 Countries, 200 Years, 4 Minutes* (BBC / Gapminder)](https://www.youtube.com/watch?v=jbkSRLYSojo) — full write-up in [§1. The Joy of Stats](#1-the-joy-of-stats--200-countries-200-years-in-minutes) below.

**Why it belongs in *your* demo:** Judges remember **motion**, not another static PDF screenshot. One animated scatter turns “we parsed meetings” into “**your county moved** on this metric vs. peers.”

| Gapminder element | CommunityOne / Open Navigator mapping |
| --- | --- |
| **X axis** | e.g. **% of general fund from fines & forfeitures** (Governing bands: >10%, >20%) |
| **Y axis** | e.g. **violations per homepage** (`bronze_jurisdiction_website_accessibility`) or **median household income** |
| **Bubble size** | Population (`jurisdiction` dimension) or **# of decisions** scraped |
| **Color** | State, `primary_theme` majority, or Shield **flag rate** |
| **Time slider** | **Fiscal year** or meeting `calendar_year` string from warehouse rollups |

**Automation path:** Batch Gemma → `financial_items` + `decisions[]` in bronze → SQL or Python aggregate by `jurisdiction_id` + year → export CSV → **[Flourish](https://flourish.studio/)**, **[Observable Plot](https://observablehq.com/plot/)**, or **Looker Studio** for the animation. Re-run the same notebook each quarter; only the data file changes.

**15s script:** “This dot is Tuscaloosa County. Watch what happens when we add **every Alabama county** we’ve scraped—same chart Rosling used, but for **who funds government through tickets**.”

### Alternate everyday opener (potholes & street repair)

**Pitch hook:** *Your council approved road money last month—so why is your block still full of potholes?*

Pairs the same pipeline with **Infrastructure and Capital Projects** / **Transportation and Mobility** themes: capital budget lines, paving contracts, ARPA or gas-tax allocations, and **public comment** on neglected streets in minutes or audio.

**Reveal beat:** One chart or table—**$ approved for streets** (from `financial_items` or budget PDF) next to **what was actually discussed** (deferral, change order, contractor dispute) from `policy_analysis_v1` JSON.

**How to say it on camera:** “Residents don’t live inside the audit PDF—they drive the road. We connect **the vote** to **the dollar** and the **timestamp** where they debated your street.”

---

## Killer idea: Scrub 100k public meetings for hate speech and safety concerns

**Pitch hook:** *What if we ran every scraped city council and county commission record—100,000 meetings—through the same safety layer we use on chatbots, and published a public “trust index” by jurisdiction?*

### Why this lands

- **Scale with a number:** “100k meetings” is concrete; judges remember it.
- **“For good” fit:** Hate speech, harassment, and dangerous content in **official** minutes/audio is a civic-trust problem—not just social media moderation.
- **Pairs with Open Navigator:** You already scrape agendas/minutes/video, run Gemma policy deconstruction (Demo 3), and **ShieldGemma-style review** (`05_safety_review/`, on by default at end of §6).

### What the pipeline does today (demo scale)

| Step | At hackathon demo | At national scale |
| --- | --- | --- |
| Ingest | Tuscaloosa County `county_01125`, **2 recent meeting dates**, **6 PDFs** (`SCOPE=fast`) | ~22k jurisdictions × N meetings/year |
| Understand | Gemma 4 OCR, token budget, policy JSON + thinking trace | Batch on AI Studio / Colab workers |
| Safety pass | `shieldgemma-9b` on LLM outputs → `*.shield.json` + `_summary.json` | Same pattern, one review row per artifact |
| Publish | Drive folder + optional bronze tables | Map: flagged rate by county, trend by year |

### How to say it on camera (15s + reveal)

- **Problem:** “Residents assume official meeting records are neutral—but nobody systematically checks whether **model-generated summaries** or **raw public comment** in minutes cross safety lines at scale.”
- **Reveal:** Show `_summary.json` with `reviewed_count > 0`, one **flagged** category (or a clean bill of health), then zoom out to a slide: “Pilot: 2 meetings, 6 PDFs → path to **100k meetings** with the same Shield + Gemma stack.”

### Architecture one-liner

**Scrape → Gatekeeper → Gemma analysis → ShieldGemma review → aggregate trust scores** — same Colab notebook, wider `SCOPE` and warehouse export.

**Caveats:** Automated “hate speech” labels are **screening**, not legal findings; cite Shield categories, human appeal, and that government **source** text is public record being **reviewed for downstream AI safety**, not censored at source.

---

## Killer idea: 100k decisions — reasoning scores vs. LLM narrative, and systemic bias in who wins

**Pitch hook:** *Across 100,000 local government decisions, does the “official story” in the minutes match how strong the arguments actually were—and who keeps benefiting when you follow the people, not just the votes?*

### Why this lands

- **Scale with a number:** “100k **decisions**” (not just meetings) is a research-grade civic dataset—each row is a vote, allocation, or directive with structured **arguments** and **narrative** fields.
- **“For good” fit:** Transparency is not only *what* passed but *whose reasoning dominated* and whether the same commissioners, industries, or neighborhoods show up again and again in **winning** interpretations.
- **Pairs with Open Navigator:** `prompts/policy_analysis_v1.md` already emits per-decision `arguments_for` / `arguments_against` (with `rationale`), `narrative_analysis` (dominant vs. dissenting diagnoses, `value_conflicts`, `tradeoff_analysis`), `power_map`, and stable `person_id` / `org_id` slugs—Gemma Demo 3 + Demo 4 drift at pilot scale; warehouse at national scale.

### Research questions (demo → national)

| Question | Pilot (Tuscaloosa `county_01125`, 2 dates, agenda + minutes + video) | At ~100k decisions |
| --- | --- | --- |
| **Reasoning quality vs. outcome** | For 5–10 decisions, score each `arguments_for` / `arguments_against` `rationale` on a simple rubric (evidence cited, specificity, logical structure). Compare to the **prevailing** `narrative_analysis.dominant_narrative` and `outcome`. | Distribution: when dissent scores *higher* on the rubric but loses the vote, flag as “narrative override.” |
| **LLM consistency** | Re-run or hold out one meeting; compare Gemma’s `dominant_narrative` + `primary_theme` to a second pass or human coder. | Aggregate **theme_audit** / COFOG flags (`*.thinking.theme_audit.json`) and disagreement rate by jurisdiction. |
| **Who champions what** | Join `narrative_champions`, `arguments_for.person_id`, `power_map`, and scraped `structured_contacts` / `_contact_images` metadata. | Graph: persons/orgs → themes won → `$` in `financial_items`; test concentration (Gini, repeat sponsors). |
| **Systemic bias (careful framing)** | One slice—e.g. **Parks and Recreation** mis-tagged as **Civil Rights and Equity** (COFOG-01)—show audit table + correction. | Stratify outcomes by `postal_code`, `county_fips`, `primary_theme`, `stakeholder_role`, `is_lobbyist`; report **disparities** with confidence intervals, not individual accusations. |

### Suggested metrics (all exportable from JSON)

1. **Argument strength score** — automated or human-on-sample: length + presence of `evidence_cited`, `underlying_causes.contested`, explicit tradeoffs in `rationale`.
2. **Narrative–argument gap** — `dominant_narrative.problem_diagnosis` vs. highest-scoring `arguments_against` when `outcome` is APPROVED (measure “winning story vs. best counterargument”).
3. **Champion recurrence** — count decisions where the same `person_id` appears in `narrative_champions` across meetings/months.
4. **Proponent profile skew** — cross-tab `arguments_for.stakeholder_role` and `is_lobbyist` against `interests_advanced` in `tradeoff_analysis` (who gains when safety, housing, or fines themes dominate).
5. **Theme–geography mismatch** — decisions where `primary_theme` disagrees with keyword audit (parks language + non-parks theme); ties to consolidated `_meeting_summary.md` theme table.

### What the pipeline does today (demo scale)

| Step | Hackathon demo | National vision |
| --- | --- | --- |
| Deconstruct | Demo 3 `.thinking.json` per PDF; Demo 4 chunks + `policy_drift.json` on video | Batch Gemma / warehouse `decisions[]` |
| Explain themes | `*.thinking.theme_audit.json` + COFOG table in `_meeting_summary.md` | Dashboard: misclassification rate by theme |
| People | `person_id`, contacts bronze, optional Demo 5 image triage | Entity graph across jurisdictions |
| Compare reasoning | Manual rubric on 10 rationales vs. `dominant_narrative` in notebook or Sheet | Sample 1k → model calibration; full 100k → aggregate gaps only |
| Bias (systemic) | One chart: champion concentration or theme×ZIP for county pilot | Public report: disparity metrics + methodology appendix |

### How to say it on camera (15s + reveal)

- **Problem:** “Minutes tell you the vote—not whether the **strongest argument** won, or whether the same players and neighborhoods keep winning the **story**.”
- **Reveal:** Open one decision’s JSON: read `arguments_against[0].rationale` (strong) next to `narrative_analysis.dominant_narrative` (what locked in)—then a slide: “Pilot: **N** decisions → path to **100k** with reasoning scores + champion profiles.”

### Architecture one-liner

**Scrape → Gemma policy JSON (`decisions[]`, `arguments_*`, `narrative_analysis`) → optional second-pass reasoning scorer → entity join on `person_id` / contacts → aggregate bias & gap statistics** — same schema at pilot and warehouse scale.

**Caveats for judges:** This is **research and accountability tooling**, not proof of individual bad faith. Report **systemic patterns** with transparent rubrics; keep humans in the loop for any public naming; distinguish **LLM extraction error** (theme audit flags) from **governance bias** (repeat champions, geographic skew in outcomes).

---

## Hackathon idea: Integrated timeline, entities, and maps ([KronoGraph](https://kronograph.cambridge-intelligence.com/))

**Pitch hook:** *When did your council debate 711 Queen City Avenue—and who spoke, what changed, and where on the map does that decision actually land?*

Today Open Navigator already extracts **decisions**, **people**, **places**, and **timestamped media anchors** from meetings. A hackathon “wow” is not another PDF summary—it is one **interactive** surface where **time**, **entities**, and **geography** stay linked while a resident investigates.

### Why this lands

- **Familiar investigative pattern:** Judges recognize “timeline + network + map” from crime, fraud, and OSINT demos—your twist is **public meetings** and **budget lines**, not private chat logs.
- **Uses data you already ship:** `decisions[]`, `people[]`, `places[]`, `media_anchor.playback_url`, and Mermaid `diagram_timeline` / `diagram_mindmap` from `policy_analysis_part_1` + Smart Brevity reports in `03_reports/`.
- **Clear upgrade story:** Static Mermaid in Markdown is the **MVP**; [KronoGraph](https://kronograph.cambridge-intelligence.com/) is the **scalable UI** when you need zoom, filter, and cross-highlight across hundreds of events.

### Reference product — [KronoGraph](https://kronograph.cambridge-intelligence.com/)

Cambridge Intelligence’s **[KronoGraph](https://kronograph.cambridge-intelligence.com/)** is a JavaScript timeline SDK for **interactive, scalable** views of evolving relationships between events ([introduction demo](https://kronograph.cambridge-intelligence.com/), [Playground](https://kronograph.cambridge-intelligence.com/), [docs](https://kronograph.cambridge-intelligence.com/), [examples](https://kronograph.cambridge-intelligence.com/)). Relevant showcase patterns for civic data:

| KronoGraph showcase | Open Navigator mapping |
| --- | --- |
| [**Who, Where, When?**](https://kronograph.cambridge-intelligence.com/) — data fusion investigations | Join `person_id` + `places[]` + `media_anchor.timestamp_start_seconds` on one decision |
| [**Track movements over time**](https://kronograph.cambridge-intelligence.com/) — geospatial timelines | `places[].latitude` / `longitude` (Nominatim via `enrich_analysis_places.py`) + meeting `calendar_year` |
| [**Tell the story of a network**](https://kronograph.cambridge-intelligence.com/) | `arguments_for` / `arguments_against` → `person_id` / `org_id`; `narrative_champions` |
| [**See alerts in context**](https://kronograph.cambridge-intelligence.com/) | Shield flags or theme-audit anomalies pinned on the same timeline as the vote |

Request a trial from the site if you embed KronoGraph in a React/JS demo page; the **Playground** is enough for a hackathon storyboard without a full integration.

### Three-pane “integrated” layout (hackathon storyboard)

```text
┌─────────────────────┬──────────────────────────────────────┐
│  ENTITY LIST        │  KronoGraph TIMELINE (events)        │
│  people[]           │  • agenda item opened              │
│  orgs[]             │  • public comment (timestamp)      │
│  places[]           │  • vote / COA approval (decision)    │
│  (filter by theme)  │  scrubber ↔ YouTube playback_url   │
├─────────────────────┴──────────────────────────────────────┤
│  MAP (Leaflet / Google Maps / Mapbox)                     │
│  pins from places[] · highlight active place_refs         │
└──────────────────────────────────────────────────────────┘
```

**Event feed (export from JSON):**

| Field | Source in Open Navigator |
| --- | --- |
| `event_id` | `decision_id` or `item_id` |
| `start` / `end` | `media_anchor.timestamp_start_seconds` (video) or meeting date for PDF-only |
| `label` | `headline` or `one_line_summary` |
| `entity_ids` | `presenter_person_ids`, `place_refs`, `legislation_refs` |
| `link` | `media_anchor.playback_url` |

**Entity graph (parallel to timeline):** Use `subject_id`, `primary_place_id`, and `power_map` / champion fields from Part 1 JSON—the same slugs you already join to `structured_contacts` and `_contact_images`.

### What you have today vs. hackathon stretch

| Layer | Today (repo) | Hackathon stretch |
| --- | --- | --- |
| **Timeline** | Mermaid `diagram_timeline` in `03_reports/`; `diagram_timeline_lines` in `02_analysis/` | CSV/JSON event list → KronoGraph or [Observable Plot](https://observablehq.com/plot/) |
| **Entities** | `people[]`, `organizations[]`, `subjects[]`, stable `person_id` | Click person → filter timeline + map |
| **Maps** | `places[]` + optional geocode (`packages/llm/src/llm/gemini/enrich_analysis_places.py`) | Pin **711 Queen City Avenue** when user selects COA patio decision |
| **Playback** | `media_anchor` on uncontested + contested rows | Click event → seek YouTube at `t=` seconds |

**Pilot meeting for the video:** Tuscaloosa Historic Preservation Commission (May 13, 2026)—multiple **street-address** COAs (`711 Queen City Avenue`, `1100 Queen City Avenue`, …) after `infer-missing` + `--geocode` on analysis JSON.

### Hackathon MVP (one weekend)

1. **Export** one `02_analysis/*.json` to `events.jsonl` (10–30 rows: decisions + key uncontested items with anchors).
2. **Prototype timeline** — either embed [KronoGraph](https://kronograph.cambridge-intelligence.com/) in a small React page **or** animate the existing Mermaid lifecycle in the report while narrating the KronoGraph-shaped UX.
3. **Map panel** — plot `places[]` with lat/lon; selecting a timeline event highlights `place_refs`.
4. **Entity sidebar** — list `people[]` for that meeting; selecting “Julia Cherry” filters events where `presenter_person_ids` or argument slugs match.

**Demo path (no new models):**

```bash
# Places + geocode on existing Part 1 JSON
.venv/bin/python -m llm.gemini.enrich_analysis_places \
  "data/cache/gemini_transcript_policy/municipality_0177256/02_analysis/2026-05-14_Tuscaloosa Historic Preservation Commission Meeting - May 13, 2026.json" \
  --jurisdiction-id municipality_0177256 --infer-missing --geocode

# Optional: regenerate report with Where / place context
.venv/bin/python -m llm.gemini.meeting_transcript_policy \
  --part-2-only --jurisdiction-id municipality_0177256 --video-id _N25jQdQ4jQ
```

Then screen-record: click **711 Queen City Avenue** on the map → timeline zooms to patio COA → open `playback_url` at the cited second.

### How to say it on camera (15s + reveal)

- **Problem (15s):** “Minutes give you paragraphs—not **when** each address was debated, **who** spoke, and **where** it is on the block.”
- **Reveal (45s):** Drag the timeline scrubber; watch the map pin and the entity list update; jump to the **YouTube** moment for that vote.
- **Scale (10s):** “Same JSON schema for **one** HPC night or **100k** decisions—KronoGraph-class UI when static diagrams aren’t enough.”

### Complements other tracks in this doc

- [**Gapminder-style reveal**](#gapminder-style-reveal-use-this-chart-pattern) — peer **motion** across jurisdictions; KronoGraph — **depth** on one jurisdiction’s night.
- [**100k decisions — reasoning & bias**](#killer-idea-100k-decisions--reasoning-scores-vs-llm-narrative-and-systemic-bias-in-who-wins) — entity graph + timeline makes **champion recurrence** visible.
- [**TikTok-style summaries**](#hackathon-idea-tiktok-style-meeting-summaries-issue-first-everyday-user) — export one timeline event as the script’s **hook timestamp**.

**Caveats:** KronoGraph is a **commercial SDK** (trial/license for production); cite [kronograph.cambridge-intelligence.com](https://kronograph.cambridge-intelligence.com/) and show Mermaid/report output as the open fallback. Geocodes are approximate (Nominatim); say “parcel-level” only when you have verified GIS, not LLM-extracted addresses alone.

---

## Hackathon idea: Government website accessibility checker

**Pitch hook:** *Can a resident who uses a screen reader actually pay a fine, find meeting minutes, or contact their commissioner on the official `.gov` site?*

This pairs well with the fines-revenue story: towns that depend on ticketing often push residents to **online portals**—if those sites fail **WCAG** checks, “digital government” excludes the people most affected.

### What’s already in Open Navigator

Bulk scans of **canonical jurisdiction homepages** from `intermediate.int_jurisdiction_websites`, with results in Postgres bronze for maps and scorecards.

| Layer | Engines | Bronze table |
| --- | --- | --- |
| **HTML homepages** | [axe-core](https://github.com/dequelabs/axe-core) + Puppeteer, [Pa11y-CI](https://github.com/pa11y/pa11y-ci) | `bronze.bronze_jurisdiction_website_accessibility` |
| **PDFs linked from homepages** | [veraPDF](https://verapdf.org/) (PDF/UA, PDF/A) | `bronze.bronze_jurisdiction_pdf_verapdf` |

Full runbook: **[Accessibility testing](/docs/guides/accessibility-testing)**.

### Fast demo path (one state, one reveal)

From the repo root, after `int_jurisdiction_websites` is built and `.env` has a database URL:

```bash
# HTML: WCAG-oriented violations (axe) for Alabama pilot jurisdictions
./packages/accessibility/src/accessibility/run_accessibility_scan.sh --engine axe --state AL

# Optional: PDF/UA on agenda/minutes PDFs discovered on those homepages
./packages/accessibility/src/accessibility/run_verapdf_scan.sh --state AL --max-pdfs-per-site 3
```

**Video reveal:** Side-by-side—**Tuscaloosa County** vs **City of Tuscaloosa** homepage URLs, sorted by `violation_count` in SQL or a simple chart. Call out one concrete failure (missing form label, low contrast, empty link text) and tie it to a real task (“pay court costs,” “download tonight’s agenda PDF”).

```sql
SELECT jurisdiction_id, website_url, scanner, violation_count, status, scanned_at
FROM bronze.bronze_jurisdiction_website_accessibility
ORDER BY violation_count DESC NULLS LAST
LIMIT 20;
```

### How to say it on camera

- **Problem (15s):** “My town funds itself partly from fines, then sends me to a website my blind neighbor can’t use.”
- **Demo (45s):** Run scan → show top violations → open the live `.gov` page with the same issue highlighted.
- **Action (10s):** “Advocates can rank jurisdictions, file ADA complaints with evidence, or ask councils to fix the portal—not guess.”

### Why judges like this track

- Fits **“for good”** and **accessibility** rubrics (see §3 in this doc’s reference videos).
- **Measurable** output (violation counts, PDF/UA pass-fail)—not a subjective LLM summary.
- Complements the **Gemma meeting pipeline**: meetings are useless if residents cannot **reach** them online.

**Caveats:** Automated tools catch many but not all barriers; say “axe/Pa11y flags” vs. “fully ADA compliant.” Homepage-only scans miss deep pages unless you extend the crawler.

---

## Hackathon idea: TikTok-style meeting summaries (issue-first, everyday user)

**Pitch hook:** *Your city council voted on your money last Tuesday—would you watch a 4-hour stream, or a 45-second clip that says what changed for **you**?*

Turn **official meeting intelligence** into **short-form, shareable stories** for residents who will never read minutes—framed around **issues they already care about**, not procedural jargon.

### Why this lands

- **Distribution:** TikTok, Reels, and Shorts are where **younger and working residents** get news; `.gov` livestreams are not.
- **Issue hook, not “government TV”:** Lead with **speed traps / fine revenue**, **potholes & paving**, **rent or zoning**, **school cuts**, **water bills**, **sheriff contracts**—the same hooks as the fines-revenue opener, not “Item 7 on the consent agenda.”
- **Trust through receipts:** Pair each clip with **source links**—budget line, agenda PDF page, or **`playback_url`** at `timestamp_start` from `policy_analysis_v1.md` + `media_playback_links.py` so viewers can jump to the moment in the recording.
- **“For good” angle:** Informed neighbors show up prepared; journalists and advocates get **pre-digested** frames with dissent and tradeoffs preserved (not rage-bait summaries).

### What to generate (one “card” per issue)

| Output | Purpose |
| --- | --- |
| **Hook (≤3s text on screen)** | “This town gets **18%** of its budget from tickets.” |
| **So-what (15–30s voiceover)** | Smart Brevity from `decision.headline` + `tradeoffs` / `narrative_analysis` |
| **Receipt (5s)** | QR or URL: fines % chart, Shield-clean summary, or **Watch at 1:05:30** deep link |
| **CTA (final 3–5s)** | Dedicated slide—see [Call to action slide](#call-to-action-slide-required-closing-beat) below |

**Tone rules for scripts (prompt or post-process):**

- Second person (“your taxes,” “your commute”)—not “the commission adopted…”
- One **concrete number** or **named place** per clip when the JSON has it
- Name **who won and who lost** in plain language (`tradeoff_analysis`, dissenting frame)—avoid false balance, but don’t invent conflict
- **No legal advice**; end with “read the minutes” / “verify on the city site”

### Example issue templates (rotate by jurisdiction)

1. **Speed traps & fines** — `% of general fund from fines` (Governing baseline) + council/audio line on enforcement or court fees → ties to flagship hook above.
2. **Potholes & street repair** — hook: “They approved **$X** for roads—your street wasn’t on the list.” Pull paving / capital outlay from `financial_items`; `primary_theme` Infrastructure or Transportation; clip resident comment or engineer report from `playback_url`.
3. **Housing & rent** — zoning vote, demolition, or landlord registry debate from minutes + `primary_theme` Zoning / Housing.
4. **Public safety spend** — sheriff contract, new patrol cars, or diversion program; show **vote tally** on screen.
5. **Schools & kids** — board cuts, bus routes, discipline policy; NTEE **Education / Youth** tags from analysis JSON.
6. **Utilities & bills** — rate hike hearing; flash **$ / month** from `financial_items`.
7. **Access fail** — “They want your fine paid online” + same jurisdiction’s **axe violation** on the payment portal (combine with accessibility track).

### Pipeline sketch (builds on what exists)

```text
Scrape → Gatekeeper → Gemma policy_analysis_v1 (JSON + media_citation)
    → issue picker (theme / COFOG / fines % / keyword)
    → Gemma or template: 45–60s script + on-screen captions
    → optional: ffmpeg clip from SuiteOne/YouTube using timestamp_start_seconds
    → publish: vertical 9:16 + pinned source URL
```

**Demo path (hackathon):** One Tuscaloosa County decision with a clear **financial_items** or **fines** angle → show **JSON headline** → generated **TikTok script** → open **`playback_url`** at the cited timestamp in the browser (even if seek is manual on SuiteOne).

### How to say it on camera (15s + reveal)

- **Problem:** “Council meetings are public but invisible—unless you have four hours and a law degree.”
- **Reveal:** Play a **vertical mock** (CapCut template or slide): hook text → 20s plain-English outcome → “Source: county budget FY24 + meeting at 1:05:30.”
- **Close:** Hold the **[CTA slide](#call-to-action-slide-required-closing-beat)** for a full **3–5 seconds**—do not fade out over the demo UI.
- **Scale:** “Same Gemma pass that powers **100k meeting safety scrub** also powers **100k clips**—one per issue residents actually search for.”

### Caveats for judges

- Short-form **compresses** nuance; always show **link to full JSON / minutes** and label **AI-generated script**.
- Don’t imply endorsement by the city or platform; use **public record** framing.
- **Platform policy:** automated posting to TikTok is out of scope for a hackathon MVP—ship **scripts + captioned storyboards** or manual upload.

---

## Hackathon idea: Voice signatures, contact graph, and political personality analysis

**Pitch hook:** *You know their face from the council photo and their vote from the minutes—but do you know how they **sound**, how they **sign** documents, and whether their rhetoric is consistent meeting to meeting?*

Build a **multimodal official profile** that links **scraped headshots**, **diarized meeting audio**, and **LLM-readable personality signals**—always framed as **public-record accountability**, not pop psychology or endorsement.

**“Signature” here means three things:** (1) **identity card**—face + role from the official directory; (2) **voice signature**—diarized clips and optional speaker embeddings so the same official is recognizable across meetings; (3) **rhetorical signature**—recurring phrases, stance, and tone extracted from what they actually said (cited to timestamps). Optional stretch: match **handwritten signatures** on scanned agenda PDFs to `person_id` when packets include sign-in sheets.

### What to capture (three layers)

| Layer | Source | Output |
| --- | --- | --- |
| **Identity signature** | `_contact_images/` from jurisdiction crawl (`contacts.json` + headshots) | Stable `person_id`, role, district, photo URL for UI and video overlays |
| **Voice signature** | YouTube meeting audio → WhisperX diarization + `speaker_guess` mapped to contacts | Per-official audio clips, speaking-time share, optional embedding for “same voice?” checks across meetings |
| **Personality / rhetoric** | Policy JSON (`decisions[]`, `narrative_analysis`) + labeled transcripts | Rolling traits: formality, conflict style, fiscal hawk/dove cues, repeat phrases—**with citations** to timestamped lines |

### What’s already in Open Navigator (Tuscaloosa pilot)

| Piece | Path / script |
| --- | --- |
| Council directory | `data/cache/scraped_meetings/.../municipality_0177256/_contact_images/contacts.json` |
| Transcripts | `data/cache/gemini_transcript_policy/.../YYYY-MM-DD_<title>.json` (basename matches Opus in `youtube_audio/al/city_of_tuscaloosa_…/`) |
| Speaker hints (heuristic) | `packages/llm/src/llm/gemini/enrich_transcript_diarization.py` — names from contacts on caption segments |
| Full diarization (optional) | Same script with `--whisperx` + `HF_TOKEN`; Tuscaloosa Opus already at `data/cache/youtube_audio/al/city_of_tuscaloosa_uc74dczs0b3mhdhuhp2zgrpa/` (~117 meetings, `YYYY-MM-DD_<title>.opus`) |
| Policy + narrative | `policy_analysis_part_1.md` → `*_analysis.json` via Flash-Lite or Gemma Colab pipeline |

### Hackathon MVP (one weekend)

1. **Enroll voices** — For 5–10 officials, cut 30–60s diarized clips where `speaker_guess` matches `contacts.json`; store `voice_clip_path` + `video_id` + `start`/`end`.
2. **Personality pass** — Second LLM prompt over last *N* labeled transcripts per `person_id`: output **structured** `rhetoric_profile` (themes, tone, stance on fines/capital/trust) with `evidence_quotes[]` tied to timestamps—not free-form horoscope text.
3. **Reveal UI** — One card per councilor: photo, 10s audio waveform, three trait chips, “receipt” link to meeting clip (`playback_url` + offset).

```text
Scrape contacts → meeting transcripts (diarized) → policy JSON
       ↓                    ↓                      ↓
  face + role         voice segments +        rhetoric_profile
                      speaking stats          (cited, per meeting)
```

### How to say it on camera (15s + reveal)

- **Problem:** “Residents see a **headshot** and a **vote**—not whether the same person sounds confident on fines but evasive on housing.”
- **Reveal:** Play two clips of the **same** `person_id` from different meetings; flash `rhetoric_profile.consistency_note`; open citations in transcript JSON.
- **Scale:** “Pilot: **14** councilors in Tuscaloosa → schema scales to **100k** officials when transcripts + contacts exist nationally.”

### Why judges like this track

- **Multimodal** (vision + audio + text) without requiring new surveillance—only **public meetings** and **public directories**.
- Complements **Gemma policy analysis** and **TikTok summaries** (face + voice + issue hook in one package).
- **Measurable:** speaking time %, citation count per trait, cross-meeting phrase overlap—not “the AI thinks they’re an extrovert.”

### Ethics & caveats (say these out loud)

- **Not personality disorder diagnosis** or campaign opposition research—**rhetoric and participation** descriptors with sources.
- **Diarization errors** mis-attribute speech; show confidence and allow “unknown speaker” buckets.
- **Demographics / perceived traits** from photos (Demo 5 in Colab) are optional and must be labeled **model-inferred**, not ground truth.
- Obtain **consent** only where required; public-meeting audio and official portraits are generally public record—still avoid harassing or deceptive use (deepfake voice, impersonation).

**Repo commands (pilot):**

```bash
# Label transcripts with council names (fast)
python -m llm.gemini.enrich_transcript_diarization \
  --jurisdiction-id municipality_0177256 --state AL

# WhisperX: auto-finds Opus by title in the Tuscaloosa channel folder (no video_id in filename)
python -m llm.gemini.enrich_transcript_diarization \
  --video-id zpaawfaNsQM --whisperx
# → …/city_of_tuscaloosa_uc74dczs0b3mhdhuhp2zgrpa/2026-03-31_Tuscaloosa Projects Committee Meeting - Mar 31, 2026.opus
```

---

## Hackathon idea: Circular seasonal storytelling (Searching for Birds pattern)

**Reference:** [Searching for Birds](https://searchingforbirds.visualcinnamon.com/) — Nadieh Bremer (Visual Cinnamon) × Google Trends, February 2026. Sponsored data story; **D3.js** bespoke interactives; analysis in **R**; built with **Gemini 2.5 Flash Lite** for the in-page “spark bird” helper.

**Pitch hook:** *Council attention and resident curiosity don’t move in straight lines—they pulse through the year like migration. Can we see those rhythms the way birders see spring surges?*

### The concept (what to steal)

A **masterclass in complex time-series storytelling**: how **birding popularity shifts across America throughout the year**, told without default line charts.

| Layer | What Bremer built | Why it works |
| --- | --- | --- |
| **Macro rhythm** | 10-year **seasonal search curves** — April/May peaks, pandemic amplification | One glance shows **annual cycles** + anomalies |
| **Taxonomy nest** | Circular **“egg nest”** — general types (hawk, duck, owl) sized by search share | Hierarchy + beauty; drill from vague to specific |
| **Spark drill-down** | Zoomable **egg** subdividing 700 species → 76 types → 98 “search-popular” species | Scroll = discovery, not dashboard fatigue |
| **Reality check** | **Google search rank** vs **eBird observations** vs **population** (bar + connectors) | Surfaces **curiosity ≠ abundance** (Snowy Owl spike vs rare sightings) |
| **Geography** | **Top bird per state** hex map + localized surges (e.g. Sandhill Crane in NE) | Regional **seasonal surges** without 50 small multiples |
| **Hero moment** | Snowy Owl in Central Park → **NYC search spike** Jan 2021 | Event-driven **attention** as narrative hook |

### The signature visualization (your demo should name this)

Bremer mapped **hundreds of species’ weekly Google Trends** onto an **elegant, flowing circular design**—part interactive field guide, part abstract art. **Organic, color-coded wave patterns** follow the ring like **flock migrations**, so massive temporal trends are **intuitive** without reading axes on 589 small multiples.

**Why it stands out:** Judges remember **motion and metaphor**—not another grid of line charts. The form *is* the explanation (seasonality = orbit; species = lanes; surge = wave crest).

### Civic translation for Open Navigator

Same mechanics, **public-governance** subjects:

| Birds (reference) | CommunityOne mapping |
| --- | --- |
| Species search interest (weekly, 10y) | **Issue/theme** search or meeting signal by month: fines, potholes, zoning, water, sheriff contract |
| 76 “types” / nest eggs | **COFOG themes** or `primary_theme` buckets from Gemma `decisions[]` |
| eBird observations | **Meeting mentions** — transcript segment counts, `financial_items` hits, bronze event volume |
| State top species | **Top issue per state** among scraped jurisdictions (AL pilot → 67 counties + cities) |
| Snowy Owl spike | Local **spark event** — one viral agenda item (special election, owl-equivalent scandal, rate hike vote) |
| Circular waves | **Radial stream / polar heatmap**: month × theme, arc length = share of discourse |

**Data you already have (Tuscaloosa / warehouse path):**

- `bronze.bronze_event_youtube` — `event_date`, title, jurisdiction
- Caption cache — `YYYY-MM-DD_<title>.json` aligned with Opus basenames
- Policy JSON — `decisions[].primary_theme`, `narrative_analysis`, timestamps
- Optional external layer — **Google Trends** (`pytrends`) for resident search vs official record (mirror the story’s “search vs sightings” gap)

### Hackathon MVP (one state, one ring)

1. **Aggregate** — SQL or Python: count meetings / decisions / transcript mentions by **calendar month** and **theme** for `municipality_0177256` + one county peer set.
2. **Export** — CSV: `month`, `theme`, `meeting_count`, `search_index` (if Trends API used).
3. **Visualize** — D3 polar stack or [Observable](https://observablehq.com/) radial area; **color = theme**, **radius = month**, **wave height = intensity**.
4. **Reveal** — Click March peak → jump to **Pre-Council / Projects Committee** `playback_url` at peak week (same receipt pattern as TikTok track).
5. **Compare panel** — Side mini-chart: **Google Trends “property tax”** vs **mentions in minutes** (the civic “eBird vs search” slide).

```text
Bronze meetings + policy themes → monthly rollups → polar/wave D3 viz
         ↓                              ↓
   optional Google Trends          spark-event callout + deep link
```

### How to say it on camera (15s + reveal)

- **Problem:** “Residents only show up when something **explodes**—we never see the **season** of how councils and neighbors actually obsess over fines, streets, or water.”
- **Reveal:** Spin the ring—**April surge** in infrastructure talk; tap wave → **2026-03-31 Projects Committee** clip; flash “search interest vs agenda mentions don’t match.”
- **Scale:** “Pilot: **one city channel** → same schema for **100k meetings** nationally.”

### Why judges like this track

- **Data viz craft** rubric winner—shows you can ship **breathing** UI, not tables.
- Pairs with [**Gapminder-style reveal**](#gapminder-style-reveal-use-this-chart-pattern) (motion) and [**TikTok summaries**](#hackathon-idea-tiktok-style-meeting-summaries-issue-first-everyday-user) (distribution).
- **Google for Good** fit if you use **Trends + public meetings** with clear methodology footnotes.

### Tech notes (from the reference project)

- Trends pulled via **`pytrends`** (5 terms per request; normalized to a base species—plan the same for civic keywords).
- Interactives: **custom D3** (not off-the-shelf chart library defaults).
- On-page AI: **Gemini 2.5 Flash Lite** identification helper—analogous to your **`meeting_transcript_policy.py`** stack.

### Caveats

- **Google Trends** is relative index, not volume; label axes “search interest,” not “searches.”
- Meeting scrape coverage is **biased to what was recorded**—like eBird vs casual search.
- Circular layouts are hard on **screen readers**—provide a **table download** and keyboard-focusable legend.
- Do not imply Cornell/Google endorsement; cite [Searching for Birds](https://searchingforbirds.visualcinnamon.com/) as **design inspiration**.

---

## Hackathon idea: Automated interactive annual report (resident edition)

**Pitch hook:** *Your city publishes a 200-page PDF every year—what if residents got the same story LVMH gives shareholders: scrollable chapters, live charts, and one click to the source vote?*

Corporate and state **interactive annual reports** are the UX benchmark. Open Navigator can **generate the data layer** from meetings + audits so you are not hand-keying charts each fiscal year.

### What “best in class” interactive reports do (patterns to steal)

These are **design patterns**, not endorsements—study structure and reuse the mechanics on **public** data.

| Example | Format | What works | Steal for civic automation |
| --- | --- | --- | --- |
| [LVMH 2025 Interactive Annual Report](https://hosting.fluidbook.com/LVMH/2025interactiveannualreport/en/30-2025-Interactive-Annual-Report-LVMH.html) | Fluidbook / long scroll | Chapter per theme; KPI tiles; HR and capital side stories | One **scroll chapter per COFOG theme** or **meeting session** (`meetings/YYYY_MM_DD/session/`) |
| [Patagonia — Work in Progress (2025)](https://www.patagonia.com/progress-report/) | Scroll + video + honest metrics | Founder letter, “we missed this target,” repair/grant totals | **Chair letter** = excerpt from `narrative_analysis`; **repairs** = capital `financial_items` vs. discussion in minutes |
| [On — 2025 Impact Progress Report](https://press.on-running.com/ons-2025-impact-progress-report-on-shares-lessons-in-impact-from-its-15-year-journey) | Narrative + data split | Pillars (Decarbonization, Circularity, Social) with KPIs | Three pillars = **Fiscal health**, **Streets & capital**, **Trust & safety** (Shield summaries) |
| [NYC Comptroller — Popular Annual Financial Report (PAFR)](https://comptroller.nyc.gov/newsroom/nyc-comptrollers-office-releases-fiscal-year-2025-popular-annual-financial-report/) | Plain-language + visuals | “Popular” companion to the technical ACFR | Auto **`_meeting_summary.md`** + one chart per chapter = PAFR for one county |
| [NY State Comptroller — local government dashboards](https://www.osc.ny.gov/local-government/publications) / Open Book | Compare all entities in a class | Pick your county vs. peers | **Gapminder scatter** or bar rank: same metric, all counties in state |
| [Multnomah County — Financial Condition Report (Tableau)](https://multco.us/info/financial-condition-report-2026) | Embedded dashboards | Revenue vs. expenditure drill-down | dbt rollups → **Looker Studio** or static embed from exported CSV |

**Common thread:** **Story first**, numbers second, **drill-down** for skeptics, **download** for journalists.

### Reusable interaction patterns (automate once, refresh quarterly)

| Pattern | Resident question it answers | Open Navigator source |
| --- | --- | --- |
| **KPI hero cards** | “What changed this year?” | Sum `financial_items` by `category`; YoY compare on `fiscal_year` label |
| **Scrolly chapter** | “What did council argue about?” | `_meeting_summary.md` sections + `decisions[].headline` |
| **Receipt link** | “Show me the vote.” | `media_citation.playback_url` + `timestamp_start_seconds` |
| **Drift timeline** | “How did their story on this issue shift?” | `policy_drift.mmd` / `policy_drift.json` from Demo 4 |
| **Peer compare** | “Are we worse than neighbors?” | Warehouse by `state_code` + `scope`; fines % or accessibility count |
| **Gapminder moment** | “How do we move vs. everyone else?” | Animated scatter by `jurisdiction_id` over `calendar_year` strings |
| **Trust appendix** | “Was the AI summary safe?” | `05_safety_review/*.shield.json` aggregate |
| **Download data** | “I want the spreadsheet.” | Bronze export / `02_gemma_json` / dbt `bronze_*` tables |

### Automation pipeline (same stack as the Colab demo)

```text
Scrape agendas, minutes, ACFR PDFs, MP4
  → Gatekeeper → Gemma (policy_analysis_v1)
  → financial_items[] + decisions[] + narrative_analysis
  → dbt bronze_decisions / bronze_financial_items (warehouse)
  → rollup SQL: jurisdiction_id × fiscal_year × primary_theme
  → static site OR Flourish/Looker embeds (refresh on schedule)
  → optional: Gemma-generated “chair letter” prose per year from summaries
```

**Hackathon MVP (one weekend):**

1. **Inputs:** Tuscaloosa `county_01125`, **2 meeting dates**, budget/minutes PDFs (`SCOPE=fast`).
2. **Outputs:** Three “chapters” as markdown or a single-page site:
   - **Revenue & fines** — fines % KPI + one decision quote + Governing national band callout.
   - **Streets & capital** — top `financial_items` for paving/capital + potholes hook from minutes.
   - **Trust** — Shield `_summary.json` + “how we review AI on public records.”
3. **Wow chart:** Gapminder-style **AL counties** (or 600 jurisdictions from Open Book–style public data) with **your county highlighted**.
4. **Refresh story:** “Re-run Colab §6 + dbt seed; charts update—no designer rebuilding from Word.”

**Tools that fit hackathon time:** [MkDocs](https://www.mkdocs.org/) / Docusaurus page with embedded iframes; [Flourish](https://flourish.studio/) story; [Observable](https://observablehq.com/) notebook published to HTML; Google **Looker Studio** on a bronze CSV export.

### How to say it on camera (15s + reveal)

- **Problem:** “Annual reports are written for bond analysts, not for the person who got the ticket or the pothole.”
- **Reveal:** Scroll one **auto-generated chapter** (not a PDF)—click a KPI → jump to **meeting video at 1:05:30** → show **Gapminder** dots for every county.
- **Close:** “We don’t replace the audit—we **repackage** what meetings and budgets already say, every year, from the same pipeline.”

### CTA copy (annual report track)

Add to [Call to action slide](#call-to-action-slide-required-closing-beat):

- **Headline:** Read your county’s **living annual report**
- **Subline:** Meetings + budget → charts that update · Tuscaloosa pilot
- **CTA:** Open `_meeting_summary.md` · Run Colab §6 · Embed the Flourish chart

**Caveats:** Label **AI-assisted** sections; link to primary PDFs; separate **official ACFR** from **CommunityOne narrative**; animated charts need **source table** footnotes (audit year, fund).

---

## Why this matters

## Cross-dataset corruption investigation (OSINT pipeline)

You do **not** need one monolithic “anti-corruption” model to connect **meeting notes, campaign finance, property records, and charities**. Investigative desks (ICIJ on the Panama Papers, OCCRP on cross-border graft) use **open-source intelligence (OSINT)**, **entity resolution**, **network analysis**, and **NLP**—mostly on GitHub. Reuse that stack; use CommunityOne for the **meeting + policy + timestamp** layer.

**Citations and licenses:** [Data and Citations — Investigative OSINT toolkit](../data-sources/citations.md#investigative-osint--anti-corruption-toolkit).

### 1. Core investigative ecosystem (entity resolution + data model)

| Tool | Repo | Role in your demo |
| --- | --- | --- |
| **Splink** | [moj-analytical-services/splink](https://github.com/moj-analytical-services/splink) | Link “John Smith” / “J. Smith” / “Johnny Smith” across property, FEC, and charity tables (Fellegi–Sunter probabilities) |
| **Aleph** | [alephdata/aleph](https://github.com/alephdata/aleph) | OCCRP-style investigation workspace: ingest, search, cross-reference |
| **Follow the Money** | [alephdata/followthemoney](https://github.com/alephdata/followthemoney) | Shared schema: Person, Company, Land, Interest, Donation—before you graph |

**Maps to fraud tracks:** [Track 2 (valuation collusion)](#track-2-artificial-valuation-and-tax-evasion-collusion), [Track 4 (shell contractors)](#track-4-the-shell-game-contractor-audit).

### 2. Text & NLP (meetings + legislation)

| Tool | Repo | Role |
| --- | --- | --- |
| **Datashare** | [ICIJ/datashare](https://github.com/ICIJ/datashare) | OCR + entity extraction + search over thousands of PDF minutes (local or API) |
| **Grano** | [ANCIR/grano](https://github.com/ANCIR/grano) | Influence networks from mixed political/economic sources |

**CommunityOne shortcut:** You already have **transcripts + policy JSON** (`decisions[]`, `people[]`, `places[]`). Pitch Datashare for **bulk PDF backfill**; pitch CommunityOne for **structured decisions with playback timestamps**.

**Maps to fraud tracks:** [Track 5 (earmarks / dark money)](#track-5-the-earmark-and-dark-money-unveiler), [Track 3 (quid pro quo matrix)](#track-3-the-quid-pro-quo-policy-matrix).

### 3. Graph & network analysis

| Tool | Repo | Role |
| --- | --- | --- |
| **Datashare → Neo4j** | [ICIJ/datashare-extension-neo4j](https://github.com/ICIJ/datashare-extension-neo4j) | Visual traversable graph: “Who in Meeting X also donated before Vote Y?” |
| **NetworkX** | [networkx/networkx](https://github.com/networkx/networkx) | Centrality and cluster detection—who are the hubs? |

**Maps to fraud tracks:** [Track 3](#track-3-the-quid-pro-quo-policy-matrix), [Track 6 (land-use predictor)](#track-6-the-insider-trading-and-land-use-predictor).

### 4. Anomaly detection (property & donations)

| Tool | Repo | Role |
| --- | --- | --- |
| **ProACT** | [INTVP/proACT](https://github.com/INTVP/proACT) | Procurement-focused but includes transferable scripts (e.g. **Benford**) for skewed distributions |
| **Canary** | [CanaryInAMine/Canary](https://github.com/CanaryInAMine/Canary) | Public-records fraud / anomaly patterns for journalism |

**Maps to fraud tracks:** [Track 1 (appraisal gap)](#track-1-the-appraisal-gap-watchdog), [Track 7 (bond / infrastructure audit)](#track-7-municipal-bond-and-infrastructure-fund-auditing).

### Recommended workflow (hackathon slide)

```text
[Meeting notes / bills]  →  Datashare (or CommunityOne JSON)  →  entities
[Donations & charities]  →  Splink                            →  same person?
[Property DB]            →  Benford / outliers                →  value spikes
                                                              ↓
                                                    Neo4j / NetworkX
                                                    Cypher: short paths
                                                    policy ↔ money ↔ land
```

**60-second demo beat:** One zoning vote from a **Tuscaloosa** (or pilot) meeting → Splink matches a donor name to a **parcel owner** → Neo4j shows a **3-hop path** in under 10 seconds on screen.

**Do not:** Rebuild entity resolution from scratch with fuzzy `LIKE` joins—judges have seen Splink/OCCRP stories; name the tools.

---

## Fraud and conflict-of-interest hackathon ideas (master list)

The list below adds 10 fraud and conflict-of-interest detection tracks organized into thematic lanes. Each track includes data pipelines, technical targets, and a concrete engineering deliverable.

### Theme A: Real estate, appraisal, and property valuation fraud

#### Track 1: The appraisal gap watchdog

**Core concept:** Detect predatory flipping, artificial equity inflation, and mortgage fraud by identifying unjustified divergence between official property appraisals and market sale prices.

**Challenge:** Build an anomaly detection pipeline that flags properties where finalized sale price jumps far above recent county appraisals without matching structural permits or neighborhood-wide economic shifts.

**Data sources:** County assessor appraisal history, MLS or deed recorder finalized sale values, municipal building permit datasets.

**Target technologies:** Isolation Forest, DBSCAN, XGBoost or LightGBM expected-value modeling, GeoPandas spatial normalization.

**Deliverable:** Dashboard or API endpoint returning an Appraisal Fraud Risk Score for newly recorded deeds.

#### Track 2: Artificial valuation and tax evasion collusion

**Core concept:** Detect collusion where assets are undervalued for local taxes but inflated for lending.

**Challenge:** Build entity-resolution and comparison logic that identifies dual-identity valuation behavior across tax and financing contexts.

**Data sources:** County tax assessments, CMBS disclosures, zoning boundaries, state corporate tax filings.

**Target technologies:** [Splink](https://github.com/moj-analytical-services/splink) (probabilistic linkage), autoencoders for multivariate accounting anomalies. See [OSINT pipeline](#cross-dataset-corruption-investigation-osint-pipeline).

**Deliverable:** A detector for valuation schizophrenia patterns that maps assets with inconsistent valuation identities across agencies.

### Theme B: Conflicts of interest and public accountability

#### Track 3: The quid pro quo policy matrix

**Core concept:** Map temporal and network correlation between donations and policy actions by the same officials.

**Challenge:** Build a graph + time-window model that flags contribution spikes within 30 to 60 days of policy action likely to benefit donor sectors.

**Data sources:** OpenFEC Schedule A or OpenSecrets donations; Open States bill actions, amendments, and roll-call votes using ocd IDs.

**Target technologies:** Graph neural networks, cross-correlation, link prediction.

**Deliverable:** A policy-to-dollar network visualization highlighting highest-conviction influence clusters.

#### Track 4: The shell game contractor audit

**Core concept:** Detect procurement conflicts where officials award contracts to entities linked through ownership, family, or prior business networks.

**Challenge:** Resolve entities across corporate registries and contract award systems; flag newly formed or proxy-linked entities receiving public contracts.

**Data sources:** OpenCorporates or state corporate registries, USAspending or local checkbook datasets, official rosters.

**Target technologies:** [Splink](https://github.com/moj-analytical-services/splink) or Dedupe, [NetworkX](https://github.com/networkx/networkx) centrality. See [OSINT pipeline](#cross-dataset-corruption-investigation-osint-pipeline).

**Deliverable:** Compliance engine that flags high-risk procurement awards with explainable entity-link evidence.

#### Track 5: The earmark and dark money unveiler

**Core concept:** Expose how dark money channels influence local earmarks and infrastructure allocations.

**Challenge:** Extract hyper-local earmarks from dense legislative text and cross-reference with nearby acquisitions or lobbying activity before drafting.

**Data sources:** Open States and Legistar or Granicus legislative text, state lobbying disclosures, geospatial infrastructure datasets.

**Target technologies:** RAG + NER, vector databases such as Milvus or Chroma.

**Deliverable:** Interactive map translating bill paragraphs into likely financial beneficiaries.

### Theme C: Public infrastructure and funding misallocation

#### Track 6: The insider trading and land-use predictor

**Core concept:** Identify acquisitions that precede major public investment or zoning changes.

**Challenge:** Cross-reference transparency disclosures with localized acquisition spikes by politically exposed persons or linked entities before announcements.

**Data sources:** Data.gov and legislative appropriations portals, OpenCorporates filings, property sale records by ZIP or coordinates.

**Target technologies:** [Neo4j](https://neo4j.com/) + [followthemoney](https://github.com/alephdata/followthemoney) / [Datashare Neo4j extension](https://github.com/ICIJ/datashare-extension-neo4j), NER over investment text, lagged time-series analysis. See [OSINT pipeline](#cross-dataset-corruption-investigation-osint-pipeline).

**Deliverable:** Alerting system for high-value localized acquisitions within a 90-day pre-announcement window.

#### Track 7: Municipal bond and infrastructure fund auditing

**Core concept:** Verify whether public land and housing acquisitions align with fair market value.

**Challenge:** Build an automated auditor that compares public disbursements against local valuation baselines to detect inflated purchases.

**Data sources:** HUD and municipal bond project data, OCD jurisdiction identifiers, local transaction indexes and AVMs.

**Target technologies:** Explainable AI with SHAP for transparent overpricing flags.

**Deliverable:** Open-source forensic accounting tool that flags projects paid above a threshold such as 25 percent over comparable median appraised values.

### Theme D: Healthcare, identity, and environmental systems

#### Track 8: The healthcare phantom billing and upcoding detector

**Core concept:** Detect provider billing outliers for non-rendered services and upcoding patterns in public insurance claims.

**Challenge:** Build peer-normalized provider profiles and flag outlier behavior such as impossible procedure volume or complex-code inflation.

**Data sources:** CMS public use files with provider-level utilization and payment metrics.

**Target technologies:** Benford analysis, K-Means peer clustering, robust Z-score anomaly detection.

**Deliverable:** Interactive auditing app ranking facilities by Upcoding Risk Index.

#### Track 9: Synthetic identity theft and credit collusion

**Core concept:** Detect synthetic identities built from mixed stolen and fabricated attributes before account approval.

**Challenge:** Train a classifier that spots profiles lacking natural history and exhibiting shared-node fraud signatures across address, phone, device, or IP.

**Data sources:** Anonymized synthetic application logs, public address or phone structures, open credit simulation datasets.

**Target technologies:** Deep autoencoders, graph databases for shared-node detection, LightGBM classification.

**Deliverable:** Real-time ingestion gate that flags high-risk synthetic identity signatures pre-approval.

#### Track 10: Greenwashing and environmental grant fraud

**Core concept:** Detect mismatch between subsidized environmental claims and physical-world evidence.

**Challenge:** Cross-validate compliance narratives with satellite-derived land and vegetation signals.

**Data sources:** EPA ECHO, Sentinel or Landsat imagery via AWS Open Data, state or federal green subsidy award logs.

**Target technologies:** CNN-based change detection, NDVI analysis, multimodal fusion of imagery + text reports.

**Deliverable:** Automated reporting system flagging carbon-offset and green grant projects whose satellite footprint conflicts with paperwork.

### Execution tip for organizers

To keep teams focused on engineering instead of cleaning:

1. **Enforce standard joins:** Provide shared entity mapping templates (properties, agencies, officials, and geography to normalized boundaries or OCD divisions). Point teams at **[Splink](https://github.com/moj-analytical-services/splink)** + **[followthemoney](https://github.com/alephdata/followthemoney)** rather than hand-rolled name matching.
2. **Seed class imbalance intentionally:** Include synthetic anomalies or historic known cases so teams can calibrate thresholds and compare precision-recall tradeoffs.
3. **Document stack:** Require a one-slide “OSINT pipeline” ([template above](#recommended-workflow-hackathon-slide)) so demos interoperate with ICIJ/OCCRP-style tooling.

---

Judges and voters often decide from a **short demo**: problem clarity, human face, and a single **reveal** beat a long architecture tour. Treat the recording as a **pitch product**, not an afterthought.

## Reference videos and takeaways

### 1. The “data action” narrative (civic / academic gold standard)

**Focus:** Making **invisible** systems visible so policy and residents can act.

- **Example framing:** Sarah Williams’ work on *Data Action* and projects like informal transit mapping (e.g. crowdfunded data that shaped real planning)—the pattern is: **data → map/story → decision**.

**Takeaway for CommunityOne:** Show one concrete thing your data makes **visible** that a normal person couldn’t see before (e.g. who represents them, where money or services flow, or how engagement varies by place)—and state **what someone can do next** with that view.

**Find the talk:** Search YouTube for [DATA ACTION: Using Data for a Public Good | Sarah Williams | TEDxMIT](https://www.youtube.com/results?search_query=DATA+ACTION+Using+Data+for+a+Public+Good+Sarah+Williams+TEDxMIT) or see the [TEDxMIT speaker page for Sarah Williams](https://tedx.mit.edu/speaker/sarah-williams).

### 2. The high-stakes pitch framework (problem → UX → live demo)

**Focus:** Winners often **anchor on the user** and a **crisp problem**, then prove the product is real with a **live or screen demo**, not slides about the stack.

- **Pattern:** “Here’s who hurts” → “Here’s the experience” → “Here’s it working in 60 seconds.”

**Takeaway for CommunityOne:** Lead with **one persona** (resident, small business, advocate) and one **job-to-be-done**; show the **shortest path** through your UI to completion.

**Find similar pitches:** Search YouTube for [EOS London hackathon winning pitch $100,000](https://www.youtube.com/results?search_query=EOS+London+Hackathon+winning+pitch+100000) (many uploads recap EOS Global Hackathon London finalists and winners).

### 3. Multi-team impact demos (Google Cloud / “for good” adjacency)

**Focus:** Finalist-style compilations show **variety** and **production values**: clear problem, demo, outcome; often **accessibility** or **sustainability** angles land well in “for good” tracks.

- **Example playlist-style source:** [Google Cloud Vertex AI Hackathon: Finalists Pitches](https://www.youtube.com/watch?v=-_HKEyIYS_Q) (long compilation—skim for structure, overlays, and pacing).

**Takeaway for CommunityOne:** Study **picture-in-picture**: a person using the app while **data or maps update** in the same frame; keeps trust high and explains **cause → effect**.

### 4. What judges optimize for (meta: demo > raw code)

**Focus:** Experienced competitors stress that **storytelling and demo quality** often beat marginal code polish in short formats.

- **Example:** [How to Win EVERY Hackathon (from a Top 50 Hacker)](https://www.youtube.com/watch?v=JWxcEL4mg_Q)

**Takeaway for CommunityOne:** Script a **“reveal” beat**: first 15s = relatable pain; middle = your unique data angle; end = **one memorable before/after**.

## Inspirational catalog: civic data, tech & visualizations

Short talks, product stories, and case studies that show how **data + maps + humane design** change what people can *see* and *do* in civic life. Most clips are **under about seven minutes** (one TED talk runs slightly longer—called out below). Use them as **tone references** for your own demo: problem → insight → action.

### 1. The Joy of Stats — 200 countries, 200 years in minutes (Gapminder)

**Video (≈4:47):** [Hans Rosling — *200 Countries, 200 Years, 4 Minutes* (BBC / Gapminder)](https://www.youtube.com/watch?v=jbkSRLYSojo) · Live tool: [Gapminder Tools](https://www.gapminder.org/tools/)

**The problem:** Global health and wealth are often framed through static, pessimistic narratives.

**The tech:** Animated bubble charts (Gapminder-style) turn **~120,000 data points** into motion: income vs. life expectancy across countries and centuries—**play/pause**, **trails**, and **time** on one canvas.

**Why it’s inspirational:** Dry statistics become a **story of change**—the gold standard for a **reveal beat** in a hackathon video.

**Reuse in CommunityOne (required beat for many tracks):** See [Gapminder-style reveal](#gapminder-style-reveal-use-this-chart-pattern) under the flagship fines hook—map **jurisdictions** instead of countries, **fines %** or **street spend** instead of GDP, **fiscal year** instead of century. Same emotional arc: “You thought you knew your town—watch the dot move.”

---

### 2. Mapping “invisible” neighborhoods (humanitarian OpenStreetMap)

**Video (≈2 min tutorial):** [HOT — *What is Missing Maps?*](https://www.youtube.com/watch?v=wEEnOqmVfqM)

**Related explainer:** [HOT — *How to use the OpenStreetMap Tasking Manager*](https://www.youtube.com/watch?v=_feTGQXLf_M) · Organization: [Humanitarian OpenStreetMap Team (HOT)](https://www.hotosm.org/)

**The problem:** Many communities are **under-mapped**, which weakens disaster response, planning, and service delivery (see also [Herfort *et al.*, 2021](https://www.nature.com/articles/s41598-021-82404-z) — open access on humanitarian mapping in OSM).

**The tech:** Volunteers trace roads and buildings from **satellite imagery** into **OpenStreetMap**, coordinated through the **Tasking Manager**.

**Why it’s inspirational:** Crowdsourced geodata can give vulnerable places a **digital footprint** on the same basemap the rest of the world uses.

---

### 3. Predicting crime with data visualization (predictive policing)

**Video (≈4 min explainer):** [BBC News — *How predictive policing software works*](https://www.youtube.com/watch?v=YxvyeaL7NEM)

**The problem:** Police departments need to deploy **limited patrol resources** where harm is most likely—without falling back only on intuition or reactive hot-spot lists.

**The tech:** Algorithms ingest **historical incident** data and surface **space–time “hot” cells** (heat-map style) to guide patrol plans.

**Why it’s inspirational:** It illustrates **data-driven governance** in public safety—and invites a necessary hackathon conversation about **bias, transparency, oversight, and community consent** (not only algorithmic accuracy).

---

### 4. Visualizing air quality in near real time

**Video (≈2–3 min product story):** [Plume Labs — *Flow* personal air monitor (YouTube)](https://www.youtube.com/watch?v=ZBy9fJ0BWZk) · Product context: [Plume Labs — Flow](https://plumelabs.com/en/flow/) *(hardware discontinued for retail; ideas about sensing + maps remain relevant)*

**The problem:** Urban air pollution is **invisible** at street scale, so people can’t easily avoid exposure or advocate with evidence.

**The tech:** **Portable sensors** plus **mobile maps** expose pollution along routes and over time.

**Why it’s inspirational:** Personal and community-scale **environmental telemetry** turns “air quality” from an abstract index into **actionable spatial behavior**.

---

### 5. Code for America — fixing the safety net (GetCalFresh)

**Video (≈3–4 min):** [Alan Williams — *Voices of GetCalFresh.org*](https://www.youtube.com/watch?v=hzf8kJk07r8) · Deeper talk: [Jake Solomon — *A User-Centered Approach to Food Stamps* (CfA Summit)](https://www.youtube.com/watch?v=lqTFi2U2Ebc) · Program: [GetCalFresh](https://www.getcalfresh.org/)

**The problem:** Long, confusing paper and web flows stop eligible households from receiving **food assistance**.

**The tech:** **User-centered design** and a **mobile-first** flow shrink a bureaucratic ordeal into a **short, guided** application.

**Why it’s inspirational:** “Civic hacking” here means **respecting residents’ time** as much as shipping code—service design as equity work.

---

### 6. The 15-minute city (proximity & urban visualization)

**Video (≈7:53 — slightly over seven minutes, still a tight TED):** [Carlos Moreno — *The 15-minute city*](https://www.youtube.com/watch?v=TQ2f4sJVXAI) · Same talk on [TED.com](https://www.ted.com/talks/carlos_moreno_the_15_minute_city)

**Reading (2021):** [Carlos Moreno — *Introducing the “15-Minute City”…* (open-access journal article)](https://www.mdpi.com/2624-6518/4/1/6)

**The problem:** Sprawl and car dependence create **long commutes**, emissions, and weak neighborhood completeness.

**The tech:** **Spatial analysis** and **digital planning** tools express “complete neighborhoods” as measurable proximity to daily needs.

**Why it’s inspirational:** Data and maps help argue for a **human-scale city**—where time, carbon, and social connection are design outcomes, not afterthoughts.

---

### 7. Searching for Birds — circular seasonal data storytelling (Google Trends × civic analogy)

**Site:** [Searching for Birds — Visual Cinnamon](https://searchingforbirds.visualcinnamon.com/) (Feb 2026; Google Trends–sponsored)

**The problem:** Seasonal shifts in what people care about are buried in **hundreds of parallel time series**—easy to drown in line charts.

**The tech:** **~589 bird species** × weekly Google Trends mapped to a **flowing circular layout** with **color-coded waves** (migration metaphor); nested **egg** visual for taxonomy; **search vs eBird vs population** triptych; state hex map for top species; **Gemini Flash Lite** spark-bird chat.

**Why it’s inspirational:** Proves **complex temporal data** can feel **organic and immediate**—a direct antidote to “dashboard of 50 sparklines.”

**Reuse in CommunityOne:** See [Circular seasonal storytelling](#hackathon-idea-circular-seasonal-storytelling-searching-for-birds-pattern)—map **meeting themes × month** on the ring, **resident Trends** vs **minutes/transcripts**, Tuscaloosa committee calendar as pilot.

---

### 8. Safe water access — mapping and field data (mWater)

**Video (overview):** [mWater — *Overview / key concepts*](https://www.youtube.com/watch?v=ah6yX1fNM9w) · Hub: [mWater — Learn with video](https://www.mwater.co/learn-with-video)

**The problem:** Communities can’t manage what they don’t **locate and measure**—unsafe or unknown water points stay invisible to planners and residents.

**The tech:** A **mobile + cloud** platform to **map assets**, run **surveys**, and **visualize** water quality and infrastructure over geography.

**Why it’s inspirational:** It puts **lightweight M&E tooling** in the hands of local actors—classic “infra + map + feedback loop” civic tech.

---

### 9. Streetmix — civic design for everyone

**Video (community redesign using Streetmix):** [Shifter — *Help redesign this street so it’s better for all users*](https://www.youtube.com/watch?v=7G3hw4IJdmc) · Tool: [streetmix.net](https://streetmix.net) · Docs: [Streetmix documentation](https://docs.streetmix.net/)

**The problem:** Street design is often **opaque** to people who live on the corridor; PDFs and jargon block participation.

**The tech:** A **browser-based cross-section editor**—drag and drop lanes, trees, transit, and buffers to **prototype** alternatives.

**Why it’s inspirational:** Residents can **show**, not only tell, what they want—visual language bridges community and public works.

---

### 10. Data against modern slavery (supply-chain awareness)

**Video (≈2:30):** [Slavery Footprint — *How Many Slaves Work For You?*](https://www.youtube.com/watch?v=x8K-tMog1f4) · Experience: [slaveryfootprint.org](https://slaveryfootprint.org/)

**The problem:** Forced labor in global supply chains feels **distant** to everyday consumers.

**The tech:** An **interactive survey** turns lifestyle inputs into a **personalized footprint estimate** and visualization.

**Why it’s inspirational:** Dataviz makes an abstract human-rights crisis **personal**—a pattern your hackathon app can echo for other “hidden” harms.

---

### 11. “No-blame” civic problem solving (Power Civics)

**Videos (short course — pick modules that fit your pitch):** [The Citizens Campaign — *Power Civics* video library](https://thecitizenscampaign.org/power-civics-videos/watch/) · Broader search: [YouTube — “Power Civics” + Citizens Campaign](https://www.youtube.com/results?search_query=Power+Civics+Citizens+Campaign)

**The problem:** Residents feel they lack a **repeatable path** from concern to **evidence-based** proposals in local institutions.

**The tech:** A **structured curriculum** (short videos + materials) teaches power centers, roles, and **no-blame** problem framing—**civic education as a platform**.

**Why it’s inspirational:** It treats democracy partly as **literacy and method**—skills that compound when paired with open data products.

---

### 12. Township garage sale — from paper maps to live vendor layout (Maine Township, Illinois)

**Case study:** [CivicPlus — *Modernizing Tradition: Maine Township’s Garage Sale Goes Digital*](https://www.civicplus.com/case-studies/pr/maine-township-goes-digital-successfully/)

**The problem:** A large annual community fundraiser relied on **in-person-only** vendor signup, **cash/check** payments, and a **paper map** of spaces—creating long lines, weak accessibility for non-residents and daytime workers, and occasional **double bookings** when availability wasn’t updated in real time.

**The tech:** **Online registration and payments**, an **interactive map** of vendor spaces with **live sold/available** status, **centralized records** (including walk-ins entered into the same system), and **equipment rental** inventory (e.g. tables).

**Why it’s inspirational:** It’s a concrete **“civic operations + maps + payments”** story—exactly the kind of workflow a hackathon team could reimagine with **open data**, transparent rules, and **resident-first** UX without requiring a proprietary stack.

---

## Call to action slide (required closing beat)

**Every hackathon submission video should end on a dedicated CTA slide**—not a trailing voiceover over code. Hold it **3–5 full seconds** so judges can screenshot it.

### Slide layout (16:9 demo or 9:16 TikTok)

| Zone | Content |
| --- | --- |
| **Headline (large)** | One imperative—what to do **next** |
| **Subline** | One proof line—jurisdiction + source |
| **Primary button / URL** | Single link or QR (repo, Colab, or lookup) |
| **Logo** | CommunityOne / Open Navigator mark (small, corner) |

### Copy templates (pick one track per video)

**Fines / speed traps**

- **Headline:** Look up your town’s **fine-revenue %**
- **Subline:** Budget + meeting sources · Tuscaloosa County pilot
- **CTA:** `github.com/…/open-navigator` · Run Colab `02_run_meeting_llm`

**Potholes / infrastructure**

- **Headline:** See **what your council approved** for your roads
- **Subline:** Capital budget + meeting vote · linked timestamp
- **CTA:** Open your county folder · Compare **$ streets** vs. **your ZIP**

**TikTok / short-form**

- **Headline:** **45 seconds** beats 4 hours of council video
- **Subline:** AI summary + link to the real recording
- **CTA:** Full meeting in bio · Comment your **ZIP** for a fact-check

**100k meetings / safety scrub**

- **Headline:** Ask for a **trust index** on public meeting AI
- **Subline:** Shield-reviewed summaries · pilot → national scale
- **CTA:** Star the repo · Request your **state** in the pilot

**100k decisions / reasoning & bias**

- **Headline:** Did the **strongest argument** win the vote?
- **Subline:** 100k decisions · champion profiles · systemic patterns
- **CTA:** Open `*.thinking.json` · Read the methodology appendix

**Accessibility**

- **Headline:** Test **your** city’s `.gov` homepage
- **Subline:** axe + Pa11y scan · violation count by jurisdiction
- **CTA:** Run `./packages/accessibility/src/accessibility/run_accessibility_scan.sh --state AL`

**Interactive annual report**

- **Headline:** Open your county’s **living annual report**
- **Subline:** Auto chapters from meetings + budget · updates each run
- **CTA:** `_meeting_summary.md` · Colab §6 · Gapminder chart embed

**Gapminder / peer compare**

- **Headline:** See **every county** on one chart
- **Subline:** Fines % · accessibility · or street spend — your dot highlighted
- **CTA:** Export bronze CSV · Flourish / Looker Studio template

### Recording checklist

- [ ] CTA slide is the **last frame** (no terminal scroll, no credits over UI)
- [ ] URL or QR is **readable at 1080p** on a phone recording of the projector
- [ ] Spoken line matches the slide: “**Do this tomorrow:** …”
- [ ] One action only—don’t list three equal CTAs

---

## “Wow” video checklist (summary)

| Idea | What to do |
| --- | --- |
| **15-second rule** | Open with a **regular person** (or voiceover + b-roll) stating a **specific** local problem—not your stack. |
| **Magic moment** | One smooth **zoom** or transition: region → neighborhood → **one insight** (map, chart, or profile) that answers that problem. |
| **Google / familiar UI** | If the hackathon is Google-adjacent, **show** Maps, Sheets/Looker Studio, or another familiar surface **next to** your data so trust is instant. |
| **Demo over deck** | Prefer **screen capture** (e.g. OBS, Loom) of a **happy path** over architecture diagrams. |
| **Data action** | Explicitly say what became **actionable** (find, compare, contact, plan) that wasn’t before. |
| **Accessibility reveal** | Show a **scanner result** next to the live `.gov` page (axe/Pa11y violation → same element on screen). |
| **TikTok beat** | One **vertical** clip: hook stat → 20s plain English → **source URL + timestamp** on the last frame. |
| **Reasoning vs. narrative** | Side-by-side: `arguments_against` **rationale** vs. `dominant_narrative` for one decision—then a national “100k gaps” slide. |
| **CTA slide (required)** | Final **3–5s** full-screen slide: one headline + one link/QR—see [Call to action slide](#call-to-action-slide-required-closing-beat). |
| **Gapminder reveal** | One **animated scatter** (play button)—jurisdictions or years in motion—not a static screenshot. |
| **Interactive annual report** | **Scroll** one auto-generated chapter; KPI → **source timestamp**; mention “refreshes when we re-run the pipeline.” |
| **Timeline + entities + map** | One scrub: timeline event → **map pin** (`places[]`) → **person** filter; cite [KronoGraph](https://kronograph.cambridge-intelligence.com/) or show Mermaid + map side-by-side. |

## Applying this to Open Navigator / CommunityOne

- **Gapminder beat:** At least one animated chart (Flourish/Observable) with **jurisdiction_id** on X/Y and **year** slider—tie to fines % or peer accessibility; script it like [Rosling](https://www.youtube.com/watch?v=jbkSRLYSojo).
- **Living annual report:** Publish `_meeting_summary.md` + 2–3 KPI cards + `policy_drift.mmd` as a scroll page; position as **PAFR-style** companion to the official PDF.
- **One jurisdiction, one story:** Default Gemma run: **Tuscaloosa County, AL** (`county_01125`) with **`SCOPE=fast`** (**2 meetings**, **6 PDFs**)—fines %, Feb+May meetings, and Shield review in one pass.
- **Killer scale story:** Pilot on county_01125 → slide to **100k meetings** safety scrub (Shield + Gemma) as the national vision.
- **Research scale story:** Same `decisions[]` JSON → score **arguments** vs. **LLM dominant narrative** → join **decision-maker / proponent** profiles → report **systemic** skew (themes, ZIPs, repeat champions)—not single-villain framing.
- **Short-form branch:** Same JSON → one **issue-focused 45s script** (speed trap / fine % or **potholes / street $** hook) + optional clip at `media_citation.playback_url`.
- **Integrated investigation UI:** Export `decisions[]` + `places[]` + `media_anchor` to a timeline ([KronoGraph](https://kronograph.cambridge-intelligence.com/) or map + playback)—pilot on Tuscaloosa HPC **711 Queen City Avenue** COA; see [Integrated timeline, entities, and maps](#hackathon-idea-integrated-timeline-entities-and-maps-kronographcambridge-intelligencecom).
- **Combine tracks (advanced):** Fines % + accessibility score + safety `_summary.json` for the same `jurisdiction_id`.
- **Other goals still work:** Officials lookup, nonprofit + government spend context, meeting drift—but keep **one** primary hook per video.
- **Source credibility:** Flash **audit year**, **fund name**, and **Governing / state comptroller** on screen for a second—reinforces “real data,” not a mockup.
- **End on the CTA slide (non-negotiable):** Use the [template above](#call-to-action-slide-required-closing-beat)—hold **3–5 seconds**, one headline, one link. Say aloud: “**Do this tomorrow:** run the notebook / look up your county / comment your ZIP.”

---

*Internal doc: ideas only; not an endorsement of any sponsor or platform. Refresh YouTube links periodically if uploads move.*
