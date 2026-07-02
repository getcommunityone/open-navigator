# Open Navigator — Winning Demo Storyboard

> Source of truth for `record-demo.mjs`. Each scene below maps 1:1 to a `scene()` call
> in the recorder. Narration lines are what a presenter says; on-screen captions are the
> short lower-third text the recorder burns into the video.

**Target length:** ~2:45. **Resolution:** 1920×1080. **Audience:** judges scanning many
demos — lead with the hook and the one thing nobody else has (match evidence + real money,
no fabricated numbers).

**Through-line (from the README):** *"CommunityOne: One Map for Every Community."* Public
power is scattered and invisible. Open Navigator turns 279k+ real civic records — meetings,
decisions, money, people — into one searchable map where every claim is backed by a real,
highlighted source.

---

## Scene 1 — Hook (Home hero) · ~14s
- **Route:** `/`
- **On-screen caption:** `One map for every community` / `279,000+ real civic records — meetings, money, decisions, people`
- **Narration:** "Public power is hard to see. Meetings, budgets, and decisions are scattered across thousands of sites. Open Navigator pulls it into one map — and everything you'll see is a real record, never a made-up number."
- **Action:** land on hero, slow scroll through the homepage value props.

## Scene 2 — Scale you can search (Unified Search, empty) · ~12s
- **Route:** `/search`
- **Caption:** `Search the whole civic record` / `Meetings · decisions · bills · nonprofits · grants · people`
- **Narration:** "One search bar over the entire civic record: 119,000 meetings, 13,000 bills, 1.8 million nonprofits, federal grants, and the people behind them."
- **Action:** show the search landing + type into the box.

## Scene 3 — The differentiator: match evidence (Search "fluoride") · ~22s
- **Route:** `/search` → type `fluoride`
- **Caption:** `Every result shows you WHY it matched` / `A real, highlighted quote from the actual transcript — never fabricated`
- **Narration:** "Search 'fluoride' and you don't just get titles — every tile shows the exact passage where it came up in the real meeting transcript, with the term highlighted. If we can't show you the quote, we don't show you the result. No invented numbers, ever."
- **Action:** submit search, let results render, scroll to show highlighted `<mark>` snippets on several tiles.

## Scene 4 — Browse by what people actually care about (Browse Topics) · ~18s
- **Route:** `/browse-topics`
- **Caption:** `Browse by topic — straight to the decisions` / `Real meeting clips, scoped to a place`
- **Narration:** "Don't know what to search? Browse by topic. Pick one and you land on the actual decisions and meeting clips — scoped to a community, with the scope label always matching the data."
- **Action:** click a topic pill, let decision cards load, scroll.

## Scene 5 — Follow the money (Money & Talk / Money flow) · ~20s
- **Route:** `/money-and-talk`
- **Caption:** `Follow the money` / `Real dollar impact from real decisions — Census, grants, 990s`
- **Narration:** "Here's where it gets powerful for funders and residents alike: money. Real dollar impact pulled from real decisions, federal grants, and nonprofit filings — not a demo placeholder."
- **Action:** let the money visualization render, scroll/hover.

## Scene 6 — The map (Decisions Map) · ~18s
- **Route:** `/decisions-map`
- **Caption:** `One map for every community` / `Civic decisions, placed where they happened`
- **Narration:** "Every decision lives somewhere. The map places them geographically so you can see what's happening on the ground — block by block, town by town."
- **Action:** let the map tiles + markers render, gentle zoom/pan or scroll.

## Scene 7 — The civic story in depth (a Decision / Meeting detail) · ~20s
- **Route:** first real result from `/api/search` decisions leg (deep link), fallback `/browse-causes`
- **Caption:** `Go deep — the full civic story` / `Competing views, jump-to-moment, sourced`
- **Narration:** "Click in and you get the whole story: what was decided, the competing arguments, and a jump-to-moment link straight to the second it was said on video. Every layer traces back to a real source."
- **Action:** scroll the detail page through its sections.

## Scene 8 — Close (Home) · ~12s
- **Route:** `/`
- **Caption:** `Open Navigator` / `One map for every community · communityone.com`
- **Narration:** "Residents, leaders, and funders — connected to what's really happening, on one map, all of it real. Open Navigator. communityone.com."
- **Action:** return home, settle on the hero, hold.

---

### Why this wins (judge-facing notes)
1. **Unique, verifiable feature first.** Match-evidence highlighting + the "no fabricated data"
   guarantee is the thing competitors can't fake. We lead with it (Scene 3).
2. **Scale is shown, not claimed.** Real counts from the live corpus (Scene 2).
3. **Money is the closer for funders** (Scene 5) — concrete, sourced, civic dollars.
4. **Narrative arc** mirrors the README pitch exactly: scattered → one map → residents/leaders/funders.
5. **Every screen is populated.** The recorder deep-links into entities that have data and
   skips/falls back gracefully so the final cut never shows an empty state.
