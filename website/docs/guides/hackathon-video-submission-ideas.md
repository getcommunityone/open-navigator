---
displayed_sidebar: developersSidebar
description: Reference patterns and a checklist for strong “Google for Good”–style hackathon demo videos (CommunityOne / Open Navigator), including flagship pitch hooks (speed-trap revenue, 100k-meeting safety scrub, jurisdiction website accessibility), plus inspirational civic data talks and case studies.
---

# Hackathon video submission ideas (reference library)

Short guide for a **CommunityOne** (or similar civic-data) submission where the **video** has to carry the “wow” as much as the product. These notes distill reference talks and pitch formats that bridge **complex data → real-world utility**.

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
./scripts/accessibility/run_accessibility_scan.sh --engine axe --state AL

# Optional: PDF/UA on agenda/minutes PDFs discovered on those homepages
./scripts/accessibility/run_verapdf_scan.sh --state AL --max-pdfs-per-site 3
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

## Why this matters

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

### 1. The Joy of Stats — 200 countries, 200 years in minutes

**Video (≈4:47):** [Hans Rosling — *200 Countries, 200 Years, 4 Minutes* (BBC / Gapminder)](https://www.youtube.com/watch?v=jbkSRLYSojo)

**The problem:** Global health and wealth are often framed through static, pessimistic narratives.

**The tech:** Animated bubble charts (Gapminder-style) turn **~120,000 data points** into motion: income vs. life expectancy across countries and centuries.

**Why it’s inspirational:** Dry statistics become a **story of change**—a reminder that visualization can reframe what “the data says” about progress and inequality.

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

### 7. Safe water access — mapping and field data (mWater)

**Video (overview):** [mWater — *Overview / key concepts*](https://www.youtube.com/watch?v=ah6yX1fNM9w) · Hub: [mWater — Learn with video](https://www.mwater.co/learn-with-video)

**The problem:** Communities can’t manage what they don’t **locate and measure**—unsafe or unknown water points stay invisible to planners and residents.

**The tech:** A **mobile + cloud** platform to **map assets**, run **surveys**, and **visualize** water quality and infrastructure over geography.

**Why it’s inspirational:** It puts **lightweight M&E tooling** in the hands of local actors—classic “infra + map + feedback loop” civic tech.

---

### 8. Streetmix — civic design for everyone

**Video (community redesign using Streetmix):** [Shifter — *Help redesign this street so it’s better for all users*](https://www.youtube.com/watch?v=7G3hw4IJdmc) · Tool: [streetmix.net](https://streetmix.net) · Docs: [Streetmix documentation](https://docs.streetmix.net/)

**The problem:** Street design is often **opaque** to people who live on the corridor; PDFs and jargon block participation.

**The tech:** A **browser-based cross-section editor**—drag and drop lanes, trees, transit, and buffers to **prototype** alternatives.

**Why it’s inspirational:** Residents can **show**, not only tell, what they want—visual language bridges community and public works.

---

### 9. Data against modern slavery (supply-chain awareness)

**Video (≈2:30):** [Slavery Footprint — *How Many Slaves Work For You?*](https://www.youtube.com/watch?v=x8K-tMog1f4) · Experience: [slaveryfootprint.org](https://slaveryfootprint.org/)

**The problem:** Forced labor in global supply chains feels **distant** to everyday consumers.

**The tech:** An **interactive survey** turns lifestyle inputs into a **personalized footprint estimate** and visualization.

**Why it’s inspirational:** Dataviz makes an abstract human-rights crisis **personal**—a pattern your hackathon app can echo for other “hidden” harms.

---

### 10. “No-blame” civic problem solving (Power Civics)

**Videos (short course — pick modules that fit your pitch):** [The Citizens Campaign — *Power Civics* video library](https://thecitizenscampaign.org/power-civics-videos/watch/) · Broader search: [YouTube — “Power Civics” + Citizens Campaign](https://www.youtube.com/results?search_query=Power+Civics+Citizens+Campaign)

**The problem:** Residents feel they lack a **repeatable path** from concern to **evidence-based** proposals in local institutions.

**The tech:** A **structured curriculum** (short videos + materials) teaches power centers, roles, and **no-blame** problem framing—**civic education as a platform**.

**Why it’s inspirational:** It treats democracy partly as **literacy and method**—skills that compound when paired with open data products.

---

### 11. Township garage sale — from paper maps to live vendor layout (Maine Township, Illinois)

**Case study:** [CivicPlus — *Modernizing Tradition: Maine Township’s Garage Sale Goes Digital*](https://www.civicplus.com/case-studies/pr/maine-township-goes-digital-successfully/)

**The problem:** A large annual community fundraiser relied on **in-person-only** vendor signup, **cash/check** payments, and a **paper map** of spaces—creating long lines, weak accessibility for non-residents and daytime workers, and occasional **double bookings** when availability wasn’t updated in real time.

**The tech:** **Online registration and payments**, an **interactive map** of vendor spaces with **live sold/available** status, **centralized records** (including walk-ins entered into the same system), and **equipment rental** inventory (e.g. tables).

**Why it’s inspirational:** It’s a concrete **“civic operations + maps + payments”** story—exactly the kind of workflow a hackathon team could reimagine with **open data**, transparent rules, and **resident-first** UX without requiring a proprietary stack.

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

## Applying this to Open Navigator / CommunityOne

- **One jurisdiction, one story:** Default Gemma run: **Tuscaloosa County, AL** (`county_01125`) with **`SCOPE=fast`** (**2 meetings**, **6 PDFs**)—fines %, Feb+May meetings, and Shield review in one pass.
- **Killer scale story:** Pilot on county_01125 → slide to **100k meetings** safety scrub (Shield + Gemma) as the national vision.
- **Combine tracks (advanced):** Fines % + accessibility score + safety `_summary.json` for the same `jurisdiction_id`.
- **Other goals still work:** Officials lookup, nonprofit + government spend context, meeting drift—but keep **one** primary hook per video.
- **Source credibility:** Flash **audit year**, **fund name**, and **Governing / state comptroller** on screen for a second—reinforces “real data,” not a mockup.
- **End on a CTA:** What should a viewer **do tomorrow**—open their county’s folder, run the Colab notebook, or look up their town’s fine-revenue %?

---

*Internal doc: ideas only; not an endorsement of any sponsor or platform. Refresh YouTube links periodically if uploads move.*
