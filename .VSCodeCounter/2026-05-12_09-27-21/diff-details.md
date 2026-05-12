# Diff Details

Date : 2026-05-12 09:27:21

Directory /home/developer/projects/open-navigator

Total : 596 files,  164050 codes, 3722 comments, 28404 blanks, all 196176 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [.claude/settings.json](/.claude/settings.json) | JSON with Comments | 12 | 0 | 1 | 13 |
| [.github/copilot-instructions.md](/.github/copilot-instructions.md) | Markdown | 599 | 0 | 159 | 758 |
| [.github/workflows/ci-build-test.yml](/.github/workflows/ci-build-test.yml) | YAML | 119 | 6 | 26 | 151 |
| [.github/workflows/deploy-huggingface.yml](/.github/workflows/deploy-huggingface.yml) | YAML | 51 | 2 | 10 | 63 |
| [.huggingface/README.md](/.huggingface/README.md) | Markdown | 74 | 0 | 28 | 102 |
| [.huggingface/nginx.conf](/.huggingface/nginx.conf) | Properties | 97 | 17 | 21 | 135 |
| [.huggingface/start.sh](/.huggingface/start.sh) | Shell Script | 44 | 8 | 10 | 62 |
| [.huggingface/supervisord.conf](/.huggingface/supervisord.conf) | Properties | 26 | 0 | 3 | 29 |
| [CITATIONS.md](/CITATIONS.md) | Markdown | 1,756 | 0 | 351 | 2,107 |
| [CODE\_OF\_CONDUCT.md](/CODE_OF_CONDUCT.md) | Markdown | 28 | 0 | 20 | 48 |
| [CONTRIBUTING.md](/CONTRIBUTING.md) | Markdown | 72 | 0 | 28 | 100 |
| [Dockerfile](/Dockerfile) | Docker | 49 | 21 | 21 | 91 |
| [Makefile](/Makefile) | Makefile | 145 | 0 | 25 | 170 |
| [README.md](/README.md) | Markdown | 417 | 0 | 162 | 579 |
| [README\_HF.md](/README_HF.md) | Markdown | 74 | 0 | 28 | 102 |
| [api/static/assets/index-C\_ibBpnu.css](/api/static/assets/index-C_ibBpnu.css) | PostCSS | 1 | 0 | 1 | 2 |
| [api/static/assets/index-CkmiImSA.js](/api/static/assets/index-CkmiImSA.js) | JavaScript | 204 | 0 | 3 | 207 |
| [api/static/communityone\_logo.svg](/api/static/communityone_logo.svg) | XML | 13 | 5 | 5 | 23 |
| [api/static/google6934fc6e3618949f.html](/api/static/google6934fc6e3618949f.html) | HTML | 1 | 0 | 0 | 1 |
| [api/static/index.html](/api/static/index.html) | HTML | 78 | 8 | 9 | 95 |
| [api/static/privacyfacebook.html](/api/static/privacyfacebook.html) | HTML | 244 | 0 | 33 | 277 |
| [api/static/sitemap-app.xml](/api/static/sitemap-app.xml) | XML | 89 | 5 | 19 | 113 |
| [api/static/sitemap.xml](/api/static/sitemap.xml) | XML | 11 | 2 | 4 | 17 |
| [app.yaml](/app.yaml) | YAML | 31 | 2 | 5 | 38 |
| [claude.md](/claude.md) | Markdown | 77 | 0 | 16 | 93 |
| [config/settings.py](/config/settings.py) | Python | 3 | 2 | 1 | 6 |
| [databricks/README.md](/databricks/README.md) | Markdown | 279 | 0 | 71 | 350 |
| [databricks/communityone\_schema.sql](/databricks/communityone_schema.sql) | MS SQL | 501 | 88 | 53 | 642 |
| [dbt\_project/.user.yml](/dbt_project/.user.yml) | YAML | 1 | 0 | 1 | 2 |
| [dbt\_project/MIGRATION\_PYTHON\_TO\_DBT.md](/dbt_project/MIGRATION_PYTHON_TO_DBT.md) | Markdown | 214 | 0 | 60 | 274 |
| [dbt\_project/QUICK\_REFERENCE.md](/dbt_project/QUICK_REFERENCE.md) | Markdown | 230 | 0 | 77 | 307 |
| [dbt\_project/README.md](/dbt_project/README.md) | Markdown | 198 | 0 | 78 | 276 |
| [dbt\_project/README\_TRENDING\_CAUSES.md](/dbt_project/README_TRENDING_CAUSES.md) | Markdown | 222 | 0 | 70 | 292 |
| [dbt\_project/analyses/audit\_county\_gsa\_naco\_domain\_mismatch.sql](/dbt_project/analyses/audit_county_gsa_naco_domain_mismatch.sql) | MS SQL | 19 | 2 | 2 | 23 |
| [dbt\_project/analyses/audit\_gsa\_domain\_types\_not\_in\_map.sql](/dbt_project/analyses/audit_gsa_domain_types_not_in_map.sql) | MS SQL | 38 | 3 | 2 | 43 |
| [dbt\_project/analyses/audit\_gsa\_mapping\_summary\_by\_state.sql](/dbt_project/analyses/audit_gsa_mapping_summary_by_state.sql) | MS SQL | 9 | 2 | 2 | 13 |
| [dbt\_project/analyses/audit\_gsa\_unmapped\_domains.sql](/dbt_project/analyses/audit_gsa_unmapped_domains.sql) | MS SQL | 12 | 3 | 2 | 17 |
| [dbt\_project/dbt\_project.yml](/dbt_project/dbt_project.yml) | YAML | 45 | 20 | 15 | 80 |
| [dbt\_project/macros/calculate\_confidence.sql](/dbt_project/macros/calculate_confidence.sql) | MS SQL | 11 | 8 | 1 | 20 |
| [dbt\_project/macros/generate\_schema\_name.sql](/dbt_project/macros/generate_schema_name.sql) | MS SQL | 8 | 0 | 4 | 12 |
| [dbt\_project/macros/normalize\_bill\_number.sql](/dbt_project/macros/normalize_bill_number.sql) | MS SQL | 14 | 11 | 1 | 26 |
| [dbt\_project/macros/normalize\_jurisdiction\_label\_for\_match.sql](/dbt_project/macros/normalize_jurisdiction_label_for_match.sql) | MS SQL | 41 | 0 | 1 | 42 |
| [dbt\_project/macros/normalize\_name.sql](/dbt_project/macros/normalize_name.sql) | MS SQL | 11 | 11 | 1 | 23 |
| [dbt\_project/models/bronze/bronze\_bills\_from\_ai.sql](/dbt_project/models/bronze/bronze_bills_from_ai.sql) | MS SQL | 65 | 12 | 8 | 85 |
| [dbt\_project/models/bronze/bronze\_causes\_from\_ai.sql](/dbt_project/models/bronze/bronze_causes_from_ai.sql) | MS SQL | 76 | 18 | 10 | 104 |
| [dbt\_project/models/bronze/bronze\_contacts\_from\_ai.sql](/dbt_project/models/bronze/bronze_contacts_from_ai.sql) | MS SQL | 63 | 16 | 8 | 87 |
| [dbt\_project/models/bronze/bronze\_decisions\_from\_ai.sql](/dbt_project/models/bronze/bronze_decisions_from_ai.sql) | MS SQL | 111 | 18 | 12 | 141 |
| [dbt\_project/models/bronze/bronze\_events\_youtube.sql](/dbt_project/models/bronze/bronze_events_youtube.sql) | MS SQL | 41 | 20 | 15 | 76 |
| [dbt\_project/models/bronze/bronze\_financial\_items\_from\_ai.sql](/dbt_project/models/bronze/bronze_financial_items_from_ai.sql) | MS SQL | 75 | 14 | 8 | 97 |
| [dbt\_project/models/bronze/bronze\_organizations\_from\_ai.sql](/dbt_project/models/bronze/bronze_organizations_from_ai.sql) | MS SQL | 109 | 19 | 9 | 137 |
| [dbt\_project/models/bronze/bronze\_topics\_from\_ai.sql](/dbt_project/models/bronze/bronze_topics_from_ai.sql) | MS SQL | 71 | 14 | 8 | 93 |
| [dbt\_project/models/intermediate/\_intermediate.yml](/dbt_project/models/intermediate/_intermediate.yml) | YAML | 471 | 0 | 27 | 498 |
| [dbt\_project/models/intermediate/int\_events\_channels.sql](/dbt_project/models/intermediate/int_events_channels.sql) | MS SQL | 138 | 21 | 23 | 182 |
| [dbt\_project/models/intermediate/int\_events\_channels\_enriched.sql](/dbt_project/models/intermediate/int_events_channels_enriched.sql) | MS SQL | 61 | 19 | 12 | 92 |
| [dbt\_project/models/intermediate/int\_events\_localview.sql](/dbt_project/models/intermediate/int_events_localview.sql) | MS SQL | 24 | 8 | 3 | 35 |
| [dbt\_project/models/intermediate/int\_jurisdiction\_websites.sql](/dbt_project/models/intermediate/int_jurisdiction_websites.sql) | MS SQL | 619 | 25 | 32 | 676 |
| [dbt\_project/models/intermediate/int\_jurisdictions.sql](/dbt_project/models/intermediate/int_jurisdictions.sql) | MS SQL | 350 | 25 | 14 | 389 |
| [dbt\_project/models/intermediate/int\_jurisdictions\_clean.sql](/dbt_project/models/intermediate/int_jurisdictions_clean.sql) | MS SQL | 74 | 27 | 21 | 122 |
| [dbt\_project/models/intermediate/int\_jurisdictions\_linked.sql](/dbt_project/models/intermediate/int_jurisdictions_linked.sql) | MS SQL | 71 | 25 | 13 | 109 |
| [dbt\_project/models/intermediate/int\_jurisdictions\_scraped\_discoveries.sql](/dbt_project/models/intermediate/int_jurisdictions_scraped_discoveries.sql) | MS SQL | 89 | 8 | 13 | 110 |
| [dbt\_project/models/intermediate/int\_localview\_channel\_geography.sql](/dbt_project/models/intermediate/int_localview_channel_geography.sql) | MS SQL | 44 | 10 | 6 | 60 |
| [dbt\_project/models/intermediate/int\_localview\_jurisdiction\_geography.sql](/dbt_project/models/intermediate/int_localview_jurisdiction_geography.sql) | MS SQL | 293 | 21 | 27 | 341 |
| [dbt\_project/models/intermediate/int\_nonprofits\_combined.sql](/dbt_project/models/intermediate/int_nonprofits_combined.sql) | MS SQL | 128 | 11 | 6 | 145 |
| [dbt\_project/models/intermediate/int\_nonprofits\_irs\_with\_zcta.sql](/dbt_project/models/intermediate/int_nonprofits_irs_with_zcta.sql) | MS SQL | 64 | 36 | 13 | 113 |
| [dbt\_project/models/intermediate/int\_nonprofits\_nccs\_with\_zcta.sql](/dbt_project/models/intermediate/int_nonprofits_nccs_with_zcta.sql) | MS SQL | 66 | 40 | 14 | 120 |
| [dbt\_project/models/intermediate/int\_nonprofits\_with\_county\_fips.sql](/dbt_project/models/intermediate/int_nonprofits_with_county_fips.sql) | MS SQL | 104 | 51 | 10 | 165 |
| [dbt\_project/models/intermediate/int\_trending\_causes\_by\_jurisdiction.sql](/dbt_project/models/intermediate/int_trending_causes_by_jurisdiction.sql) | MS SQL | 83 | 17 | 14 | 114 |
| [dbt\_project/models/marts/\_marts.yml](/dbt_project/models/marts/_marts.yml) | YAML | 338 | 0 | 62 | 400 |
| [dbt\_project/models/marts/events\_channels\_search.sql](/dbt_project/models/marts/events_channels_search.sql) | MS SQL | 53 | 27 | 13 | 93 |
| [dbt\_project/models/marts/events\_search.sql](/dbt_project/models/marts/events_search.sql) | MS SQL | 113 | 29 | 13 | 155 |
| [dbt\_project/models/marts/events\_text\_search.sql](/dbt_project/models/marts/events_text_search.sql) | MS SQL | 90 | 17 | 8 | 115 |
| [dbt\_project/models/marts/jurisdictions.sql](/dbt_project/models/marts/jurisdictions.sql) | MS SQL | 49 | 32 | 16 | 97 |
| [dbt\_project/models/marts/organizations\_nonprofit\_search.sql](/dbt_project/models/marts/organizations_nonprofit_search.sql) | MS SQL | 148 | 16 | 6 | 170 |
| [dbt\_project/models/marts/organizations\_nonprofits.sql](/dbt_project/models/marts/organizations_nonprofits.sql) | MS SQL | 143 | 38 | 27 | 208 |
| [dbt\_project/models/marts/stats\_aggregates.sql](/dbt_project/models/marts/stats_aggregates.sql) | MS SQL | 268 | 44 | 29 | 341 |
| [dbt\_project/models/staging/\_staging.yml](/dbt_project/models/staging/_staging.yml) | YAML | 887 | 0 | 53 | 940 |
| [dbt\_project/models/staging/stg\_bronze\_decisions.sql](/dbt_project/models/staging/stg_bronze_decisions.sql) | MS SQL | 40 | 14 | 13 | 67 |
| [dbt\_project/models/staging/stg\_bronze\_events\_cdp.sql](/dbt_project/models/staging/stg_bronze_events_cdp.sql) | MS SQL | 62 | 23 | 17 | 102 |
| [dbt\_project/models/staging/stg\_bronze\_events\_text\_ai.sql](/dbt_project/models/staging/stg_bronze_events_text_ai.sql) | MS SQL | 47 | 20 | 16 | 83 |
| [dbt\_project/package-lock.yml](/dbt_project/package-lock.yml) | YAML | 11 | 0 | 1 | 12 |
| [dbt\_project/packages.yml](/dbt_project/packages.yml) | YAML | 5 | 0 | 1 | 6 |
| [dbt\_project/scripts/dbt.sh](/dbt_project/scripts/dbt.sh) | Shell Script | 3 | 2 | 1 | 6 |
| [dbt\_project/scripts/discovery/run\_jurisdiction\_discovery.sh](/dbt_project/scripts/discovery/run_jurisdiction_discovery.sh) | Shell Script | 20 | 2 | 3 | 25 |
| [dbt\_project/scripts/ensure\_int\_jurisdictions\_indexes.sh](/dbt_project/scripts/ensure_int_jurisdictions_indexes.sh) | Shell Script | 27 | 10 | 8 | 45 |
| [dbt\_project/seeds/schema.yml](/dbt_project/seeds/schema.yml) | YAML | 20 | 0 | 3 | 23 |
| [dbt\_project/setup.sh](/dbt_project/setup.sh) | Shell Script | 67 | 11 | 14 | 92 |
| [dbt\_project/test\_ai\_extraction\_models.sh](/dbt_project/test_ai_extraction_models.sh) | Shell Script | 66 | 3 | 10 | 79 |
| [dbt\_project/tests/assert\_no\_ai\_overrides\_authoritative.sql](/dbt_project/tests/assert_no_ai_overrides_authoritative.sql) | MS SQL | 36 | 10 | 5 | 51 |
| [debug-dropdown.html](/debug-dropdown.html) | HTML | 80 | 0 | 13 | 93 |
| [docker-compose.socks-proxy.example.yml](/docker-compose.socks-proxy.example.yml) | YAML | 6 | 7 | 2 | 15 |
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
| [docs/JURISDICTION\_WEBSITE\_ENRICHMENT.md](/docs/JURISDICTION_WEBSITE_ENRICHMENT.md) | Markdown | 107 | 0 | 57 | 164 |
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
| [frontend/.eslintrc.cjs](/frontend/.eslintrc.cjs) | JavaScript | 18 | 0 | 1 | 19 |
| [frontend/README.md](/frontend/README.md) | Markdown | 126 | 0 | 41 | 167 |
| [frontend/index.html](/frontend/index.html) | HTML | 77 | 8 | 9 | 94 |
| [frontend/package-lock.json](/frontend/package-lock.json) | JSON | 5,287 | 0 | 1 | 5,288 |
| [frontend/package.json](/frontend/package.json) | JSON | 48 | 0 | 1 | 49 |
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
| [frontend/src/App.tsx](/frontend/src/App.tsx) | TypeScript JSX | 84 | 5 | 7 | 96 |
| [frontend/src/components/AddressLookup.tsx](/frontend/src/components/AddressLookup.tsx) | TypeScript JSX | 583 | 30 | 59 | 672 |
| [frontend/src/components/FollowButton.tsx](/frontend/src/components/FollowButton.tsx) | TypeScript JSX | 147 | 4 | 10 | 161 |
| [frontend/src/components/JurisdictionDiscovery.tsx](/frontend/src/components/JurisdictionDiscovery.tsx) | TypeScript JSX | 239 | 13 | 17 | 269 |
| [frontend/src/components/Layout.tsx](/frontend/src/components/Layout.tsx) | TypeScript JSX | 504 | 16 | 21 | 541 |
| [frontend/src/components/MultiSelect.tsx](/frontend/src/components/MultiSelect.tsx) | TypeScript JSX | 128 | 2 | 8 | 138 |
| [frontend/src/components/RegistrationModal.tsx](/frontend/src/components/RegistrationModal.tsx) | TypeScript JSX | 192 | 7 | 18 | 217 |
| [frontend/src/components/ScrollToTop.tsx](/frontend/src/components/ScrollToTop.tsx) | TypeScript JSX | 9 | 4 | 4 | 17 |
| [frontend/src/components/SocialStats.tsx](/frontend/src/components/SocialStats.tsx) | TypeScript JSX | 106 | 2 | 14 | 122 |
| [frontend/src/components/USMap.tsx](/frontend/src/components/USMap.tsx) | TypeScript JSX | 461 | 46 | 60 | 567 |
| [frontend/src/contexts/AuthContext.tsx](/frontend/src/contexts/AuthContext.tsx) | TypeScript JSX | 122 | 9 | 19 | 150 |
| [frontend/src/contexts/LocationContext.tsx](/frontend/src/contexts/LocationContext.tsx) | TypeScript JSX | 78 | 6 | 19 | 103 |
| [frontend/src/index.css](/frontend/src/index.css) | PostCSS | 78 | 3 | 13 | 94 |
| [frontend/src/lib/api.ts](/frontend/src/lib/api.ts) | TypeScript | 123 | 16 | 26 | 165 |
| [frontend/src/main.tsx](/frontend/src/main.tsx) | TypeScript JSX | 37 | 0 | 3 | 40 |
| [frontend/src/pages/AdvocacyTopics.tsx](/frontend/src/pages/AdvocacyTopics.tsx) | TypeScript JSX | 217 | 5 | 8 | 230 |
| [frontend/src/pages/Analytics.tsx](/frontend/src/pages/Analytics.tsx) | TypeScript JSX | 204 | 32 | 14 | 250 |
| [frontend/src/pages/BillDetail.tsx](/frontend/src/pages/BillDetail.tsx) | TypeScript JSX | 248 | 7 | 15 | 270 |
| [frontend/src/pages/CensusMapPage.tsx](/frontend/src/pages/CensusMapPage.tsx) | TypeScript JSX | 2,026 | 11 | 113 | 2,150 |
| [frontend/src/pages/Dashboard.tsx](/frontend/src/pages/Dashboard.tsx) | TypeScript JSX | 183 | 6 | 13 | 202 |
| [frontend/src/pages/DebateGrader.tsx](/frontend/src/pages/DebateGrader.tsx) | TypeScript JSX | 245 | 8 | 22 | 275 |
| [frontend/src/pages/Developers.tsx](/frontend/src/pages/Developers.tsx) | TypeScript JSX | 182 | 8 | 11 | 201 |
| [frontend/src/pages/Documents.tsx](/frontend/src/pages/Documents.tsx) | TypeScript JSX | 216 | 5 | 13 | 234 |
| [frontend/src/pages/Events.tsx](/frontend/src/pages/Events.tsx) | TypeScript JSX | 105 | 6 | 6 | 117 |
| [frontend/src/pages/Explore.tsx](/frontend/src/pages/Explore.tsx) | TypeScript JSX | 435 | 32 | 36 | 503 |
| [frontend/src/pages/FactChecking.tsx](/frontend/src/pages/FactChecking.tsx) | TypeScript JSX | 252 | 6 | 11 | 269 |
| [frontend/src/pages/Hackathons.tsx](/frontend/src/pages/Hackathons.tsx) | TypeScript JSX | 199 | 9 | 11 | 219 |
| [frontend/src/pages/Heatmap.tsx](/frontend/src/pages/Heatmap.tsx) | TypeScript JSX | 158 | 4 | 13 | 175 |
| [frontend/src/pages/Home.tsx](/frontend/src/pages/Home.tsx) | TypeScript JSX | 2,332 | 119 | 142 | 2,593 |
| [frontend/src/pages/HomeModern.tsx](/frontend/src/pages/HomeModern.tsx) | TypeScript JSX | 1,356 | 68 | 83 | 1,507 |
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
| [frontend/src/pages/UnifiedSearch.tsx](/frontend/src/pages/UnifiedSearch.tsx) | TypeScript JSX | 1,531 | 85 | 109 | 1,725 |
| [frontend/src/utils/censusMapTransforms.ts](/frontend/src/utils/censusMapTransforms.ts) | TypeScript | 95 | 11 | 11 | 117 |
| [frontend/src/utils/censusMapValueMode.ts](/frontend/src/utils/censusMapValueMode.ts) | TypeScript | 42 | 1 | 6 | 49 |
| [frontend/src/utils/formatters.ts](/frontend/src/utils/formatters.ts) | TypeScript | 26 | 10 | 6 | 42 |
| [frontend/src/utils/huggingface.ts](/frontend/src/utils/huggingface.ts) | TypeScript | 161 | 107 | 35 | 303 |
| [frontend/src/utils/stateMapping.ts](/frontend/src/utils/stateMapping.ts) | TypeScript | 73 | 15 | 7 | 95 |
| [frontend/src/vite-env.d.ts](/frontend/src/vite-env.d.ts) | TypeScript | 6 | 2 | 3 | 11 |
| [frontend/tailwind.config.js](/frontend/tailwind.config.js) | JavaScript | 36 | 1 | 1 | 38 |
| [frontend/tsconfig.json](/frontend/tsconfig.json) | JSON with Comments | 21 | 2 | 3 | 26 |
| [frontend/tsconfig.node.json](/frontend/tsconfig.node.json) | JSON | 10 | 0 | 1 | 11 |
| [frontend/vite.config.ts](/frontend/vite.config.ts) | TypeScript | 33 | 2 | 2 | 37 |
| [output/TUSCALOOSA\_ADVOCACY\_BRIEF.md](/output/TUSCALOOSA_ADVOCACY_BRIEF.md) | Markdown | 83 | 0 | 62 | 145 |
| [output/tuscaloosa/suiteonemedia\_20260503\_041932.json](/output/tuscaloosa/suiteonemedia_20260503_041932.json) | JSON | 404 | 0 | 0 | 404 |
| [output/tuscaloosa\_accountability\_dashboards.json](/output/tuscaloosa_accountability_dashboards.json) | JSON | 9 | 0 | 0 | 9 |
| [prompts/polcy\_analysis\_readable.md](/prompts/polcy_analysis_readable.md) | Markdown | 228 | 0 | 44 | 272 |
| [prompts/policy\_analysis.md](/prompts/policy_analysis.md) | Markdown | 548 | 0 | 52 | 600 |
| [prompts/policy\_analysis\_concsie.md](/prompts/policy_analysis_concsie.md) | Markdown | 146 | 0 | 18 | 164 |
| [prompts/policy\_analysis\_sample\_inputs.md](/prompts/policy_analysis_sample_inputs.md) | Markdown | 10 | 0 | 0 | 10 |
| [requirements.txt](/requirements.txt) | pip requirements | 76 | 25 | 16 | 117 |
| [scripts/README.md](/scripts/README.md) | Markdown | 156 | 0 | 46 | 202 |
| [scripts/datasources/README.md](/scripts/datasources/README.md) | Markdown | 106 | 0 | 40 | 146 |
| [scripts/datasources/ballotpedia/README.md](/scripts/datasources/ballotpedia/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/cdp/README.md](/scripts/datasources/cdp/README.md) | Markdown | 187 | 0 | 75 | 262 |
| [scripts/datasources/census/DATASETS.md](/scripts/datasources/census/DATASETS.md) | Markdown | 239 | 0 | 84 | 323 |
| [scripts/datasources/census/README.md](/scripts/datasources/census/README.md) | Markdown | 156 | 0 | 61 | 217 |
| [scripts/datasources/census/STATUS.md](/scripts/datasources/census/STATUS.md) | Markdown | 189 | 0 | 59 | 248 |
| [scripts/datasources/census/add\_jurisdiction\_columns\_to\_search.sql](/scripts/datasources/census/add_jurisdiction_columns_to_search.sql) | MS SQL | 19 | 11 | 5 | 35 |
| [scripts/datasources/census/download\_census\_acs.sh](/scripts/datasources/census/download_census_acs.sh) | Shell Script | 25 | 19 | 7 | 51 |
| [scripts/datasources/census/download\_census\_acs\_data.py](/scripts/datasources/census/download_census_acs_data.py) | Python | 191 | 29 | 15 | 235 |
| [scripts/datasources/census/enrich\_nonprofits\_with\_county\_fips.sql](/scripts/datasources/census/enrich_nonprofits_with_county_fips.sql) | MS SQL | 173 | 23 | 19 | 215 |
| [scripts/datasources/census/enrich\_nonprofits\_with\_place\_geoid.sql](/scripts/datasources/census/enrich_nonprofits_with_place_geoid.sql) | MS SQL | 103 | 21 | 15 | 139 |
| [scripts/datasources/census/export\_census\_map\_static.py](/scripts/datasources/census/export_census_map_static.py) | Python | 263 | 14 | 25 | 302 |
| [scripts/datasources/census/load\_acs.py](/scripts/datasources/census/load_acs.py) | Python | 19 | 3 | 1 | 23 |
| [scripts/datasources/census/run\_acs\_download.sh](/scripts/datasources/census/run_acs_download.sh) | Shell Script | 4 | 8 | 2 | 14 |
| [scripts/datasources/census/sync\_jurisdictions\_fast.sql](/scripts/datasources/census/sync_jurisdictions_fast.sql) | MS SQL | 53 | 18 | 18 | 89 |
| [scripts/datasources/cityscrapers/README.md](/scripts/datasources/cityscrapers/README.md) | Markdown | 169 | 0 | 61 | 230 |
| [scripts/datasources/dbpedia/README.md](/scripts/datasources/dbpedia/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/fec/POLITICAL\_FINANCE\_QUICK\_START.md](/scripts/datasources/fec/POLITICAL_FINANCE_QUICK_START.md) | Markdown | 308 | 0 | 94 | 402 |
| [scripts/datasources/fec/POLITICAL\_INFLUENCE\_INTEGRATION.md](/scripts/datasources/fec/POLITICAL_INFLUENCE_INTEGRATION.md) | Markdown | 384 | 0 | 91 | 475 |
| [scripts/datasources/fec/README.md](/scripts/datasources/fec/README.md) | Markdown | 205 | 0 | 51 | 256 |
| [scripts/datasources/gemini/MERGE\_STATUS.md](/scripts/datasources/gemini/MERGE_STATUS.md) | Markdown | 213 | 0 | 68 | 281 |
| [scripts/datasources/gemini/README.md](/scripts/datasources/gemini/README.md) | Markdown | 391 | 0 | 114 | 505 |
| [scripts/datasources/gemini/README\_BRONZE\_MERGE.md](/scripts/datasources/gemini/README_BRONZE_MERGE.md) | Markdown | 183 | 0 | 63 | 246 |
| [scripts/datasources/gemini/migrations/README.md](/scripts/datasources/gemini/migrations/README.md) | Markdown | 65 | 0 | 28 | 93 |
| [scripts/datasources/gemini/run\_bronze\_merge.sh](/scripts/datasources/gemini/run_bronze_merge.sh) | Shell Script | 153 | 5 | 32 | 190 |
| [scripts/datasources/google\_civic/README.md](/scripts/datasources/google_civic/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/govwebsites/README.md](/scripts/datasources/govwebsites/README.md) | Markdown | 82 | 0 | 28 | 110 |
| [scripts/datasources/grants\_gov/GRANTS\_GOV\_VALUE.md](/scripts/datasources/grants_gov/GRANTS_GOV_VALUE.md) | Markdown | 181 | 0 | 48 | 229 |
| [scripts/datasources/grants\_gov/README.md](/scripts/datasources/grants_gov/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/hifld/README.md](/scripts/datasources/hifld/README.md) | Markdown | 157 | 0 | 58 | 215 |
| [scripts/datasources/hifld/download\_and\_load\_hifld.sh](/scripts/datasources/hifld/download_and_load_hifld.sh) | Shell Script | 33 | 33 | 10 | 76 |
| [scripts/datasources/irs/README.md](/scripts/datasources/irs/README.md) | Markdown | 39 | 0 | 17 | 56 |
| [scripts/datasources/irs/README\_IRS\_BMF.md](/scripts/datasources/irs/README_IRS_BMF.md) | Markdown | 62 | 0 | 22 | 84 |
| [scripts/datasources/irs/README\_NONPROFIT\_DISCOVERY.md](/scripts/datasources/irs/README_NONPROFIT_DISCOVERY.md) | Markdown | 338 | 0 | 102 | 440 |
| [scripts/datasources/localview/README.md](/scripts/datasources/localview/README.md) | Markdown | 19 | 0 | 11 | 30 |
| [scripts/datasources/master\_data/README.md](/scripts/datasources/master_data/README.md) | Markdown | 310 | 0 | 79 | 389 |
| [scripts/datasources/master\_data/query\_examples.sql](/scripts/datasources/master_data/query_examples.sql) | MS SQL | 281 | 72 | 52 | 405 |
| [scripts/datasources/meetingbank/README.md](/scripts/datasources/meetingbank/README.md) | Markdown | 13 | 0 | 8 | 21 |
| [scripts/datasources/naco/README.md](/scripts/datasources/naco/README.md) | Markdown | 54 | 0 | 28 | 82 |
| [scripts/datasources/naco/run\_naco\_all\_states.sh](/scripts/datasources/naco/run_naco_all_states.sh) | Shell Script | 18 | 12 | 7 | 37 |
| [scripts/datasources/naco/run\_naco\_pipeline.sh](/scripts/datasources/naco/run_naco_pipeline.sh) | Shell Script | 21 | 14 | 7 | 42 |
| [scripts/datasources/nccs/README.md](/scripts/datasources/nccs/README.md) | Markdown | 165 | 0 | 53 | 218 |
| [scripts/datasources/nces/README.md](/scripts/datasources/nces/README.md) | Markdown | 82 | 0 | 34 | 116 |
| [scripts/datasources/nces/README\_ENRICHMENT.md](/scripts/datasources/nces/README_ENRICHMENT.md) | Markdown | 160 | 0 | 46 | 206 |
| [scripts/datasources/ntee/README.md](/scripts/datasources/ntee/README.md) | Markdown | 163 | 0 | 49 | 212 |
| [scripts/datasources/openstates/README.md](/scripts/datasources/openstates/README.md) | Markdown | 83 | 0 | 29 | 112 |
| [scripts/datasources/openstates/load\_openstates\_csv.sh](/scripts/datasources/openstates/load_openstates_csv.sh) | Shell Script | 76 | 9 | 15 | 100 |
| [scripts/datasources/openstates/parallel\_download.sh](/scripts/datasources/openstates/parallel_download.sh) | Shell Script | 42 | 7 | 10 | 59 |
| [scripts/datasources/openstates/repair\_main\_venv\_after\_dbt\_conflict.sh](/scripts/datasources/openstates/repair_main_venv_after_dbt_conflict.sh) | Shell Script | 19 | 9 | 6 | 34 |
| [scripts/datasources/openstates/run\_openstates\_jurisdiction\_mapping.sh](/scripts/datasources/openstates/run_openstates_jurisdiction_mapping.sh) | Shell Script | 42 | 17 | 8 | 67 |
| [scripts/datasources/openstates/setup\_dbt\_venv.sh](/scripts/datasources/openstates/setup_dbt_venv.sh) | Shell Script | 16 | 8 | 6 | 30 |
| [scripts/datasources/openstates/setup\_openstates\_db.sh](/scripts/datasources/openstates/setup_openstates_db.sh) | Shell Script | 144 | 32 | 26 | 202 |
| [scripts/datasources/osf/load\_osf\_rds\_to\_bronze.R](/scripts/datasources/osf/load_osf_rds_to_bronze.R) | R | 126 | 24 | 22 | 172 |
| [scripts/datasources/osf/readme.md](/scripts/datasources/osf/readme.md) | Markdown | 42 | 0 | 24 | 66 |
| [scripts/datasources/uscm/README.md](/scripts/datasources/uscm/README.md) | Markdown | 80 | 0 | 33 | 113 |
| [scripts/datasources/voter\_data/README.md](/scripts/datasources/voter_data/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/wikidata/README.md](/scripts/datasources/wikidata/README.md) | Markdown | 73 | 0 | 32 | 105 |
| [scripts/datasources/wikidata/generate\_mapping\_report.sql](/scripts/datasources/wikidata/generate_mapping_report.sql) | MS SQL | 108 | 13 | 10 | 131 |
| [scripts/datasources/wikidata/load\_jurisdictions\_wikidata\_colab.ipynb](/scripts/datasources/wikidata/load_jurisdictions_wikidata_colab.ipynb) | JSON | 464 | 0 | 0 | 464 |
| [scripts/datasources/wikidata/run\_load\_jurisdictions\_wikidata.sh](/scripts/datasources/wikidata/run_load_jurisdictions_wikidata.sh) | Shell Script | 8 | 3 | 4 | 15 |
| [scripts/datasources/wikidata/run\_wikidata\_happy\_path.sh](/scripts/datasources/wikidata/run_wikidata_happy_path.sh) | Shell Script | 8 | 11 | 4 | 23 |
| [scripts/datasources/wikidata/run\_wikidata\_priority\_states\_background.sh](/scripts/datasources/wikidata/run_wikidata_priority_states_background.sh) | Shell Script | 37 | 16 | 8 | 61 |
| [scripts/datasources/wikidata/wikidata\_fips\_gnis\_extract\_colab.ipynb](/scripts/datasources/wikidata/wikidata_fips_gnis_extract_colab.ipynb) | JSON | 348 | 0 | 0 | 348 |
| [scripts/datasources/youtube/BRONZE\_MIGRATION.md](/scripts/datasources/youtube/BRONZE_MIGRATION.md) | Markdown | 125 | 0 | 32 | 157 |
| [scripts/datasources/youtube/BYPASS\_IP\_BLOCK.md](/scripts/datasources/youtube/BYPASS_IP_BLOCK.md) | Markdown | 119 | 0 | 40 | 159 |
| [scripts/datasources/youtube/CHANNEL\_SANITY\_CHECK.md](/scripts/datasources/youtube/CHANNEL_SANITY_CHECK.md) | Markdown | 179 | 0 | 45 | 224 |
| [scripts/datasources/youtube/README\_AUDIO\_DOWNLOAD.md](/scripts/datasources/youtube/README_AUDIO_DOWNLOAD.md) | Markdown | 142 | 0 | 38 | 180 |
| [scripts/datasources/youtube/download\_audio\_colab.ipynb](/scripts/datasources/youtube/download_audio_colab.ipynb) | JSON | 1,191 | 0 | 0 | 1,191 |
| [scripts/datasources/youtube/load\_youtube\_events\_colab.ipynb](/scripts/datasources/youtube/load_youtube_events_colab.ipynb) | JSON | 775 | 0 | 1 | 776 |
| [scripts/datasources/youtube/setup\_channels\_bronze.sh](/scripts/datasources/youtube/setup_channels_bronze.sh) | Shell Script | 49 | 8 | 9 | 66 |
| [scripts/dbt.sh](/scripts/dbt.sh) | Shell Script | 4 | 6 | 1 | 11 |
| [scripts/dbt/README.md](/scripts/dbt/README.md) | Markdown | 265 | 0 | 83 | 348 |
| [scripts/deployment/README.md](/scripts/deployment/README.md) | Markdown | 61 | 0 | 22 | 83 |
| [scripts/deployment/deploy-databricks-app.sh](/scripts/deployment/deploy-databricks-app.sh) | Shell Script | 50 | 10 | 13 | 73 |
| [scripts/deployment/install.sh](/scripts/deployment/install.sh) | Shell Script | 96 | 11 | 14 | 121 |
| [scripts/deployment/migrate\_neon\_to\_dev.sh](/scripts/deployment/migrate_neon_to_dev.sh) | Shell Script | 70 | 7 | 12 | 89 |
| [scripts/deployment/neon/README.md](/scripts/deployment/neon/README.md) | Markdown | 270 | 0 | 72 | 342 |
| [scripts/deployment/neon/SETUP\_YOUTUBE.md](/scripts/deployment/neon/SETUP_YOUTUBE.md) | Markdown | 119 | 0 | 45 | 164 |
| [scripts/deployment/neon/migrate\_all\_bronze\_tables.sh](/scripts/deployment/neon/migrate_all_bronze_tables.sh) | Shell Script | 49 | 7 | 14 | 70 |
| [scripts/deployment/neon/migrate\_bronze\_to\_schemas.sh](/scripts/deployment/neon/migrate_bronze_to_schemas.sh) | Shell Script | 58 | 7 | 14 | 79 |
| [scripts/deployment/neon/migrations/001\_add\_datasource\_fields.sql](/scripts/deployment/neon/migrations/001_add_datasource_fields.sql) | MS SQL | 178 | 52 | 59 | 289 |
| [scripts/deployment/neon/migrations/001\_add\_datasource\_fields\_rollback.sql](/scripts/deployment/neon/migrations/001_add_datasource_fields_rollback.sql) | MS SQL | 38 | 13 | 9 | 60 |
| [scripts/deployment/neon/migrations/002\_create\_bronze\_events\_channels.sql](/scripts/deployment/neon/migrations/002_create_bronze_events_channels.sql) | MS SQL | 34 | 14 | 12 | 60 |
| [scripts/deployment/neon/migrations/003\_create\_bronze\_events\_search.sql](/scripts/deployment/neon/migrations/003_create_bronze_events_search.sql) | MS SQL | 58 | 38 | 20 | 116 |
| [scripts/deployment/neon/migrations/004\_create\_bronze\_events\_text\_ai.sql](/scripts/deployment/neon/migrations/004_create_bronze_events_text_ai.sql) | MS SQL | 28 | 35 | 18 | 81 |
| [scripts/deployment/neon/migrations/005\_create\_bronze\_events\_youtube.sql](/scripts/deployment/neon/migrations/005_create_bronze_events_youtube.sql) | MS SQL | 48 | 21 | 16 | 85 |
| [scripts/deployment/neon/migrations/006\_add\_audio\_tracking\_fields.sql](/scripts/deployment/neon/migrations/006_add_audio_tracking_fields.sql) | MS SQL | 19 | 12 | 8 | 39 |
| [scripts/deployment/neon/migrations/007\_create\_bronze\_events\_analysis\_ai.sql](/scripts/deployment/neon/migrations/007_create_bronze_events_analysis_ai.sql) | MS SQL | 22 | 0 | 2 | 24 |
| [scripts/deployment/neon/migrations/008\_create\_bronze\_zip\_county.sql](/scripts/deployment/neon/migrations/008_create_bronze_zip_county.sql) | MS SQL | 16 | 0 | 3 | 19 |
| [scripts/deployment/neon/migrations/009\_create\_bronze\_jurisdictions\_scraped.sql](/scripts/deployment/neon/migrations/009_create_bronze_jurisdictions_scraped.sql) | MS SQL | 89 | 8 | 10 | 107 |
| [scripts/deployment/neon/migrations/010\_add\_jurisdiction\_id.sql](/scripts/deployment/neon/migrations/010_add_jurisdiction_id.sql) | MS SQL | 80 | 31 | 36 | 147 |
| [scripts/deployment/neon/migrations/011\_add\_jurisdiction\_type\_and\_source.sql](/scripts/deployment/neon/migrations/011_add_jurisdiction_type_and_source.sql) | MS SQL | 63 | 21 | 15 | 99 |
| [scripts/deployment/neon/migrations/012\_convert\_jurisdiction\_columns\_to\_enum.sql](/scripts/deployment/neon/migrations/012_convert_jurisdiction_columns_to_enum.sql) | MS SQL | 124 | 32 | 19 | 175 |
| [scripts/deployment/neon/migrations/013\_add\_jurisdiction\_id\_prefix.sql](/scripts/deployment/neon/migrations/013_add_jurisdiction_id_prefix.sql) | MS SQL | 94 | 32 | 18 | 144 |
| [scripts/deployment/neon/migrations/014\_create\_bronze\_jurisdictions\_openstates.sql](/scripts/deployment/neon/migrations/014_create_bronze_jurisdictions_openstates.sql) | MS SQL | 21 | 8 | 5 | 34 |
| [scripts/deployment/neon/migrations/015\_rename\_bronze\_naco\_jurisdictions.sql](/scripts/deployment/neon/migrations/015_rename_bronze_naco_jurisdictions.sql) | MS SQL | 22 | 2 | 5 | 29 |
| [scripts/deployment/neon/migrations/016\_rename\_bronze\_jurisdictions\_municipalities\_uscm.sql](/scripts/deployment/neon/migrations/016_rename_bronze_jurisdictions_municipalities_uscm.sql) | MS SQL | 30 | 3 | 5 | 38 |
| [scripts/deployment/neon/migrations/017\_calendar\_year\_columns\_to\_varchar.sql](/scripts/deployment/neon/migrations/017_calendar_year_columns_to_varchar.sql) | MS SQL | 98 | 15 | 9 | 122 |
| [scripts/deployment/neon/migrations/018\_create\_bronze\_events\_meetings\_scraped.sql](/scripts/deployment/neon/migrations/018_create_bronze_events_meetings_scraped.sql) | MS SQL | 71 | 3 | 12 | 86 |
| [scripts/deployment/neon/migrations/019\_recreate\_bronze\_events\_meetings\_scraped\_granular.sql](/scripts/deployment/neon/migrations/019_recreate_bronze_events_meetings_scraped_granular.sql) | MS SQL | 109 | 3 | 13 | 125 |
| [scripts/deployment/neon/migrations/020\_recreate\_bronze\_events\_meetings\_scraped\_link\_document.sql](/scripts/deployment/neon/migrations/020_recreate_bronze_events_meetings_scraped_link_document.sql) | MS SQL | 123 | 2 | 13 | 138 |
| [scripts/deployment/neon/run\_bronze\_jurisdictions\_to\_cloud.sh](/scripts/deployment/neon/run_bronze_jurisdictions_to_cloud.sh) | Shell Script | 15 | 13 | 7 | 35 |
| [scripts/deployment/neon/run\_jurisdiction\_id\_migration.sh](/scripts/deployment/neon/run_jurisdiction_id_migration.sh) | Shell Script | 82 | 29 | 15 | 126 |
| [scripts/deployment/neon/schema.sql](/scripts/deployment/neon/schema.sql) | MS SQL | 288 | 82 | 78 | 448 |
| [scripts/deployment/neon/schema\_bills.sql](/scripts/deployment/neon/schema_bills.sql) | MS SQL | 35 | 13 | 12 | 60 |
| [scripts/deployment/neon/setup\_youtube\_tables.sh](/scripts/deployment/neon/setup_youtube_tables.sh) | Shell Script | 234 | 52 | 38 | 324 |
| [scripts/deployment/set-pg-password.sh](/scripts/deployment/set-pg-password.sh) | Shell Script | 9 | 2 | 7 | 18 |
| [scripts/deployment/setup-database.sh](/scripts/deployment/setup-database.sh) | Shell Script | 174 | 26 | 36 | 236 |
| [scripts/deployment/setup-git-hooks.sh](/scripts/deployment/setup-git-hooks.sh) | Shell Script | 24 | 5 | 6 | 35 |
| [scripts/deployment/setup-local-postgres.sh](/scripts/deployment/setup-local-postgres.sh) | Shell Script | 49 | 8 | 11 | 68 |
| [scripts/deployment/setup-local.sh](/scripts/deployment/setup-local.sh) | Shell Script | 32 | 5 | 8 | 45 |
| [scripts/development/README.md](/scripts/development/README.md) | Markdown | 11 | 0 | 9 | 20 |
| [scripts/discovery/README.md](/scripts/discovery/README.md) | Markdown | 113 | 0 | 40 | 153 |
| [scripts/discovery/discover\_oral\_health\_states.sh](/scripts/discovery/discover_oral_health_states.sh) | Shell Script | 35 | 6 | 13 | 54 |
| [scripts/discovery/discover\_top\_cities.sh](/scripts/discovery/discover_top_cities.sh) | Shell Script | 27 | 5 | 10 | 42 |
| [scripts/discovery/run\_jurisdiction\_discovery.sh](/scripts/discovery/run_jurisdiction_discovery.sh) | Shell Script | 20 | 4 | 3 | 27 |
| [scripts/discovery/sql/bronze\_jurisdictions\_scraped.sql](/scripts/discovery/sql/bronze_jurisdictions_scraped.sql) | MS SQL | 89 | 9 | 10 | 108 |
| [scripts/enrichment/README.md](/scripts/enrichment/README.md) | Markdown | 32 | 0 | 15 | 47 |
| [scripts/enrichment/auto\_enrich\_nonprofits.sh](/scripts/enrichment/auto_enrich_nonprofits.sh) | Shell Script | 17 | 4 | 5 | 26 |
| [scripts/enrichment/download\_990\_zips.sh](/scripts/enrichment/download_990_zips.sh) | Shell Script | 95 | 10 | 20 | 125 |
| [scripts/enrichment/enrich\_alabama\_nonprofits.sh](/scripts/enrichment/enrich_alabama_nonprofits.sh) | Shell Script | 18 | 3 | 7 | 28 |
| [scripts/enrichment/enrich\_all\_states\_local.sh](/scripts/enrichment/enrich_all_states_local.sh) | Shell Script | 74 | 8 | 16 | 98 |
| [scripts/enrichment/enrich\_nonprofits\_no\_auth.sh](/scripts/enrichment/enrich_nonprofits_no_auth.sh) | Shell Script | 77 | 13 | 13 | 103 |
| [scripts/enrichment/extract\_990\_dev\_states.sh](/scripts/enrichment/extract_990_dev_states.sh) | Shell Script | 101 | 24 | 27 | 152 |
| [scripts/enrichment/extract\_990\_zips.sh](/scripts/enrichment/extract_990_zips.sh) | Shell Script | 62 | 11 | 15 | 88 |
| [scripts/enrichment/run\_tuscaloosa\_pipeline.sh](/scripts/enrichment/run_tuscaloosa_pipeline.sh) | Shell Script | 214 | 31 | 57 | 302 |
| [scripts/enrichment\_ai/README.md](/scripts/enrichment_ai/README.md) | Markdown | 152 | 0 | 57 | 209 |
| [scripts/enrichment\_ai/README\_BILL\_TEXT.md](/scripts/enrichment_ai/README_BILL_TEXT.md) | Markdown | 179 | 0 | 72 | 251 |
| [scripts/enrichment\_ai/install\_xpu\_pytorch.sh](/scripts/enrichment_ai/install_xpu_pytorch.sh) | Shell Script | 50 | 5 | 11 | 66 |
| [scripts/enrichment\_ai/intel\_llm\_setup.sh](/scripts/enrichment_ai/intel_llm_setup.sh) | Shell Script | 56 | 13 | 16 | 85 |
| [scripts/enrichment\_ai/setup\_intel\_gpu.sh](/scripts/enrichment_ai/setup_intel_gpu.sh) | Shell Script | 79 | 11 | 16 | 106 |
| [scripts/examples/README.md](/scripts/examples/README.md) | Markdown | 33 | 0 | 16 | 49 |
| [scripts/examples/targets.json](/scripts/examples/targets.json) | JSON | 32 | 0 | 1 | 33 |
| [scripts/huggingface/README.md](/scripts/huggingface/README.md) | Markdown | 101 | 0 | 39 | 140 |
| [scripts/huggingface/deploy-huggingface.sh](/scripts/huggingface/deploy-huggingface.sh) | Shell Script | 253 | 42 | 41 | 336 |
| [scripts/huggingface/deploy-via-api.sh](/scripts/huggingface/deploy-via-api.sh) | Shell Script | 93 | 12 | 18 | 123 |
| [scripts/huggingface/force-hf-rebuild.sh](/scripts/huggingface/force-hf-rebuild.sh) | Shell Script | 17 | 3 | 6 | 26 |
| [scripts/huggingface/hf-dataset-cleanup.sh](/scripts/huggingface/hf-dataset-cleanup.sh) | Shell Script | 28 | 4 | 7 | 39 |
| [scripts/huggingface/safe-deploy.sh](/scripts/huggingface/safe-deploy.sh) | Shell Script | 96 | 10 | 13 | 119 |
| [scripts/huggingface/setup-huggingface.sh](/scripts/huggingface/setup-huggingface.sh) | Shell Script | 111 | 12 | 23 | 146 |
| [scripts/huggingface/test-huggingface-build.sh](/scripts/huggingface/test-huggingface-build.sh) | Shell Script | 147 | 24 | 32 | 203 |
| [scripts/huggingface/verify-hf-deployment.sh](/scripts/huggingface/verify-hf-deployment.sh) | Shell Script | 61 | 6 | 10 | 77 |
| [scripts/localview/README.md](/scripts/localview/README.md) | Markdown | 121 | 0 | 52 | 173 |
| [scripts/localview/load\_priority\_states.sh](/scripts/localview/load_priority_states.sh) | Shell Script | 133 | 16 | 26 | 175 |
| [scripts/localview/update\_all.sh](/scripts/localview/update_all.sh) | Shell Script | 39 | 9 | 11 | 59 |
| [scripts/maintenance/README.md](/scripts/maintenance/README.md) | Markdown | 98 | 0 | 32 | 130 |
| [scripts/maintenance/cleanup\_disk\_space.sh](/scripts/maintenance/cleanup_disk_space.sh) | Shell Script | 83 | 12 | 18 | 113 |
| [scripts/maintenance/cleanup\_frontend\_junk.sh](/scripts/maintenance/cleanup_frontend_junk.sh) | Shell Script | 24 | 4 | 4 | 32 |
| [scripts/maintenance/docker-cleanup.sh](/scripts/maintenance/docker-cleanup.sh) | Shell Script | 75 | 12 | 17 | 104 |
| [scripts/maintenance/migrate-docs.sh](/scripts/maintenance/migrate-docs.sh) | Shell Script | 46 | 8 | 9 | 63 |
| [scripts/maintenance/move\_secrets\_to\_home.sh](/scripts/maintenance/move_secrets_to_home.sh) | Shell Script | 35 | 7 | 12 | 54 |
| [scripts/maintenance/prevent\_terminal\_corruption.sh](/scripts/maintenance/prevent_terminal_corruption.sh) | Shell Script | 16 | 8 | 7 | 31 |
| [scripts/maintenance/update-repo-urls.sh](/scripts/maintenance/update-repo-urls.sh) | Shell Script | 36 | 5 | 7 | 48 |
| [scripts/mcp/README.md](/scripts/mcp/README.md) | Markdown | 150 | 0 | 59 | 209 |
| [scripts/media/README.md](/scripts/media/README.md) | Markdown | 136 | 0 | 41 | 177 |
| [scripts/migrations/README.md](/scripts/migrations/README.md) | Markdown | 164 | 0 | 50 | 214 |
| [scripts/state\_symbols/README.md](/scripts/state_symbols/README.md) | Markdown | 22 | 0 | 13 | 35 |
| [scripts/state\_symbols/download\_state\_symbols\_assets.sh](/scripts/state_symbols/download_state_symbols_assets.sh) | Shell Script | 68 | 4 | 10 | 82 |
| [start-all.sh](/start-all.sh) | Shell Script | 156 | 26 | 37 | 219 |
| [stop-all.sh](/stop-all.sh) | Shell Script | 41 | 6 | 13 | 60 |
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
| [website/docs/data-sources/ballot-election-sources.md](/website/docs/data-sources/ballot-election-sources.md) | Markdown | 321 | 0 | 87 | 408 |
| [website/docs/data-sources/census-acs.md](/website/docs/data-sources/census-acs.md) | Markdown | 320 | 0 | 131 | 451 |
| [website/docs/data-sources/census-data.md](/website/docs/data-sources/census-data.md) | Markdown | 72 | 0 | 33 | 105 |
| [website/docs/data-sources/census-shapefiles.md](/website/docs/data-sources/census-shapefiles.md) | Markdown | 270 | 0 | 99 | 369 |
| [website/docs/data-sources/charity-navigator.md](/website/docs/data-sources/charity-navigator.md) | Markdown | 297 | 0 | 102 | 399 |
| [website/docs/data-sources/citations.md](/website/docs/data-sources/citations.md) | Markdown | 2,115 | 0 | 508 | 2,623 |
| [website/docs/data-sources/council-data-project-compatibility.md](/website/docs/data-sources/council-data-project-compatibility.md) | Markdown | 165 | 0 | 53 | 218 |
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
| [website/docs/dbt/place-county-enrichment.md](/website/docs/dbt/place-county-enrichment.md) | Markdown | 234 | 0 | 55 | 289 |
| [website/docs/dbt/quick-reference.md](/website/docs/dbt/quick-reference.md) | Markdown | 233 | 0 | 78 | 311 |
| [website/docs/dbt/trending-causes.md](/website/docs/dbt/trending-causes.md) | Markdown | 163 | 0 | 54 | 217 |
| [website/docs/dbt/zcta-enrichment.md](/website/docs/dbt/zcta-enrichment.md) | Markdown | 263 | 0 | 72 | 335 |
| [website/docs/dbt/zcta-summary.md](/website/docs/dbt/zcta-summary.md) | Markdown | 140 | 0 | 45 | 185 |
| [website/docs/deployment/authentication-setup.md](/website/docs/deployment/authentication-setup.md) | Markdown | 326 | 0 | 124 | 450 |
| [website/docs/deployment/build-protection.md](/website/docs/deployment/build-protection.md) | Markdown | 246 | 0 | 88 | 334 |
| [website/docs/deployment/build-verification.md](/website/docs/deployment/build-verification.md) | Markdown | 173 | 0 | 60 | 233 |
| [website/docs/deployment/costs.md](/website/docs/deployment/costs.md) | Markdown | 179 | 0 | 62 | 241 |
| [website/docs/deployment/d-drive-configuration.md](/website/docs/deployment/d-drive-configuration.md) | Markdown | 355 | 0 | 149 | 504 |
| [website/docs/deployment/databricks-apps.md](/website/docs/deployment/databricks-apps.md) | Markdown | 298 | 0 | 104 | 402 |
| [website/docs/deployment/databricks-migration.md](/website/docs/deployment/databricks-migration.md) | Markdown | 224 | 0 | 53 | 277 |
| [website/docs/deployment/docker-troubleshooting.md](/website/docs/deployment/docker-troubleshooting.md) | Markdown | 279 | 0 | 103 | 382 |
| [website/docs/deployment/events-bronze-migration.md](/website/docs/deployment/events-bronze-migration.md) | Markdown | 253 | 0 | 60 | 313 |
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
| [website/docs/deployment/youtube-channels-bronze-migration.md](/website/docs/deployment/youtube-channels-bronze-migration.md) | Markdown | 251 | 0 | 85 | 336 |
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
| [website/docs/development/search-update-summary.md](/website/docs/development/search-update-summary.md) | Markdown | 216 | 0 | 65 | 281 |
| [website/docs/development/state-field-naming-standard.md](/website/docs/development/state-field-naming-standard.md) | Markdown | 212 | 0 | 62 | 274 |
| [website/docs/development/state-naming-migration.md](/website/docs/development/state-naming-migration.md) | Markdown | 177 | 0 | 49 | 226 |
| [website/docs/development/terminal-corruption-prevention.md](/website/docs/development/terminal-corruption-prevention.md) | Markdown | 76 | 0 | 26 | 102 |
| [website/docs/development/trending-causes-by-geography.md](/website/docs/development/trending-causes-by-geography.md) | Markdown | 229 | 0 | 70 | 299 |
| [website/docs/development/trending-causes-implementation.md](/website/docs/development/trending-causes-implementation.md) | Markdown | 175 | 0 | 52 | 227 |
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
| [website/docs/guides/google-colab-setup.md](/website/docs/guides/google-colab-setup.md) | Markdown | 400 | 0 | 137 | 537 |
| [website/docs/guides/hackathon-video-submission-ideas.md](/website/docs/guides/hackathon-video-submission-ideas.md) | Markdown | 105 | 0 | 94 | 199 |
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
| [website/docs/guides/open-states-legislative-data.md](/website/docs/guides/open-states-legislative-data.md) | Markdown | 849 | 0 | 175 | 1,024 |
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
| [website/docs/intro.md](/website/docs/intro.md) | Markdown | 204 | 0 | 68 | 272 |
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
| [website/docs/resources/nonprofit-resources.md](/website/docs/resources/nonprofit-resources.md) | Markdown | 50 | 0 | 27 | 77 |
| [website/docusaurus.config.ts](/website/docusaurus.config.ts) | TypeScript | 246 | 24 | 14 | 284 |
| [website/package-lock.json](/website/package-lock.json) | JSON | 20,802 | 0 | 1 | 20,803 |
| [website/package.json](/website/package.json) | JSON | 52 | 0 | 1 | 53 |
| [website/sidebars.ts](/website/sidebars.ts) | TypeScript | 458 | 22 | 9 | 489 |
| [website/src/components/HomepageFeatures/index.tsx](/website/src/components/HomepageFeatures/index.tsx) | TypeScript JSX | 67 | 0 | 5 | 72 |
| [website/src/components/HomepageFeatures/styles.module.css](/website/src/components/HomepageFeatures/styles.module.css) | PostCSS | 10 | 0 | 2 | 12 |
| [website/src/components/StructuredData.tsx](/website/src/components/StructuredData.tsx) | TypeScript JSX | 101 | 4 | 5 | 110 |
| [website/src/components/ZoomableMermaid/index.tsx](/website/src/components/ZoomableMermaid/index.tsx) | TypeScript JSX | 64 | 0 | 3 | 67 |
| [website/src/components/ZoomableMermaid/styles.module.css](/website/src/components/ZoomableMermaid/styles.module.css) | PostCSS | 147 | 3 | 24 | 174 |
| [website/src/css/custom.css](/website/src/css/custom.css) | PostCSS | 196 | 25 | 37 | 258 |
| [website/src/pages/dashboard.tsx](/website/src/pages/dashboard.tsx) | TypeScript JSX | 72 | 2 | 8 | 82 |
| [website/src/pages/index.module.css](/website/src/pages/index.module.css) | PostCSS | 16 | 4 | 4 | 24 |
| [website/src/pages/index.tsx](/website/src/pages/index.tsx) | TypeScript JSX | 508 | 7 | 29 | 544 |
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