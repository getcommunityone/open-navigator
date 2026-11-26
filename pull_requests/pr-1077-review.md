
## Agent review

- Closes #1073; follow-ups #1074 (990-PF), #1075 (contributions/lobbying), #1076 (org pages on Neon).
- Scans: no secrets or personal data (grants between organizations, from IRS filings). No fabricated data: amounts are sums of 990 line amounts; a blank amount stays blank; each foundation link cites a public source with a verbatim excerpt; OpenAI Foundation is labelled as the nonprofit that controls the company, not corporate giving.
- Keys: PK grant_id, FKs to grant / company and foundation master_org_id / grantee (nullable); contract enforced.
- Checks: pytest 4 passed and tsc clean (re-run by me); totals re-queried locally (Airbnb.org $18,528,372; Oracle Health Foundation $18,385,477; OpenAI Foundation $12,683,542); ODCS current.

No blocking findings.
