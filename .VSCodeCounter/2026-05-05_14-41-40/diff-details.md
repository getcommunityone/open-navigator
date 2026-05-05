# Diff Details

Date : 2026-05-05 14:41:40

Directory /home/developer/projects/open-navigator

Total : 710 files,  196703 codes, 24936 comments, 37109 blanks, all 258748 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [.dockerignore](/.dockerignore) | Ignore | 62 | 13 | 13 | 88 |
| [.github/copilot-instructions.md](/.github/copilot-instructions.md) | Markdown | 326 | 0 | 92 | 418 |
| [.github/workflows/ci-build-test.yml](/.github/workflows/ci-build-test.yml) | YAML | 119 | 6 | 26 | 151 |
| [.github/workflows/deploy-huggingface.yml](/.github/workflows/deploy-huggingface.yml) | YAML | 51 | 2 | 10 | 63 |
| [.huggingface/README.md](/.huggingface/README.md) | Markdown | 74 | 0 | 28 | 102 |
| [.huggingface/nginx.conf](/.huggingface/nginx.conf) | Properties | 97 | 17 | 21 | 135 |
| [.huggingface/start.sh](/.huggingface/start.sh) | Shell Script | 44 | 8 | 10 | 62 |
| [.huggingface/supervisord.conf](/.huggingface/supervisord.conf) | Properties | 26 | 0 | 3 | 29 |
| [CITATIONS.md](/CITATIONS.md) | Markdown | 1,750 | 0 | 350 | 2,100 |
| [CODE\_OF\_CONDUCT.md](/CODE_OF_CONDUCT.md) | Markdown | 28 | 0 | 20 | 48 |
| [CONTRIBUTING.md](/CONTRIBUTING.md) | Markdown | 72 | 0 | 28 | 100 |
| [Dockerfile](/Dockerfile) | Docker | 49 | 21 | 21 | 91 |
| [Makefile](/Makefile) | Makefile | 145 | 0 | 25 | 170 |
| [README.md](/README.md) | Markdown | 411 | 0 | 160 | 571 |
| [README\_HF.md](/README_HF.md) | Markdown | 74 | 0 | 28 | 102 |
| [SEARCH\_UPDATE\_SUMMARY.md](/SEARCH_UPDATE_SUMMARY.md) | Markdown | 213 | 0 | 64 | 277 |
| [\_\_init\_\_.py](/__init__.py) | Python | 17 | 1 | 4 | 22 |
| [agents/\_\_init\_\_.py](/agents/__init__.py) | Python | 14 | 1 | 2 | 17 |
| [agents/advocacy.py](/agents/advocacy.py) | Python | 298 | 58 | 53 | 409 |
| [agents/base.py](/agents/base.py) | Python | 100 | 47 | 25 | 172 |
| [agents/classifier.py](/agents/classifier.py) | Python | 189 | 67 | 40 | 296 |
| [agents/debate\_grader.py](/agents/debate_grader.py) | Python | 305 | 64 | 56 | 425 |
| [agents/mlflow\_base.py](/agents/mlflow_base.py) | Python | 162 | 108 | 38 | 308 |
| [agents/mlflow\_classifier.py](/agents/mlflow_classifier.py) | Python | 140 | 147 | 22 | 309 |
| [agents/orchestrator.py](/agents/orchestrator.py) | Python | 154 | 81 | 35 | 270 |
| [agents/parser.py](/agents/parser.py) | Python | 123 | 47 | 30 | 200 |
| [agents/policy\_reasoning\_analyzer.py](/agents/policy_reasoning_analyzer.py) | Python | 370 | 91 | 42 | 503 |
| [agents/scraper.py](/agents/scraper.py) | Python | 1,505 | 286 | 323 | 2,114 |
| [agents/scraper\_undetected.py](/agents/scraper_undetected.py) | Python | 173 | 46 | 43 | 262 |
| [agents/sentiment.py](/agents/sentiment.py) | Python | 248 | 73 | 61 | 382 |
| [agents/test\_policy\_analyzer.py](/agents/test_policy_analyzer.py) | Python | 72 | 14 | 27 | 113 |
| [alerts/keyword\_monitor.py](/alerts/keyword_monitor.py) | Python | 344 | 146 | 78 | 568 |
| [api/\_\_init\_\_.py](/api/__init__.py) | Python | 2 | 1 | 2 | 5 |
| [api/app.py](/api/app.py) | Python | 507 | 108 | 97 | 712 |
| [api/auth.py](/api/auth.py) | Python | 74 | 52 | 28 | 154 |
| [api/database.py](/api/database.py) | Python | 41 | 22 | 10 | 73 |
| [api/errors.py](/api/errors.py) | Python | 112 | 24 | 19 | 155 |
| [api/main.py](/api/main.py) | Python | 816 | 501 | 81 | 1,398 |
| [api/models.py](/api/models.py) | Python | 160 | 43 | 66 | 269 |
| [api/routes/\_\_init\_\_.py](/api/routes/__init__.py) | Python | 0 | 3 | 1 | 4 |
| [api/routes/auth.py](/api/routes/auth.py) | Python | 420 | 79 | 101 | 600 |
| [api/routes/bills.py](/api/routes/bills.py) | Python | 294 | 558 | 42 | 894 |
| [api/routes/bills\_neon.py](/api/routes/bills_neon.py) | Python | 425 | 678 | 40 | 1,143 |
| [api/routes/contact.py](/api/routes/contact.py) | Python | 41 | 65 | 13 | 119 |
| [api/routes/data\_deletion.py](/api/routes/data_deletion.py) | Python | 80 | 34 | 28 | 142 |
| [api/routes/hf\_search.py](/api/routes/hf_search.py) | Python | 90 | 67 | 26 | 183 |
| [api/routes/search.py](/api/routes/search.py) | Python | 868 | 671 | 176 | 1,715 |
| [api/routes/search\_postgres.py](/api/routes/search_postgres.py) | Python | 333 | 635 | 41 | 1,009 |
| [api/routes/social.py](/api/routes/social.py) | Python | 393 | 43 | 109 | 545 |
| [api/routes/stats.py](/api/routes/stats.py) | Python | 172 | 408 | 20 | 600 |
| [api/routes/stats\_neon.py](/api/routes/stats_neon.py) | Python | 267 | 65 | 44 | 376 |
| [api/routes/trending.py](/api/routes/trending.py) | Python | 157 | 42 | 43 | 242 |
| [api/static/assets/index-DDBrFhnz.js](/api/static/assets/index-DDBrFhnz.js) | JavaScript | 203 | 0 | 3 | 206 |
| [api/static/assets/index-DSYSwRuY.css](/api/static/assets/index-DSYSwRuY.css) | PostCSS | 1 | 0 | 1 | 2 |
| [api/static/communityone\_logo.svg](/api/static/communityone_logo.svg) | XML | 13 | 5 | 5 | 23 |
| [api/static/google6934fc6e3618949f.html](/api/static/google6934fc6e3618949f.html) | HTML | 1 | 0 | 0 | 1 |
| [api/static/index.html](/api/static/index.html) | HTML | 78 | 8 | 9 | 95 |
| [api/static/privacyfacebook.html](/api/static/privacyfacebook.html) | HTML | 244 | 0 | 33 | 277 |
| [api/static/sitemap-app.xml](/api/static/sitemap-app.xml) | XML | 89 | 5 | 19 | 113 |
| [api/static/sitemap.xml](/api/static/sitemap.xml) | XML | 11 | 2 | 4 | 17 |
| [app.yaml](/app.yaml) | YAML | 31 | 2 | 5 | 38 |
| [config/\_\_init\_\_.py](/config/__init__.py) | Python | 2 | 1 | 2 | 5 |
| [config/settings.py](/config/settings.py) | Python | 77 | 22 | 22 | 121 |
| [databricks/README.md](/databricks/README.md) | Markdown | 279 | 0 | 71 | 350 |
| [databricks/communityone\_schema.sql](/databricks/communityone_schema.sql) | MS SQL | 501 | 88 | 53 | 642 |
| [databricks/deployment.py](/databricks/deployment.py) | Python | 193 | 108 | 44 | 345 |
| [databricks/evaluation.py](/databricks/evaluation.py) | Python | 162 | 146 | 36 | 344 |
| [databricks/notebooks/01\_agent\_bricks\_quickstart.py](/databricks/notebooks/01_agent_bricks_quickstart.py) | Python | 52 | 262 | 16 | 330 |
| [dbt\_project/QUICK\_REFERENCE.md](/dbt_project/QUICK_REFERENCE.md) | Markdown | 230 | 0 | 77 | 307 |
| [dbt\_project/README.md](/dbt_project/README.md) | Markdown | 198 | 0 | 78 | 276 |
| [dbt\_project/README\_TRENDING\_CAUSES.md](/dbt_project/README_TRENDING_CAUSES.md) | Markdown | 160 | 0 | 53 | 213 |
| [dbt\_project/dbt\_project.yml](/dbt_project/dbt_project.yml) | YAML | 45 | 18 | 14 | 77 |
| [dbt\_project/macros/calculate\_confidence.sql](/dbt_project/macros/calculate_confidence.sql) | MS SQL | 11 | 8 | 1 | 20 |
| [dbt\_project/macros/normalize\_bill\_number.sql](/dbt_project/macros/normalize_bill_number.sql) | MS SQL | 14 | 11 | 1 | 26 |
| [dbt\_project/macros/normalize\_name.sql](/dbt_project/macros/normalize_name.sql) | MS SQL | 11 | 11 | 1 | 23 |
| [dbt\_project/models/intermediate/\_intermediate.yml](/dbt_project/models/intermediate/_intermediate.yml) | YAML | 58 | 0 | 3 | 61 |
| [dbt\_project/models/intermediate/int\_trending\_causes\_by\_jurisdiction.sql](/dbt_project/models/intermediate/int_trending_causes_by_jurisdiction.sql) | MS SQL | 83 | 17 | 14 | 114 |
| [dbt\_project/models/marts/\_marts.yml](/dbt_project/models/marts/_marts.yml) | YAML | 100 | 0 | 27 | 127 |
| [dbt\_project/models/marts/stats\_aggregates.sql](/dbt_project/models/marts/stats_aggregates.sql) | MS SQL | 117 | 23 | 20 | 160 |
| [dbt\_project/models/staging/\_staging.yml](/dbt_project/models/staging/_staging.yml) | YAML | 139 | 0 | 11 | 150 |
| [dbt\_project/models/staging/stg\_bronze\_decisions.sql](/dbt_project/models/staging/stg_bronze_decisions.sql) | MS SQL | 40 | 14 | 13 | 67 |
| [dbt\_project/package-lock.yml](/dbt_project/package-lock.yml) | YAML | 11 | 0 | 1 | 12 |
| [dbt\_project/packages.yml](/dbt_project/packages.yml) | YAML | 5 | 0 | 1 | 6 |
| [dbt\_project/setup.sh](/dbt_project/setup.sh) | Shell Script | 62 | 10 | 13 | 85 |
| [dbt\_project/tests/assert\_no\_ai\_overrides\_authoritative.sql](/dbt_project/tests/assert_no_ai_overrides_authoritative.sql) | MS SQL | 36 | 10 | 5 | 51 |
| [debug-dropdown.html](/debug-dropdown.html) | HTML | 80 | 0 | 13 | 93 |
| [docker-compose.yml](/docker-compose.yml) | YAML | 73 | 1 | 7 | 81 |
| [docs/ACCOUNTABILITY\_DASHBOARD\_STRATEGY.md](/docs/ACCOUNTABILITY_DASHBOARD_STRATEGY.md) | Markdown | 178 | 0 | 76 | 254 |
| [docs/ANSWER\_URL\_DATASETS.md](/docs/ANSWER_URL_DATASETS.md) | Markdown | 155 | 0 | 50 | 205 |
| [docs/API\_INTEGRATION\_STATUS.md](/docs/API_INTEGRATION_STATUS.md) | Markdown | 364 | 0 | 110 | 474 |
| [docs/BIGQUERY\_ENRICHMENT.md](/docs/BIGQUERY_ENRICHMENT.md) | Markdown | 141 | 0 | 51 | 192 |
| [docs/BULK\_VS\_API.md](/docs/BULK_VS_API.md) | Markdown | 252 | 0 | 91 | 343 |
| [docs/CENSUS\_DATA\_FIX.md](/docs/CENSUS_DATA_FIX.md) | Markdown | 69 | 0 | 32 | 101 |
| [docs/CHANGELOG\_DISCOVERY\_V2.md](/docs/CHANGELOG_DISCOVERY_V2.md) | Markdown | 112 | 0 | 38 | 150 |
| [docs/CIVIC\_TECH\_URL\_SOURCES.md](/docs/CIVIC_TECH_URL_SOURCES.md) | Markdown | 188 | 0 | 67 | 255 |
| [docs/CONTACTS\_MEETINGS\_SUMMARY.md](/docs/CONTACTS_MEETINGS_SUMMARY.md) | Markdown | 274 | 0 | 81 | 355 |
| [docs/CONTACTS\_MEETINGS\_WORKFLOW.md](/docs/CONTACTS_MEETINGS_WORKFLOW.md) | Markdown | 246 | 0 | 103 | 349 |
| [docs/COST\_BREAKDOWN.md](/docs/COST_BREAKDOWN.md) | Markdown | 176 | 0 | 61 | 237 |
| [docs/COST\_EFFECTIVE\_STORAGE.md](/docs/COST_EFFECTIVE_STORAGE.md) | Markdown | 389 | 0 | 159 | 548 |
| [docs/DATAVERSE\_INTEGRATION.md](/docs/DATAVERSE_INTEGRATION.md) | Markdown | 334 | 0 | 112 | 446 |
| [docs/DATAVERSE\_INTEGRATION\_SUMMARY.md](/docs/DATAVERSE_INTEGRATION_SUMMARY.md) | Markdown | 170 | 0 | 57 | 227 |
| [docs/DATA\_SOURCES.md](/docs/DATA_SOURCES.md) | Markdown | 179 | 0 | 61 | 240 |
| [docs/DEBATE\_GRADER\_GUIDE.md](/docs/DEBATE_GRADER_GUIDE.md) | Markdown | 241 | 0 | 67 | 308 |
| [docs/EBOARD\_AUTOMATED\_SOLUTIONS.md](/docs/EBOARD_AUTOMATED_SOLUTIONS.md) | Markdown | 304 | 0 | 98 | 402 |
| [docs/EBOARD\_COOKIE\_GUIDE.md](/docs/EBOARD_COOKIE_GUIDE.md) | Markdown | 184 | 0 | 63 | 247 |
| [docs/EBOARD\_MANUAL\_DOWNLOAD.md](/docs/EBOARD_MANUAL_DOWNLOAD.md) | Markdown | 95 | 0 | 31 | 126 |
| [docs/ENHANCEMENT\_OFFICIAL\_SOURCES.md](/docs/ENHANCEMENT_OFFICIAL_SOURCES.md) | Markdown | 175 | 0 | 79 | 254 |
| [docs/FAST\_ENRICHMENT\_STRATEGY.md](/docs/FAST_ENRICHMENT_STRATEGY.md) | Markdown | 247 | 0 | 77 | 324 |
| [docs/FRONTEND\_INTEGRATION\_GUIDE.md](/docs/FRONTEND_INTEGRATION_GUIDE.md) | Markdown | 332 | 0 | 113 | 445 |
| [docs/GSA\_DOMAIN\_INTEGRATION.md](/docs/GSA_DOMAIN_INTEGRATION.md) | Markdown | 262 | 0 | 65 | 327 |
| [docs/HANDLING\_MULTIPLE\_FORMATS.md](/docs/HANDLING_MULTIPLE_FORMATS.md) | Markdown | 508 | 0 | 152 | 660 |
| [docs/HUGGINGFACE\_DATASETS\_ANALYSIS.md](/docs/HUGGINGFACE_DATASETS_ANALYSIS.md) | Markdown | 278 | 0 | 91 | 369 |
| [docs/HUGGINGFACE\_FEATURE\_SUMMARY.md](/docs/HUGGINGFACE_FEATURE_SUMMARY.md) | Markdown | 186 | 0 | 76 | 262 |
| [docs/HUGGINGFACE\_FILE\_LIMITS.md](/docs/HUGGINGFACE_FILE_LIMITS.md) | Markdown | 338 | 0 | 111 | 449 |
| [docs/HUGGINGFACE\_PUBLISHING.md](/docs/HUGGINGFACE_PUBLISHING.md) | Markdown | 318 | 0 | 129 | 447 |
| [docs/HUGGINGFACE\_QUICK\_START.md](/docs/HUGGINGFACE_QUICK_START.md) | Markdown | 290 | 0 | 112 | 402 |
| [docs/IMPACT\_NAVIGATION\_GUIDE.md](/docs/IMPACT_NAVIGATION_GUIDE.md) | Markdown | 249 | 0 | 100 | 349 |
| [docs/INSTALLING\_DOCUMENT\_LIBRARIES.md](/docs/INSTALLING_DOCUMENT_LIBRARIES.md) | Markdown | 118 | 0 | 44 | 162 |
| [docs/INTEGRATION\_GUIDE.md](/docs/INTEGRATION_GUIDE.md) | Markdown | 450 | 0 | 107 | 557 |
| [docs/INTEGRATION\_STATUS.md](/docs/INTEGRATION_STATUS.md) | Markdown | 172 | 0 | 58 | 230 |
| [docs/JURISDICTION\_DISCOVERY.md](/docs/JURISDICTION_DISCOVERY.md) | Markdown | 450 | 0 | 131 | 581 |
| [docs/JURISDICTION\_DISCOVERY\_DEPLOYMENT.md](/docs/JURISDICTION_DISCOVERY_DEPLOYMENT.md) | Markdown | 150 | 0 | 60 | 210 |
| [docs/JURISDICTION\_DISCOVERY\_SETUP.md](/docs/JURISDICTION_DISCOVERY_SETUP.md) | Markdown | 408 | 0 | 151 | 559 |
| [docs/LOCALVIEW\_INTEGRATION\_GUIDE.md](/docs/LOCALVIEW_INTEGRATION_GUIDE.md) | Markdown | 177 | 0 | 76 | 253 |
| [docs/MIGRATION\_SUMMARY\_V2.md](/docs/MIGRATION_SUMMARY_V2.md) | Markdown | 193 | 0 | 77 | 270 |
| [docs/NEW\_CAPABILITIES.md](/docs/NEW_CAPABILITIES.md) | Markdown | 256 | 0 | 89 | 345 |
| [docs/OAUTH\_HUGGINGFACE\_FIX.md](/docs/OAUTH_HUGGINGFACE_FIX.md) | Markdown | 189 | 0 | 57 | 246 |
| [docs/POLITICAL\_ECONOMY\_ANALYSIS.md](/docs/POLITICAL_ECONOMY_ANALYSIS.md) | Markdown | 266 | 0 | 89 | 355 |
| [docs/RUNNING\_DISCOVERY\_AT\_SCALE.md](/docs/RUNNING_DISCOVERY_AT_SCALE.md) | Markdown | 410 | 0 | 126 | 536 |
| [docs/SCALE\_AND\_SEARCH\_PATTERNS.md](/docs/SCALE_AND_SEARCH_PATTERNS.md) | Markdown | 684 | 0 | 170 | 854 |
| [docs/SCRAPER\_IMPROVEMENTS.md](/docs/SCRAPER_IMPROVEMENTS.md) | Markdown | 234 | 0 | 71 | 305 |
| [docs/SOCIAL\_FEATURES.md](/docs/SOCIAL_FEATURES.md) | Markdown | 376 | 0 | 99 | 475 |
| [docs/SPLIT\_SCREEN\_SYSTEM.md](/docs/SPLIT_SCREEN_SYSTEM.md) | Markdown | 293 | 0 | 81 | 374 |
| [docs/TERMINAL\_CORRUPTION\_FIX.md](/docs/TERMINAL_CORRUPTION_FIX.md) | Markdown | 71 | 0 | 25 | 96 |
| [docs/UNIFIED\_NONPROFIT\_WORKFLOW.md](/docs/UNIFIED_NONPROFIT_WORKFLOW.md) | Markdown | 205 | 0 | 64 | 269 |
| [docs/URL\_DATASETS\_CONFIRMED.md](/docs/URL_DATASETS_CONFIRMED.md) | Markdown | 250 | 0 | 91 | 341 |
| [docs/URL\_DATASET\_INVESTIGATION.md](/docs/URL_DATASET_INVESTIGATION.md) | Markdown | 226 | 0 | 89 | 315 |
| [docs/VIDEO\_CHANNEL\_DISCOVERY.md](/docs/VIDEO_CHANNEL_DISCOVERY.md) | Markdown | 458 | 0 | 151 | 609 |
| [docs/VIDEO\_SOURCES\_COMPLETE.md](/docs/VIDEO_SOURCES_COMPLETE.md) | Markdown | 313 | 0 | 125 | 438 |
| [docs/VIDEO\_URL\_SOURCES.md](/docs/VIDEO_URL_SOURCES.md) | Markdown | 371 | 0 | 93 | 464 |
| [docs/YOUTUBE\_DISCOVERY\_IMPROVEMENTS.md](/docs/YOUTUBE_DISCOVERY_IMPROVEMENTS.md) | Markdown | 337 | 0 | 102 | 439 |
| [examples/README.md](/examples/README.md) | Markdown | 365 | 0 | 114 | 479 |
| [extraction/accountability\_dashboards.py](/extraction/accountability_dashboards.py) | Python | 391 | 137 | 87 | 615 |
| [extraction/budget\_analyzer.py](/extraction/budget_analyzer.py) | Python | 155 | 202 | 23 | 380 |
| [extraction/decision\_analyzer.py](/extraction/decision_analyzer.py) | Python | 408 | 110 | 45 | 563 |
| [extraction/summarizer.py](/extraction/summarizer.py) | Python | 187 | 216 | 49 | 452 |
| [extraction/temporal\_analyzer.py](/extraction/temporal_analyzer.py) | Python | 226 | 65 | 55 | 346 |
| [extraction/universal\_extractor.py](/extraction/universal_extractor.py) | Python | 248 | 65 | 71 | 384 |
| [frontend/.eslintrc.cjs](/frontend/.eslintrc.cjs) | JavaScript | 18 | 0 | 1 | 19 |
| [frontend/README.md](/frontend/README.md) | Markdown | 126 | 0 | 41 | 167 |
| [frontend/index.html](/frontend/index.html) | HTML | 77 | 8 | 9 | 94 |
| [frontend/package-lock.json](/frontend/package-lock.json) | JSON | 5,291 | 0 | 1 | 5,292 |
| [frontend/package.json](/frontend/package.json) | JSON | 46 | 0 | 1 | 47 |
| [frontend/policy-dashboards/README.md](/frontend/policy-dashboards/README.md) | Markdown | 174 | 0 | 78 | 252 |
| [frontend/policy-dashboards/package-lock.json](/frontend/policy-dashboards/package-lock.json) | JSON | 17,457 | 0 | 1 | 17,458 |
| [frontend/policy-dashboards/package.json](/frontend/policy-dashboards/package.json) | JSON | 36 | 0 | 1 | 37 |
| [frontend/policy-dashboards/public/communityone\_logo.svg](/frontend/policy-dashboards/public/communityone_logo.svg) | XML | 13 | 5 | 5 | 23 |
| [frontend/policy-dashboards/public/index.html](/frontend/policy-dashboards/public/index.html) | HTML | 17 | 0 | 1 | 18 |
| [frontend/policy-dashboards/src/App.jsx](/frontend/policy-dashboards/src/App.jsx) | JavaScript JSX | 1,277 | 30 | 49 | 1,356 |
| [frontend/policy-dashboards/src/components/EndlessStudyLoop.jsx](/frontend/policy-dashboards/src/components/EndlessStudyLoop.jsx) | JavaScript JSX | 139 | 13 | 11 | 163 |
| [frontend/policy-dashboards/src/components/HomePage.jsx](/frontend/policy-dashboards/src/components/HomePage.jsx) | JavaScript JSX | 274 | 8 | 10 | 292 |
| [frontend/policy-dashboards/src/components/ImpactDashboard.jsx](/frontend/policy-dashboards/src/components/ImpactDashboard.jsx) | JavaScript JSX | 243 | 20 | 18 | 281 |
| [frontend/policy-dashboards/src/components/NonprofitCard.jsx](/frontend/policy-dashboards/src/components/NonprofitCard.jsx) | JavaScript JSX | 273 | 9 | 9 | 291 |
| [frontend/policy-dashboards/src/components/SplitScreenView.jsx](/frontend/policy-dashboards/src/components/SplitScreenView.jsx) | JavaScript JSX | 347 | 12 | 17 | 376 |
| [frontend/policy-dashboards/src/components/Summary.jsx](/frontend/policy-dashboards/src/components/Summary.jsx) | JavaScript JSX | 168 | 9 | 7 | 184 |
| [frontend/policy-dashboards/src/components/TopicNavigation.jsx](/frontend/policy-dashboards/src/components/TopicNavigation.jsx) | JavaScript JSX | 488 | 11 | 13 | 512 |
| [frontend/policy-dashboards/src/components/WhereMoneyWent.jsx](/frontend/policy-dashboards/src/components/WhereMoneyWent.jsx) | JavaScript JSX | 146 | 9 | 8 | 163 |
| [frontend/policy-dashboards/src/components/WhoIsInCharge.jsx](/frontend/policy-dashboards/src/components/WhoIsInCharge.jsx) | JavaScript JSX | 141 | 11 | 11 | 163 |
| [frontend/policy-dashboards/src/components/WordsVsDollars.jsx](/frontend/policy-dashboards/src/components/WordsVsDollars.jsx) | JavaScript JSX | 134 | 10 | 8 | 152 |
| [frontend/policy-dashboards/src/components/shared/BarMeter.jsx](/frontend/policy-dashboards/src/components/shared/BarMeter.jsx) | JavaScript JSX | 28 | 4 | 3 | 35 |
| [frontend/policy-dashboards/src/components/shared/Compare.jsx](/frontend/policy-dashboards/src/components/shared/Compare.jsx) | JavaScript JSX | 51 | 4 | 4 | 59 |
| [frontend/policy-dashboards/src/components/shared/DashboardTile.jsx](/frontend/policy-dashboards/src/components/shared/DashboardTile.jsx) | JavaScript JSX | 148 | 14 | 10 | 172 |
| [frontend/policy-dashboards/src/components/shared/DecisionCard.jsx](/frontend/policy-dashboards/src/components/shared/DecisionCard.jsx) | JavaScript JSX | 236 | 8 | 10 | 254 |
| [frontend/policy-dashboards/src/components/shared/FilterPanel.jsx](/frontend/policy-dashboards/src/components/shared/FilterPanel.jsx) | JavaScript JSX | 225 | 6 | 10 | 241 |
| [frontend/policy-dashboards/src/components/shared/InsightBox.jsx](/frontend/policy-dashboards/src/components/shared/InsightBox.jsx) | JavaScript JSX | 30 | 4 | 4 | 38 |
| [frontend/policy-dashboards/src/components/shared/MetricCard.jsx](/frontend/policy-dashboards/src/components/shared/MetricCard.jsx) | JavaScript JSX | 30 | 4 | 3 | 37 |
| [frontend/policy-dashboards/src/index.css](/frontend/policy-dashboards/src/index.css) | PostCSS | 26 | 0 | 6 | 32 |
| [frontend/policy-dashboards/src/index.js](/frontend/policy-dashboards/src/index.js) | JavaScript | 10 | 0 | 2 | 12 |
| [frontend/postcss.config.js](/frontend/postcss.config.js) | JavaScript | 6 | 0 | 1 | 7 |
| [frontend/public/communityone\_logo.svg](/frontend/public/communityone_logo.svg) | XML | 13 | 5 | 5 | 23 |
| [frontend/public/google6934fc6e3618949f.html](/frontend/public/google6934fc6e3618949f.html) | HTML | 1 | 0 | 0 | 1 |
| [frontend/public/privacyfacebook.html](/frontend/public/privacyfacebook.html) | HTML | 244 | 0 | 33 | 277 |
| [frontend/public/sitemap-app.xml](/frontend/public/sitemap-app.xml) | XML | 89 | 5 | 19 | 113 |
| [frontend/public/sitemap.xml](/frontend/public/sitemap.xml) | XML | 11 | 2 | 4 | 17 |
| [frontend/src/App.tsx](/frontend/src/App.tsx) | TypeScript JSX | 65 | 4 | 6 | 75 |
| [frontend/src/components/AddressLookup.tsx](/frontend/src/components/AddressLookup.tsx) | TypeScript JSX | 583 | 30 | 59 | 672 |
| [frontend/src/components/FollowButton.tsx](/frontend/src/components/FollowButton.tsx) | TypeScript JSX | 147 | 4 | 10 | 161 |
| [frontend/src/components/JurisdictionDiscovery.tsx](/frontend/src/components/JurisdictionDiscovery.tsx) | TypeScript JSX | 239 | 13 | 17 | 269 |
| [frontend/src/components/Layout.tsx](/frontend/src/components/Layout.tsx) | TypeScript JSX | 503 | 16 | 21 | 540 |
| [frontend/src/components/MultiSelect.tsx](/frontend/src/components/MultiSelect.tsx) | TypeScript JSX | 128 | 2 | 8 | 138 |
| [frontend/src/components/RegistrationModal.tsx](/frontend/src/components/RegistrationModal.tsx) | TypeScript JSX | 192 | 7 | 18 | 217 |
| [frontend/src/components/ScrollToTop.tsx](/frontend/src/components/ScrollToTop.tsx) | TypeScript JSX | 9 | 4 | 4 | 17 |
| [frontend/src/components/SocialStats.tsx](/frontend/src/components/SocialStats.tsx) | TypeScript JSX | 106 | 2 | 14 | 122 |
| [frontend/src/components/USMap.tsx](/frontend/src/components/USMap.tsx) | TypeScript JSX | 461 | 46 | 60 | 567 |
| [frontend/src/contexts/AuthContext.tsx](/frontend/src/contexts/AuthContext.tsx) | TypeScript JSX | 122 | 9 | 19 | 150 |
| [frontend/src/contexts/LocationContext.tsx](/frontend/src/contexts/LocationContext.tsx) | TypeScript JSX | 73 | 7 | 16 | 96 |
| [frontend/src/index.css](/frontend/src/index.css) | PostCSS | 57 | 1 | 10 | 68 |
| [frontend/src/lib/api.ts](/frontend/src/lib/api.ts) | TypeScript | 123 | 16 | 26 | 165 |
| [frontend/src/main.tsx](/frontend/src/main.tsx) | TypeScript JSX | 37 | 0 | 3 | 40 |
| [frontend/src/pages/AdvocacyTopics.tsx](/frontend/src/pages/AdvocacyTopics.tsx) | TypeScript JSX | 217 | 5 | 8 | 230 |
| [frontend/src/pages/Analytics.tsx](/frontend/src/pages/Analytics.tsx) | TypeScript JSX | 204 | 32 | 14 | 250 |
| [frontend/src/pages/BillDetail.tsx](/frontend/src/pages/BillDetail.tsx) | TypeScript JSX | 248 | 7 | 15 | 270 |
| [frontend/src/pages/Dashboard.tsx](/frontend/src/pages/Dashboard.tsx) | TypeScript JSX | 183 | 6 | 13 | 202 |
| [frontend/src/pages/DebateGrader.tsx](/frontend/src/pages/DebateGrader.tsx) | TypeScript JSX | 245 | 8 | 22 | 275 |
| [frontend/src/pages/Developers.tsx](/frontend/src/pages/Developers.tsx) | TypeScript JSX | 182 | 8 | 11 | 201 |
| [frontend/src/pages/Documents.tsx](/frontend/src/pages/Documents.tsx) | TypeScript JSX | 216 | 5 | 13 | 234 |
| [frontend/src/pages/Events.tsx](/frontend/src/pages/Events.tsx) | TypeScript JSX | 105 | 6 | 6 | 117 |
| [frontend/src/pages/Explore.tsx](/frontend/src/pages/Explore.tsx) | TypeScript JSX | 435 | 32 | 36 | 503 |
| [frontend/src/pages/FactChecking.tsx](/frontend/src/pages/FactChecking.tsx) | TypeScript JSX | 252 | 6 | 11 | 269 |
| [frontend/src/pages/Hackathons.tsx](/frontend/src/pages/Hackathons.tsx) | TypeScript JSX | 199 | 9 | 11 | 219 |
| [frontend/src/pages/Heatmap.tsx](/frontend/src/pages/Heatmap.tsx) | TypeScript JSX | 158 | 4 | 13 | 175 |
| [frontend/src/pages/Home.tsx](/frontend/src/pages/Home.tsx) | TypeScript JSX | 2,207 | 108 | 132 | 2,447 |
| [frontend/src/pages/HomeModern.tsx](/frontend/src/pages/HomeModern.tsx) | TypeScript JSX | 1,336 | 67 | 81 | 1,484 |
| [frontend/src/pages/JurisdictionsSearch.tsx](/frontend/src/pages/JurisdictionsSearch.tsx) | TypeScript JSX | 684 | 33 | 51 | 768 |
| [frontend/src/pages/Nonprofits.tsx](/frontend/src/pages/Nonprofits.tsx) | TypeScript JSX | 286 | 6 | 24 | 316 |
| [frontend/src/pages/NonprofitsHF.tsx](/frontend/src/pages/NonprofitsHF.tsx) | TypeScript JSX | 354 | 26 | 29 | 409 |
| [frontend/src/pages/NotFound.tsx](/frontend/src/pages/NotFound.tsx) | TypeScript JSX | 103 | 4 | 10 | 117 |
| [frontend/src/pages/OpenSource.tsx](/frontend/src/pages/OpenSource.tsx) | TypeScript JSX | 238 | 5 | 12 | 255 |
| [frontend/src/pages/Opportunities.tsx](/frontend/src/pages/Opportunities.tsx) | TypeScript JSX | 145 | 6 | 14 | 165 |
| [frontend/src/pages/PeopleFinder.tsx](/frontend/src/pages/PeopleFinder.tsx) | TypeScript JSX | 400 | 21 | 36 | 457 |
| [frontend/src/pages/PolicyMap.tsx](/frontend/src/pages/PolicyMap.tsx) | TypeScript JSX | 1,061 | 64 | 74 | 1,199 |
| [frontend/src/pages/Profile.tsx](/frontend/src/pages/Profile.tsx) | TypeScript JSX | 381 | 9 | 20 | 410 |
| [frontend/src/pages/Services.tsx](/frontend/src/pages/Services.tsx) | TypeScript JSX | 136 | 10 | 10 | 156 |
| [frontend/src/pages/Settings.tsx](/frontend/src/pages/Settings.tsx) | TypeScript JSX | 279 | 15 | 23 | 317 |
| [frontend/src/pages/UnifiedSearch.tsx](/frontend/src/pages/UnifiedSearch.tsx) | TypeScript JSX | 1,439 | 76 | 100 | 1,615 |
| [frontend/src/utils/formatters.ts](/frontend/src/utils/formatters.ts) | TypeScript | 26 | 10 | 6 | 42 |
| [frontend/src/utils/huggingface.ts](/frontend/src/utils/huggingface.ts) | TypeScript | 161 | 107 | 35 | 303 |
| [frontend/src/utils/stateMapping.ts](/frontend/src/utils/stateMapping.ts) | TypeScript | 73 | 15 | 7 | 95 |
| [frontend/src/vite-env.d.ts](/frontend/src/vite-env.d.ts) | TypeScript | 6 | 2 | 3 | 11 |
| [frontend/tailwind.config.js](/frontend/tailwind.config.js) | JavaScript | 36 | 1 | 1 | 38 |
| [frontend/tsconfig.json](/frontend/tsconfig.json) | JSON with Comments | 21 | 2 | 3 | 26 |
| [frontend/tsconfig.node.json](/frontend/tsconfig.node.json) | JSON | 10 | 0 | 1 | 11 |
| [frontend/vite.config.ts](/frontend/vite.config.ts) | TypeScript | 33 | 2 | 2 | 37 |
| [main.py](/main.py) | Python | 307 | 44 | 95 | 446 |
| [models/meeting\_event.py](/models/meeting_event.py) | Python | 220 | 71 | 51 | 342 |
| [notebooks/Jurisdiction\_Discovery.py](/notebooks/Jurisdiction_Discovery.py) | Python | 76 | 168 | 64 | 308 |
| [notebooks/example\_analysis.py](/notebooks/example_analysis.py) | Python | 101 | 59 | 52 | 212 |
| [output/TUSCALOOSA\_ADVOCACY\_BRIEF.md](/output/TUSCALOOSA_ADVOCACY_BRIEF.md) | Markdown | 83 | 0 | 62 | 145 |
| [output/tuscaloosa/suiteonemedia\_20260503\_041932.json](/output/tuscaloosa/suiteonemedia_20260503_041932.json) | JSON | 404 | 0 | 0 | 404 |
| [output/tuscaloosa\_accountability\_dashboards.json](/output/tuscaloosa_accountability_dashboards.json) | JSON | 9 | 0 | 0 | 9 |
| [pipeline/\_\_init\_\_.py](/pipeline/__init__.py) | Python | 2 | 1 | 2 | 5 |
| [pipeline/create\_campaigns\_gold\_tables.py](/pipeline/create_campaigns_gold_tables.py) | Python | 359 | 133 | 91 | 583 |
| [pipeline/create\_contacts\_gold\_tables.py](/pipeline/create_contacts_gold_tables.py) | Python | 339 | 127 | 107 | 573 |
| [pipeline/create\_events\_gold\_tables.py](/pipeline/create_events_gold_tables.py) | Python | 219 | 66 | 77 | 362 |
| [pipeline/create\_grants\_gold\_tables.py](/pipeline/create_grants_gold_tables.py) | Python | 182 | 110 | 43 | 335 |
| [pipeline/create\_meetings\_gold\_tables.py](/pipeline/create_meetings_gold_tables.py) | Python | 219 | 66 | 77 | 362 |
| [pipeline/create\_nonprofits\_gold\_tables.py](/pipeline/create_nonprofits_gold_tables.py) | Python | 317 | 117 | 78 | 512 |
| [pipeline/delta\_lake.py](/pipeline/delta_lake.py) | Python | 274 | 75 | 7 | 356 |
| [pipeline/delta\_lake\_queries.py](/pipeline/delta_lake_queries.py) | Python | 84 | 122 | 2 | 208 |
| [pipeline/huggingface\_publisher.py](/pipeline/huggingface_publisher.py) | Python | 226 | 137 | 79 | 442 |
| [prompts/polcy\_analysis\_readable.md](/prompts/polcy_analysis_readable.md) | Markdown | 228 | 0 | 44 | 272 |
| [prompts/policy\_analysis.md](/prompts/policy_analysis.md) | Markdown | 532 | 0 | 49 | 581 |
| [prompts/policy\_analysis\_sample\_inputs.md](/prompts/policy_analysis_sample_inputs.md) | Markdown | 10 | 0 | 0 | 10 |
| [requirements.txt](/requirements.txt) | pip requirements | 72 | 21 | 15 | 108 |
| [scripts/README.md](/scripts/README.md) | Markdown | 118 | 0 | 28 | 146 |
| [scripts/\_\_init\_\_.py](/scripts/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/README.md](/scripts/datasources/README.md) | Markdown | 106 | 0 | 40 | 146 |
| [scripts/datasources/\_\_init\_\_.py](/scripts/datasources/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/ballotpedia/README.md](/scripts/datasources/ballotpedia/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/ballotpedia/ballotpedia\_integration.py](/scripts/datasources/ballotpedia/ballotpedia_integration.py) | Python | 361 | 215 | 104 | 680 |
| [scripts/datasources/census/README.md](/scripts/datasources/census/README.md) | Markdown | 109 | 0 | 44 | 153 |
| [scripts/datasources/census/\_\_init\_\_.py](/scripts/datasources/census/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/census/create\_zip\_county\_mapping.py](/scripts/datasources/census/create_zip_county_mapping.py) | Python | 186 | 52 | 68 | 306 |
| [scripts/datasources/census/download\_acs.sh](/scripts/datasources/census/download_acs.sh) | Shell Script | 9 | 6 | 4 | 19 |
| [scripts/datasources/census/fix\_geoid\_format.py](/scripts/datasources/census/fix_geoid_format.py) | Python | 38 | 53 | 7 | 98 |
| [scripts/datasources/census/link\_cities\_counties\_to\_search.py](/scripts/datasources/census/link_cities_counties_to_search.py) | Python | 114 | 203 | 12 | 329 |
| [scripts/datasources/census/load\_acs.py](/scripts/datasources/census/load_acs.py) | Python | 214 | 134 | 79 | 427 |
| [scripts/datasources/census/load\_acs\_data.py](/scripts/datasources/census/load_acs_data.py) | Python | 232 | 75 | 66 | 373 |
| [scripts/datasources/census/load\_census.py](/scripts/datasources/census/load_census.py) | Python | 217 | 110 | 61 | 388 |
| [scripts/datasources/census/load\_county\_mappings.py](/scripts/datasources/census/load_county_mappings.py) | Python | 147 | 64 | 50 | 261 |
| [scripts/datasources/census/load\_shapefiles.py](/scripts/datasources/census/load_shapefiles.py) | Python | 150 | 66 | 43 | 259 |
| [scripts/datasources/census/load\_states\_to\_search.py](/scripts/datasources/census/load_states_to_search.py) | Python | 122 | 16 | 19 | 157 |
| [scripts/datasources/cityscrapers/README.md](/scripts/datasources/cityscrapers/README.md) | Markdown | 169 | 0 | 61 | 230 |
| [scripts/datasources/cityscrapers/city\_scrapers\_urls.py](/scripts/datasources/cityscrapers/city_scrapers_urls.py) | Python | 170 | 85 | 59 | 314 |
| [scripts/datasources/dbpedia/README.md](/scripts/datasources/dbpedia/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/dbpedia/dbpedia\_integration.py](/scripts/datasources/dbpedia/dbpedia_integration.py) | Python | 226 | 167 | 24 | 417 |
| [scripts/datasources/fec/POLITICAL\_FINANCE\_QUICK\_START.md](/scripts/datasources/fec/POLITICAL_FINANCE_QUICK_START.md) | Markdown | 308 | 0 | 94 | 402 |
| [scripts/datasources/fec/POLITICAL\_INFLUENCE\_INTEGRATION.md](/scripts/datasources/fec/POLITICAL_INFLUENCE_INTEGRATION.md) | Markdown | 384 | 0 | 91 | 475 |
| [scripts/datasources/fec/README.md](/scripts/datasources/fec/README.md) | Markdown | 205 | 0 | 51 | 256 |
| [scripts/datasources/fec/demo\_fec\_integration.py](/scripts/datasources/fec/demo_fec_integration.py) | Python | 180 | 54 | 55 | 289 |
| [scripts/datasources/fec/demo\_political\_influence.py](/scripts/datasources/fec/demo_political_influence.py) | Python | 260 | 32 | 60 | 352 |
| [scripts/datasources/fec/fec\_integration.py](/scripts/datasources/fec/fec_integration.py) | Python | 300 | 164 | 77 | 541 |
| [scripts/datasources/fec/load\_fec\_bulk.py](/scripts/datasources/fec/load_fec_bulk.py) | Python | 302 | 141 | 70 | 513 |
| [scripts/datasources/fec/unzip\_fec\_data.py](/scripts/datasources/fec/unzip_fec_data.py) | Python | 403 | 172 | 97 | 672 |
| [scripts/datasources/gemini/MERGE\_STATUS.md](/scripts/datasources/gemini/MERGE_STATUS.md) | Markdown | 213 | 0 | 68 | 281 |
| [scripts/datasources/gemini/README.md](/scripts/datasources/gemini/README.md) | Markdown | 391 | 0 | 114 | 505 |
| [scripts/datasources/gemini/README\_BRONZE\_MERGE.md](/scripts/datasources/gemini/README_BRONZE_MERGE.md) | Markdown | 183 | 0 | 63 | 246 |
| [scripts/datasources/gemini/\_\_init\_\_.py](/scripts/datasources/gemini/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [scripts/datasources/gemini/analyze\_with\_multi\_models.py](/scripts/datasources/gemini/analyze_with_multi_models.py) | Python | 157 | 44 | 36 | 237 |
| [scripts/datasources/gemini/check\_models\_used.py](/scripts/datasources/gemini/check_models_used.py) | Python | 62 | 9 | 19 | 90 |
| [scripts/datasources/gemini/compare\_model\_extractions.py](/scripts/datasources/gemini/compare_model_extractions.py) | Python | 162 | 37 | 42 | 241 |
| [scripts/datasources/gemini/entity\_resolution.py](/scripts/datasources/gemini/entity_resolution.py) | Python | 228 | 122 | 93 | 443 |
| [scripts/datasources/gemini/load\_meeting\_transcripts.py](/scripts/datasources/gemini/load_meeting_transcripts.py) | Python | 501 | 188 | 49 | 738 |
| [scripts/datasources/gemini/load\_meeting\_transcripts\_bronze.py](/scripts/datasources/gemini/load_meeting_transcripts_bronze.py) | Python | 670 | 54 | 70 | 794 |
| [scripts/datasources/gemini/merge\_bronze\_to\_production.py](/scripts/datasources/gemini/merge_bronze_to_production.py) | Python | 612 | 96 | 114 | 822 |
| [scripts/datasources/gemini/migrations/README.md](/scripts/datasources/gemini/migrations/README.md) | Markdown | 65 | 0 | 28 | 93 |
| [scripts/datasources/gemini/migrations/backfill\_ntee\_from\_arguments.py](/scripts/datasources/gemini/migrations/backfill_ntee_from_arguments.py) | Python | 139 | 16 | 23 | 178 |
| [scripts/datasources/gemini/migrations/backfill\_ntee\_to\_topics.py](/scripts/datasources/gemini/migrations/backfill_ntee_to_topics.py) | Python | 108 | 15 | 20 | 143 |
| [scripts/datasources/gemini/migrations/cleanup\_null\_records.py](/scripts/datasources/gemini/migrations/cleanup_null_records.py) | Python | 88 | 20 | 35 | 143 |
| [scripts/datasources/gemini/migrations/infer\_ntee\_from\_topics.py](/scripts/datasources/gemini/migrations/infer_ntee_from_topics.py) | Python | 144 | 16 | 30 | 190 |
| [scripts/datasources/gemini/migrations/migrate\_add\_ntee\_to\_topics.py](/scripts/datasources/gemini/migrations/migrate_add_ntee_to_topics.py) | Python | 109 | 17 | 22 | 148 |
| [scripts/datasources/gemini/migrations/migrate\_add\_secondary\_ntee.py](/scripts/datasources/gemini/migrations/migrate_add_secondary_ntee.py) | Python | 102 | 8 | 20 | 130 |
| [scripts/datasources/gemini/migrations/migrate\_multimodel\_support.py](/scripts/datasources/gemini/migrations/migrate_multimodel_support.py) | Python | 154 | 158 | 31 | 343 |
| [scripts/datasources/gemini/migrations/repopulate\_ntee\_codes.py](/scripts/datasources/gemini/migrations/repopulate_ntee_codes.py) | Python | 293 | 40 | 53 | 386 |
| [scripts/datasources/gemini/moa\_synthesize.py](/scripts/datasources/gemini/moa_synthesize.py) | Python | 273 | 155 | 41 | 469 |
| [scripts/datasources/gemini/run\_bronze\_merge.sh](/scripts/datasources/gemini/run_bronze_merge.sh) | Shell Script | 153 | 5 | 32 | 190 |
| [scripts/datasources/google\_civic/README.md](/scripts/datasources/google_civic/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/google\_civic/google\_civic\_integration.py](/scripts/datasources/google_civic/google_civic_integration.py) | Python | 225 | 100 | 64 | 389 |
| [scripts/datasources/google\_data\_commons/google\_data\_commons.py](/scripts/datasources/google_data_commons/google_data_commons.py) | Python | 162 | 119 | 40 | 321 |
| [scripts/datasources/govwebsites/README.md](/scripts/datasources/govwebsites/README.md) | Markdown | 82 | 0 | 28 | 110 |
| [scripts/datasources/govwebsites/scrape\_gov\_websites.py](/scripts/datasources/govwebsites/scrape_gov_websites.py) | Python | 142 | 108 | 38 | 288 |
| [scripts/datasources/grants\_gov/GRANTS\_GOV\_VALUE.md](/scripts/datasources/grants_gov/GRANTS_GOV_VALUE.md) | Markdown | 181 | 0 | 48 | 229 |
| [scripts/datasources/grants\_gov/README.md](/scripts/datasources/grants_gov/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/grants\_gov/demo\_grants\_gov.py](/scripts/datasources/grants_gov/demo_grants_gov.py) | Python | 204 | 35 | 52 | 291 |
| [scripts/datasources/grants\_gov/grants\_gov\_integration.py](/scripts/datasources/grants_gov/grants_gov_integration.py) | Python | 218 | 115 | 61 | 394 |
| [scripts/datasources/gsa/gsa\_domains.py](/scripts/datasources/gsa/gsa_domains.py) | Python | 105 | 56 | 39 | 200 |
| [scripts/datasources/gsa/load\_gsa\_domains\_to\_postgres.py](/scripts/datasources/gsa/load_gsa_domains_to_postgres.py) | Python | 183 | 435 | 45 | 663 |
| [scripts/datasources/hifld/README.md](/scripts/datasources/hifld/README.md) | Markdown | 157 | 0 | 58 | 215 |
| [scripts/datasources/hifld/download\_and\_load\_hifld.sh](/scripts/datasources/hifld/download_and_load_hifld.sh) | Shell Script | 44 | 36 | 12 | 92 |
| [scripts/datasources/hifld/load\_arcgis\_hifld.py](/scripts/datasources/hifld/load_arcgis_hifld.py) | Python | 193 | 88 | 52 | 333 |
| [scripts/datasources/hifld/load\_hifld\_to\_postgres.py](/scripts/datasources/hifld/load_hifld_to_postgres.py) | Python | 261 | 81 | 64 | 406 |
| [scripts/datasources/irs/README.md](/scripts/datasources/irs/README.md) | Markdown | 39 | 0 | 17 | 56 |
| [scripts/datasources/irs/README\_IRS\_BMF.md](/scripts/datasources/irs/README_IRS_BMF.md) | Markdown | 62 | 0 | 22 | 84 |
| [scripts/datasources/irs/README\_NONPROFIT\_DISCOVERY.md](/scripts/datasources/irs/README_NONPROFIT_DISCOVERY.md) | Markdown | 338 | 0 | 102 | 440 |
| [scripts/datasources/irs/create\_nonprofit\_officer\_contacts.py](/scripts/datasources/irs/create_nonprofit_officer_contacts.py) | Python | 99 | 26 | 28 | 153 |
| [scripts/datasources/irs/load\_irs\_bmf.py](/scripts/datasources/irs/load_irs_bmf.py) | Python | 334 | 142 | 87 | 563 |
| [scripts/datasources/irs/manage\_nonprofits.py](/scripts/datasources/irs/manage_nonprofits.py) | Python | 189 | 46 | 69 | 304 |
| [scripts/datasources/irs/nonprofit\_discovery.py](/scripts/datasources/irs/nonprofit_discovery.py) | Python | 410 | 164 | 119 | 693 |
| [scripts/datasources/jurisdictions/export\_localview\_to\_parquet.py](/scripts/datasources/jurisdictions/export_localview_to_parquet.py) | Python | 61 | 21 | 23 | 105 |
| [scripts/datasources/jurisdictions/load\_counties\_to\_postgres.py](/scripts/datasources/jurisdictions/load_counties_to_postgres.py) | Python | 154 | 27 | 34 | 215 |
| [scripts/datasources/jurisdictions/load\_details\_to\_postgres.py](/scripts/datasources/jurisdictions/load_details_to_postgres.py) | Python | 221 | 24 | 37 | 282 |
| [scripts/datasources/jurisdictions/migrate\_parquet\_state\_naming.py](/scripts/datasources/jurisdictions/migrate_parquet_state_naming.py) | Python | 60 | 22 | 17 | 99 |
| [scripts/datasources/localview/README.md](/scripts/datasources/localview/README.md) | Markdown | 17 | 0 | 10 | 27 |
| [scripts/datasources/localview/dataverse\_client.py](/scripts/datasources/localview/dataverse_client.py) | Python | 345 | 189 | 91 | 625 |
| [scripts/datasources/localview/enrich\_from\_localview.py](/scripts/datasources/localview/enrich_from_localview.py) | Python | 233 | 48 | 67 | 348 |
| [scripts/datasources/localview/fuzzy\_jurisdiction\_matcher.py](/scripts/datasources/localview/fuzzy_jurisdiction_matcher.py) | Python | 183 | 128 | 55 | 366 |
| [scripts/datasources/localview/load\_localview.py](/scripts/datasources/localview/load_localview.py) | Python | 74 | 16 | 22 | 112 |
| [scripts/datasources/localview/load\_localview\_data.py](/scripts/datasources/localview/load_localview_data.py) | Python | 301 | 100 | 76 | 477 |
| [scripts/datasources/localview/load\_to\_postgres.py](/scripts/datasources/localview/load_to_postgres.py) | Python | 161 | 27 | 41 | 229 |
| [scripts/datasources/master\_data/README.md](/scripts/datasources/master_data/README.md) | Markdown | 310 | 0 | 79 | 389 |
| [scripts/datasources/master\_data/create\_jurisdiction\_master.py](/scripts/datasources/master_data/create_jurisdiction_master.py) | Python | 1,005 | 182 | 144 | 1,331 |
| [scripts/datasources/master\_data/query\_examples.sql](/scripts/datasources/master_data/query_examples.sql) | MS SQL | 281 | 72 | 52 | 405 |
| [scripts/datasources/meetingbank/README.md](/scripts/datasources/meetingbank/README.md) | Markdown | 13 | 0 | 8 | 21 |
| [scripts/datasources/meetingbank/load\_meetingbank.py](/scripts/datasources/meetingbank/load_meetingbank.py) | Python | 256 | 128 | 81 | 465 |
| [scripts/datasources/naco/README.md](/scripts/datasources/naco/README.md) | Markdown | 37 | 0 | 18 | 55 |
| [scripts/datasources/naco/scrape\_naco\_counties.py](/scripts/datasources/naco/scrape_naco_counties.py) | Python | 133 | 71 | 44 | 248 |
| [scripts/datasources/nccs/README.md](/scripts/datasources/nccs/README.md) | Markdown | 165 | 0 | 53 | 218 |
| [scripts/datasources/nccs/load\_nccs\_bulk.py](/scripts/datasources/nccs/load_nccs_bulk.py) | Python | 788 | 157 | 134 | 1,079 |
| [scripts/datasources/nces/README.md](/scripts/datasources/nces/README.md) | Markdown | 81 | 0 | 34 | 115 |
| [scripts/datasources/nces/README\_ENRICHMENT.md](/scripts/datasources/nces/README_ENRICHMENT.md) | Markdown | 160 | 0 | 46 | 206 |
| [scripts/datasources/nces/enrich\_jurisdictions\_from\_nces.py](/scripts/datasources/nces/enrich_jurisdictions_from_nces.py) | Python | 284 | 53 | 60 | 397 |
| [scripts/datasources/nces/fix\_and\_enrich\_school\_districts.py](/scripts/datasources/nces/fix_and_enrich_school_districts.py) | Python | 144 | 167 | 22 | 333 |
| [scripts/datasources/nces/load\_nces.py](/scripts/datasources/nces/load_nces.py) | Python | 292 | 144 | 61 | 497 |
| [scripts/datasources/nces/load\_nces\_to\_postgres.py](/scripts/datasources/nces/load_nces_to_postgres.py) | Python | 301 | 40 | 57 | 398 |
| [scripts/datasources/nces/migrate\_schools\_to\_orgloc.py](/scripts/datasources/nces/migrate_schools_to_orgloc.py) | Python | 123 | 18 | 28 | 169 |
| [scripts/datasources/nces/update\_jurisdictions\_from\_nces\_simple.py](/scripts/datasources/nces/update_jurisdictions_from_nces_simple.py) | Python | 92 | 163 | 12 | 267 |
| [scripts/datasources/ntee/README.md](/scripts/datasources/ntee/README.md) | Markdown | 163 | 0 | 49 | 212 |
| [scripts/datasources/ntee/\_\_init\_\_.py](/scripts/datasources/ntee/__init__.py) | Python | 0 | 10 | 1 | 11 |
| [scripts/datasources/ntee/load\_to\_postgres.py](/scripts/datasources/ntee/load_to_postgres.py) | Python | 183 | 49 | 57 | 289 |
| [scripts/datasources/openstates/README.md](/scripts/datasources/openstates/README.md) | Markdown | 83 | 0 | 29 | 112 |
| [scripts/datasources/openstates/aggregate\_bills\_from\_postgres.py](/scripts/datasources/openstates/aggregate_bills_from_postgres.py) | Python | 241 | 170 | 33 | 444 |
| [scripts/datasources/openstates/create\_openstates\_schema.py](/scripts/datasources/openstates/create_openstates_schema.py) | Python | 49 | 13 | 11 | 73 |
| [scripts/datasources/openstates/export\_committee\_reports.py](/scripts/datasources/openstates/export_committee_reports.py) | Python | 61 | 97 | 19 | 177 |
| [scripts/datasources/openstates/export\_legislators\_to\_gold.py](/scripts/datasources/openstates/export_legislators_to_gold.py) | Python | 142 | 36 | 28 | 206 |
| [scripts/datasources/openstates/export\_openstates\_to\_gold.py](/scripts/datasources/openstates/export_openstates_to_gold.py) | Python | 364 | 60 | 104 | 528 |
| [scripts/datasources/openstates/export\_testimony.py](/scripts/datasources/openstates/export_testimony.py) | Python | 63 | 89 | 19 | 171 |
| [scripts/datasources/openstates/legislative\_tracker.py](/scripts/datasources/openstates/legislative_tracker.py) | Python | 295 | 110 | 75 | 480 |
| [scripts/datasources/openstates/load\_openstates\_bulk.py](/scripts/datasources/openstates/load_openstates_bulk.py) | Python | 293 | 153 | 82 | 528 |
| [scripts/datasources/openstates/load\_openstates\_csv.sh](/scripts/datasources/openstates/load_openstates_csv.sh) | Shell Script | 76 | 9 | 15 | 100 |
| [scripts/datasources/openstates/load\_openstates\_documents.py](/scripts/datasources/openstates/load_openstates_documents.py) | Python | 470 | 198 | 108 | 776 |
| [scripts/datasources/openstates/load\_openstates\_people.py](/scripts/datasources/openstates/load_openstates_people.py) | Python | 205 | 73 | 47 | 325 |
| [scripts/datasources/openstates/openstates\_sources.py](/scripts/datasources/openstates/openstates_sources.py) | Python | 163 | 69 | 65 | 297 |
| [scripts/datasources/openstates/parallel\_download.sh](/scripts/datasources/openstates/parallel_download.sh) | Shell Script | 42 | 7 | 10 | 59 |
| [scripts/datasources/social\_media/social\_media\_discovery.py](/scripts/datasources/social_media/social_media_discovery.py) | Python | 238 | 137 | 59 | 434 |
| [scripts/datasources/usmayors/README.md](/scripts/datasources/usmayors/README.md) | Markdown | 69 | 0 | 30 | 99 |
| [scripts/datasources/usmayors/add\_mayor\_columns.sql](/scripts/datasources/usmayors/add_mayor_columns.sql) | MS SQL | 9 | 1 | 4 | 14 |
| [scripts/datasources/usmayors/scrape\_mayor\_elections.py](/scripts/datasources/usmayors/scrape_mayor_elections.py) | Python | 207 | 53 | 55 | 315 |
| [scripts/datasources/voter\_data/README.md](/scripts/datasources/voter_data/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/voter\_data/voter\_data\_integration.py](/scripts/datasources/voter_data/voter_data_integration.py) | Python | 169 | 143 | 50 | 362 |
| [scripts/datasources/wikidata/README.md](/scripts/datasources/wikidata/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/wikidata/cleanup\_bad\_counties.py](/scripts/datasources/wikidata/cleanup_bad_counties.py) | Python | 111 | 21 | 18 | 150 |
| [scripts/datasources/wikidata/fix\_fips\_codes.py](/scripts/datasources/wikidata/fix_fips_codes.py) | Python | 111 | 21 | 25 | 157 |
| [scripts/datasources/wikidata/generate\_mapping\_report.sql](/scripts/datasources/wikidata/generate_mapping_report.sql) | MS SQL | 108 | 13 | 10 | 131 |
| [scripts/datasources/wikidata/load\_jurisdictions\_wikidata.py](/scripts/datasources/wikidata/load_jurisdictions_wikidata.py) | Python | 518 | 192 | 44 | 754 |
| [scripts/datasources/wikidata/validate\_channels\_wikidata.py](/scripts/datasources/wikidata/validate_channels_wikidata.py) | Python | 193 | 35 | 50 | 278 |
| [scripts/datasources/wikidata/wikidata\_integration.py](/scripts/datasources/wikidata/wikidata_integration.py) | Python | 271 | 246 | 41 | 558 |
| [scripts/datasources/youtube/BYPASS\_IP\_BLOCK.md](/scripts/datasources/youtube/BYPASS_IP_BLOCK.md) | Markdown | 119 | 0 | 40 | 159 |
| [scripts/datasources/youtube/CHANNEL\_SANITY\_CHECK.md](/scripts/datasources/youtube/CHANNEL_SANITY_CHECK.md) | Markdown | 179 | 0 | 45 | 224 |
| [scripts/datasources/youtube/analyze\_channels.py](/scripts/datasources/youtube/analyze_channels.py) | Python | 73 | 125 | 18 | 216 |
| [scripts/datasources/youtube/backfill\_transcripts.py](/scripts/datasources/youtube/backfill_transcripts.py) | Python | 333 | 47 | 82 | 462 |
| [scripts/datasources/youtube/load\_channels.py](/scripts/datasources/youtube/load_channels.py) | Python | 498 | 195 | 48 | 741 |
| [scripts/datasources/youtube/load\_youtube\_events\_to\_postgres.py](/scripts/datasources/youtube/load_youtube_events_to_postgres.py) | Python | 1,056 | 169 | 198 | 1,423 |
| [scripts/datasources/youtube/youtube\_channel\_discovery.py](/scripts/datasources/youtube/youtube_channel_discovery.py) | Python | 305 | 119 | 84 | 508 |
| [scripts/dbt/README.md](/scripts/dbt/README.md) | Markdown | 165 | 0 | 58 | 223 |
| [scripts/dbt/export\_stats\_to\_open\_navigator.py](/scripts/dbt/export_stats_to_open_navigator.py) | Python | 108 | 21 | 29 | 158 |
| [scripts/deployment/README.md](/scripts/deployment/README.md) | Markdown | 61 | 0 | 22 | 83 |
| [scripts/deployment/deploy-databricks-app.sh](/scripts/deployment/deploy-databricks-app.sh) | Shell Script | 50 | 10 | 13 | 73 |
| [scripts/deployment/install.sh](/scripts/deployment/install.sh) | Shell Script | 96 | 11 | 14 | 121 |
| [scripts/deployment/neon/README.md](/scripts/deployment/neon/README.md) | Markdown | 252 | 0 | 65 | 317 |
| [scripts/deployment/neon/calculate\_stats\_only.py](/scripts/deployment/neon/calculate_stats_only.py) | Python | 131 | 21 | 40 | 192 |
| [scripts/deployment/neon/migrate.py](/scripts/deployment/neon/migrate.py) | Python | 889 | 108 | 180 | 1,177 |
| [scripts/deployment/neon/migrate\_bills.py](/scripts/deployment/neon/migrate_bills.py) | Python | 158 | 64 | 49 | 271 |
| [scripts/deployment/neon/migrations/001\_add\_datasource\_fields.sql](/scripts/deployment/neon/migrations/001_add_datasource_fields.sql) | MS SQL | 178 | 52 | 59 | 289 |
| [scripts/deployment/neon/migrations/001\_add\_datasource\_fields\_rollback.sql](/scripts/deployment/neon/migrations/001_add_datasource_fields_rollback.sql) | MS SQL | 38 | 13 | 9 | 60 |
| [scripts/deployment/neon/regenerate\_bills\_map.py](/scripts/deployment/neon/regenerate_bills_map.py) | Python | 73 | 13 | 18 | 104 |
| [scripts/deployment/neon/schema.sql](/scripts/deployment/neon/schema.sql) | MS SQL | 288 | 82 | 78 | 448 |
| [scripts/deployment/neon/schema\_bills.sql](/scripts/deployment/neon/schema_bills.sql) | MS SQL | 35 | 13 | 12 | 60 |
| [scripts/deployment/neon/update\_stats.py](/scripts/deployment/neon/update_stats.py) | Python | 141 | 24 | 41 | 206 |
| [scripts/deployment/setup-database.sh](/scripts/deployment/setup-database.sh) | Shell Script | 174 | 26 | 36 | 236 |
| [scripts/deployment/setup-git-hooks.sh](/scripts/deployment/setup-git-hooks.sh) | Shell Script | 24 | 5 | 6 | 35 |
| [scripts/deployment/setup-local-postgres.sh](/scripts/deployment/setup-local-postgres.sh) | Shell Script | 49 | 8 | 11 | 68 |
| [scripts/deployment/setup-local.sh](/scripts/deployment/setup-local.sh) | Shell Script | 32 | 5 | 8 | 45 |
| [scripts/deployment/setup\_openstates\_db.sh](/scripts/deployment/setup_openstates_db.sh) | Shell Script | 140 | 31 | 25 | 196 |
| [scripts/development/README.md](/scripts/development/README.md) | Markdown | 11 | 0 | 9 | 20 |
| [scripts/development/debug\_eboard.py](/scripts/development/debug_eboard.py) | Python | 89 | 15 | 30 | 134 |
| [scripts/development/export\_chrome\_cookies.py](/scripts/development/export_chrome_cookies.py) | Python | 58 | 15 | 16 | 89 |
| [scripts/discovery/README.md](/scripts/discovery/README.md) | Markdown | 113 | 0 | 40 | 153 |
| [scripts/discovery/\_\_init\_\_.py](/scripts/discovery/__init__.py) | Python | 0 | 11 | 1 | 12 |
| [scripts/discovery/batch\_processor.py](/scripts/discovery/batch_processor.py) | Python | 352 | 115 | 78 | 545 |
| [scripts/discovery/comprehensive\_discovery\_pipeline.py](/scripts/discovery/comprehensive_discovery_pipeline.py) | Python | 645 | 141 | 133 | 919 |
| [scripts/discovery/curated\_sources.py](/scripts/discovery/curated_sources.py) | Python | 173 | 163 | 68 | 404 |
| [scripts/discovery/discover\_oral\_health\_states.sh](/scripts/discovery/discover_oral_health_states.sh) | Shell Script | 35 | 6 | 13 | 54 |
| [scripts/discovery/discover\_top\_cities.sh](/scripts/discovery/discover_top_cities.sh) | Shell Script | 27 | 5 | 10 | 42 |
| [scripts/discovery/discovery\_pipeline.py](/scripts/discovery/discovery_pipeline.py) | Python | 192 | 93 | 58 | 343 |
| [scripts/discovery/external\_url\_datasets.py](/scripts/discovery/external_url_datasets.py) | Python | 362 | 74 | 64 | 500 |
| [scripts/discovery/platform\_detector.py](/scripts/discovery/platform_detector.py) | Python | 202 | 98 | 37 | 337 |
| [scripts/discovery/url\_discovery\_agent.py](/scripts/discovery/url_discovery_agent.py) | Python | 260 | 147 | 52 | 459 |
| [scripts/enrichment/README.md](/scripts/enrichment/README.md) | Markdown | 32 | 0 | 15 | 47 |
| [scripts/enrichment/auto\_enrich\_nonprofits.sh](/scripts/enrichment/auto_enrich_nonprofits.sh) | Shell Script | 17 | 4 | 5 | 26 |
| [scripts/enrichment/batch\_download\_990s.py](/scripts/enrichment/batch_download_990s.py) | Python | 116 | 27 | 32 | 175 |
| [scripts/enrichment/build\_990\_local\_index.py](/scripts/enrichment/build_990_local_index.py) | Python | 154 | 32 | 42 | 228 |
| [scripts/enrichment/cleanup\_nonprofit\_files.py](/scripts/enrichment/cleanup_nonprofit_files.py) | Python | 113 | 25 | 42 | 180 |
| [scripts/enrichment/discover\_tuscaloosa\_nonprofits.py](/scripts/enrichment/discover_tuscaloosa_nonprofits.py) | Python | 79 | 19 | 21 | 119 |
| [scripts/enrichment/download\_990\_zips.sh](/scripts/enrichment/download_990_zips.sh) | Shell Script | 95 | 10 | 20 | 125 |
| [scripts/enrichment/enrich\_alabama\_nonprofits.sh](/scripts/enrichment/enrich_alabama_nonprofits.sh) | Shell Script | 18 | 3 | 7 | 28 |
| [scripts/enrichment/enrich\_all\_states\_local.sh](/scripts/enrichment/enrich_all_states_local.sh) | Shell Script | 74 | 8 | 16 | 98 |
| [scripts/enrichment/enrich\_ma\_990\_fast.py](/scripts/enrichment/enrich_ma_990_fast.py) | Python | 62 | 107 | 17 | 186 |
| [scripts/enrichment/enrich\_nonprofits\_async.py](/scripts/enrichment/enrich_nonprofits_async.py) | Python | 249 | 72 | 49 | 370 |
| [scripts/enrichment/enrich\_nonprofits\_bigquery.py](/scripts/enrichment/enrich_nonprofits_bigquery.py) | Python | 169 | 407 | 20 | 596 |
| [scripts/enrichment/enrich\_nonprofits\_everyorg.py](/scripts/enrichment/enrich_nonprofits_everyorg.py) | Python | 231 | 71 | 55 | 357 |
| [scripts/enrichment/enrich\_nonprofits\_form990.py](/scripts/enrichment/enrich_nonprofits_form990.py) | Python | 290 | 93 | 74 | 457 |
| [scripts/enrichment/enrich\_nonprofits\_gt990.py](/scripts/enrichment/enrich_nonprofits_gt990.py) | Python | 473 | 177 | 118 | 768 |
| [scripts/enrichment/enrich\_nonprofits\_logodev.py](/scripts/enrichment/enrich_nonprofits_logodev.py) | Python | 239 | 112 | 60 | 411 |
| [scripts/enrichment/enrich\_nonprofits\_no\_auth.sh](/scripts/enrichment/enrich_nonprofits_no_auth.sh) | Shell Script | 77 | 13 | 13 | 103 |
| [scripts/enrichment/enrich\_nonprofits\_propublica.py](/scripts/enrichment/enrich_nonprofits_propublica.py) | Python | 237 | 93 | 58 | 388 |
| [scripts/enrichment/extract\_990\_dev\_states.sh](/scripts/enrichment/extract_990_dev_states.sh) | Shell Script | 101 | 24 | 27 | 152 |
| [scripts/enrichment/extract\_990\_zips.sh](/scripts/enrichment/extract_990_zips.sh) | Shell Script | 62 | 11 | 15 | 88 |
| [scripts/enrichment/regen\_simple.py](/scripts/enrichment/regen_simple.py) | Python | 12 | 6 | 5 | 23 |
| [scripts/enrichment/run\_tuscaloosa\_pipeline.sh](/scripts/enrichment/run_tuscaloosa_pipeline.sh) | Shell Script | 214 | 31 | 57 | 302 |
| [scripts/enrichment\_ai/README.md](/scripts/enrichment_ai/README.md) | Markdown | 152 | 0 | 57 | 209 |
| [scripts/enrichment\_ai/README\_BILL\_TEXT.md](/scripts/enrichment_ai/README_BILL_TEXT.md) | Markdown | 179 | 0 | 72 | 251 |
| [scripts/enrichment\_ai/batch\_analyze\_bills.py](/scripts/enrichment_ai/batch_analyze_bills.py) | Python | 118 | 79 | 25 | 222 |
| [scripts/enrichment\_ai/batch\_analyze\_bills\_api.py](/scripts/enrichment_ai/batch_analyze_bills_api.py) | Python | 132 | 202 | 25 | 359 |
| [scripts/enrichment\_ai/batch\_analyze\_bills\_groq.py](/scripts/enrichment_ai/batch_analyze_bills_groq.py) | Python | 192 | 279 | 27 | 498 |
| [scripts/enrichment\_ai/batch\_analyze\_bills\_ollama.py](/scripts/enrichment_ai/batch_analyze_bills_ollama.py) | Python | 114 | 164 | 13 | 291 |
| [scripts/enrichment\_ai/bill\_text\_sources.py](/scripts/enrichment_ai/bill_text_sources.py) | Python | 16 | 3 | 6 | 25 |
| [scripts/enrichment\_ai/demo\_ollama\_quick.py](/scripts/enrichment_ai/demo_ollama_quick.py) | Python | 78 | 8 | 10 | 96 |
| [scripts/enrichment\_ai/download\_alabama\_bills\_scraper.py](/scripts/enrichment_ai/download_alabama_bills_scraper.py) | Python | 326 | 76 | 75 | 477 |
| [scripts/enrichment\_ai/download\_bill\_text.py](/scripts/enrichment_ai/download_bill_text.py) | Python | 387 | 116 | 99 | 602 |
| [scripts/enrichment\_ai/duckdb\_vss\_demo.py](/scripts/enrichment_ai/duckdb_vss_demo.py) | Python | 190 | 36 | 40 | 266 |
| [scripts/enrichment\_ai/install\_xpu\_pytorch.sh](/scripts/enrichment_ai/install_xpu_pytorch.sh) | Shell Script | 50 | 5 | 11 | 66 |
| [scripts/enrichment\_ai/intel\_llm\_setup.sh](/scripts/enrichment_ai/intel_llm_setup.sh) | Shell Script | 56 | 13 | 16 | 85 |
| [scripts/enrichment\_ai/legislative\_analysis\_intel.py](/scripts/enrichment_ai/legislative_analysis_intel.py) | Python | 313 | 446 | 38 | 797 |
| [scripts/enrichment\_ai/query\_analysis\_results.py](/scripts/enrichment_ai/query_analysis_results.py) | Python | 59 | 99 | 11 | 169 |
| [scripts/enrichment\_ai/setup\_intel\_gpu.sh](/scripts/enrichment_ai/setup_intel_gpu.sh) | Shell Script | 79 | 11 | 16 | 106 |
| [scripts/examples/README.md](/scripts/examples/README.md) | Markdown | 33 | 0 | 16 | 49 |
| [scripts/examples/example\_workflow.py](/scripts/examples/example_workflow.py) | Python | 132 | 19 | 24 | 175 |
| [scripts/examples/full\_demo.py](/scripts/examples/full_demo.py) | Python | 319 | 27 | 57 | 403 |
| [scripts/examples/integration\_demo.py](/scripts/examples/integration_demo.py) | Python | 143 | 36 | 41 | 220 |
| [scripts/examples/legislative\_map\_demo.py](/scripts/examples/legislative_map_demo.py) | Python | 113 | 30 | 45 | 188 |
| [scripts/examples/process\_multiple\_formats.py](/scripts/examples/process_multiple_formats.py) | Python | 93 | 33 | 36 | 162 |
| [scripts/examples/targets.json](/scripts/examples/targets.json) | JSON | 32 | 0 | 1 | 33 |
| [scripts/examples/tuscaloosa\_accountability\_report.py](/scripts/examples/tuscaloosa_accountability_report.py) | Python | 491 | 168 | 117 | 776 |
| [scripts/examples/tuscaloosa\_decision\_analysis.py](/scripts/examples/tuscaloosa_decision_analysis.py) | Python | 162 | 29 | 46 | 237 |
| [scripts/examples/tuscaloosa\_political\_economy.py](/scripts/examples/tuscaloosa_political_economy.py) | Python | 282 | 78 | 107 | 467 |
| [scripts/huggingface/README.md](/scripts/huggingface/README.md) | Markdown | 101 | 0 | 39 | 140 |
| [scripts/huggingface/check-hf-vars.py](/scripts/huggingface/check-hf-vars.py) | Python | 40 | 9 | 9 | 58 |
| [scripts/huggingface/delete\_and\_publish\_all\_datasets.py](/scripts/huggingface/delete_and_publish_all_datasets.py) | Python | 147 | 42 | 48 | 237 |
| [scripts/huggingface/deploy-huggingface.sh](/scripts/huggingface/deploy-huggingface.sh) | Shell Script | 253 | 42 | 41 | 336 |
| [scripts/huggingface/deploy-space.py](/scripts/huggingface/deploy-space.py) | Python | 114 | 15 | 23 | 152 |
| [scripts/huggingface/deploy-via-api.sh](/scripts/huggingface/deploy-via-api.sh) | Shell Script | 93 | 12 | 18 | 123 |
| [scripts/huggingface/finalize\_huggingface\_structure.py](/scripts/huggingface/finalize_huggingface_structure.py) | Python | 171 | 17 | 20 | 208 |
| [scripts/huggingface/fix\_and\_publish\_failed.py](/scripts/huggingface/fix_and_publish_failed.py) | Python | 109 | 18 | 35 | 162 |
| [scripts/huggingface/force-hf-rebuild.sh](/scripts/huggingface/force-hf-rebuild.sh) | Shell Script | 17 | 3 | 6 | 26 |
| [scripts/huggingface/hf-dataset-cleanup.sh](/scripts/huggingface/hf-dataset-cleanup.sh) | Shell Script | 28 | 4 | 7 | 39 |
| [scripts/huggingface/publish\_gold\_datasets.py](/scripts/huggingface/publish_gold_datasets.py) | Python | 101 | 20 | 33 | 154 |
| [scripts/huggingface/reorganize\_for\_huggingface.py](/scripts/huggingface/reorganize_for_huggingface.py) | Python | 97 | 27 | 32 | 156 |
| [scripts/huggingface/retry\_failed\_datasets.py](/scripts/huggingface/retry_failed_datasets.py) | Python | 111 | 17 | 35 | 163 |
| [scripts/huggingface/safe-deploy.sh](/scripts/huggingface/safe-deploy.sh) | Shell Script | 96 | 10 | 13 | 119 |
| [scripts/huggingface/setup-huggingface.sh](/scripts/huggingface/setup-huggingface.sh) | Shell Script | 111 | 12 | 23 | 146 |
| [scripts/huggingface/test-huggingface-build.sh](/scripts/huggingface/test-huggingface-build.sh) | Shell Script | 147 | 24 | 32 | 203 |
| [scripts/huggingface/upload\_consolidated\_gold.py](/scripts/huggingface/upload_consolidated_gold.py) | Python | 168 | 57 | 48 | 273 |
| [scripts/huggingface/upload\_meetings\_to\_hf.py](/scripts/huggingface/upload_meetings_to_hf.py) | Python | 196 | 71 | 42 | 309 |
| [scripts/huggingface/upload\_nonprofits\_to\_hf.py](/scripts/huggingface/upload_nonprofits_to_hf.py) | Python | 185 | 126 | 61 | 372 |
| [scripts/huggingface/upload\_state\_splits\_to\_hf.py](/scripts/huggingface/upload_state_splits_to_hf.py) | Python | 183 | 73 | 44 | 300 |
| [scripts/huggingface/upload\_to\_huggingface.py](/scripts/huggingface/upload_to_huggingface.py) | Python | 294 | 185 | 80 | 559 |
| [scripts/huggingface/verify-hf-deployment.sh](/scripts/huggingface/verify-hf-deployment.sh) | Shell Script | 61 | 6 | 10 | 77 |
| [scripts/localview/README.md](/scripts/localview/README.md) | Markdown | 121 | 0 | 52 | 173 |
| [scripts/localview/check\_meeting\_data.py](/scripts/localview/check_meeting_data.py) | Python | 205 | 24 | 60 | 289 |
| [scripts/localview/extract\_transcripts.py](/scripts/localview/extract_transcripts.py) | Python | 144 | 47 | 45 | 236 |
| [scripts/localview/load\_priority\_states.sh](/scripts/localview/load_priority_states.sh) | Shell Script | 133 | 16 | 26 | 175 |
| [scripts/localview/scrape\_youtube\_channels.py](/scripts/localview/scrape_youtube_channels.py) | Python | 397 | 123 | 103 | 623 |
| [scripts/localview/update\_all.sh](/scripts/localview/update_all.sh) | Shell Script | 39 | 9 | 11 | 59 |
| [scripts/localview/update\_municipality\_list.py](/scripts/localview/update_municipality_list.py) | Python | 202 | 45 | 52 | 299 |
| [scripts/maintenance/README.md](/scripts/maintenance/README.md) | Markdown | 66 | 0 | 24 | 90 |
| [scripts/maintenance/cleanup\_disk\_space.sh](/scripts/maintenance/cleanup_disk_space.sh) | Shell Script | 83 | 12 | 18 | 113 |
| [scripts/maintenance/cleanup\_frontend\_junk.sh](/scripts/maintenance/cleanup_frontend_junk.sh) | Shell Script | 24 | 4 | 4 | 32 |
| [scripts/maintenance/cleanup\_non\_gold\_files.py](/scripts/maintenance/cleanup_non_gold_files.py) | Python | 147 | 51 | 35 | 233 |
| [scripts/maintenance/docker-cleanup.sh](/scripts/maintenance/docker-cleanup.sh) | Shell Script | 75 | 12 | 17 | 104 |
| [scripts/maintenance/migrate-docs.sh](/scripts/maintenance/migrate-docs.sh) | Shell Script | 46 | 8 | 9 | 63 |
| [scripts/maintenance/move\_secrets\_to\_home.sh](/scripts/maintenance/move_secrets_to_home.sh) | Shell Script | 35 | 7 | 12 | 54 |
| [scripts/maintenance/prevent\_terminal\_corruption.sh](/scripts/maintenance/prevent_terminal_corruption.sh) | Shell Script | 16 | 8 | 7 | 31 |
| [scripts/maintenance/test-app.py](/scripts/maintenance/test-app.py) | Python | 25 | 8 | 7 | 40 |
| [scripts/maintenance/test\_oauth\_flow.py](/scripts/maintenance/test_oauth_flow.py) | Python | 52 | 6 | 13 | 71 |
| [scripts/maintenance/update-repo-urls.sh](/scripts/maintenance/update-repo-urls.sh) | Shell Script | 36 | 5 | 7 | 48 |
| [scripts/mcp/README.md](/scripts/mcp/README.md) | Markdown | 150 | 0 | 59 | 209 |
| [scripts/mcp/open\_navigator\_server.py](/scripts/mcp/open_navigator_server.py) | Python | 420 | 55 | 56 | 531 |
| [scripts/media/README.md](/scripts/media/README.md) | Markdown | 136 | 0 | 41 | 177 |
| [scripts/media/generate\_all\_cause\_images.py](/scripts/media/generate_all_cause_images.py) | Python | 186 | 44 | 54 | 284 |
| [scripts/media/generate\_topic\_images.py](/scripts/media/generate_topic_images.py) | Python | 68 | 269 | 19 | 356 |
| [scripts/migrate\_all\_parquet\_state\_naming.py](/scripts/migrate_all_parquet_state_naming.py) | Python | 122 | 28 | 33 | 183 |
| [scripts/migrate\_all\_state\_naming.py](/scripts/migrate_all_state_naming.py) | Python | 97 | 88 | 7 | 192 |
| [scripts/migrations/README.md](/scripts/migrations/README.md) | Markdown | 164 | 0 | 50 | 214 |
| [scripts/migrations/migrate\_state\_naming.py](/scripts/migrations/migrate_state_naming.py) | Python | 269 | 38 | 31 | 338 |
| [setup.py](/setup.py) | Python | 96 | 2 | 3 | 101 |
| [start-all.sh](/start-all.sh) | Shell Script | 156 | 26 | 37 | 219 |
| [stop-all.sh](/stop-all.sh) | Shell Script | 41 | 6 | 13 | 60 |
| [tests/test\_agents.py](/tests/test_agents.py) | Python | 57 | 16 | 24 | 97 |
| [visualization/\_\_init\_\_.py](/visualization/__init__.py) | Python | 6 | 3 | 3 | 12 |
| [visualization/heatmap.py](/visualization/heatmap.py) | Python | 229 | 162 | 34 | 425 |
| [website/DOCUMENTATION\_MIGRATION.md](/website/DOCUMENTATION_MIGRATION.md) | Markdown | 167 | 0 | 37 | 204 |
| [website/README.md](/website/README.md) | Markdown | 49 | 0 | 25 | 74 |
| [website/blog/2026-04-06-data-model-expansion.md](/website/blog/2026-04-06-data-model-expansion.md) | Markdown | 58 | 0 | 26 | 84 |
| [website/blog/2026-04-13-citations-migration.md](/website/blog/2026-04-13-citations-migration.md) | Markdown | 93 | 0 | 32 | 125 |
| [website/blog/2026-04-20-homepage-navigation-fixes.md](/website/blog/2026-04-20-homepage-navigation-fixes.md) | Markdown | 123 | 0 | 40 | 163 |
| [website/blog/authors.yml](/website/blog/authors.yml) | YAML | 8 | 0 | 2 | 10 |
| [website/blog/tags.yml](/website/blog/tags.yml) | YAML | 28 | 0 | 8 | 36 |
| [website/docs/architecture.md](/website/docs/architecture.md) | Markdown | 164 | 0 | 44 | 208 |
| [website/docs/case-studies/tuscaloosa-complete.md](/website/docs/case-studies/tuscaloosa-complete.md) | Markdown | 269 | 0 | 86 | 355 |
| [website/docs/case-studies/tuscaloosa-discovery.md](/website/docs/case-studies/tuscaloosa-discovery.md) | Markdown | 335 | 0 | 113 | 448 |
| [website/docs/case-studies/tuscaloosa-pipeline.md](/website/docs/case-studies/tuscaloosa-pipeline.md) | Markdown | 870 | 0 | 268 | 1,138 |
| [website/docs/data-sources/\_civic-tech-sources.md](/website/docs/data-sources/_civic-tech-sources.md) | Markdown | 189 | 0 | 67 | 256 |
| [website/docs/data-sources/\_confirmed-datasets.md](/website/docs/data-sources/_confirmed-datasets.md) | Markdown | 250 | 0 | 91 | 341 |
| [website/docs/data-sources/ballot-election-sources.md](/website/docs/data-sources/ballot-election-sources.md) | Markdown | 304 | 0 | 73 | 377 |
| [website/docs/data-sources/census-acs.md](/website/docs/data-sources/census-acs.md) | Markdown | 320 | 0 | 131 | 451 |
| [website/docs/data-sources/census-data.md](/website/docs/data-sources/census-data.md) | Markdown | 72 | 0 | 33 | 105 |
| [website/docs/data-sources/census-shapefiles.md](/website/docs/data-sources/census-shapefiles.md) | Markdown | 270 | 0 | 99 | 369 |
| [website/docs/data-sources/charity-navigator.md](/website/docs/data-sources/charity-navigator.md) | Markdown | 297 | 0 | 102 | 399 |
| [website/docs/data-sources/citations.md](/website/docs/data-sources/citations.md) | Markdown | 1,996 | 0 | 478 | 2,474 |
| [website/docs/data-sources/data-model-erd.md](/website/docs/data-sources/data-model-erd.md) | Markdown | 3,236 | 0 | 403 | 3,639 |
| [website/docs/data-sources/factcheck-sources.md](/website/docs/data-sources/factcheck-sources.md) | Markdown | 522 | 0 | 127 | 649 |
| [website/docs/data-sources/form-990-xml.md](/website/docs/data-sources/form-990-xml.md) | Markdown | 606 | 0 | 180 | 786 |
| [website/docs/data-sources/huggingface-datasets.md](/website/docs/data-sources/huggingface-datasets.md) | Markdown | 281 | 0 | 92 | 373 |
| [website/docs/data-sources/irs-bulk-data.md](/website/docs/data-sources/irs-bulk-data.md) | Markdown | 318 | 0 | 115 | 433 |
| [website/docs/data-sources/jurisdiction-discovery.md](/website/docs/data-sources/jurisdiction-discovery.md) | Markdown | 453 | 0 | 132 | 585 |
| [website/docs/data-sources/meeting-data.md](/website/docs/data-sources/meeting-data.md) | Markdown | 194 | 0 | 63 | 257 |
| [website/docs/data-sources/nonprofit-sources.md](/website/docs/data-sources/nonprofit-sources.md) | Markdown | 251 | 0 | 92 | 343 |
| [website/docs/data-sources/open-source-repositories.md](/website/docs/data-sources/open-source-repositories.md) | Markdown | 284 | 0 | 91 | 375 |
| [website/docs/data-sources/overview.md](/website/docs/data-sources/overview.md) | Markdown | 215 | 0 | 74 | 289 |
| [website/docs/data-sources/polling-survey-sources.md](/website/docs/data-sources/polling-survey-sources.md) | Markdown | 411 | 0 | 117 | 528 |
| [website/docs/data-sources/url-datasets.md](/website/docs/data-sources/url-datasets.md) | Markdown | 158 | 0 | 51 | 209 |
| [website/docs/data-sources/video-channels.md](/website/docs/data-sources/video-channels.md) | Markdown | 461 | 0 | 152 | 613 |
| [website/docs/data-sources/video-sources.md](/website/docs/data-sources/video-sources.md) | Markdown | 316 | 0 | 126 | 442 |
| [website/docs/data-sources/youtube-discovery.md](/website/docs/data-sources/youtube-discovery.md) | Markdown | 340 | 0 | 103 | 443 |
| [website/docs/dbt/quick-reference.md](/website/docs/dbt/quick-reference.md) | Markdown | 233 | 0 | 78 | 311 |
| [website/docs/dbt/trending-causes.md](/website/docs/dbt/trending-causes.md) | Markdown | 163 | 0 | 54 | 217 |
| [website/docs/deployment/authentication-setup.md](/website/docs/deployment/authentication-setup.md) | Markdown | 326 | 0 | 124 | 450 |
| [website/docs/deployment/build-protection.md](/website/docs/deployment/build-protection.md) | Markdown | 246 | 0 | 88 | 334 |
| [website/docs/deployment/build-verification.md](/website/docs/deployment/build-verification.md) | Markdown | 173 | 0 | 60 | 233 |
| [website/docs/deployment/costs.md](/website/docs/deployment/costs.md) | Markdown | 179 | 0 | 62 | 241 |
| [website/docs/deployment/d-drive-configuration.md](/website/docs/deployment/d-drive-configuration.md) | Markdown | 355 | 0 | 149 | 504 |
| [website/docs/deployment/databricks-apps.md](/website/docs/deployment/databricks-apps.md) | Markdown | 298 | 0 | 104 | 402 |
| [website/docs/deployment/databricks-migration.md](/website/docs/deployment/databricks-migration.md) | Markdown | 224 | 0 | 53 | 277 |
| [website/docs/deployment/docker-troubleshooting.md](/website/docs/deployment/docker-troubleshooting.md) | Markdown | 279 | 0 | 103 | 382 |
| [website/docs/deployment/huggingface-spaces.md](/website/docs/deployment/huggingface-spaces.md) | Markdown | 272 | 0 | 100 | 372 |
| [website/docs/deployment/jurisdiction-discovery.md](/website/docs/deployment/jurisdiction-discovery.md) | Markdown | 153 | 0 | 61 | 214 |
| [website/docs/deployment/localview-scraper.md](/website/docs/deployment/localview-scraper.md) | Markdown | 177 | 0 | 64 | 241 |
| [website/docs/deployment/neon-deployment.md](/website/docs/deployment/neon-deployment.md) | Markdown | 149 | 0 | 56 | 205 |
| [website/docs/deployment/oauth-providers-setup.md](/website/docs/deployment/oauth-providers-setup.md) | Markdown | 342 | 0 | 143 | 485 |
| [website/docs/deployment/quickstart-databricks.md](/website/docs/deployment/quickstart-databricks.md) | Markdown | 159 | 0 | 54 | 213 |
| [website/docs/deployment/rename-repository.md](/website/docs/deployment/rename-repository.md) | Markdown | 219 | 0 | 89 | 308 |
| [website/docs/deployment/scale.md](/website/docs/deployment/scale.md) | Markdown | 413 | 0 | 127 | 540 |
| [website/docs/deployment/schema-migration.md](/website/docs/deployment/schema-migration.md) | Markdown | 323 | 0 | 51 | 374 |
| [website/docs/deployment/storage.md](/website/docs/deployment/storage.md) | Markdown | 392 | 0 | 160 | 552 |
| [website/docs/deployment/variable-migration.md](/website/docs/deployment/variable-migration.md) | Markdown | 121 | 0 | 56 | 177 |
| [website/docs/development/adding-data-sources.md](/website/docs/development/adding-data-sources.md) | Markdown | 326 | 0 | 121 | 447 |
| [website/docs/development/ai-model-evaluation.md](/website/docs/development/ai-model-evaluation.md) | Markdown | 277 | 0 | 81 | 358 |
| [website/docs/development/ai-model-merging.md](/website/docs/development/ai-model-merging.md) | Markdown | 396 | 0 | 124 | 520 |
| [website/docs/development/ai-policy-analysis.md](/website/docs/development/ai-policy-analysis.md) | Markdown | 413 | 0 | 124 | 537 |
| [website/docs/development/api-logging-errors.md](/website/docs/development/api-logging-errors.md) | Markdown | 225 | 0 | 67 | 292 |
| [website/docs/development/backlog.md](/website/docs/development/backlog.md) | Markdown | 374 | 0 | 143 | 517 |
| [website/docs/development/bronze-to-production-merge.md](/website/docs/development/bronze-to-production-merge.md) | Markdown | 328 | 0 | 83 | 411 |
| [website/docs/development/changelog.md](/website/docs/development/changelog.md) | Markdown | 112 | 0 | 38 | 150 |
| [website/docs/development/county-data-status.md](/website/docs/development/county-data-status.md) | Markdown | 124 | 0 | 46 | 170 |
| [website/docs/development/dashboard-redesign.md](/website/docs/development/dashboard-redesign.md) | Markdown | 87 | 0 | 22 | 109 |
| [website/docs/development/database-driven-homepage.md](/website/docs/development/database-driven-homepage.md) | Markdown | 370 | 0 | 112 | 482 |
| [website/docs/development/database-setup.md](/website/docs/development/database-setup.md) | Markdown | 243 | 0 | 77 | 320 |
| [website/docs/development/dbt-etl-strategy.md](/website/docs/development/dbt-etl-strategy.md) | Markdown | 445 | 0 | 90 | 535 |
| [website/docs/development/docs-migration.md](/website/docs/development/docs-migration.md) | Markdown | 73 | 0 | 23 | 96 |
| [website/docs/development/enhancements.md](/website/docs/development/enhancements.md) | Markdown | 175 | 0 | 79 | 254 |
| [website/docs/development/events-naming-migration.md](/website/docs/development/events-naming-migration.md) | Markdown | 115 | 0 | 33 | 148 |
| [website/docs/development/gold-consolidation.md](/website/docs/development/gold-consolidation.md) | Markdown | 158 | 0 | 41 | 199 |
| [website/docs/development/homepage-quick-start.md](/website/docs/development/homepage-quick-start.md) | Markdown | 78 | 0 | 27 | 105 |
| [website/docs/development/homepage-redesign-summary.md](/website/docs/development/homepage-redesign-summary.md) | Markdown | 263 | 0 | 69 | 332 |
| [website/docs/development/homepage-redesign.md](/website/docs/development/homepage-redesign.md) | Markdown | 317 | 0 | 91 | 408 |
| [website/docs/development/integration-status.md](/website/docs/development/integration-status.md) | Markdown | 172 | 0 | 58 | 230 |
| [website/docs/development/intel-arc-quickstart.md](/website/docs/development/intel-arc-quickstart.md) | Markdown | 169 | 0 | 50 | 219 |
| [website/docs/development/intel-optimization.md](/website/docs/development/intel-optimization.md) | Markdown | 131 | 0 | 43 | 174 |
| [website/docs/development/migration-v2.md](/website/docs/development/migration-v2.md) | Markdown | 193 | 0 | 77 | 270 |
| [website/docs/development/new-capabilities.md](/website/docs/development/new-capabilities.md) | Markdown | 256 | 0 | 89 | 345 |
| [website/docs/development/openstates-integration.md](/website/docs/development/openstates-integration.md) | Markdown | 246 | 0 | 94 | 340 |
| [website/docs/development/port-guide.md](/website/docs/development/port-guide.md) | Markdown | 125 | 0 | 41 | 166 |
| [website/docs/development/quickstart-database-causes.md](/website/docs/development/quickstart-database-causes.md) | Markdown | 209 | 0 | 75 | 284 |
| [website/docs/development/react-refactoring.md](/website/docs/development/react-refactoring.md) | Markdown | 433 | 0 | 118 | 551 |
| [website/docs/development/readme-migration.md](/website/docs/development/readme-migration.md) | Markdown | 131 | 0 | 40 | 171 |
| [website/docs/development/real-time-statistics.md](/website/docs/development/real-time-statistics.md) | Markdown | 457 | 0 | 128 | 585 |
| [website/docs/development/refactoring-summary.md](/website/docs/development/refactoring-summary.md) | Markdown | 377 | 0 | 113 | 490 |
| [website/docs/development/schema-migration-summary.md](/website/docs/development/schema-migration-summary.md) | Markdown | 239 | 0 | 60 | 299 |
| [website/docs/development/state-field-naming-standard.md](/website/docs/development/state-field-naming-standard.md) | Markdown | 212 | 0 | 62 | 274 |
| [website/docs/development/state-naming-migration.md](/website/docs/development/state-naming-migration.md) | Markdown | 177 | 0 | 49 | 226 |
| [website/docs/development/terminal-corruption-prevention.md](/website/docs/development/terminal-corruption-prevention.md) | Markdown | 76 | 0 | 26 | 102 |
| [website/docs/families/community-events.md](/website/docs/families/community-events.md) | Markdown | 289 | 0 | 82 | 371 |
| [website/docs/families/community-resources.md](/website/docs/families/community-resources.md) | Markdown | 120 | 0 | 31 | 151 |
| [website/docs/families/service-requests.md](/website/docs/families/service-requests.md) | Markdown | 380 | 0 | 91 | 471 |
| [website/docs/families/training-education.md](/website/docs/families/training-education.md) | Markdown | 383 | 0 | 105 | 488 |
| [website/docs/families/voter-registration.md](/website/docs/families/voter-registration.md) | Markdown | 380 | 0 | 111 | 491 |
| [website/docs/for-advocates.md](/website/docs/for-advocates.md) | Markdown | 153 | 0 | 70 | 223 |
| [website/docs/for-developers.md](/website/docs/for-developers.md) | Markdown | 330 | 0 | 112 | 442 |
| [website/docs/for-families.md](/website/docs/for-families.md) | Markdown | 317 | 0 | 97 | 414 |
| [website/docs/guides/accountability-strategy.md](/website/docs/guides/accountability-strategy.md) | Markdown | 181 | 0 | 77 | 258 |
| [website/docs/guides/api-troubleshooting.md](/website/docs/guides/api-troubleshooting.md) | Markdown | 154 | 0 | 62 | 216 |
| [website/docs/guides/contacts-contacts\_officials.md](/website/docs/guides/contacts-contacts_officials.md) | Markdown | 370 | 0 | 143 | 513 |
| [website/docs/guides/county-aggregation.md](/website/docs/guides/county-aggregation.md) | Markdown | 236 | 0 | 78 | 314 |
| [website/docs/guides/document-libraries.md](/website/docs/guides/document-libraries.md) | Markdown | 118 | 0 | 44 | 162 |
| [website/docs/guides/enterprise-tech-integration.md](/website/docs/guides/enterprise-tech-integration.md) | Markdown | 213 | 0 | 85 | 298 |
| [website/docs/guides/form-990-enrichment.md](/website/docs/guides/form-990-enrichment.md) | Markdown | 182 | 0 | 52 | 234 |
| [website/docs/guides/gold-table-pipeline.md](/website/docs/guides/gold-table-pipeline.md) | Markdown | 201 | 0 | 92 | 293 |
| [website/docs/guides/handling-formats.md](/website/docs/guides/handling-formats.md) | Markdown | 508 | 0 | 152 | 660 |
| [website/docs/guides/huggingface-datasets.md](/website/docs/guides/huggingface-datasets.md) | Markdown | 400 | 0 | 105 | 505 |
| [website/docs/guides/huggingface-features.md](/website/docs/guides/huggingface-features.md) | Markdown | 186 | 0 | 76 | 262 |
| [website/docs/guides/huggingface-integration.md](/website/docs/guides/huggingface-integration.md) | Markdown | 250 | 0 | 97 | 347 |
| [website/docs/guides/huggingface-limits.md](/website/docs/guides/huggingface-limits.md) | Markdown | 338 | 0 | 111 | 449 |
| [website/docs/guides/huggingface-publishing.md](/website/docs/guides/huggingface-publishing.md) | Markdown | 318 | 0 | 129 | 447 |
| [website/docs/guides/huggingface-quickstart.md](/website/docs/guides/huggingface-quickstart.md) | Markdown | 290 | 0 | 112 | 402 |
| [website/docs/guides/impact-navigation.md](/website/docs/guides/impact-navigation.md) | Markdown | 252 | 0 | 101 | 353 |
| [website/docs/guides/intel-arc-optimization.md](/website/docs/guides/intel-arc-optimization.md) | Markdown | 302 | 0 | 109 | 411 |
| [website/docs/guides/jurisdiction-setup.md](/website/docs/guides/jurisdiction-setup.md) | Markdown | 408 | 0 | 151 | 559 |
| [website/docs/guides/legislative-tracking-maps.md](/website/docs/guides/legislative-tracking-maps.md) | Markdown | 551 | 0 | 206 | 757 |
| [website/docs/guides/legislative-tracking.md](/website/docs/guides/legislative-tracking.md) | Markdown | 171 | 0 | 68 | 239 |
| [website/docs/guides/loading-meeting-data.md](/website/docs/guides/loading-meeting-data.md) | Markdown | 223 | 0 | 84 | 307 |
| [website/docs/guides/logo-enrichment.md](/website/docs/guides/logo-enrichment.md) | Markdown | 272 | 0 | 86 | 358 |
| [website/docs/guides/nonprofit-officers-contacts.md](/website/docs/guides/nonprofit-officers-contacts.md) | Markdown | 312 | 0 | 106 | 418 |
| [website/docs/guides/open-states-legislative-data.md](/website/docs/guides/open-states-legislative-data.md) | Markdown | 837 | 0 | 168 | 1,005 |
| [website/docs/guides/partitioned-datasets.md](/website/docs/guides/partitioned-datasets.md) | Markdown | 221 | 0 | 69 | 290 |
| [website/docs/guides/political-economy.md](/website/docs/guides/political-economy.md) | Markdown | 269 | 0 | 90 | 359 |
| [website/docs/guides/scraper-improvements.md](/website/docs/guides/scraper-improvements.md) | Markdown | 234 | 0 | 71 | 305 |
| [website/docs/guides/search-patterns.md](/website/docs/guides/search-patterns.md) | Markdown | 684 | 0 | 170 | 854 |
| [website/docs/guides/seo-optimization.md](/website/docs/guides/seo-optimization.md) | Markdown | 316 | 0 | 95 | 411 |
| [website/docs/guides/specialized-ai-models.md](/website/docs/guides/specialized-ai-models.md) | Markdown | 306 | 0 | 121 | 427 |
| [website/docs/guides/split-screen.md](/website/docs/guides/split-screen.md) | Markdown | 293 | 0 | 81 | 374 |
| [website/docs/guides/state-split-data.md](/website/docs/guides/state-split-data.md) | Markdown | 128 | 0 | 44 | 172 |
| [website/docs/guides/unified-search.md](/website/docs/guides/unified-search.md) | Markdown | 226 | 0 | 52 | 278 |
| [website/docs/integrations/dataverse-summary.md](/website/docs/integrations/dataverse-summary.md) | Markdown | 170 | 0 | 57 | 227 |
| [website/docs/integrations/dataverse.md](/website/docs/integrations/dataverse.md) | Markdown | 334 | 0 | 112 | 446 |
| [website/docs/integrations/eboard-automated.md](/website/docs/integrations/eboard-automated.md) | Markdown | 304 | 0 | 98 | 402 |
| [website/docs/integrations/eboard-cookies.md](/website/docs/integrations/eboard-cookies.md) | Markdown | 184 | 0 | 63 | 247 |
| [website/docs/integrations/eboard-manual.md](/website/docs/integrations/eboard-manual.md) | Markdown | 95 | 0 | 31 | 126 |
| [website/docs/integrations/fec-campaign-finance.md](/website/docs/integrations/fec-campaign-finance.md) | Markdown | 356 | 0 | 134 | 490 |
| [website/docs/integrations/fec-integration-summary.md](/website/docs/integrations/fec-integration-summary.md) | Markdown | 172 | 0 | 55 | 227 |
| [website/docs/integrations/fec-political-contributions.md](/website/docs/integrations/fec-political-contributions.md) | Markdown | 285 | 0 | 85 | 370 |
| [website/docs/integrations/frontend.md](/website/docs/integrations/frontend.md) | Markdown | 332 | 0 | 113 | 445 |
| [website/docs/integrations/grants-gov-api.md](/website/docs/integrations/grants-gov-api.md) | Markdown | 232 | 0 | 77 | 309 |
| [website/docs/integrations/localview.md](/website/docs/integrations/localview.md) | Markdown | 177 | 0 | 76 | 253 |
| [website/docs/integrations/mcp-server.md](/website/docs/integrations/mcp-server.md) | Markdown | 405 | 0 | 135 | 540 |
| [website/docs/integrations/overview.md](/website/docs/integrations/overview.md) | Markdown | 450 | 0 | 107 | 557 |
| [website/docs/intro.md](/website/docs/intro.md) | Markdown | 199 | 0 | 65 | 264 |
| [website/docs/legal-compliance.md](/website/docs/legal-compliance.md) | Markdown | 491 | 0 | 171 | 662 |
| [website/docs/legal/\_README.md](/website/docs/legal/_README.md) | Markdown | 103 | 0 | 35 | 138 |
| [website/docs/legal/data-deletion.md](/website/docs/legal/data-deletion.md) | Markdown | 148 | 0 | 68 | 216 |
| [website/docs/legal/data-provider-terms.md](/website/docs/legal/data-provider-terms.md) | Markdown | 840 | 0 | 267 | 1,107 |
| [website/docs/legal/index.md](/website/docs/legal/index.md) | Markdown | 308 | 0 | 113 | 421 |
| [website/docs/legal/legal-documentation-complete.md](/website/docs/legal/legal-documentation-complete.md) | Markdown | 198 | 2 | 53 | 253 |
| [website/docs/legal/legal-documentation-summary.md](/website/docs/legal/legal-documentation-summary.md) | Markdown | 176 | 0 | 47 | 223 |
| [website/docs/legal/privacy-policy.md](/website/docs/legal/privacy-policy.md) | Markdown | 317 | 0 | 130 | 447 |
| [website/docs/legal/terms-of-service.md](/website/docs/legal/terms-of-service.md) | Markdown | 258 | 0 | 108 | 366 |
| [website/docs/open-navigator.md](/website/docs/open-navigator.md) | Markdown | 98 | 0 | 40 | 138 |
| [website/docs/quick-reference.md](/website/docs/quick-reference.md) | Markdown | 93 | 0 | 29 | 122 |
| [website/docs/quickstart.md](/website/docs/quickstart.md) | Markdown | 144 | 0 | 64 | 208 |
| [website/docusaurus.config.ts](/website/docusaurus.config.ts) | TypeScript | 246 | 24 | 14 | 284 |
| [website/package-lock.json](/website/package-lock.json) | JSON | 20,802 | 0 | 1 | 20,803 |
| [website/package.json](/website/package.json) | JSON | 52 | 0 | 1 | 53 |
| [website/sidebars.ts](/website/sidebars.ts) | TypeScript | 432 | 22 | 9 | 463 |
| [website/src/components/HomepageFeatures/index.tsx](/website/src/components/HomepageFeatures/index.tsx) | TypeScript JSX | 67 | 0 | 5 | 72 |
| [website/src/components/HomepageFeatures/styles.module.css](/website/src/components/HomepageFeatures/styles.module.css) | PostCSS | 10 | 0 | 2 | 12 |
| [website/src/components/StructuredData.tsx](/website/src/components/StructuredData.tsx) | TypeScript JSX | 101 | 4 | 5 | 110 |
| [website/src/components/ZoomableMermaid/index.tsx](/website/src/components/ZoomableMermaid/index.tsx) | TypeScript JSX | 64 | 0 | 3 | 67 |
| [website/src/components/ZoomableMermaid/styles.module.css](/website/src/components/ZoomableMermaid/styles.module.css) | PostCSS | 147 | 3 | 24 | 174 |
| [website/src/css/custom.css](/website/src/css/custom.css) | PostCSS | 196 | 25 | 37 | 258 |
| [website/src/pages/dashboard.tsx](/website/src/pages/dashboard.tsx) | TypeScript JSX | 72 | 2 | 8 | 82 |
| [website/src/pages/index.module.css](/website/src/pages/index.module.css) | PostCSS | 16 | 4 | 4 | 24 |
| [website/src/pages/index.tsx](/website/src/pages/index.tsx) | TypeScript JSX | 358 | 4 | 22 | 384 |
| [website/src/theme/Root.tsx](/website/src/theme/Root.tsx) | TypeScript JSX | 11 | 0 | 2 | 13 |
| [website/static/google6934fc6e3618949f.html](/website/static/google6934fc6e3618949f.html) | HTML | 1 | 0 | 0 | 1 |
| [website/static/img/communityone\_logo.svg](/website/static/img/communityone_logo.svg) | XML | 13 | 5 | 5 | 23 |
| [website/static/img/logo.svg](/website/static/img/logo.svg) | XML | 1 | 0 | 0 | 1 |
| [website/static/img/undraw\_docusaurus\_mountain.svg](/website/static/img/undraw_docusaurus_mountain.svg) | XML | 171 | 0 | 1 | 172 |
| [website/static/img/undraw\_docusaurus\_react.svg](/website/static/img/undraw_docusaurus_react.svg) | XML | 170 | 0 | 1 | 171 |
| [website/static/img/undraw\_docusaurus\_tree.svg](/website/static/img/undraw_docusaurus_tree.svg) | XML | 40 | 0 | 1 | 41 |
| [website/test-admonition.md](/website/test-admonition.md) | Markdown | 13 | 0 | 5 | 18 |
| [website/tsconfig.json](/website/tsconfig.json) | JSON with Comments | 9 | 3 | 1 | 13 |

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details