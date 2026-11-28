---
pr: 1435
verdict: approve
---

# Review of PR 1435

Scope: `.gitattributes`, `web_docs/docusaurus.config.ts`, `web_docs/src/css/custom.css`, new `web_docs/static/img/favicon.svg`.

- No blocking findings. Attribute exemption is limited to two files, so the LFS-pointer undraw SVGs stay untouched.
- Verified with a production build and Playwright (360, 412, 1440): logo loads, no broken images, no overflow. Deploy staging simulation keeps both SVGs as raw text.
- Nit: the live site needs a deploy to pick this up.
