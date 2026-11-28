---
pr: 1453
issue: 1452
verdict: approve
---

# PR #1453 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `chore/1452-mit-license`, `Closes #1452`; the issue has all four parts and the `documentation` label.
- **Scans:** no secrets, no fabricated data, no personal data, no data changes. The PR body names outside contributors only to say the owner should confirm consent; nobody is contacted.
- **Correctness:**
  - `LICENSE` is word-for-word the SPDX `MIT` text (whitespace-normalised diff against spdx/license-list-data `text/MIT.txt` is empty), with `Copyright (c) 2026 CommunityOne`, wrapped as in GitHub's choosealicense template so Licensee can detect it. It remains the only licence file at the root.
  - Every remaining `apache` match in the tree was read in context: Delta Lake/PySpark (costs.md), Bitol ODCS/ODPS (data-contracts.md), civic-scraper (integrations/overview.md), OMOP and other citations, Apache Spark/Iceberg/Parquet as technologies, Spark config class names, and the vendored `dbt_project/contracts/_schema/NOTICE`. All describe third parties and are correctly unchanged.
  - Hugging Face front matter uses `license: mit`, a valid HF licence identifier.
  - `setup.py` uses the valid trove classifier `License :: OSI Approved :: MIT License`.
- **Verification:** grep for `apache` across the edited files returns only the historical note in `huggingface-spaces.md` ("relicensed from Apache 2.0"). No code paths change, so no tests apply.
- **Docs:** the governed pages `web_docs/docs/deployment/huggingface-spaces.md` and `web_docs/docs/pitch/full-text-and-notes.md` are updated in this PR.

🔵 Nit (not blocking): `apps/rag-chat-app/package.json` says `"license": "Unlicensed"`. It is a separate sample app and never said Apache, so it is listed in the PR for the owner rather than changed.

No blocking findings. Owner action outside the code: confirm outside contributors' consent to relicensing.
