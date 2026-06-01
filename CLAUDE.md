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
- **Roadmap / Manager memory:** `docs/CLEANUP_ROADMAP.md` — the living backlog + status for the `scripts/ → packages/` library refactor. Read it before starting cleanup work.
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

## Logging Standards (MANDATORY)

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
- Internal paths may still use numeric years for folders; convert with `str(y)` at the JSON boundary.
- Migration: `python scripts/discovery/fix_scraped_meetings_manifest_years.py` (see `--dry-run`).
