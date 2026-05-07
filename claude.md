# Open Navigator Project Rules (React, FastAPI, dbt)

## 🏗️ Three-Service Architecture
1. **Documentation** (Docusaurus) - Port 3000
2. **Main Application** (React + Vite) - Port 5173
3. **API Backend** (FastAPI) - Port 8000
- Launch command: `./start-all.sh`

## 📊 Data Pipeline Standards (CRITICAL)
- **Transformations**: ALWAYS use **dbt**. No Python for SQL logic or JSONB extraction.
- **Python**: Use only for ingestion (API calls, scraping), ML, or orchestration.
- **Naming**: 
    - `state_code` (2-letter) vs `state` (Full name). Include BOTH.
    - `website_url` is the primary web column name.
- **Scripts**: Data loading scripts in `scripts/datasources/` must start with `load_`.

## 🗄️ Database Access
- **Host**: localhost:5433 (ALREADY RUNNING - Do not suggest new Docker PG instances).
- **Databases**: `open_navigator` (Primary) and `openstates` (Source).
- **API Access**: Use the `public` schema in `open_navigator`. Avoid direct `bronze` access.
- **CAUTION**: Never delete or suggest deleting `data/cache/`.

## 📝 Documentation Rules (Docusaurus)
- **MANDATORY**: ALL docs go in `website/docs/` subdirectories.
- **Formatting**: kebab-case filenames, YAML frontmatter included, lowercase only.
- **Root**: No `.md` files in root except README, LICENSE, and CONTRIBUTING.

## 💻 Code Style
- **Python**: Type hints, PEP 8, `pathlib`.
- **React**: Functional components, TypeScript interfaces, Tailwind CSS.
- **dbt**: Use Medallion architecture (bronze -> staging -> intermediate -> marts).

## 📝 Git Commit Standards (MANDATORY)
- **ALWAYS** use [Conventional Commits](https://www.conventionalcommits.org/) for ALL commit messages.
- Format: `<type>(<scope>): <description>`
- Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `ci`, `build`, `revert`
- Examples:
  - `feat(api): add jurisdiction search endpoint`
  - `fix(bronze): handle missing state_code in census loader`
  - `chore(deps): upgrade loguru to 0.7.3`
  - `docs(website): add FastAPI deployment guide`

## 🪵 Logging Standards (MANDATORY)

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