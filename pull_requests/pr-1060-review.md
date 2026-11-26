
## Agent review

- Issue and branch: fix/1059-voices-reviewed-zero, Closes #1059; four parts present.
- Scans: no secrets or personal data; no fabricated data: the 0 is the API's real speaker total over meetings_reviewed analysed meetings (the mart defines 0 as analysed, none found), and the reason line names that count; scopes with no reviewed meeting still read not recorded.
- Correctness: votes unchanged; a real 0 beside real counts still 0; the scope label in the reason matches the page scope.
- Checks: vitest 316 passed, tsc clean. Docs: data-center-who-spoke-up.md.

No blocking findings.
