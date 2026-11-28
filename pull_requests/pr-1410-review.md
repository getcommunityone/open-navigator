---
pr: 1410
verdict: approve-with-nits
---
# Review of PR 1410

Scope is small and builds on #1404's flight layer. Every box maps to real yearly counts (partial top box is proportional); no placeholder data. Copy fix removes a capped-list claim and states the peak from full counts.

Nits: the perf check fails its 100 ms assertion in this environment (screen mount cost, also present under reduced motion); tracked in a follow-up issue. story-scroll's "broaden to National" failure is pre-existing (same on main's dev server).
