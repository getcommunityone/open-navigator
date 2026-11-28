---
pr: 1448
issue: 1416
verdict: approve-with-nits
---

# PR #1448 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `feat/1416-hot-topic-pills`, `Closes #1416`; the issue has all four parts.
- **Scans:** no secrets, no personal data, no fabricated numbers. Every pill badge, headline count and percentage is read from `/api/topics/yoy`; a topic with nothing recorded says so; heat shows only with the API's 20-speaker minimum.
- **Scope label:** pills, headline and map all follow the place in the URL; the pill row is recomputed from the yoy response for that place and labelled with its scope (`aria-label`, `data-scope`).
- **Contract:** no new endpoint (a combined list is a pure client function, unit-tested). Shared files touched additively: `boxFlight.ts` (`captureDomBoxesChunked`), `BoxFlightProvider.tsx` (count polling, prehide cleanup), `storyCharts.css` (prehide rule).
- **Verification:** `tsc` clean, vitest 993 pass. `e2e/hero-topic-switch.check.mjs` at Pixel 7 and 1440 (national, GA, FL): pills render with badges and Compare all last; a pill pick changes the headline and `?topic=`; boxes are present before and after; National to AL to National flies (canvas frames above 0, boxes before and after).
- **Nit (not blocking, #1458):** the 100 ms long-task budget at 4x throttle is not met. On a contended host (load average 12 to 29) topic switches measured 244 to 2,559 ms and place switches 1,978 to 6,651 ms; profiling puts the cost in React mounting the 2,200 to 4,200 box maps, which also happens without the flight (see #1412). Needs a render change in the map components.
- **Nit (#1449):** map place counts disagree with yoy counts for some topics (FL fire-and-ems: 57 vs 0); an API-side fix.
- **Not done:** tapping a state on the national hero map still opens that state's story (existing #1285 behaviour), it does not apply the place on the home page.
- **Docs:** `web_docs/docs/guides/data-stories.md` has the new section.

No blocking findings.
