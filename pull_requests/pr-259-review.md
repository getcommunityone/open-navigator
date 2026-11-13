---
pr: 259
branch: feat/258-api-db-tracing
title: "feat(api): trace every database query with OpenTelemetry"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: maintainer session (self-review; each finding reproduced before it was written down)
verdict: approve
---

# PR Review: feat(api): trace every database query with OpenTelemetry

## Summary

The API traced every request but none of its database queries. This PR instruments asyncpg, psycopg2 and
SQLAlchemy in `setup_telemetry`, so each query gets a client span under its request. It works end to end: after
importing `api.main` the way uvicorn does, a query through the API's own engine (`api.database`) gives `connect` and
`select` spans under the request span. The review found two problems in the PR's own tests, both fixed on the branch:
one test passed or failed by test order, and the wiring test only read source text. The personal-data scan mattered
here, because spans carry SQL text, and it's clean. The verdict is approve.

## Scope of Change

- Files changed: 4. `api/telemetry.py`, `requirements.txt` and `tests/test_telemetry_db.py`, plus this review.
- Areas touched: `api`, `tests`
- Commits:
  - 707e13d feat(api): trace every database query with OpenTelemetry
  - 946666a test(api): trace the API's own engine end to end; tests no longer depend on order

## CI Status

At 707e13d, Frontend Build, Documentation Build, Backend Tests and API Types were green, and PR conventions passed.
The Docker Build Test isn't required, but it installs the three new pins, so the merge waits for it. CI doesn't run
the root pytest suite, so the tests were run by hand (below).

## Scans (secrets, fabricated data, personal data, destructive data changes)

- **Secrets:** clean.
- **Fabricated data in a served path:** clean. No data or numbers are added.
- **Personal data:** clean, and this is the scan that mattered. Each span carries its query's SQL text
  (`db.statement`).
  - Every query builds its SQL from `$n` placeholders. Values travel as parameters, the typed address of an address
    search included (`api/routes/addresses.py`, `q`).
  - The f-string SQL in `addresses.py` and `locations.py` inserts only column lists and placeholder clauses.
  - No SQL in `api/` puts a value inside quotes.
  - Parameter capture is off in all three instrumentors: asyncpg's `capture_parameters` keeps its default, off, and
    the psycopg2 and SQLAlchemy instrumentors don't record parameters.
- **Destructive data changes:** none.

## Strengths

- One central place covers every route and every driver, without touching a route file.
- Tracing stays optional: a missing package or driver logs a warning and the API starts anyway. A test covers it.
- The SQLAlchemy version-range skip is narrow (that one instrumentor), and it's backed by a real query on the version
  pip resolves (2.1.8).
- The import order holds. `api.database` binds `create_engine` at import. It's first imported by the route imports at
  line 323 of `api/main.py`, after `setup_telemetry` at line 115, so its engine is traced. The new end-to-end test
  pins this.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important), both fixed in 946666a

1. **A test depended on test order.** `api/__init__.py` imports `api.main`, so the test module's
   `from api import telemetry` runs `setup_telemetry`. That instruments the drivers against the app's provider before
   any test runs. Run alone (`pytest -k sqlalchemy_query`), the SQLAlchemy span test found no span. It passed in the
   full file only because the first test's teardown had uninstrumented the drivers. Fixed: the fixture now
   uninstruments all three before each test as well as after. Each test passes alone, and all pass together.
2. **The wiring test only read source text.** `test_setup_telemetry_instruments_the_databases` checked that
   `setup_telemetry`'s source contains `instrument_databases(`. But import order matters here. The SQLAlchemy and
   psycopg2 instrumentors patch `create_engine` and `connect`, so a module that binds them earlier keeps the unpatched
   function. Its engine would go untraced, and no test would fail. Fixed: an end-to-end test in a fresh interpreter
   imports `api.main`, queries through `api.database.engine` inside a stand-in request span, and requires a query span
   under it. Checked both ways: it passes now, and finds no query span when the instrumentation packages are made
   unimportable.

### 🔵 Nit (Minor)

1. `api/__init__.py` imports the whole app, so importing any `api.*` module starts the app's telemetry. That's what
   caused finding 1. It's existing behavior and out of scope here, so it's filed as #261.

## Compliance

| Rule | Status |
|---|---|
| Issue first | ✅ #258 has all four parts; branch `feat/258-api-db-tracing`; `Closes #258`. Follow-ups filed as #260 and #261 |
| Conventional Commits | ✅ both commits, with co-author trailers |
| No fabricated data | ✅ scan clean |
| New Python in `packages/` | ✅ n/a: the API's own module |
| dbt for transformations | ✅ n/a |
| Naming, keys, calendar years | ✅ n/a |
| Scope label, match evidence | ✅ n/a (no UI) |
| Docs | ✅ n/a: the code comments say why each choice was made |
| Telemetry and logging | ✅ this is the telemetry change; warnings go through `loguru` |
| Tests | ✅ 5 tests, written first. The end-to-end one fails without the instrumentation |
| Shared libraries | ✅ n/a: nothing in `packages/` changed |

## Verification

- `pytest tests/test_telemetry_db.py tests/test_api_states.py`: 12 passed. Each telemetry test also passed alone.
- `ruff check api/telemetry.py tests/test_telemetry_db.py`: all checks passed.
- Importing `api.main` logs `database queries traced via AsyncPGInstrumentor, Psycopg2Instrumentor,
  SQLAlchemyInstrumentor`.
- Not run: asyncpg and psycopg2 spans against a live Postgres (none is reachable here). The tests check that those two
  instrumentors are active instead.

## Not in this PR

- #260: frontend data loads. Only 6 of 48 pages trace them, and browser requests carry no trace context.
- #261: importing any `api` module loads the whole app.
