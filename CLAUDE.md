# Monorepo Architecture & Rules — Open Navigator

## Tech Stack
- **Backend:** FastAPI (Python 3.11+)
- **Data:** dbt Core + SQL (PostgreSQL — local warehouse on `localhost:5433`)
- **Frontend:** React (Vite, TypeScript); Docusaurus for documentation
- **Tooling:** **uv** for Python dependency management & the workspace (NOT Poetry); Ruff for lint/format; Node.js for the frontend

## Repository Layout
- `api/`: FastAPI application — entry points `api/main.py` / `api/app.py`, route handlers in `api/routes/`, Pydantic models in `api/models.py`.
- `web_app/`: React + Vite + TypeScript app (port 5173).
- `web_docs/`: Docusaurus documentation site (port 3000).
- `dbt_project/`: dbt models, macros, and `schema.yml` files. Standalone uv project (its protobuf/pathspec pins conflict with the main resolution). Medallion: `bronze → staging → intermediate → marts`.
- `packages/`: internal shared Python libraries — the **uv workspace** (`packages/*`): `core`, `core-lib`, `datamodels`, `ingestion`, `scrapers`, `llm`, `agents`, `accessibility`. This is the destination for the `scripts/ → packages/` refactor.
- `scripts/`: **LEGACY** top-level scripts being ported into `packages/`. Do not add new code here — port instead (see Refactor Workflow).

> Note: `apps/` (FastAPI, web) and `services/` are planned for a later migration phase per `pyproject.toml`; today the API lives in `api/` and the web app in `web_app/`.

## Where New Code Goes — `scripts/` Is Being Retired (CRITICAL)
- **`scripts/` is frozen.** We are actively retiring the top-level `scripts/` tree into `packages/`. Treat it as legacy: read it, port from it, but **never add to it**.
- **All new Python features go in `packages/`** as a proper importable library module (under the relevant `packages/<lib>/src/<lib>/…`), with a real module path, not a loose top-level script.
- **New runnable entry points** belong in a package as a CLI module invoked with `python -m <lib>.<module>` (argparse `main()` + `if __name__ == "__main__"`), **not** as a new file in `scripts/`.
- **Do not even suggest** creating a new `scripts/` file or a "`scripts/`-style runner." If a one-off runner is needed, propose it as a package CLI module instead.
- When a task would naturally extend a `scripts/` file, port the needed piece into the appropriate package first, then build on the package version. Route such work to the `python-packages-specialist` sub-agent, which enforces this rule.

## Running Locally — Three Services
1. **Documentation** (Docusaurus) — port 3000
2. **Main Application** (React + Vite) — port 5173
3. **API Backend** (FastAPI) — port 8000
- Launch command: `./start-all.sh`

## Explicit Development Guidelines
- **CRITICAL:** Never refactor a shared Python library in `packages/` without running its tests first. A library change can ripple into both the API (`api/`) and the ingestion/dbt-adjacent loaders — run `pytest` for the touched package **and** its dependents before committing.
- **Do not read large raw or mock data files directly** (e.g. `analyze.log`, parquet dumps, `data/cache/` contents). Refer to schemas, the Pydantic models in `packages/datamodels`, or dbt `schema.yml` / TypeScript type definitions instead.
- **When refactoring dbt models, always verify downstream dependencies via the dbt DAG** (`dbt ls --select <model>+`, or the docs graph) before changing them.
- New Python belongs in `packages/` as a proper library — never extend `scripts/` in place.

## Refactor Workflow
- **Roadmap / Manager memory:** `web_docs/docs/development/cleanup-roadmap.md` — the living backlog + status for the `scripts/ → packages/` library refactor. Read it before starting cleanup work.
- **Specialist sub-agents** (in `.claude/agents/`): route scoped work to `python-packages-specialist` (Python libraries in `packages/`; enforces prefer-packages / never-add-to-`scripts/`), `data-dbt-specialist` (dbt/SQL), `api-specialist` (FastAPI), or `frontend-specialist` (React/Docusaurus). Cross-layer tasks get split across them.

## Data Pipeline Standards (CRITICAL)
- **Transformations:** ALWAYS use **dbt**. No Python for SQL logic or JSONB extraction.
- **Python:** Use only for ingestion (API calls, scraping), ML, or orchestration.
- **Naming:**
    - `state_code` (2-letter) vs `state` (full name). Include BOTH.
    - `website_url` is the primary web column name.
    - **Do NOT use dimensional `dim_`/`fact_` (dimension/fact) names** — do not recommend or apply star-schema dim/fact naming to models or tables. Name models by the entity they represent (e.g. `jurisdictions`, `event_*`).
- **Keys:** ALWAYS define an explicit primary key, and foreign keys for every relationship, on tables/models exposed in the `public` schema (declare via dbt constraints / `schema.yml` so they are enforced in Postgres).
- **Scripts:** Data loading scripts in `scripts/datasources/` must start with `load_`.

## No Fabricated Data (CRITICAL)
- **NEVER display fabricated, dummy, placeholder, mocked, or hard-coded "example" numbers or data to the user** — not in the UI, API responses, charts, docs, or summaries. Every figure shown must trace to a real value from the warehouse/source.
- This applies especially to **financial and civic figures** (budgets, dollar amounts, contributions, "Follow the money" / "Money Moves" lenses, vote counts, statistics). A made-up dollar amount is worse than showing nothing.
- **If real data is missing, empty, or not yet ingested, show an explicit empty/unavailable state** (e.g. "No data available", a disabled card, `null`/`—`) — do **not** invent stand-in numbers to fill the gap or make a demo "look complete."
- Do **not** seed components, fixtures-as-defaults, or fallback constants with realistic-looking numbers. Test fixtures stay in tests; never let them leak into a served code path.
- When unsure whether a value is real, **treat it as unavailable** and surface the gap rather than guessing.

## Database Access
- **Host:** `localhost:5433` (ALREADY RUNNING — do not suggest new Docker PG instances).
- **Databases:** `open_navigator` (primary) and `openstates` (source).
- **API Access:** Use the `public` schema in `open_navigator`. Avoid direct `bronze` access.
- **Keys:** Every table/model exposed in `public` MUST declare an explicit primary key and foreign keys for all relationships (enforced via dbt constraints / `schema.yml`).
- **CAUTION:** Never delete or suggest deleting `data/cache/`.

## Documentation Rules (Docusaurus)
- **MANDATORY:** ALL docs go in `web_docs/docs/` subdirectories.
- **Formatting:** kebab-case filenames, YAML frontmatter included, lowercase only.
- **Root:** No `.md` files in root except `README`, `LICENSE`, and `CONTRIBUTING`.

## Code Style
- **Python:** Type hints, PEP 8, `pathlib`.
- **React:** Functional components, TypeScript interfaces, Tailwind CSS.
- **dbt:** Use Medallion architecture (`bronze -> staging -> intermediate -> marts`).

## Git Commit Standards (MANDATORY)
- **ALWAYS** use [Conventional Commits](https://www.conventionalcommits.org/) for ALL commit messages.
- Format: `<type>(<scope>): <description>`
- Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `ci`, `build`, `revert`
- Examples:
  - `feat(api): add jurisdiction search endpoint`
  - `fix(bronze): handle missing state_code in census loader`
  - `chore(deps): upgrade loguru to 0.7.3`
  - `docs(web_docs): add FastAPI deployment guide`

## Branch & PR Workflow (MANDATORY)
- **NEVER push directly to `main`.** `main` is branch-protected on GitHub (`getcommunityone/open-navigator`): direct pushes are rejected. All changes land via pull request.
- **Every change goes through a PR.** Branch off the latest `main`, commit there, push the branch, and open a PR against `main`:
  ```bash
  git checkout main && git pull
  git checkout -b <type>/<short-topic>        # e.g. feat/money-flow-sankey
  # ... commit work (Conventional Commits) ...
  git push -u origin <type>/<short-topic>
  gh pr create --base main
  ```
- **A PR must be green before merge.** Required CI checks (Frontend Build, Documentation Build, Backend Tests, API Types) must pass; resolve all conversations. The Docker Build Test is **not** required (it self-skips when no Docker files change).
- **Do NOT merge your own work silently.** Prefer review. The solo maintainer may self-merge as admin (`gh pr merge <n> --squash --admin`) only because GitHub forbids self-approval; this is a stopgap, not the norm — once a second reviewer exists, require the approval.
- **Never rewrite or force-push shared history** (`main`, or any branch with an open PR). A parallel session may be committing alongside you: stage only your own files, and verify your work landed via `git log` rather than amending.
- **Agents/automation** must follow the same flow — branch + PR, never a direct push to `main`.

## Git Commit Standards (MANDATORY)

### Simple Python Scripts & Packages → Loguru
Use `loguru` for all standalone scripts and simple Python packages:
```python
from loguru import logger

logger.info("Loading data from {}", source)
logger.success("Loaded {:,} rows", count)
logger.warning("Missing field: {}", field)
logger.error("Failed to connect: {}", err)
```
- Import only `from loguru import logger` — no manual handler setup needed for scripts.
- Use `logger.success()` to signal a completed step.
- For scripts that write log files, follow the pattern in `scripts/load_bronze.py` (sink to timestamped file + `scripts/utils/log_sync.py` for upload).

### FastAPI → OpenTelemetry
Use OpenTelemetry for all FastAPI services:
```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

FastAPIInstrumentor.instrument_app(app)
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("operation-name") as span:
    span.set_attribute("key", value)
```
- Instrument at app startup via `FastAPIInstrumentor`.
- Use spans for discrete operations (DB queries, external calls, enrichment steps).
- Export to OTLP collector; fall back to console exporter in development.

### React → OpenTelemetry
Use OpenTelemetry for frontend observability:
```typescript
import { trace } from '@opentelemetry/api';

const tracer = trace.getTracer('open-navigator-frontend');
const span = tracer.startSpan('fetch-jurisdictions');
// ... operation ...
span.end();
```
- Initialize the Web SDK once in `src/instrumentation.ts`, imported at the app entry point.
- Use `@opentelemetry/sdk-trace-web` + `@opentelemetry/exporter-trace-otlp-http`.
- Instrument route changes and key user interactions (search, filter, data load).

## Calendar Years — Storage vs Serialization
The rule splits by layer; do not conflate them:
- **SQL storage (columns):** a bare calendar year is an **`integer`** (`smallint` is fine) — never `text`/`varchar`/`double precision`/`numeric`. Integer keeps range filters (`WHERE year >= 2020`) and numeric sort correct. **Bronze** may keep the source-native type for raw fidelity, but **cast to `integer` by the staging layer** so intermediate/marts/`public` are uniform.
- **Real dates:** when you have a full date, use a `date`/`timestamp` column — not a year column.
- **JSON / API / manifests (the wire):** serialize a bare year as a **string** (e.g. `"year": "2026"`), not a number — JSON numbers get locale-formatted (e.g. `2,024`) by UI clients. Convert at the JSON boundary: `str(y)` in Python, `::text` in SQL/`jsonb_build_object`. A real `DATE`/`TIMESTAMP` already serializes as an ISO string, so this exception does not apply to it.
- **`calendar_year_label()`** (`scripts/utils/calendar_year_util.py`) is the canonical Python helper for the wire/string form — it normalizes any value to a clean 4-digit string or `None`. Use it at serialization / serving-table boundaries, **not** to define an integer storage column. Bronze raw loaders that land source-native `VARCHAR(4)` years via this helper are fine (raw fidelity); staging still casts to `integer`.
- Internal paths may still use numeric years for folders; convert with `str(y)` at the JSON boundary.
- Migration: `python scripts/discovery/fix_scraped_meetings_manifest_years.py` (see `--dry-run`).
