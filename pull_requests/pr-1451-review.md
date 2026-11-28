---
pr: 1451
verdict: approve
---

# Review of PR 1451

Scope: `.gitattributes` only. SVG entries drop `-diff -merge` and keep `-filter`.

- No blocking findings. Replayed deploy staging in a throwaway clone: logo and favicon SVGs are staged with line counts (22 and 1), none in the 63 numstat-binary files.
- Nit: needs a deploy to take effect.
