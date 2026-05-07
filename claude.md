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