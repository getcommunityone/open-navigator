---
pr: 1413
verdict: approve-with-nits
---
# Review of PR 1413 (USAspending awards, #1393)

- Data: bronze loader (package CLI), staging, match, two marts with PK/FK enforced; dbt tests 21/21 pass; benchmark pytest 7/7.
- No fabricated numbers: unmatched jurisdictions return null, not 0.
- No private persons involved; public-domain source, polite client, stops on 403/429.
- Nit: months 2022-02, 2022-09, 2023-09 did not load (API errors); loader lists them for retry. State-government recipients not loaded yet.
- Serving: jurisdiction_federal_funding about 4 MB added to CIVIC_SERVING; no Neon writes.
