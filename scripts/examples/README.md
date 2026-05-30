# General Examples & Demos

This directory contains general demonstration scripts and case studies that showcase the Open Navigator platform's capabilities.

## Demo Scripts

### Complete Workflow Examples
- **example_workflow.py** - Demonstrates the complete policy analysis pipeline with all agents
- **integration_demo.py** - Integration demonstration across multiple components

> Note: `full_demo.py` (the keyword-alerts demo) was moved to `archive/examples/full_demo.py` alongside `archive/alerts/keyword_monitor.py`.

### Specific Feature Demos
- **legislative_map_demo.py** - Demonstrates legislative tracking and mapping features
- **process_multiple_formats.py** - Shows processing of various document formats

## Case Studies

### Tuscaloosa Accountability Reports
These demonstrate evidence-based accountability dashboards for policy advocacy:

- **tuscaloosa_accountability_report.py** - Generate accountability dashboards exposing gaps and delays
- **tuscaloosa_decision_analysis.py** - Analyze decision-making patterns
- **tuscaloosa_political_economy.py** - Political economy analysis

These are designed for policy advocacy, exposing trade-offs and power imbalances rather than academic research.

## Configuration

- **targets.json** - Legistar meeting targets for scraping demos (San Francisco, LA, NYC, etc.)

## Usage

Most demo scripts can be run directly:
```bash
python scripts/examples/example_workflow.py
python scripts/examples/tuscaloosa_accountability_report.py
```

Make sure you have:
1. Activated the virtual environment: `source .venv/bin/activate`
2. Set up required API keys and environment variables
3. Downloaded necessary data (see datasource-specific scripts in `scripts/datasources/`)

## Related

- **Data source integrations**: See `scripts/datasources/` for source-specific scripts
- **Deployment**: See `scripts/deployment/` for deployment scripts
- **Data processing**: See `scripts/data/` for ETL and pipeline scripts
