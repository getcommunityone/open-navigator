---
sidebar_position: 48
title: Batch jobs data-centers cohort plan
description: Implementation plan for #676 — Data centers cohort on the YouTube pipeline dashboard.
---

# Batch jobs data-centers cohort Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators pick **Data centers** on `/admin/batch-jobs` and run Discover → Reports for site-belt ∪ mention jurisdictions only, with left→right cohort → state cascading.

**Architecture:** Add a shared cohort helper (membership + allowed states). Launch and jurisdiction listing take `COHORT` / `cohort` and filter to that set ∩ `STATES`. The dashboard status path accepts optional `cohort` so stage numbers match what Run will process. Frontend extends the existing dropdown and constrains the state `<select>`.

**Tech Stack:** FastAPI (`api/routes/batch_jobs.py`), `api/batch_jobs/*`, bash wrapper `youtube_run_priority_states_last_n.sh`, React/Vite (`BatchJobStatusPage.tsx`, `batchJobs.ts`), pytest.

**Spec:** [batch-jobs-data-centers-cohort](./batch-jobs-data-centers-cohort.md) · Issue [#676](https://github.com/getcommunityone/open-navigator/issues/676)

## Global Constraints

- Data centers membership = `intermediate.int_data_center_site__jurisdiction` ∪ `public.data_center_meeting_mention` (distinct `jurisdiction_id`)
- Left → right: cohort limits state options; invalid state resets to “all in cohort”
- Never silently broaden to all jurisdictions on empty/missing DC set — return 400/500
- Calendar years on the wire stay strings; N/A for this feature
- Branch: `feat/676-batch-jobs-dc-cohort`; Conventional Commits; `Closes #676`
- Do not add new files under `scripts/` — helpers go in `api/batch_jobs/` or packages

## File map

| File | Responsibility |
|---|---|
| `api/batch_jobs/cohorts.py` (create) | Membership SQL, resolve states for a cohort, validate launch states |
| `api/batch_jobs/batch_job_status.py` | Optional `cohort` / jurisdiction-id filter on `fetch_batch_plan_jurisdictions` |
| `api/batch_jobs/batch_job_db.py` | Optional `cohort` on `pipeline_stage_report` / discover counts |
| `api/batch_jobs/batch_job_dashboard.py` | Pass `cohort` from status builders |
| `api/routes/batch_jobs.py` | `GET /cohorts`, `LaunchRequest.cohort`, env `COHORT`, status `?cohort=` |
| `packages/scrapers/scripts/youtube_run_priority_states_last_n.sh` | Read `COHORT`, pass into Python list helper |
| `packages/scrapers/src/scrapers/youtube/load_missing_county_channels.py` | Optional `--cohort data_centers` filter |
| `packages/scrapers/src/scrapers/youtube/backfill_transcripts.py` | Optional `--cohort data_centers` filter |
| `web_app/src/api/batchJobs.ts` | `fetchCohorts`, `cohort` on `launchPipeline` / status fetch |
| `web_app/src/pages/BatchJobStatusPage.tsx` | Cohort UI, cascade, labels, query param |
| `tests/test_batch_job_cohorts.py` (create) | Helper + route tests |
| `tests/test_batch_job_plan.py` | Extend plan listing for cohort |
| Spec already committed | `web_docs/docs/development/batch-jobs-data-centers-cohort.md` |

---

### Task 1: Cohort helper (membership + resolve states)

**Files:**
- Create: `api/batch_jobs/cohorts.py`
- Test: `tests/test_batch_job_cohorts.py`

**Interfaces:**
- Produces:
 - `PRIORITY_STATE_CODES: list[str]` — `["AL","GA","IN","MA","MT","WA","WI"]`
 - `CohortName = Literal["priority","data_centers","all"]`
 - `data_center_jurisdiction_ids(conn) -> set[str]`
 - `cohort_state_codes(cohort: CohortName, *, conn=None, all_states: list[str] | None = None) -> list[str]`
 - `resolve_launch_states(cohort: CohortName, states: list[str], *, conn=None) -> list[str]` — raises `ValueError` with message on bad cohort / bad state / empty intersect
 - SQL fragment constant or function for “jid in DC set” reused by plan + stage report

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_batch_job_cohorts.py
from api.batch_jobs.cohorts import (
 PRIORITY_STATE_CODES,
 cohort_state_codes,
 resolve_launch_states,
)

def test_priority_states_are_fixed():
 assert cohort_state_codes("priority") == PRIORITY_STATE_CODES

def test_resolve_launch_states_default_priority_all():
 assert resolve_launch_states("priority", []) == PRIORITY_STATE_CODES

def test_resolve_launch_states_rejects_state_outside_cohort():
 try:
 resolve_launch_states("priority", ["TX"])
 assert False, "expected ValueError"
 except ValueError as e:
 assert "TX" in str(e)

def test_resolve_launch_states_data_centers_intersects(monkeypatch):
 monkeypatch.setattr(
 "api.batch_jobs.cohorts.cohort_state_codes",
 lambda cohort, **kw: ["AL", "VA", "TX"] if cohort == "data_centers" else [],
 )
 assert resolve_launch_states("data_centers", ["AL"]) == ["AL"]
 try:
 resolve_launch_states("data_centers", ["HI"])
 assert False
 except ValueError:
 pass
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```bash
.venv/bin/pytest tests/test_batch_job_cohorts.py -v
```

Expected: `ModuleNotFoundError` or import error for `api.batch_jobs.cohorts`

- [ ] **Step 3: Implement `api/batch_jobs/cohorts.py`**

```python
"""Batch-job launch cohorts: priority states, data centers, or all US states."""
from __future__ import annotations

from typing import Any, Literal, Optional, Sequence

CohortName = Literal["priority", "data_centers", "all"]
PRIORITY_STATE_CODES = ["AL", "GA", "IN", "MA", "MT", "WA", "WI"]

_DC_JID_SQL = """
SELECT DISTINCT jurisdiction_id FROM (
 SELECT jurisdiction_id FROM intermediate.int_data_center_site__jurisdiction
 WHERE jurisdiction_id IS NOT NULL AND BTRIM(jurisdiction_id) <> ''
 UNION
 SELECT jurisdiction_id FROM public.data_center_meeting_mention
 WHERE jurisdiction_id IS NOT NULL AND BTRIM(jurisdiction_id) <> ''
) u
"""

def data_center_jurisdiction_ids(conn: Any) -> set[str]:
 with conn.cursor() as cur:
 cur.execute(_DC_JID_SQL)
 return {str(r[0]) for r in cur.fetchall() if r and r[0]}

def cohort_state_codes(
 cohort: CohortName,
 *,
 conn: Any = None,
 all_states: Optional[Sequence[str]] = None,
) -> list[str]:
 if cohort == "priority":
 return list(PRIORITY_STATE_CODES)
 if cohort == "all":
 return list(all_states or ALL_STATE_CODES) # 50+DC; comment-sync with usStates.ts
 if cohort == "data_centers":
 if conn is None:
 raise ValueError("data_centers cohort requires a database connection")
 jids = list(data_center_jurisdiction_ids(conn))
 with conn.cursor() as cur:
 cur.execute(
 """
 SELECT DISTINCT state_code FROM intermediate.int_jurisdictions
 WHERE jurisdiction_id = ANY(%s) AND state_code IS NOT NULL
 ORDER BY 1
 """,
 (jids,),
 )
 return [str(r[0]) for r in cur.fetchall()]
 raise ValueError(f"unknown cohort: {cohort}")

def resolve_launch_states(
 cohort: CohortName,
 states: Sequence[str],
 *,
 conn: Any = None,
) -> list[str]:
 allowed = cohort_state_codes(cohort, conn=conn)
 allowed_set = set(allowed)
 wanted = [s.strip().upper() for s in states if (s or "").strip()]
 if not wanted:
 if not allowed:
 raise ValueError(f"cohort {cohort!r} has no states")
 return list(allowed)
 bad = [s for s in wanted if s not in allowed_set]
 if bad:
 raise ValueError(f"state code(s) not in cohort {cohort!r}: {bad}")
 return wanted
```

Put `ALL_STATE_CODES` (50 + DC) in this module with a comment linking `web_app/src/lib/usStates.ts`.

- [ ] **Step 4: Run tests — expect PASS**

```bash
.venv/bin/pytest tests/test_batch_job_cohorts.py -v
```

- [ ] **Step 5: Commit**

```bash
git add api/batch_jobs/cohorts.py tests/test_batch_job_cohorts.py
git commit -m "feat(batch-jobs): add launch cohort helper for data centers (#676)"
```

---

### Task 2: `GET /api/batch-jobs/cohorts`

**Files:**
- Modify: `api/routes/batch_jobs.py`
- Test: `tests/test_batch_job_cohorts.py` (extend)

**Interfaces:**
- Consumes: `cohort_state_codes`, `PRIORITY_STATE_CODES`, `ALL_STATE_CODES`
- Produces: `GET /api/batch-jobs/cohorts` → `{ priority, data_centers, all }`

- [ ] **Step 1: Failing test (TestClient)**

```python
def test_cohorts_endpoint_shape(client, monkeypatch):
 monkeypatch.setattr(
 "api.routes.batch_jobs.cohort_state_codes",
 lambda cohort, **kw: {
 "priority": ["AL", "GA"],
 "data_centers": ["AL", "VA"],
 "all": ["AL", "AK", "DC"],
 }[cohort],
 )
 # Or patch the DB path used inside the route
 r = client.get("/api/batch-jobs/cohorts")
 assert r.status_code == 200
 body = r.json()
 assert set(body.keys()) == {"priority", "data_centers", "all"}
 assert "AL" in body["priority"] or body["priority"] == ["AL", "GA"]
```

Use the repo’s existing FastAPI test client fixture pattern from `tests/test_route_gating.py` / batch job tests. If the real DB is required for `data_centers`, monkeypatch `data_center_jurisdiction_ids` + jurisdiction state lookup.

- [ ] **Step 2: Run — expect FAIL (404)**

```bash
.venv/bin/pytest tests/test_batch_job_cohorts.py::test_cohorts_endpoint_shape -v
```

- [ ] **Step 3: Add route**

```python
class CohortsResponse(BaseModel):
 priority: List[str]
 data_centers: List[str]
 all: List[str]

@router.get("/cohorts", response_model=CohortsResponse)
async def list_cohorts() -> CohortsResponse:
 # open short-lived connection via existing batch DB helper
 ...
 return CohortsResponse(
 priority=cohort_state_codes("priority"),
 data_centers=cohort_state_codes("data_centers", conn=conn),
 all=cohort_state_codes("all"),
 )
```

On DB failure for `data_centers`, return **500** (do not return empty and pretend success with no states unless the warehouse truly has zero — then `data_centers: []` is honest).

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(api): GET /api/batch-jobs/cohorts (#676)"
```

---

### Task 3: Filter jurisdiction plan by cohort

**Files:**
- Modify: `api/batch_jobs/batch_job_status.py` (`fetch_batch_plan_jurisdictions`)
- Modify: `packages/scrapers/scripts/youtube_run_priority_states_last_n.sh` (`list_jurisdictions`)
- Test: `tests/test_batch_job_plan.py`

**Interfaces:**
- Consumes: `data_center_jurisdiction_ids`
- Produces: `fetch_batch_plan_jurisdictions(..., cohort: str | None = None)` — when `cohort=="data_centers"`, keep only rows whose `jurisdiction_id` is in the DC set (after the existing video/homepage filters)

- [ ] **Step 1: Failing test**

```python
def test_fetch_batch_plan_respects_data_centers_cohort(monkeypatch):
 # Build fake rows including a non-DC jid; after cohort filter only DC remain.
 ...
 runs = fetch_batch_plan_jurisdictions(["AL"], cohort="data_centers", database_url="postgresql://fake")
 assert all(r.jurisdiction_id in {"county_01001", "municipality_0107000"} for r in runs)
```

Mirror existing monkeypatch style in `tests/test_batch_job_plan.py` (patch `psycopg2.connect` or post-filter unit).

- [ ] **Step 2: Run — FAIL (unexpected kwarg or no filter)**

- [ ] **Step 3: Implement filter**

In `fetch_batch_plan_jurisdictions`, after fetching `rows` (or in SQL `AND j.jurisdiction_id = ANY(%s)` when cohort is data_centers):

```python
cohort_norm = (cohort or "").strip().lower() or None
dc_ids = None
if cohort_norm == "data_centers":
 dc_ids = data_center_jurisdiction_ids(conn) # same connection
 if not dc_ids:
 return [] # caller/launch treats empty as error at resolve time
# add to WHERE: AND (%s::text[] IS NULL OR j.jurisdiction_id = ANY(%s))
```

Update shell `list_jurisdictions`:

```bash
# pass COHORT into the embedded Python
os.environ.get("COHORT") or None
...
runs = fetch_batch_plan_jurisdictions(states, round_robin=..., cohort=os.environ.get("COHORT") or None, ...)
```

Document at top of the shell script: `COHORT=priority|data_centers|all` (default unset = today’s behavior = all jurisdictions in STATES).

- [ ] **Step 4: Run plan tests — PASS**

```bash
.venv/bin/pytest tests/test_batch_job_plan.py tests/test_batch_job_cohorts.py -v
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(batch-jobs): filter jurisdiction plan by data_centers cohort (#676)"
```

---

### Task 4: Launch API accepts `cohort` and sets env

**Files:**
- Modify: `api/routes/batch_jobs.py` (`LaunchRequest`, `launch_pipeline`)
- Modify: discover / backfill argv when `cohort == "data_centers"`
- Test: `tests/test_batch_job_cohorts.py` or launch-focused tests with monkeypatched `subprocess.Popen`

**Interfaces:**
- Consumes: `resolve_launch_states`
- Produces: `LaunchRequest.cohort: str = "priority"`; env `COHORT`; discover/backfill `--cohort`

- [ ] **Step 1: Failing tests**

```python
def test_launch_rejects_unknown_cohort(client, monkeypatch):
 monkeypatch.setenv("BATCH_JOBS_ALLOW_LAUNCH", "1")
 # admin auth as other launch tests do
 r = client.post("/api/batch-jobs/launch", json={"step": "analyze", "cohort": "nope", "states": ["AL"]})
 assert r.status_code == 400

def test_launch_sets_cohort_env(client, monkeypatch):
 monkeypatch.setenv("BATCH_JOBS_ALLOW_LAUNCH", "1")
 captured = {}
 def fake_popen(argv, **kwargs):
 captured["env"] = kwargs["env"]
 captured["argv"] = argv
 class P:
 pid = 4242
 return P()
 monkeypatch.setattr("subprocess.Popen", fake_popen)
 # also stub _pid_alive / launch file writes as needed
 r = client.post(
 "/api/batch-jobs/launch",
 json={"step": "analyze", "cohort": "data_centers", "states": ["AL"], "n": 5, "parallel": 2},
 )
 assert r.status_code == 200
 assert captured["env"]["COHORT"] == "data_centers"
 assert captured["env"]["STATES"] == "AL"
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
class LaunchRequest(BaseModel):
 step: str = "analyze"
 states: List[str] = Field(default_factory=list)
 n: int = 10
 parallel: int = 4
 cohort: str = "priority"

# in launch_pipeline:
cohort = (req.cohort or "priority").strip().lower()
if cohort not in ("priority", "data_centers", "all"):
 raise HTTPException(400, detail=f"cohort must be one of ...")
try:
 # open conn when cohort == data_centers (and always OK to open for resolve)
 states = resolve_launch_states(cohort, req.states or [], conn=conn)
except ValueError as e:
 raise HTTPException(400, detail=str(e)) from e
...
env["COHORT"] = cohort
env["STATES"] = ",".join(states)
# discover:
argv = [..., "--states", ",".join(states)]
if cohort == "data_centers":
 argv += ["--cohort", "data_centers"]
# backfill: same
```

Add `--cohort` to `load_missing_county_channels.py` and `backfill_transcripts.py`: when `data_centers`, restrict SQL to JIDs in the DC set (reuse helper or inline the same UNION). Prefer importing `data_center_jurisdiction_ids` from `api.batch_jobs.cohorts` if those scripts already import from `api`; otherwise duplicate the SQL string constant imported from a tiny shared place — **prefer one import from `api.batch_jobs.cohorts`** if the scrapers script PYTHONPATH already includes the repo root (the launch cwd is repo root).

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(api): honor cohort on batch-jobs launch (#676)"
```

---

### Task 5: Stage report / status honor `cohort`

**Files:**
- Modify: `api/batch_jobs/batch_job_db.py` (`pipeline_stage_report`)
- Modify: `api/batch_jobs/batch_job_dashboard.py` (pass cohort through)
- Modify: `api/routes/batch_jobs.py` (status + SSE query param `cohort`)
- Test: unit test on SQL filter or monkeypatched report

**Interfaces:**
- Consumes: `data_center_jurisdiction_ids`
- Produces: `pipeline_stage_report(conn, cohort: str | None = None)`; status endpoints accept `?cohort=`

- [ ] **Step 1: Failing test** — when `cohort="data_centers"`, mocked connection returns only rows for DC-linked jurisdictions; `states` list ⊆ DC states; ALL rollup totals ≤ unfiltered.

- [ ] **Step 2: Implement**

For youtube stages, add:

```sql
FROM bronze.bronze_event_youtube y
WHERE (%s::text[] IS NULL OR y.jurisdiction_id = ANY(%s))
GROUP BY 1
```

For discover scraped tables, join to `int_jurisdictions` on geoid/usps and require `jurisdiction_id = ANY(dc_ids)` when cohort is data_centers. If join is too heavy for a first cut, filter discover totals by `usps = ANY(dc_state_codes)` **only as an interim** — prefer JID filter so a priority-sized state doesn’t inflate DC discover progress. Spec requires cohort ∩ membership, not merely DC states.

Wire `GET` dashboard payload and SSE snapshot to read `cohort` query param (default omit = current behavior).

- [ ] **Step 3: Run tests — PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(batch-jobs): filter stage report by data_centers cohort (#676)"
```

---

### Task 6: Frontend cohort dropdown + cascade

**Files:**
- Modify: `web_app/src/api/batchJobs.ts`
- Modify: `web_app/src/pages/BatchJobStatusPage.tsx`
- Test: if the repo has component/API tests for batch jobs, extend; otherwise add a small pure helper test for “states for cohort” in `web_app` if a vitest pattern exists — otherwise manual verification steps below

**Interfaces:**
- Consumes: `GET /api/batch-jobs/cohorts`, launch + status with `cohort`
- Produces: UI `allScope: 'priority' | 'data_centers' | 'all'`; URL `?cohort=` + `?state=`

- [ ] **Step 1: API client**

```typescript
export type BatchCohort = 'priority' | 'data_centers' | 'all'

export type CohortsResponse = {
 priority: string[]
 data_centers: string[]
 all: string[]
}

export async function fetchCohorts(): Promise<CohortsResponse> { ... }

// launchPipeline body adds cohort?: BatchCohort
// status/SSE fetch appends cohort query when set
```

- [ ] **Step 2: Page behavior**

1. Persist cohort in `localStorage` key `batch-launch-scope` (reuse; values `priority` | `data_centers` | `all`).
2. Always show the select when launch enabled (not only when `scope === 'ALL'`).
3. Options: Priority states / Data centers / All states (50 + DC).
4. `stateOpts` for the right dropdown = `cohorts[allScope]` (from `fetchCohorts`), not raw `report.states` alone — intersect with report states if you still want “only states that have pipeline rows”, but **never show a state outside the cohort**. Spec: “options are only states valid for the selected cohort.” Prefer cohort list as source of truth; optional intersect with report for empty-progress hiding is OK if documented in a one-line comment.
5. On cohort change, if current `state` ∉ new list, `setScope('')`.
6. `launchScopeStates` = single state if selected, else full cohort state list from `fetchCohorts`.
7. Pass `cohort: allScope` into every `runLaunch` / `launchPipeline` call.
8. Pass `cohort` into status refetch / SSE so stage numbers match.
9. Labels: ` Run all · data centers` / ` Run all · data centers · AL`; scope chip matches.

- [ ] **Step 3: Manual check**

```bash
# with API + web running
# 1. Open /admin/batch-jobs
# 2. Select Data centers → state dropdown lists only DC states
# 3. Select Priority states → only AL,GA,IN,MA,MT,WA,WI
# 4. Switch Data centers while state=IN if IN not in DC list → resets to All
# 5. Run analyze with Data centers + AL → launch message / log shows COHORT=data_centers STATES=AL
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(web): data centers cohort on batch-jobs dashboard (#676)"
```

---

### Task 7: End-to-end verification + PR

- [ ] **Step 1: Run focused suites**

```bash
.venv/bin/pytest tests/test_batch_job_cohorts.py tests/test_batch_job_plan.py tests/test_route_gating.py -v
cd web_app && npm run build
```

- [ ] **Step 2: Confirm no silent national fallback** — unit already covers; optionally dry-run:

```bash
COHORT=data_centers STATES=AL N=1 DRY_RUN=1 \
 ./packages/scrapers/scripts/youtube_run_priority_states_last_n.sh catalog
```

Expect only DC jurisdictions in AL printed.

- [ ] **Step 3: Open PR**

```bash
git push -u origin HEAD
gh pr create --base main --title "feat(batch-jobs): Data centers cohort on YouTube pipeline dashboard" --body "$(cat <<'EOF'
| Attribute | Value |
|---|---|
| Epic | [DC · Data Center Accountability](https://github.com/getcommunityone/open-navigator/issues/236) |
| User story | [#676](https://github.com/getcommunityone/open-navigator/issues/676) |
| PI · Sprint | — |
| Points | — |

Closes #676

## Summary
- Adds **Data centers** cohort (site belt ∪ meeting mentions) to `/admin/batch-jobs`
- Left→right cascade: cohort limits state options; launch + stage progress honor cohort ∩ state
- Design: `web_docs/docs/development/batch-jobs-data-centers-cohort.md`

## Test plan
- [ ] `pytest` cohort + plan + gating tests
- [ ] UI: Data centers limits state list; Run sends `cohort`
- [ ] Dry-run catalog with `COHORT=data_centers` lists only DC jurisdictions
EOF
)"
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
|---|---|
| Data centers = site ∪ mention | Task 1 |
| Third option in same dropdown | Task 6 |
| Left→right state options limited | Task 6 (+ Task 2 for lists) |
| Invalid state resets | Task 6 |
| `GET /cohorts` | Task 2 |
| `POST /launch` + `cohort` + env | Task 4 |
| Plan listing filtered | Task 3 |
| Discover / backfill honor cohort | Task 4 |
| Stage progress filtered | Task 5 |
| 400 empty / bad state; 500 missing tables | Tasks 1, 2, 4 |
| Tests | Tasks 1–5 |
| Out of scope: company video_search | (none) |
