# PR 467 review: fix(fec): pass a timeout on both FEC HTTP calls

Closes #465. Range: `origin/main..fix/465-fec-request-timeouts`. Files: `packages/scrapers/src/scrapers/fec/fec_integration.py` (+7 -2), `packages/scrapers/tests/test_fec_integration_timeouts.py` (new).

## Scans

- **Secrets:** none. The tests use `api_key="test-key"` and mocks; no real key, no network.
- **Fabricated data:** none served; test fixtures stay in tests.

## Findings (verified)

- 🔵 Nit: a timeout now raises `requests.exceptions.Timeout` from both calls, where before they hung. Callers that loop over many API requests will stop at the first timeout instead of waiting; a retry belongs to the follow-up in #466 (the shared `core_lib.http` client), not here.
- 🔵 Nit: `(10, 600)` for the bulk read is a judgement: 10 minutes without a chunk is far beyond a slow but live server.

## Rules

| Rule | Result |
|---|---|
| Issue first, four parts | ✅ #465 |
| Branch and PR naming | ✅ `fix/465-...`, `Closes #465` |
| Conventional Commits | ✅ |
| New Python in packages/, not scripts/ | ✅ |
| Tests | ✅ 3 new, failed before, pass after |
| Never read raw data / data/cache | ✅ temp folder only |

## Checks

`pytest packages/scrapers/tests/test_fec_integration_timeouts.py`: 3 passed. (`test_fec_unzip_workers.py` needs `tqdm`, not installed in the reviewer's environment; untouched by this PR.)

## Verdict

Ready for the maintainer to merge when CI is green.
