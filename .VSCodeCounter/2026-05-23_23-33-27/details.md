# Details

Date : 2026-05-23 23:33:27

Directory /home/developer/projects/open-navigator

Total : 1193 files,  302275 codes, 39929 comments, 50411 blanks, all 392615 lines

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [.claude/settings.json](/.claude/settings.json) | JSON with Comments | 12 | 0 | 1 | 13 |
| [.github/copilot-instructions.md](/.github/copilot-instructions.md) | Markdown | 611 | 0 | 164 | 775 |
| [.github/workflows/ci-build-test.yml](/.github/workflows/ci-build-test.yml) | YAML | 119 | 6 | 26 | 151 |
| [.github/workflows/deploy-huggingface.yml](/.github/workflows/deploy-huggingface.yml) | YAML | 51 | 2 | 10 | 63 |
| [.huggingface/README.md](/.huggingface/README.md) | Markdown | 74 | 0 | 28 | 102 |
| [.huggingface/nginx.conf](/.huggingface/nginx.conf) | Properties | 103 | 18 | 22 | 143 |
| [.huggingface/start.sh](/.huggingface/start.sh) | Shell Script | 44 | 8 | 10 | 62 |
| [.huggingface/supervisord.conf](/.huggingface/supervisord.conf) | Properties | 26 | 0 | 3 | 29 |
| [CITATIONS.md](/CITATIONS.md) | Markdown | 1,774 | 0 | 355 | 2,129 |
| [CODE\_OF\_CONDUCT.md](/CODE_OF_CONDUCT.md) | Markdown | 28 | 0 | 20 | 48 |
| [CONTRIBUTING.md](/CONTRIBUTING.md) | Markdown | 72 | 0 | 28 | 100 |
| [Dockerfile](/Dockerfile) | Docker | 49 | 21 | 21 | 91 |
| [Makefile](/Makefile) | Makefile | 145 | 0 | 25 | 170 |
| [README.md](/README.md) | Markdown | 417 | 0 | 162 | 579 |
| [README\_HF.md](/README_HF.md) | Markdown | 74 | 0 | 28 | 102 |
| [\_\_init\_\_.py](/__init__.py) | Python | 17 | 1 | 4 | 22 |
| [agents/\_\_init\_\_.py](/agents/__init__.py) | Python | 14 | 1 | 2 | 17 |
| [agents/advocacy.py](/agents/advocacy.py) | Python | 298 | 58 | 53 | 409 |
| [agents/base.py](/agents/base.py) | Python | 97 | 47 | 25 | 169 |
| [agents/classifier.py](/agents/classifier.py) | Python | 189 | 67 | 40 | 296 |
| [agents/debate\_grader.py](/agents/debate_grader.py) | Python | 305 | 64 | 56 | 425 |
| [agents/mlflow\_base.py](/agents/mlflow_base.py) | Python | 162 | 108 | 38 | 308 |
| [agents/mlflow\_classifier.py](/agents/mlflow_classifier.py) | Python | 140 | 147 | 22 | 309 |
| [agents/orchestrator.py](/agents/orchestrator.py) | Python | 154 | 81 | 35 | 270 |
| [agents/parser.py](/agents/parser.py) | Python | 123 | 47 | 30 | 200 |
| [agents/policy\_reasoning\_analyzer.py](/agents/policy_reasoning_analyzer.py) | Python | 370 | 91 | 42 | 503 |
| [agents/scraper.py](/agents/scraper.py) | Python | 34 | 7 | 10 | 51 |
| [agents/scraper\_undetected.py](/agents/scraper_undetected.py) | Python | 173 | 46 | 43 | 262 |
| [agents/sentiment.py](/agents/sentiment.py) | Python | 248 | 73 | 61 | 382 |
| [agents/test\_policy\_analyzer.py](/agents/test_policy_analyzer.py) | Python | 72 | 14 | 27 | 113 |
| [alerts/keyword\_monitor.py](/alerts/keyword_monitor.py) | Python | 344 | 146 | 78 | 568 |
| [api/\_\_init\_\_.py](/api/__init__.py) | Python | 2 | 1 | 2 | 5 |
| [api/app.py](/api/app.py) | Python | 513 | 109 | 98 | 720 |
| [api/auth.py](/api/auth.py) | Python | 74 | 52 | 28 | 154 |
| [api/database.py](/api/database.py) | Python | 41 | 22 | 10 | 73 |
| [api/errors.py](/api/errors.py) | Python | 112 | 24 | 19 | 155 |
| [api/main.py](/api/main.py) | Python | 827 | 501 | 81 | 1,409 |
| [api/models.py](/api/models.py) | Python | 160 | 43 | 66 | 269 |
| [api/routes/\_\_init\_\_.py](/api/routes/__init__.py) | Python | 0 | 3 | 1 | 4 |
| [api/routes/auth.py](/api/routes/auth.py) | Python | 420 | 79 | 101 | 600 |
| [api/routes/bills.py](/api/routes/bills.py) | Python | 294 | 558 | 42 | 894 |
| [api/routes/bills\_neon.py](/api/routes/bills_neon.py) | Python | 425 | 678 | 40 | 1,143 |
| [api/routes/contact.py](/api/routes/contact.py) | Python | 41 | 65 | 13 | 119 |
| [api/routes/data\_deletion.py](/api/routes/data_deletion.py) | Python | 80 | 34 | 28 | 142 |
| [api/routes/hf\_search.py](/api/routes/hf_search.py) | Python | 90 | 67 | 26 | 183 |
| [api/routes/jurisdiction\_mapping.py](/api/routes/jurisdiction_mapping.py) | Python | 108 | 40 | 14 | 162 |
| [api/routes/lighthouse\_reports.py](/api/routes/lighthouse_reports.py) | Python | 167 | 54 | 31 | 252 |
| [api/routes/locations.py](/api/routes/locations.py) | Python | 110 | 57 | 22 | 189 |
| [api/routes/search.py](/api/routes/search.py) | Python | 872 | 669 | 178 | 1,719 |
| [api/routes/search\_postgres.py](/api/routes/search_postgres.py) | Python | 338 | 647 | 41 | 1,026 |
| [api/routes/social.py](/api/routes/social.py) | Python | 393 | 43 | 109 | 545 |
| [api/routes/stats.py](/api/routes/stats.py) | Python | 167 | 379 | 17 | 563 |
| [api/routes/stats\_neon.py](/api/routes/stats_neon.py) | Python | 241 | 193 | 32 | 466 |
| [api/routes/trending.py](/api/routes/trending.py) | Python | 157 | 42 | 43 | 242 |
| [api/static/assets/index-7vzWAgiE.css](/api/static/assets/index-7vzWAgiE.css) | PostCSS | 1 | 0 | 1 | 2 |
| [api/static/assets/index-CuLxv8We.js](/api/static/assets/index-CuLxv8We.js) | JavaScript | 223 | 0 | 21 | 244 |
| [api/static/communityone\_logo.svg](/api/static/communityone_logo.svg) | XML | 13 | 5 | 5 | 23 |
| [api/static/google6934fc6e3618949f.html](/api/static/google6934fc6e3618949f.html) | HTML | 1 | 0 | 0 | 1 |
| [api/static/index.html](/api/static/index.html) | HTML | 128 | 9 | 9 | 146 |
| [api/static/privacyfacebook.html](/api/static/privacyfacebook.html) | HTML | 244 | 0 | 33 | 277 |
| [api/static/sitemap-app.xml](/api/static/sitemap-app.xml) | XML | 89 | 5 | 19 | 113 |
| [api/static/sitemap.xml](/api/static/sitemap.xml) | XML | 11 | 2 | 4 | 17 |
| [api/utils/\_\_init\_\_.py](/api/utils/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [api/utils/formatters.py](/api/utils/formatters.py) | Python | 25 | 37 | 19 | 81 |
| [app.yaml](/app.yaml) | YAML | 31 | 2 | 5 | 38 |
| [claude.md](/claude.md) | Markdown | 77 | 0 | 16 | 93 |
| [config/\_\_init\_\_.py](/config/__init__.py) | Python | 2 | 1 | 2 | 5 |
| [config/settings.py](/config/settings.py) | Python | 80 | 24 | 23 | 127 |
| [databricks/README.md](/databricks/README.md) | Markdown | 279 | 0 | 71 | 350 |
| [databricks/communityone\_schema.sql](/databricks/communityone_schema.sql) | MS SQL | 501 | 88 | 53 | 642 |
| [databricks/deployment.py](/databricks/deployment.py) | Python | 193 | 108 | 44 | 345 |
| [databricks/evaluation.py](/databricks/evaluation.py) | Python | 162 | 146 | 36 | 344 |
| [databricks/notebooks/01\_agent\_bricks\_quickstart.py](/databricks/notebooks/01_agent_bricks_quickstart.py) | Python | 52 | 262 | 16 | 330 |
| [dbt\_project.yml](/dbt_project.yml) | YAML | 46 | 9 | 15 | 70 |
| [dbt\_project/.user.yml](/dbt_project/.user.yml) | YAML | 1 | 0 | 1 | 2 |
| [dbt\_project/MIGRATION\_PYTHON\_TO\_DBT.md](/dbt_project/MIGRATION_PYTHON_TO_DBT.md) | Markdown | 214 | 0 | 60 | 274 |
| [dbt\_project/QUICK\_REFERENCE.md](/dbt_project/QUICK_REFERENCE.md) | Markdown | 230 | 0 | 77 | 307 |
| [dbt\_project/README.md](/dbt_project/README.md) | Markdown | 198 | 0 | 78 | 276 |
| [dbt\_project/README\_TRENDING\_CAUSES.md](/dbt_project/README_TRENDING_CAUSES.md) | Markdown | 222 | 0 | 70 | 292 |
| [dbt\_project/analyses/audit\_county\_gsa\_naco\_domain\_mismatch.sql](/dbt_project/analyses/audit_county_gsa_naco_domain_mismatch.sql) | MS SQL | 19 | 2 | 2 | 23 |
| [dbt\_project/analyses/audit\_gsa\_domain\_types\_not\_in\_map.sql](/dbt_project/analyses/audit_gsa_domain_types_not_in_map.sql) | MS SQL | 38 | 3 | 2 | 43 |
| [dbt\_project/analyses/audit\_gsa\_mapping\_summary\_by\_state.sql](/dbt_project/analyses/audit_gsa_mapping_summary_by_state.sql) | MS SQL | 9 | 2 | 2 | 13 |
| [dbt\_project/analyses/audit\_gsa\_unmapped\_domains.sql](/dbt_project/analyses/audit_gsa_unmapped_domains.sql) | MS SQL | 12 | 3 | 2 | 17 |
| [dbt\_project/dbt\_project.yml](/dbt_project/dbt_project.yml) | YAML | 45 | 22 | 16 | 83 |
| [dbt\_project/macros/calculate\_confidence.sql](/dbt_project/macros/calculate_confidence.sql) | MS SQL | 11 | 8 | 1 | 20 |
| [dbt\_project/macros/generate\_schema\_name.sql](/dbt_project/macros/generate_schema_name.sql) | MS SQL | 8 | 0 | 4 | 12 |
| [dbt\_project/macros/jurisdiction\_acs\_exists.sql](/dbt_project/macros/jurisdiction_acs_exists.sql) | MS SQL | 8 | 0 | 1 | 9 |
| [dbt\_project/macros/jurisdiction\_mapping\_primary\_from\_source\_columns.sql](/dbt_project/macros/jurisdiction_mapping_primary_from_source_columns.sql) | MS SQL | 9 | 0 | 1 | 10 |
| [dbt\_project/macros/municipality\_name\_allows\_county\_portal\_url.sql](/dbt_project/macros/municipality_name_allows_county_portal_url.sql) | MS SQL | 9 | 0 | 1 | 10 |
| [dbt\_project/macros/normalize\_bill\_number.sql](/dbt_project/macros/normalize_bill_number.sql) | MS SQL | 14 | 11 | 1 | 26 |
| [dbt\_project/macros/normalize\_jurisdiction\_label\_for\_match.sql](/dbt_project/macros/normalize_jurisdiction_label_for_match.sql) | MS SQL | 41 | 0 | 1 | 42 |
| [dbt\_project/macros/normalize\_name.sql](/dbt_project/macros/normalize_name.sql) | MS SQL | 11 | 11 | 1 | 23 |
| [dbt\_project/macros/uscm\_league\_county\_portal\_blocked.sql](/dbt_project/macros/uscm_league_county_portal_blocked.sql) | MS SQL | 6 | 0 | 1 | 7 |
| [dbt\_project/macros/website\_domain\_is\_county\_portal\_host.sql](/dbt_project/macros/website_domain_is_county_portal_host.sql) | MS SQL | 6 | 0 | 1 | 7 |
| [dbt\_project/models/bronze/bronze\_bills\_from\_ai.sql](/dbt_project/models/bronze/bronze_bills_from_ai.sql) | MS SQL | 65 | 12 | 8 | 85 |
| [dbt\_project/models/bronze/bronze\_causes\_from\_ai.sql](/dbt_project/models/bronze/bronze_causes_from_ai.sql) | MS SQL | 76 | 18 | 10 | 104 |
| [dbt\_project/models/bronze/bronze\_contacts\_from\_ai.sql](/dbt_project/models/bronze/bronze_contacts_from_ai.sql) | MS SQL | 63 | 16 | 8 | 87 |
| [dbt\_project/models/bronze/bronze\_decisions\_from\_ai.sql](/dbt_project/models/bronze/bronze_decisions_from_ai.sql) | MS SQL | 111 | 18 | 12 | 141 |
| [dbt\_project/models/bronze/bronze\_events\_youtube.sql](/dbt_project/models/bronze/bronze_events_youtube.sql) | MS SQL | 41 | 20 | 15 | 76 |
| [dbt\_project/models/bronze/bronze\_financial\_items\_from\_ai.sql](/dbt_project/models/bronze/bronze_financial_items_from_ai.sql) | MS SQL | 75 | 14 | 8 | 97 |
| [dbt\_project/models/bronze/bronze\_organizations\_from\_ai.sql](/dbt_project/models/bronze/bronze_organizations_from_ai.sql) | MS SQL | 109 | 19 | 9 | 137 |
| [dbt\_project/models/bronze/bronze\_topics\_from\_ai.sql](/dbt_project/models/bronze/bronze_topics_from_ai.sql) | MS SQL | 71 | 14 | 8 | 93 |
| [dbt\_project/models/intermediate/\_intermediate.yml](/dbt_project/models/intermediate/_intermediate.yml) | YAML | 523 | 0 | 28 | 551 |
| [dbt\_project/models/intermediate/int\_events\_channels.sql](/dbt_project/models/intermediate/int_events_channels.sql) | MS SQL | 671 | 32 | 47 | 750 |
| [dbt\_project/models/intermediate/int\_events\_channels\_enriched.sql](/dbt_project/models/intermediate/int_events_channels_enriched.sql) | MS SQL | 61 | 19 | 12 | 92 |
| [dbt\_project/models/intermediate/int\_events\_localview.sql](/dbt_project/models/intermediate/int_events_localview.sql) | MS SQL | 24 | 8 | 3 | 35 |
| [dbt\_project/models/intermediate/int\_jurisdiction\_homepage\_youtube\_channels.sql](/dbt_project/models/intermediate/int_jurisdiction_homepage_youtube_channels.sql) | MS SQL | 259 | 7 | 15 | 281 |
| [dbt\_project/models/intermediate/int\_jurisdiction\_websites.sql](/dbt_project/models/intermediate/int_jurisdiction_websites.sql) | MS SQL | 922 | 36 | 45 | 1,003 |
| [dbt\_project/models/intermediate/int\_jurisdictions.sql](/dbt_project/models/intermediate/int_jurisdictions.sql) | MS SQL | 376 | 26 | 15 | 417 |
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
| [dbt\_project/models/marts/event.sql](/dbt_project/models/marts/event.sql) | MS SQL | 113 | 29 | 13 | 155 |
| [dbt\_project/models/marts/events\_channels\_search.sql](/dbt_project/models/marts/events_channels_search.sql) | MS SQL | 57 | 27 | 13 | 97 |
| [dbt\_project/models/marts/events\_text\_search.sql](/dbt_project/models/marts/events_text_search.sql) | MS SQL | 90 | 17 | 8 | 115 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_analysis.sql](/dbt_project/models/marts/jurisdiction_mapping_analysis.sql) | MS SQL | 233 | 19 | 8 | 260 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_analysis\_sources.sql](/dbt_project/models/marts/jurisdiction_mapping_analysis_sources.sql) | MS SQL | 20 | 4 | 3 | 27 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary.sql) | MS SQL | 51 | 9 | 3 | 63 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary\_by\_acs\_income\_level.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary_by_acs_income_level.sql) | MS SQL | 53 | 5 | 3 | 61 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary\_by\_acs\_population\_tier.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary_by_acs_population_tier.sql) | MS SQL | 53 | 5 | 3 | 61 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary\_municipality\_places.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary_municipality_places.sql) | MS SQL | 53 | 11 | 3 | 67 |
| [dbt\_project/models/marts/jurisdiction\_state\_aggregate.sql](/dbt_project/models/marts/jurisdiction_state_aggregate.sql) | MS SQL | 268 | 44 | 29 | 341 |
| [dbt\_project/models/marts/jurisdictions.sql](/dbt_project/models/marts/jurisdictions.sql) | MS SQL | 49 | 32 | 16 | 97 |
| [dbt\_project/models/marts/organization\_nonprofit.sql](/dbt_project/models/marts/organization_nonprofit.sql) | MS SQL | 148 | 16 | 6 | 170 |
| [dbt\_project/models/marts/organizations\_nonprofits.sql](/dbt_project/models/marts/organizations_nonprofits.sql) | MS SQL | 143 | 38 | 27 | 208 |
| [dbt\_project/models/staging/\_staging.yml](/dbt_project/models/staging/_staging.yml) | YAML | 930 | 0 | 55 | 985 |
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
| [docker-compose.socks-proxy.example.yml](/docker-compose.socks-proxy.example.yml) | YAML | 6 | 7 | 2 | 15 |
| [docker-compose.verapdf.example.yml](/docker-compose.verapdf.example.yml) | YAML | 19 | 7 | 2 | 28 |
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
| [docs/EBOARD\_MANUAL\_DOWNLOAD.md](/docs/EBOARD_MANUAL_DOWNLOAD.md) | Markdown | 159 | 0 | 46 | 205 |
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
| [docs/meetings\_scrape\_big\_timber\_tuscaloosa\_inventory.md](/docs/meetings_scrape_big_timber_tuscaloosa_inventory.md) | Markdown | 24 | 0 | 8 | 32 |
| [examples/README.md](/examples/README.md) | Markdown | 365 | 0 | 114 | 479 |
| [extraction/accountability\_dashboards.py](/extraction/accountability_dashboards.py) | Python | 391 | 137 | 87 | 615 |
| [extraction/budget\_analyzer.py](/extraction/budget_analyzer.py) | Python | 155 | 202 | 23 | 380 |
| [extraction/decision\_analyzer.py](/extraction/decision_analyzer.py) | Python | 408 | 110 | 45 | 563 |
| [extraction/summarizer.py](/extraction/summarizer.py) | Python | 187 | 216 | 49 | 452 |
| [extraction/temporal\_analyzer.py](/extraction/temporal_analyzer.py) | Python | 226 | 65 | 55 | 346 |
| [extraction/universal\_extractor.py](/extraction/universal_extractor.py) | Python | 248 | 65 | 71 | 384 |
| [frontend/.eslintrc.cjs](/frontend/.eslintrc.cjs) | JavaScript | 18 | 0 | 1 | 19 |
| [frontend/README.md](/frontend/README.md) | Markdown | 126 | 0 | 41 | 167 |
| [frontend/index.html](/frontend/index.html) | HTML | 127 | 9 | 9 | 145 |
| [frontend/package-lock.json](/frontend/package-lock.json) | JSON | 5,336 | 0 | 1 | 5,337 |
| [frontend/package.json](/frontend/package.json) | JSON | 49 | 0 | 1 | 50 |
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
| [frontend/src/App.tsx](/frontend/src/App.tsx) | TypeScript JSX | 135 | 6 | 9 | 150 |
| [frontend/src/api/jurisdictionMappingUnmapped.ts](/frontend/src/api/jurisdictionMappingUnmapped.ts) | TypeScript | 60 | 2 | 7 | 69 |
| [frontend/src/components/AddressLookup.tsx](/frontend/src/components/AddressLookup.tsx) | TypeScript JSX | 614 | 28 | 62 | 704 |
| [frontend/src/components/CensusRaceBarChart.tsx](/frontend/src/components/CensusRaceBarChart.tsx) | TypeScript JSX | 336 | 17 | 21 | 374 |
| [frontend/src/components/DataExplorerLayout.tsx](/frontend/src/components/DataExplorerLayout.tsx) | TypeScript JSX | 83 | 1 | 5 | 89 |
| [frontend/src/components/ExploreQuickNavSidebarPanel.tsx](/frontend/src/components/ExploreQuickNavSidebarPanel.tsx) | TypeScript JSX | 14 | 5 | 2 | 21 |
| [frontend/src/components/FollowButton.tsx](/frontend/src/components/FollowButton.tsx) | TypeScript JSX | 147 | 4 | 10 | 161 |
| [frontend/src/components/GiniInequalityReadout.tsx](/frontend/src/components/GiniInequalityReadout.tsx) | TypeScript JSX | 44 | 2 | 3 | 49 |
| [frontend/src/components/HeroLicensePlateBadge.tsx](/frontend/src/components/HeroLicensePlateBadge.tsx) | TypeScript JSX | 251 | 2 | 22 | 275 |
| [frontend/src/components/HomeExploreQuickNav.tsx](/frontend/src/components/HomeExploreQuickNav.tsx) | TypeScript JSX | 276 | 8 | 19 | 303 |
| [frontend/src/components/InfoHelpTrigger.tsx](/frontend/src/components/InfoHelpTrigger.tsx) | TypeScript JSX | 34 | 6 | 4 | 44 |
| [frontend/src/components/JurisdictionDiscovery.tsx](/frontend/src/components/JurisdictionDiscovery.tsx) | TypeScript JSX | 239 | 13 | 17 | 269 |
| [frontend/src/components/Layout.tsx](/frontend/src/components/Layout.tsx) | TypeScript JSX | 558 | 16 | 24 | 598 |
| [frontend/src/components/MultiSelect.tsx](/frontend/src/components/MultiSelect.tsx) | TypeScript JSX | 128 | 2 | 8 | 138 |
| [frontend/src/components/RegistrationModal.tsx](/frontend/src/components/RegistrationModal.tsx) | TypeScript JSX | 192 | 7 | 18 | 217 |
| [frontend/src/components/ScorecardTrendAndGiniLegend.tsx](/frontend/src/components/ScorecardTrendAndGiniLegend.tsx) | TypeScript JSX | 73 | 3 | 5 | 81 |
| [frontend/src/components/ScrollToTop.tsx](/frontend/src/components/ScrollToTop.tsx) | TypeScript JSX | 9 | 4 | 4 | 17 |
| [frontend/src/components/SocialStats.tsx](/frontend/src/components/SocialStats.tsx) | TypeScript JSX | 106 | 2 | 14 | 122 |
| [frontend/src/components/USMap.tsx](/frontend/src/components/USMap.tsx) | TypeScript JSX | 461 | 46 | 60 | 567 |
| [frontend/src/contexts/AuthContext.tsx](/frontend/src/contexts/AuthContext.tsx) | TypeScript JSX | 122 | 9 | 19 | 150 |
| [frontend/src/contexts/LocationContext.tsx](/frontend/src/contexts/LocationContext.tsx) | TypeScript JSX | 77 | 7 | 19 | 103 |
| [frontend/src/index.css](/frontend/src/index.css) | PostCSS | 712 | 8 | 33 | 753 |
| [frontend/src/lib/api.ts](/frontend/src/lib/api.ts) | TypeScript | 123 | 16 | 26 | 165 |
| [frontend/src/main.tsx](/frontend/src/main.tsx) | TypeScript JSX | 37 | 0 | 3 | 40 |
| [frontend/src/pages/AdvocacyTopics.tsx](/frontend/src/pages/AdvocacyTopics.tsx) | TypeScript JSX | 217 | 5 | 8 | 230 |
| [frontend/src/pages/Analytics.tsx](/frontend/src/pages/Analytics.tsx) | TypeScript JSX | 204 | 32 | 14 | 250 |
| [frontend/src/pages/BillDetail.tsx](/frontend/src/pages/BillDetail.tsx) | TypeScript JSX | 248 | 7 | 15 | 270 |
| [frontend/src/pages/CensusMapPage.tsx](/frontend/src/pages/CensusMapPage.tsx) | TypeScript JSX | 3,626 | 45 | 207 | 3,878 |
| [frontend/src/pages/Dashboard.tsx](/frontend/src/pages/Dashboard.tsx) | TypeScript JSX | 183 | 6 | 13 | 202 |
| [frontend/src/pages/DataExplorerScorecardPage.tsx](/frontend/src/pages/DataExplorerScorecardPage.tsx) | TypeScript JSX | 1,353 | 7 | 82 | 1,442 |
| [frontend/src/pages/DebateGrader.tsx](/frontend/src/pages/DebateGrader.tsx) | TypeScript JSX | 245 | 8 | 22 | 275 |
| [frontend/src/pages/Developers.tsx](/frontend/src/pages/Developers.tsx) | TypeScript JSX | 182 | 8 | 11 | 201 |
| [frontend/src/pages/Documents.tsx](/frontend/src/pages/Documents.tsx) | TypeScript JSX | 216 | 5 | 13 | 234 |
| [frontend/src/pages/Events.tsx](/frontend/src/pages/Events.tsx) | TypeScript JSX | 105 | 6 | 6 | 117 |
| [frontend/src/pages/Explore.tsx](/frontend/src/pages/Explore.tsx) | TypeScript JSX | 472 | 0 | 25 | 497 |
| [frontend/src/pages/FactChecking.tsx](/frontend/src/pages/FactChecking.tsx) | TypeScript JSX | 252 | 6 | 11 | 269 |
| [frontend/src/pages/Hackathons.tsx](/frontend/src/pages/Hackathons.tsx) | TypeScript JSX | 235 | 10 | 12 | 257 |
| [frontend/src/pages/Heatmap.tsx](/frontend/src/pages/Heatmap.tsx) | TypeScript JSX | 159 | 4 | 13 | 176 |
| [frontend/src/pages/Home.tsx](/frontend/src/pages/Home.tsx) | TypeScript JSX | 1,697 | 80 | 96 | 1,873 |
| [frontend/src/pages/HomeModern.tsx](/frontend/src/pages/HomeModern.tsx) | TypeScript JSX | 1,263 | 75 | 80 | 1,418 |
| [frontend/src/pages/JurisdictionMappingQualityPage.tsx](/frontend/src/pages/JurisdictionMappingQualityPage.tsx) | TypeScript JSX | 62 | 0 | 8 | 70 |
| [frontend/src/pages/JurisdictionsSearch.tsx](/frontend/src/pages/JurisdictionsSearch.tsx) | TypeScript JSX | 684 | 33 | 51 | 768 |
| [frontend/src/pages/LighthouseReportPage.tsx](/frontend/src/pages/LighthouseReportPage.tsx) | TypeScript JSX | 300 | 1 | 22 | 323 |
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
| [frontend/src/pages/jurisdiction-quality/EntityQualityDashboard.tsx](/frontend/src/pages/jurisdiction-quality/EntityQualityDashboard.tsx) | TypeScript JSX | 2,527 | 17 | 110 | 2,654 |
| [frontend/src/utils/censusDataDictionary.ts](/frontend/src/utils/censusDataDictionary.ts) | TypeScript | 253 | 22 | 19 | 294 |
| [frontend/src/utils/censusMapNarrative.ts](/frontend/src/utils/censusMapNarrative.ts) | TypeScript | 400 | 22 | 39 | 461 |
| [frontend/src/utils/censusMapTransforms.ts](/frontend/src/utils/censusMapTransforms.ts) | TypeScript | 267 | 40 | 25 | 332 |
| [frontend/src/utils/censusMapValueMode.ts](/frontend/src/utils/censusMapValueMode.ts) | TypeScript | 192 | 20 | 16 | 228 |
| [frontend/src/utils/censusRegions.ts](/frontend/src/utils/censusRegions.ts) | TypeScript | 70 | 2 | 4 | 76 |
| [frontend/src/utils/communityLocationLabel.ts](/frontend/src/utils/communityLocationLabel.ts) | TypeScript | 11 | 1 | 2 | 14 |
| [frontend/src/utils/dataExplorerPaths.ts](/frontend/src/utils/dataExplorerPaths.ts) | TypeScript | 25 | 5 | 8 | 38 |
| [frontend/src/utils/dataExplorerScorecardHelpers.ts](/frontend/src/utils/dataExplorerScorecardHelpers.ts) | TypeScript | 300 | 13 | 27 | 340 |
| [frontend/src/utils/formatters.ts](/frontend/src/utils/formatters.ts) | TypeScript | 26 | 10 | 6 | 42 |
| [frontend/src/utils/giniLetterGrade.ts](/frontend/src/utils/giniLetterGrade.ts) | TypeScript | 96 | 9 | 8 | 113 |
| [frontend/src/utils/huggingface.ts](/frontend/src/utils/huggingface.ts) | TypeScript | 161 | 107 | 35 | 303 |
| [frontend/src/utils/stateMapping.ts](/frontend/src/utils/stateMapping.ts) | TypeScript | 90 | 19 | 9 | 118 |
| [frontend/src/utils/wikicommonsLicensePlate.ts](/frontend/src/utils/wikicommonsLicensePlate.ts) | TypeScript | 20 | 12 | 6 | 38 |
| [frontend/src/vite-env.d.ts](/frontend/src/vite-env.d.ts) | TypeScript | 6 | 2 | 3 | 11 |
| [frontend/tailwind.config.js](/frontend/tailwind.config.js) | JavaScript | 51 | 1 | 1 | 53 |
| [frontend/tsconfig.json](/frontend/tsconfig.json) | JSON with Comments | 21 | 2 | 3 | 26 |
| [frontend/tsconfig.node.json](/frontend/tsconfig.node.json) | JSON | 10 | 0 | 1 | 11 |
| [frontend/vite.config.ts](/frontend/vite.config.ts) | TypeScript | 33 | 2 | 2 | 37 |
| [main.py](/main.py) | Python | 302 | 42 | 92 | 436 |
| [models/meeting\_event.py](/models/meeting_event.py) | Python | 220 | 71 | 51 | 342 |
| [notebooks/Jurisdiction\_Discovery.py](/notebooks/Jurisdiction_Discovery.py) | Python | 76 | 168 | 64 | 308 |
| [notebooks/example\_analysis.py](/notebooks/example_analysis.py) | Python | 101 | 59 | 52 | 212 |
| [output/TUSCALOOSA\_ADVOCACY\_BRIEF.md](/output/TUSCALOOSA_ADVOCACY_BRIEF.md) | Markdown | 83 | 0 | 62 | 145 |
| [output/tuscaloosa/suiteonemedia\_20260503\_041932.json](/output/tuscaloosa/suiteonemedia_20260503_041932.json) | JSON | 404 | 0 | 0 | 404 |
| [output/tuscaloosa\_accountability\_dashboards.json](/output/tuscaloosa_accountability_dashboards.json) | JSON | 9 | 0 | 0 | 9 |
| [package-lock.yml](/package-lock.yml) | YAML | 11 | 0 | 1 | 12 |
| [packages.yml](/packages.yml) | YAML | 5 | 0 | 1 | 6 |
| [pipeline/\_\_init\_\_.py](/pipeline/__init__.py) | Python | 2 | 1 | 2 | 5 |
| [pipeline/create\_campaigns\_gold\_tables.py](/pipeline/create_campaigns_gold_tables.py) | Python | 359 | 133 | 91 | 583 |
| [pipeline/create\_contacts\_gold\_tables.py](/pipeline/create_contacts_gold_tables.py) | Python | 339 | 127 | 107 | 573 |
| [pipeline/create\_events\_gold\_tables.py](/pipeline/create_events_gold_tables.py) | Python | 219 | 66 | 77 | 362 |
| [pipeline/create\_grants\_gold\_tables.py](/pipeline/create_grants_gold_tables.py) | Python | 182 | 110 | 43 | 335 |
| [pipeline/create\_meetings\_gold\_tables.py](/pipeline/create_meetings_gold_tables.py) | Python | 219 | 66 | 77 | 362 |
| [pipeline/create\_nonprofits\_gold\_tables.py](/pipeline/create_nonprofits_gold_tables.py) | Python | 318 | 117 | 78 | 513 |
| [pipeline/delta\_lake.py](/pipeline/delta_lake.py) | Python | 274 | 75 | 7 | 356 |
| [pipeline/delta\_lake\_queries.py](/pipeline/delta_lake_queries.py) | Python | 84 | 122 | 2 | 208 |
| [pipeline/huggingface\_publisher.py](/pipeline/huggingface_publisher.py) | Python | 226 | 137 | 79 | 442 |
| [prompts/polcy\_analysis\_readable.md](/prompts/polcy_analysis_readable.md) | Markdown | 233 | 0 | 45 | 278 |
| [prompts/policy\_analysis.md](/prompts/policy_analysis.md) | Markdown | 652 | 0 | 48 | 700 |
| [prompts/policy\_analysis\_concsie.md](/prompts/policy_analysis_concsie.md) | Markdown | 146 | 0 | 18 | 164 |
| [prompts/policy\_analysis\_part\_1.md](/prompts/policy_analysis_part_1.md) | Markdown | 275 | 0 | 29 | 304 |
| [prompts/policy\_analysis\_part\_2.md](/prompts/policy_analysis_part_2.md) | Markdown | 63 | 0 | 27 | 90 |
| [prompts/policy\_analysis\_sample\_inputs.md](/prompts/policy_analysis_sample_inputs.md) | Markdown | 10 | 0 | 0 | 10 |
| [prompts/policy\_analysis\_v1.md](/prompts/policy_analysis_v1.md) | Markdown | 788 | 0 | 76 | 864 |
| [pytest.ini](/pytest.ini) | Ini | 5 | 0 | 1 | 6 |
| [requirements.txt](/requirements.txt) | pip requirements | 79 | 25 | 16 | 120 |
| [scripts/README.md](/scripts/README.md) | Markdown | 157 | 0 | 46 | 203 |
| [scripts/\_\_init\_\_.py](/scripts/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/accessibility/README.md](/scripts/accessibility/README.md) | Markdown | 193 | 0 | 70 | 263 |
| [scripts/accessibility/\_\_init\_\_.py](/scripts/accessibility/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [scripts/accessibility/\_int\_websites.py](/scripts/accessibility/_int_websites.py) | Python | 11 | 2 | 6 | 19 |
| [scripts/accessibility/docker\_entrypoint.py](/scripts/accessibility/docker_entrypoint.py) | Python | 54 | 2 | 12 | 68 |
| [scripts/accessibility/export\_pdf\_urls.py](/scripts/accessibility/export_pdf_urls.py) | Python | 182 | 11 | 25 | 218 |
| [scripts/accessibility/export\_urls.py](/scripts/accessibility/export_urls.py) | Python | 86 | 99 | 14 | 199 |
| [scripts/accessibility/lambda\_handler.py](/scripts/accessibility/lambda_handler.py) | Python | 134 | 20 | 12 | 166 |
| [scripts/accessibility/pa11yci.config.cjs](/scripts/accessibility/pa11yci.config.cjs) | JavaScript | 21 | 4 | 2 | 27 |
| [scripts/accessibility/package-lock.json](/scripts/accessibility/package-lock.json) | JSON | 3,853 | 0 | 1 | 3,854 |
| [scripts/accessibility/package.json](/scripts/accessibility/package.json) | JSON | 21 | 0 | 1 | 22 |
| [scripts/accessibility/persist\_lighthouse\_results.py](/scripts/accessibility/persist_lighthouse_results.py) | Python | 100 | 160 | 6 | 266 |
| [scripts/accessibility/persist\_results.py](/scripts/accessibility/persist_results.py) | Python | 254 | 47 | 31 | 332 |
| [scripts/accessibility/persist\_verapdf\_results.py](/scripts/accessibility/persist_verapdf_results.py) | Python | 49 | 118 | 6 | 173 |
| [scripts/accessibility/run\_accessibility\_scan.sh](/scripts/accessibility/run_accessibility_scan.sh) | Shell Script | 103 | 8 | 12 | 123 |
| [scripts/accessibility/run\_axe\_scan.mjs](/scripts/accessibility/run_axe_scan.mjs) | JavaScript | 150 | 8 | 17 | 175 |
| [scripts/accessibility/run\_lighthouse\_scan.mjs](/scripts/accessibility/run_lighthouse_scan.mjs) | JavaScript | 209 | 19 | 27 | 255 |
| [scripts/accessibility/run\_pa11y\_workers.mjs](/scripts/accessibility/run_pa11y_workers.mjs) | JavaScript | 173 | 15 | 21 | 209 |
| [scripts/accessibility/run\_verapdf\_scan.py](/scripts/accessibility/run_verapdf_scan.py) | Python | 172 | 12 | 30 | 214 |
| [scripts/accessibility/run\_verapdf\_scan.sh](/scripts/accessibility/run_verapdf_scan.sh) | Shell Script | 55 | 7 | 10 | 72 |
| [scripts/accessibility/sql/bronze\_jurisdiction\_pdf\_verapdf.sql](/scripts/accessibility/sql/bronze_jurisdiction_pdf_verapdf.sql) | MS SQL | 32 | 2 | 7 | 41 |
| [scripts/accessibility/sql/bronze\_jurisdiction\_website\_accessibility.sql](/scripts/accessibility/sql/bronze_jurisdiction_website_accessibility.sql) | MS SQL | 31 | 3 | 7 | 41 |
| [scripts/accessibility/sql/bronze\_jurisdiction\_website\_lighthouse.sql](/scripts/accessibility/sql/bronze_jurisdiction_website_lighthouse.sql) | MS SQL | 66 | 4 | 8 | 78 |
| [scripts/accessibility/verapdf\_cli.py](/scripts/accessibility/verapdf_cli.py) | Python | 154 | 4 | 24 | 182 |
| [scripts/colab/01\_copy\_scraped\_meetings\_cache\_to\_gdrive.py](/scripts/colab/01_copy_scraped_meetings_cache_to_gdrive.py) | Python | 308 | 29 | 35 | 372 |
| [scripts/colab/02\_run\_meeting\_llm.ipynb](/scripts/colab/02_run_meeting_llm.ipynb) | JSON | 2,306 | 0 | 1 | 2,307 |
| [scripts/colab/README.md](/scripts/colab/README.md) | Markdown | 140 | 0 | 50 | 190 |
| [scripts/colab/colab\_bootstrap.py](/scripts/colab/colab_bootstrap.py) | Python | 161 | 23 | 32 | 216 |
| [scripts/colab/colab\_demos.py](/scripts/colab/colab_demos.py) | Python | 1,265 | 23 | 74 | 1,362 |
| [scripts/colab/colab\_local\_raw\_mirror.py](/scripts/colab/colab_local_raw_mirror.py) | Python | 145 | 23 | 32 | 200 |
| [scripts/colab/colab\_notebook\_ui.py](/scripts/colab/colab_notebook_ui.py) | Python | 149 | 17 | 29 | 195 |
| [scripts/colab/colab\_paths.py](/scripts/colab/colab_paths.py) | Python | 63 | 24 | 23 | 110 |
| [scripts/colab/colab\_public\_data.py](/scripts/colab/colab_public_data.py) | Python | 276 | 22 | 49 | 347 |
| [scripts/colab/colab\_runtime\_phases.py](/scripts/colab/colab_runtime_phases.py) | Python | 101 | 13 | 22 | 136 |
| [scripts/colab/colab\_safety\_review.py](/scripts/colab/colab_safety_review.py) | Python | 215 | 11 | 37 | 263 |
| [scripts/colab/colab\_timed\_steps.py](/scripts/colab/colab_timed_steps.py) | Python | 128 | 19 | 29 | 176 |
| [scripts/colab/demo\_scope.py](/scripts/colab/demo_scope.py) | Python | 254 | 14 | 34 | 302 |
| [scripts/colab/gatekeeper\_triage.py](/scripts/colab/gatekeeper_triage.py) | Python | 1,975 | 262 | 292 | 2,529 |
| [scripts/colab/gemma\_hf\_backend.py](/scripts/colab/gemma_hf_backend.py) | Python | 633 | 87 | 141 | 861 |
| [scripts/colab/genai\_quota\_retry.py](/scripts/colab/genai_quota_retry.py) | Python | 90 | 12 | 19 | 121 |
| [scripts/colab/governance\_meeting\_llm.py](/scripts/colab/governance_meeting_llm.py) | Python | 1,939 | 380 | 326 | 2,645 |
| [scripts/colab/jurisdiction\_pipeline.py](/scripts/colab/jurisdiction_pipeline.py) | Python | 438 | 21 | 59 | 518 |
| [scripts/colab/media\_playback\_links.py](/scripts/colab/media_playback_links.py) | Python | 321 | 21 | 39 | 381 |
| [scripts/colab/meeting\_consolidated\_summary.py](/scripts/colab/meeting_consolidated_summary.py) | Python | 867 | 26 | 92 | 985 |
| [scripts/colab/meeting\_date\_scope.py](/scripts/colab/meeting_date_scope.py) | Python | 704 | 88 | 108 | 900 |
| [scripts/colab/meeting\_grouping.py](/scripts/colab/meeting_grouping.py) | Python | 1,181 | 87 | 161 | 1,429 |
| [scripts/colab/mount\_drive.sh](/scripts/colab/mount_drive.sh) | Shell Script | 5 | 1 | 3 | 9 |
| [scripts/colab/pipeline\_logging.py](/scripts/colab/pipeline_logging.py) | Python | 342 | 13 | 58 | 413 |
| [scripts/colab/pipeline\_media\_scope.py](/scripts/colab/pipeline_media_scope.py) | Python | 214 | 22 | 39 | 275 |
| [scripts/colab/pipeline\_output\_links.py](/scripts/colab/pipeline_output_links.py) | Python | 172 | 11 | 27 | 210 |
| [scripts/colab/probe\_google\_gemma\_studio.py](/scripts/colab/probe_google_gemma_studio.py) | Python | 30 | 2 | 8 | 40 |
| [scripts/colab/theme\_audit.py](/scripts/colab/theme_audit.py) | Python | 96 | 8 | 11 | 115 |
| [scripts/database/target\_database\_url.py](/scripts/database/target_database_url.py) | Python | 18 | 9 | 6 | 33 |
| [scripts/datasources/README.md](/scripts/datasources/README.md) | Markdown | 106 | 0 | 40 | 146 |
| [scripts/datasources/\_\_init\_\_.py](/scripts/datasources/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/ballotpedia/README.md](/scripts/datasources/ballotpedia/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/ballotpedia/ballotpedia\_integration.py](/scripts/datasources/ballotpedia/ballotpedia_integration.py) | Python | 361 | 215 | 104 | 680 |
| [scripts/datasources/cdp/README.md](/scripts/datasources/cdp/README.md) | Markdown | 187 | 0 | 75 | 262 |
| [scripts/datasources/cdp/example\_fetch.py](/scripts/datasources/cdp/example_fetch.py) | Python | 56 | 21 | 15 | 92 |
| [scripts/datasources/cdp/load\_cdp\_api.py](/scripts/datasources/cdp/load_cdp_api.py) | Python | 222 | 41 | 45 | 308 |
| [scripts/datasources/cdp/load\_cdp\_events.py](/scripts/datasources/cdp/load_cdp_events.py) | Python | 183 | 74 | 50 | 307 |
| [scripts/datasources/census/DATASETS.md](/scripts/datasources/census/DATASETS.md) | Markdown | 239 | 0 | 84 | 323 |
| [scripts/datasources/census/README.md](/scripts/datasources/census/README.md) | Markdown | 156 | 0 | 61 | 217 |
| [scripts/datasources/census/STATUS.md](/scripts/datasources/census/STATUS.md) | Markdown | 189 | 0 | 59 | 248 |
| [scripts/datasources/census/\_\_init\_\_.py](/scripts/datasources/census/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/census/add\_jurisdiction\_columns\_to\_search.sql](/scripts/datasources/census/add_jurisdiction_columns_to_search.sql) | MS SQL | 19 | 11 | 5 | 35 |
| [scripts/datasources/census/download\_census\_acs.sh](/scripts/datasources/census/download_census_acs.sh) | Shell Script | 25 | 19 | 7 | 51 |
| [scripts/datasources/census/download\_census\_acs\_data.py](/scripts/datasources/census/download_census_acs_data.py) | Python | 492 | 113 | 75 | 680 |
| [scripts/datasources/census/download\_census\_gazetteer.py](/scripts/datasources/census/download_census_gazetteer.py) | Python | 144 | 29 | 36 | 209 |
| [scripts/datasources/census/download\_census\_municipalities.py](/scripts/datasources/census/download_census_municipalities.py) | Python | 41 | 25 | 20 | 86 |
| [scripts/datasources/census/download\_census\_relationships.py](/scripts/datasources/census/download_census_relationships.py) | Python | 138 | 54 | 38 | 230 |
| [scripts/datasources/census/download\_census\_school\_districts.py](/scripts/datasources/census/download_census_school_districts.py) | Python | 151 | 43 | 40 | 234 |
| [scripts/datasources/census/download\_census\_shapefiles.py](/scripts/datasources/census/download_census_shapefiles.py) | Python | 155 | 72 | 45 | 272 |
| [scripts/datasources/census/enrich\_jurisdictions\_county\_fips.py](/scripts/datasources/census/enrich_jurisdictions_county_fips.py) | Python | 113 | 220 | 21 | 354 |
| [scripts/datasources/census/enrich\_nonprofits\_with\_county\_fips.sql](/scripts/datasources/census/enrich_nonprofits_with_county_fips.sql) | MS SQL | 173 | 23 | 19 | 215 |
| [scripts/datasources/census/enrich\_nonprofits\_with\_place\_geoid.sql](/scripts/datasources/census/enrich_nonprofits_with_place_geoid.sql) | MS SQL | 103 | 21 | 15 | 139 |
| [scripts/datasources/census/export\_census\_map\_static.py](/scripts/datasources/census/export_census_map_static.py) | Python | 720 | 59 | 72 | 851 |
| [scripts/datasources/census/fix\_geoid\_format.py](/scripts/datasources/census/fix_geoid_format.py) | Python | 45 | 63 | 8 | 116 |
| [scripts/datasources/census/link\_cities\_counties\_to\_search.py](/scripts/datasources/census/link_cities_counties_to_search.py) | Python | 119 | 213 | 13 | 345 |
| [scripts/datasources/census/load\_acs.py](/scripts/datasources/census/load_acs.py) | Python | 259 | 145 | 82 | 486 |
| [scripts/datasources/census/load\_census\_counties.py](/scripts/datasources/census/load_census_counties.py) | Python | 183 | 69 | 52 | 304 |
| [scripts/datasources/census/load\_census\_gazetteer.py](/scripts/datasources/census/load_census_gazetteer.py) | Python | 418 | 77 | 40 | 535 |
| [scripts/datasources/census/load\_census\_municipalities.py](/scripts/datasources/census/load_census_municipalities.py) | Python | 151 | 43 | 36 | 230 |
| [scripts/datasources/census/load\_census\_postal\_codes.py](/scripts/datasources/census/load_census_postal_codes.py) | Python | 261 | 70 | 70 | 401 |
| [scripts/datasources/census/load\_census\_relationships.py](/scripts/datasources/census/load_census_relationships.py) | Python | 342 | 64 | 87 | 493 |
| [scripts/datasources/census/load\_census\_shapefiles.py](/scripts/datasources/census/load_census_shapefiles.py) | Python | 258 | 156 | 8 | 422 |
| [scripts/datasources/census/load\_census\_states.py](/scripts/datasources/census/load_census_states.py) | Python | 128 | 19 | 19 | 166 |
| [scripts/datasources/census/load\_county\_mappings.py](/scripts/datasources/census/load_county_mappings.py) | Python | 147 | 64 | 50 | 261 |
| [scripts/datasources/census/load\_place\_crosswalks.py](/scripts/datasources/census/load_place_crosswalks.py) | Python | 312 | 186 | 59 | 557 |
| [scripts/datasources/census/run\_acs\_download.sh](/scripts/datasources/census/run_acs_download.sh) | Shell Script | 4 | 8 | 2 | 14 |
| [scripts/datasources/census/sync\_jurisdictions\_fast.sql](/scripts/datasources/census/sync_jurisdictions_fast.sql) | MS SQL | 53 | 18 | 18 | 89 |
| [scripts/datasources/census/sync\_nonprofit\_jurisdictions.py](/scripts/datasources/census/sync_nonprofit_jurisdictions.py) | Python | 119 | 22 | 27 | 168 |
| [scripts/datasources/census/verify\_bronze\_migration.py](/scripts/datasources/census/verify_bronze_migration.py) | Python | 129 | 17 | 33 | 179 |
| [scripts/datasources/cityscrapers/README.md](/scripts/datasources/cityscrapers/README.md) | Markdown | 169 | 0 | 61 | 230 |
| [scripts/datasources/cityscrapers/city\_scrapers\_urls.py](/scripts/datasources/cityscrapers/city_scrapers_urls.py) | Python | 170 | 85 | 59 | 314 |
| [scripts/datasources/dbpedia/README.md](/scripts/datasources/dbpedia/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/dbpedia/dbpedia\_integration.py](/scripts/datasources/dbpedia/dbpedia_integration.py) | Python | 226 | 167 | 24 | 417 |
| [scripts/datasources/dot/build\_dot\_unified\_events.py](/scripts/datasources/dot/build_dot_unified_events.py) | Python | 248 | 23 | 31 | 302 |
| [scripts/datasources/dot/download\_state\_dot\_public\_pages.py](/scripts/datasources/dot/download_state_dot_public_pages.py) | Python | 273 | 29 | 36 | 338 |
| [scripts/datasources/dot/extract\_dot\_event\_candidates\_from\_cache.py](/scripts/datasources/dot/extract_dot_event_candidates_from_cache.py) | Python | 197 | 23 | 33 | 253 |
| [scripts/datasources/dot/load\_dot\_unified\_events\_to\_postgres.py](/scripts/datasources/dot/load_dot_unified_events_to_postgres.py) | Python | 121 | 12 | 19 | 152 |
| [scripts/datasources/fec/POLITICAL\_FINANCE\_QUICK\_START.md](/scripts/datasources/fec/POLITICAL_FINANCE_QUICK_START.md) | Markdown | 308 | 0 | 94 | 402 |
| [scripts/datasources/fec/POLITICAL\_INFLUENCE\_INTEGRATION.md](/scripts/datasources/fec/POLITICAL_INFLUENCE_INTEGRATION.md) | Markdown | 384 | 0 | 91 | 475 |
| [scripts/datasources/fec/README.md](/scripts/datasources/fec/README.md) | Markdown | 215 | 0 | 48 | 263 |
| [scripts/datasources/fec/demo\_fec\_integration.py](/scripts/datasources/fec/demo_fec_integration.py) | Python | 180 | 54 | 55 | 289 |
| [scripts/datasources/fec/demo\_political\_influence.py](/scripts/datasources/fec/demo_political_influence.py) | Python | 260 | 32 | 60 | 352 |
| [scripts/datasources/fec/fec\_integration.py](/scripts/datasources/fec/fec_integration.py) | Python | 300 | 164 | 77 | 541 |
| [scripts/datasources/fec/fec\_paths.py](/scripts/datasources/fec/fec_paths.py) | Python | 10 | 6 | 6 | 22 |
| [scripts/datasources/fec/load\_fec\_bulk.py](/scripts/datasources/fec/load_fec_bulk.py) | Python | 304 | 141 | 72 | 517 |
| [scripts/datasources/fec/load\_fec\_individual\_contributions\_by\_date\_to\_bronze.py](/scripts/datasources/fec/load_fec_individual_contributions_by_date_to_bronze.py) | Python | 177 | 298 | 22 | 497 |
| [scripts/datasources/fec/run\_bulk\_download.sh](/scripts/datasources/fec/run_bulk_download.sh) | Shell Script | 12 | 7 | 7 | 26 |
| [scripts/datasources/fec/unzip\_fec\_data.py](/scripts/datasources/fec/unzip_fec_data.py) | Python | 406 | 168 | 98 | 672 |
| [scripts/datasources/gemini/MERGE\_STATUS.md](/scripts/datasources/gemini/MERGE_STATUS.md) | Markdown | 213 | 0 | 68 | 281 |
| [scripts/datasources/gemini/README.md](/scripts/datasources/gemini/README.md) | Markdown | 391 | 0 | 114 | 505 |
| [scripts/datasources/gemini/README\_BRONZE\_MERGE.md](/scripts/datasources/gemini/README_BRONZE_MERGE.md) | Markdown | 183 | 0 | 63 | 246 |
| [scripts/datasources/gemini/\_\_init\_\_.py](/scripts/datasources/gemini/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [scripts/datasources/gemini/analyze\_with\_multi\_models.py](/scripts/datasources/gemini/analyze_with_multi_models.py) | Python | 157 | 44 | 36 | 237 |
| [scripts/datasources/gemini/check\_models\_used.py](/scripts/datasources/gemini/check_models_used.py) | Python | 62 | 9 | 19 | 90 |
| [scripts/datasources/gemini/compare\_model\_extractions.py](/scripts/datasources/gemini/compare_model_extractions.py) | Python | 162 | 37 | 42 | 241 |
| [scripts/datasources/gemini/entity\_resolution.py](/scripts/datasources/gemini/entity_resolution.py) | Python | 228 | 122 | 93 | 443 |
| [scripts/datasources/gemini/load\_enriched\_events\_ai.py](/scripts/datasources/gemini/load_enriched_events_ai.py) | Python | 280 | 28 | 61 | 369 |
| [scripts/datasources/gemini/load\_meeting\_transcripts.py](/scripts/datasources/gemini/load_meeting_transcripts.py) | Python | 501 | 188 | 49 | 738 |
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
| [scripts/datasources/gsa/download\_gsa\_domains.py](/scripts/datasources/gsa/download_gsa_domains.py) | Python | 123 | 14 | 31 | 168 |
| [scripts/datasources/gsa/load\_gsa\_domains\_to\_postgres.py](/scripts/datasources/gsa/load_gsa_domains_to_postgres.py) | Python | 180 | 17 | 42 | 239 |
| [scripts/datasources/hifld/README.md](/scripts/datasources/hifld/README.md) | Markdown | 157 | 0 | 58 | 215 |
| [scripts/datasources/hifld/download\_and\_load\_hifld.sh](/scripts/datasources/hifld/download_and_load_hifld.sh) | Shell Script | 33 | 33 | 10 | 76 |
| [scripts/datasources/hifld/download\_hifld.py](/scripts/datasources/hifld/download_hifld.py) | Python | 86 | 11 | 25 | 122 |
| [scripts/datasources/hifld/load\_hifld\_to\_postgres.py](/scripts/datasources/hifld/load_hifld_to_postgres.py) | Python | 265 | 81 | 64 | 410 |
| [scripts/datasources/hud/load\_zip\_county.py](/scripts/datasources/hud/load_zip_county.py) | Python | 151 | 22 | 40 | 213 |
| [scripts/datasources/irs/README.md](/scripts/datasources/irs/README.md) | Markdown | 39 | 0 | 17 | 56 |
| [scripts/datasources/irs/README\_IRS\_BMF.md](/scripts/datasources/irs/README_IRS_BMF.md) | Markdown | 62 | 0 | 22 | 84 |
| [scripts/datasources/irs/README\_NONPROFIT\_DISCOVERY.md](/scripts/datasources/irs/README_NONPROFIT_DISCOVERY.md) | Markdown | 338 | 0 | 102 | 440 |
| [scripts/datasources/irs/create\_nonprofit\_officer\_contacts.py](/scripts/datasources/irs/create_nonprofit_officer_contacts.py) | Python | 99 | 26 | 28 | 153 |
| [scripts/datasources/irs/load\_irs\_bmf.py](/scripts/datasources/irs/load_irs_bmf.py) | Python | 339 | 142 | 88 | 569 |
| [scripts/datasources/irs/manage\_nonprofits.py](/scripts/datasources/irs/manage_nonprofits.py) | Python | 189 | 46 | 69 | 304 |
| [scripts/datasources/irs/nonprofit\_discovery.py](/scripts/datasources/irs/nonprofit_discovery.py) | Python | 410 | 164 | 119 | 693 |
| [scripts/datasources/jurisdiction\_pilot/\_\_init\_\_.py](/scripts/datasources/jurisdiction_pilot/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/jurisdiction\_pilot/google\_civic\_youtube.py](/scripts/datasources/jurisdiction_pilot/google_civic_youtube.py) | Python | 69 | 27 | 25 | 121 |
| [scripts/datasources/jurisdiction\_pilot/legistar\_scraper.py](/scripts/datasources/jurisdiction_pilot/legistar_scraper.py) | Python | 69 | 35 | 24 | 128 |
| [scripts/datasources/jurisdiction\_pilot/load\_ocd\_into\_postgres.py](/scripts/datasources/jurisdiction_pilot/load_ocd_into_postgres.py) | Python | 136 | 31 | 33 | 200 |
| [scripts/datasources/jurisdiction\_pilot/load\_ocd\_jurisdictions.py](/scripts/datasources/jurisdiction_pilot/load_ocd_jurisdictions.py) | Python | 141 | 57 | 35 | 233 |
| [scripts/datasources/jurisdiction\_pilot/mayor\_url\_discovery.py](/scripts/datasources/jurisdiction_pilot/mayor_url_discovery.py) | Python | 138 | 43 | 24 | 205 |
| [scripts/datasources/jurisdiction\_pilot/scrape\_priority\_states.py](/scripts/datasources/jurisdiction_pilot/scrape_priority_states.py) | Python | 424 | 291 | 24 | 739 |
| [scripts/datasources/jurisdiction\_pilot/vendor\_detection.py](/scripts/datasources/jurisdiction_pilot/vendor_detection.py) | Python | 238 | 48 | 30 | 316 |
| [scripts/datasources/jurisdiction\_pilot/verify.sql](/scripts/datasources/jurisdiction_pilot/verify.sql) | MS SQL | 97 | 10 | 9 | 116 |
| [scripts/datasources/jurisdiction\_pilot/website\_youtube\_search.py](/scripts/datasources/jurisdiction_pilot/website_youtube_search.py) | Python | 175 | 44 | 54 | 273 |
| [scripts/datasources/jurisdiction\_pilot/youtube\_channel\_enrich.py](/scripts/datasources/jurisdiction_pilot/youtube_channel_enrich.py) | Python | 209 | 86 | 47 | 342 |
| [scripts/datasources/jurisdictions/export\_jurisdiction\_mapping\_quality\_json.py](/scripts/datasources/jurisdictions/export_jurisdiction_mapping_quality_json.py) | Python | 356 | 257 | 19 | 632 |
| [scripts/datasources/jurisdictions/jurisdiction\_mapping\_queries.py](/scripts/datasources/jurisdictions/jurisdiction_mapping_queries.py) | Python | 86 | 3 | 9 | 98 |
| [scripts/datasources/jurisdictions/load\_counties\_to\_postgres.py](/scripts/datasources/jurisdictions/load_counties_to_postgres.py) | Python | 157 | 27 | 34 | 218 |
| [scripts/datasources/jurisdictions/load\_details\_to\_postgres.py](/scripts/datasources/jurisdictions/load_details_to_postgres.py) | Python | 177 | 10 | 19 | 206 |
| [scripts/datasources/jurisdictions/migrate\_parquet\_state\_naming.py](/scripts/datasources/jurisdictions/migrate_parquet_state_naming.py) | Python | 60 | 22 | 17 | 99 |
| [scripts/datasources/jurisdictions/public\_jurisdiction\_columns.py](/scripts/datasources/jurisdictions/public_jurisdiction_columns.py) | Python | 7 | 2 | 4 | 13 |
| [scripts/datasources/jurisdictions/publish\_jurisdiction\_mapping\_analysis\_to\_hf.py](/scripts/datasources/jurisdictions/publish_jurisdiction_mapping_analysis_to_hf.py) | Python | 87 | 119 | 24 | 230 |
| [scripts/datasources/jurisdictions/state\_acs\_mapping\_quality.py](/scripts/datasources/jurisdictions/state_acs_mapping_quality.py) | Python | 309 | 21 | 42 | 372 |
| [scripts/datasources/leagueofcities/download\_league\_city\_directories.py](/scripts/datasources/leagueofcities/download_league_city_directories.py) | Python | 1,791 | 104 | 167 | 2,062 |
| [scripts/datasources/leagueofcities/league\_website\_sanitize.py](/scripts/datasources/leagueofcities/league_website_sanitize.py) | Python | 58 | 11 | 15 | 84 |
| [scripts/datasources/leagueofcities/load\_league\_city\_directories\_to\_bronze.py](/scripts/datasources/leagueofcities/load_league_city_directories_to_bronze.py) | Python | 405 | 465 | 41 | 911 |
| [scripts/datasources/leagueofcities/readme.md](/scripts/datasources/leagueofcities/readme.md) | Markdown | 52 | 0 | 0 | 52 |
| [scripts/datasources/leagueofcities/sanitize\_league\_cache\_websites.py](/scripts/datasources/leagueofcities/sanitize_league_cache_websites.py) | Python | 45 | 8 | 10 | 63 |
| [scripts/datasources/localview/README.md](/scripts/datasources/localview/README.md) | Markdown | 19 | 0 | 11 | 30 |
| [scripts/datasources/localview/archive/dataverse\_client.py](/scripts/datasources/localview/archive/dataverse_client.py) | Python | 345 | 189 | 91 | 625 |
| [scripts/datasources/localview/archive/download\_localview\_data.py](/scripts/datasources/localview/archive/download_localview_data.py) | Python | 316 | 99 | 79 | 494 |
| [scripts/datasources/localview/archive/load\_localview.py](/scripts/datasources/localview/archive/load_localview.py) | Python | 74 | 16 | 22 | 112 |
| [scripts/datasources/localview/backfill\_localview\_youtube\_channel\_map.py](/scripts/datasources/localview/backfill_localview_youtube_channel_map.py) | Python | 145 | 26 | 36 | 207 |
| [scripts/datasources/localview/enrich\_from\_localview.py](/scripts/datasources/localview/enrich_from_localview.py) | Python | 233 | 47 | 67 | 347 |
| [scripts/datasources/localview/fuzzy\_jurisdiction\_matcher.py](/scripts/datasources/localview/fuzzy_jurisdiction_matcher.py) | Python | 183 | 128 | 55 | 366 |
| [scripts/datasources/localview/load\_localview\_to\_postgres.py](/scripts/datasources/localview/load_localview_to_postgres.py) | Python | 381 | 20 | 50 | 451 |
| [scripts/datasources/ma\_pilot/\_\_init\_\_.py](/scripts/datasources/ma_pilot/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/ma\_pilot/jurisdictions.py](/scripts/datasources/ma_pilot/jurisdictions.py) | Python | 142 | 22 | 7 | 171 |
| [scripts/datasources/ma\_pilot/mayor\_boost.py](/scripts/datasources/ma_pilot/mayor_boost.py) | Python | 35 | 23 | 11 | 69 |
| [scripts/datasources/ma\_pilot/scrape\_ma\_jurisdictions.py](/scripts/datasources/ma_pilot/scrape_ma_jurisdictions.py) | Python | 207 | 35 | 35 | 277 |
| [scripts/datasources/ma\_pilot/verify.sql](/scripts/datasources/ma_pilot/verify.sql) | MS SQL | 109 | 12 | 10 | 131 |
| [scripts/datasources/master\_data/README.md](/scripts/datasources/master_data/README.md) | Markdown | 310 | 0 | 79 | 389 |
| [scripts/datasources/master\_data/create\_jurisdiction\_master.py](/scripts/datasources/master_data/create_jurisdiction_master.py) | Python | 1,005 | 182 | 144 | 1,331 |
| [scripts/datasources/master\_data/query\_examples.sql](/scripts/datasources/master_data/query_examples.sql) | MS SQL | 281 | 72 | 52 | 405 |
| [scripts/datasources/meetingbank/README.md](/scripts/datasources/meetingbank/README.md) | Markdown | 13 | 0 | 8 | 21 |
| [scripts/datasources/meetingbank/load\_meetingbank.py](/scripts/datasources/meetingbank/load_meetingbank.py) | Python | 256 | 128 | 81 | 465 |
| [scripts/datasources/naco/README.md](/scripts/datasources/naco/README.md) | Markdown | 54 | 0 | 28 | 82 |
| [scripts/datasources/naco/load\_naco\_to\_bronze.py](/scripts/datasources/naco/load_naco_to_bronze.py) | Python | 347 | 64 | 64 | 475 |
| [scripts/datasources/naco/run\_naco\_all\_states.sh](/scripts/datasources/naco/run_naco_all_states.sh) | Shell Script | 18 | 12 | 7 | 37 |
| [scripts/datasources/naco/run\_naco\_pipeline.sh](/scripts/datasources/naco/run_naco_pipeline.sh) | Shell Script | 21 | 14 | 7 | 42 |
| [scripts/datasources/naco/scrape\_naco\_counties.py](/scripts/datasources/naco/scrape_naco_counties.py) | Python | 522 | 77 | 80 | 679 |
| [scripts/datasources/nccs/README.md](/scripts/datasources/nccs/README.md) | Markdown | 165 | 0 | 53 | 218 |
| [scripts/datasources/nccs/download\_nccs\_bulk.py](/scripts/datasources/nccs/download_nccs_bulk.py) | Python | 332 | 39 | 75 | 446 |
| [scripts/datasources/nccs/load\_nccs\_bulk.py](/scripts/datasources/nccs/load_nccs_bulk.py) | Python | 336 | 36 | 46 | 418 |
| [scripts/datasources/nces/README.md](/scripts/datasources/nces/README.md) | Markdown | 82 | 0 | 34 | 116 |
| [scripts/datasources/nces/README\_ENRICHMENT.md](/scripts/datasources/nces/README_ENRICHMENT.md) | Markdown | 160 | 0 | 46 | 206 |
| [scripts/datasources/nces/download\_nces.py](/scripts/datasources/nces/download_nces.py) | Python | 303 | 16 | 34 | 353 |
| [scripts/datasources/nces/enrich\_jurisdictions\_from\_nces.py](/scripts/datasources/nces/enrich_jurisdictions_from_nces.py) | Python | 288 | 53 | 58 | 399 |
| [scripts/datasources/nces/fix\_and\_enrich\_school\_districts.py](/scripts/datasources/nces/fix_and_enrich_school_districts.py) | Python | 144 | 166 | 22 | 332 |
| [scripts/datasources/nces/load\_nces\_school\_districts\_to\_bronze.py](/scripts/datasources/nces/load_nces_school_districts_to_bronze.py) | Python | 393 | 108 | 15 | 516 |
| [scripts/datasources/nces/migrate\_schools\_to\_orgloc.py](/scripts/datasources/nces/migrate_schools_to_orgloc.py) | Python | 123 | 18 | 28 | 169 |
| [scripts/datasources/nces/update\_jurisdictions\_from\_nces\_simple.py](/scripts/datasources/nces/update_jurisdictions_from_nces_simple.py) | Python | 92 | 163 | 12 | 267 |
| [scripts/datasources/netronline/\_\_init\_\_.py](/scripts/datasources/netronline/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/netronline/crawl\_county\_directory.py](/scripts/datasources/netronline/crawl_county_directory.py) | Python | 346 | 71 | 70 | 487 |
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
| [scripts/datasources/openstates/map\_openstates\_jurisdiction\_ids.py](/scripts/datasources/openstates/map_openstates_jurisdiction_ids.py) | Python | 96 | 35 | 24 | 155 |
| [scripts/datasources/openstates/openstates\_sources.py](/scripts/datasources/openstates/openstates_sources.py) | Python | 163 | 69 | 65 | 297 |
| [scripts/datasources/openstates/parallel\_download.sh](/scripts/datasources/openstates/parallel_download.sh) | Shell Script | 42 | 7 | 10 | 59 |
| [scripts/datasources/openstates/repair\_main\_venv\_after\_dbt\_conflict.sh](/scripts/datasources/openstates/repair_main_venv_after_dbt_conflict.sh) | Shell Script | 19 | 9 | 6 | 34 |
| [scripts/datasources/openstates/run\_openstates\_jurisdiction\_mapping.sh](/scripts/datasources/openstates/run_openstates_jurisdiction_mapping.sh) | Shell Script | 42 | 17 | 8 | 67 |
| [scripts/datasources/openstates/setup\_dbt\_venv.sh](/scripts/datasources/openstates/setup_dbt_venv.sh) | Shell Script | 16 | 8 | 6 | 30 |
| [scripts/datasources/openstates/setup\_openstates\_db.sh](/scripts/datasources/openstates/setup_openstates_db.sh) | Shell Script | 144 | 32 | 26 | 202 |
| [scripts/datasources/osf/download\_osf\_zip.py](/scripts/datasources/osf/download_osf_zip.py) | Python | 307 | 48 | 82 | 437 |
| [scripts/datasources/osf/load\_osf\_rds\_to\_bronze.R](/scripts/datasources/osf/load_osf_rds_to_bronze.R) | R | 126 | 24 | 22 | 172 |
| [scripts/datasources/osf/load\_osf\_rds\_to\_bronze.py](/scripts/datasources/osf/load_osf_rds_to_bronze.py) | Python | 152 | 20 | 38 | 210 |
| [scripts/datasources/osf/load\_osf\_to\_bronze.py](/scripts/datasources/osf/load_osf_to_bronze.py) | Python | 133 | 25 | 38 | 196 |
| [scripts/datasources/osf/readme.md](/scripts/datasources/osf/readme.md) | Markdown | 42 | 0 | 24 | 66 |
| [scripts/datasources/social\_media/social\_media\_discovery.py](/scripts/datasources/social_media/social_media_discovery.py) | Python | 238 | 137 | 59 | 434 |
| [scripts/datasources/uscm/README.md](/scripts/datasources/uscm/README.md) | Markdown | 80 | 0 | 33 | 113 |
| [scripts/datasources/uscm/download\_mayors.py](/scripts/datasources/uscm/download_mayors.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/uscm/download\_uscm\_mayors.py](/scripts/datasources/uscm/download_uscm_mayors.py) | Python | 250 | 19 | 44 | 313 |
| [scripts/datasources/uscm/load\_uscm\_mayors\_to\_bronze.py](/scripts/datasources/uscm/load_uscm_mayors_to_bronze.py) | Python | 218 | 59 | 17 | 294 |
| [scripts/datasources/uscm/scrape\_mayor\_elections.py](/scripts/datasources/uscm/scrape_mayor_elections.py) | Python | 206 | 52 | 55 | 313 |
| [scripts/datasources/uscm/scrape\_meet\_the\_mayors.py](/scripts/datasources/uscm/scrape_meet_the_mayors.py) | Python | 8 | 6 | 3 | 17 |
| [scripts/datasources/uscm/state\_names.py](/scripts/datasources/uscm/state_names.py) | Python | 54 | 1 | 3 | 58 |
| [scripts/datasources/vendorsearch/readme.md](/scripts/datasources/vendorsearch/readme.md) | Markdown | 49 | 0 | 33 | 82 |
| [scripts/datasources/vendorsearch/vendor\_meeting\_portal\_search.py](/scripts/datasources/vendorsearch/vendor_meeting_portal_search.py) | Python | 259 | 25 | 38 | 322 |
| [scripts/datasources/voter\_data/README.md](/scripts/datasources/voter_data/README.md) | Markdown | 4 | 0 | 4 | 8 |
| [scripts/datasources/voter\_data/voter\_data\_integration.py](/scripts/datasources/voter_data/voter_data_integration.py) | Python | 169 | 143 | 50 | 362 |
| [scripts/datasources/wikidata/README.md](/scripts/datasources/wikidata/README.md) | Markdown | 199 | 0 | 61 | 260 |
| [scripts/datasources/wikidata/cleanup\_bad\_counties.py](/scripts/datasources/wikidata/cleanup_bad_counties.py) | Python | 111 | 21 | 18 | 150 |
| [scripts/datasources/wikidata/discover\_municipality\_website\_gaps.py](/scripts/datasources/wikidata/discover_municipality_website_gaps.py) | Python | 59 | 2 | 15 | 76 |
| [scripts/datasources/wikidata/export\_bronze\_to\_json.py](/scripts/datasources/wikidata/export_bronze_to_json.py) | Python | 190 | 226 | 10 | 426 |
| [scripts/datasources/wikidata/fix\_fips\_codes.py](/scripts/datasources/wikidata/fix_fips_codes.py) | Python | 111 | 21 | 25 | 157 |
| [scripts/datasources/wikidata/generate\_mapping\_report.sql](/scripts/datasources/wikidata/generate_mapping_report.sql) | MS SQL | 108 | 13 | 10 | 131 |
| [scripts/datasources/wikidata/geography\_qid\_cache.py](/scripts/datasources/wikidata/geography_qid_cache.py) | Python | 129 | 8 | 23 | 160 |
| [scripts/datasources/wikidata/hydrate\_county\_websites\_from\_wikidata.py](/scripts/datasources/wikidata/hydrate_county_websites_from_wikidata.py) | Python | 45 | 166 | 8 | 219 |
| [scripts/datasources/wikidata/hydrate\_municipality\_websites\_from\_wikidata.py](/scripts/datasources/wikidata/hydrate_municipality_websites_from_wikidata.py) | Python | 46 | 169 | 9 | 224 |
| [scripts/datasources/wikidata/load\_channels.py](/scripts/datasources/wikidata/load_channels.py) | Python | 498 | 195 | 48 | 741 |
| [scripts/datasources/wikidata/load\_jurisdictions\_wikidata.py](/scripts/datasources/wikidata/load_jurisdictions_wikidata.py) | Python | 2,457 | 1,524 | 152 | 4,133 |
| [scripts/datasources/wikidata/load\_jurisdictions\_wikidata\_colab.ipynb](/scripts/datasources/wikidata/load_jurisdictions_wikidata_colab.ipynb) | JSON | 468 | 0 | 1 | 469 |
| [scripts/datasources/wikidata/materialize\_bronze\_jurisdictions\_wikidata\_tables.py](/scripts/datasources/wikidata/materialize_bronze_jurisdictions_wikidata_tables.py) | Python | 289 | 39 | 38 | 366 |
| [scripts/datasources/wikidata/parquet\_qid\_lookup.py](/scripts/datasources/wikidata/parquet_qid_lookup.py) | Python | 221 | 73 | 34 | 328 |
| [scripts/datasources/wikidata/run\_hydrate\_county\_websites.sh](/scripts/datasources/wikidata/run_hydrate_county_websites.sh) | Shell Script | 11 | 9 | 5 | 25 |
| [scripts/datasources/wikidata/run\_hydrate\_municipality\_websites.sh](/scripts/datasources/wikidata/run_hydrate_municipality_websites.sh) | Shell Script | 11 | 10 | 5 | 26 |
| [scripts/datasources/wikidata/run\_load\_jurisdictions\_wikidata.sh](/scripts/datasources/wikidata/run_load_jurisdictions_wikidata.sh) | Shell Script | 8 | 3 | 4 | 15 |
| [scripts/datasources/wikidata/run\_municipality\_websites\_gap\_states.sh](/scripts/datasources/wikidata/run_municipality_websites_gap_states.sh) | Shell Script | 76 | 14 | 15 | 105 |
| [scripts/datasources/wikidata/run\_wikidata\_happy\_path.sh](/scripts/datasources/wikidata/run_wikidata_happy_path.sh) | Shell Script | 8 | 11 | 4 | 23 |
| [scripts/datasources/wikidata/run\_wikidata\_priority\_states\_background.sh](/scripts/datasources/wikidata/run_wikidata_priority_states_background.sh) | Shell Script | 37 | 16 | 8 | 61 |
| [scripts/datasources/wikidata/validate\_channels\_wikidata.py](/scripts/datasources/wikidata/validate_channels_wikidata.py) | Python | 193 | 35 | 50 | 278 |
| [scripts/datasources/wikidata/warm\_geography\_cache\_from\_parquet.py](/scripts/datasources/wikidata/warm_geography_cache_from_parquet.py) | Python | 87 | 21 | 20 | 128 |
| [scripts/datasources/wikidata/wikidata\_entity\_search.py](/scripts/datasources/wikidata/wikidata_entity_search.py) | Python | 71 | 10 | 11 | 92 |
| [scripts/datasources/wikidata/wikidata\_fips\_gnis\_extract\_colab.ipynb](/scripts/datasources/wikidata/wikidata_fips_gnis_extract_colab.ipynb) | JSON | 348 | 0 | 0 | 348 |
| [scripts/datasources/wikidata/wikidata\_fips\_gnis\_extract\_local.py](/scripts/datasources/wikidata/wikidata_fips_gnis_extract_local.py) | Python | 326 | 68 | 68 | 462 |
| [scripts/datasources/wikidata/wikidata\_hybrid\_sql.py](/scripts/datasources/wikidata/wikidata_hybrid_sql.py) | Python | 88 | 56 | 3 | 147 |
| [scripts/datasources/wikidata/wikidata\_integration.py](/scripts/datasources/wikidata/wikidata_integration.py) | Python | 937 | 295 | 100 | 1,332 |
| [scripts/datasources/wikidata/wikidata\_wbget\_claims.py](/scripts/datasources/wikidata/wikidata_wbget_claims.py) | Python | 337 | 17 | 78 | 432 |
| [scripts/datasources/youtube/BRONZE\_MIGRATION.md](/scripts/datasources/youtube/BRONZE_MIGRATION.md) | Markdown | 125 | 0 | 32 | 157 |
| [scripts/datasources/youtube/BYPASS\_IP\_BLOCK.md](/scripts/datasources/youtube/BYPASS_IP_BLOCK.md) | Markdown | 119 | 0 | 40 | 159 |
| [scripts/datasources/youtube/CHANNEL\_SANITY\_CHECK.md](/scripts/datasources/youtube/CHANNEL_SANITY_CHECK.md) | Markdown | 179 | 0 | 45 | 224 |
| [scripts/datasources/youtube/README\_AUDIO\_DOWNLOAD.md](/scripts/datasources/youtube/README_AUDIO_DOWNLOAD.md) | Markdown | 142 | 0 | 38 | 180 |
| [scripts/datasources/youtube/analyze\_channels.py](/scripts/datasources/youtube/analyze_channels.py) | Python | 73 | 125 | 18 | 216 |
| [scripts/datasources/youtube/audit\_ga\_jurisdiction\_youtube\_gaps.sql](/scripts/datasources/youtube/audit_ga_jurisdiction_youtube_gaps.sql) | MS SQL | 103 | 19 | 9 | 131 |
| [scripts/datasources/youtube/audit\_ga\_jurisdiction\_youtube\_gaps\_minimal.sql](/scripts/datasources/youtube/audit_ga_jurisdiction_youtube_gaps_minimal.sql) | MS SQL | 29 | 4 | 4 | 37 |
| [scripts/datasources/youtube/audit\_ga\_youtube\_download\_filters.sql](/scripts/datasources/youtube/audit_ga_youtube_download_filters.sql) | MS SQL | 255 | 23 | 9 | 287 |
| [scripts/datasources/youtube/audit\_localview\_youtube\_bronze\_overlap.sql](/scripts/datasources/youtube/audit_localview_youtube_bronze_overlap.sql) | MS SQL | 80 | 17 | 13 | 110 |
| [scripts/datasources/youtube/audit\_youtube\_jurisdiction\_coverage.sql](/scripts/datasources/youtube/audit_youtube_jurisdiction_coverage.sql) | MS SQL | 327 | 18 | 25 | 370 |
| [scripts/datasources/youtube/backfill\_bronze\_youtube\_publish\_dates.py](/scripts/datasources/youtube/backfill_bronze_youtube_publish_dates.py) | Python | 484 | 53 | 46 | 583 |
| [scripts/datasources/youtube/backfill\_jurisdiction\_transcripts.py](/scripts/datasources/youtube/backfill_jurisdiction_transcripts.py) | Python | 1,055 | 128 | 95 | 1,278 |
| [scripts/datasources/youtube/backfill\_transcripts.py](/scripts/datasources/youtube/backfill_transcripts.py) | Python | 333 | 47 | 82 | 462 |
| [scripts/datasources/youtube/channel\_about\_links.py](/scripts/datasources/youtube/channel_about_links.py) | Python | 573 | 196 | 81 | 850 |
| [scripts/datasources/youtube/dedupe\_meeting\_videos.py](/scripts/datasources/youtube/dedupe_meeting_videos.py) | Python | 210 | 15 | 43 | 268 |
| [scripts/datasources/youtube/download\_audio\_colab.ipynb](/scripts/datasources/youtube/download_audio_colab.ipynb) | JSON | 1,191 | 0 | 0 | 1,191 |
| [scripts/datasources/youtube/download\_audio\_colab\_example.py](/scripts/datasources/youtube/download_audio_colab_example.py) | Python | 24 | 68 | 28 | 120 |
| [scripts/datasources/youtube/download\_audio\_to\_drive.py](/scripts/datasources/youtube/download_audio_to_drive.py) | Python | 1,114 | 532 | 56 | 1,702 |
| [scripts/datasources/youtube/download\_tuscaloosa\_city\_meeting\_audio.py](/scripts/datasources/youtube/download_tuscaloosa_city_meeting_audio.py) | Python | 225 | 28 | 34 | 287 |
| [scripts/datasources/youtube/download\_youtube\_audio\_al.sh](/scripts/datasources/youtube/download_youtube_audio_al.sh) | Shell Script | 6 | 5 | 1 | 12 |
| [scripts/datasources/youtube/download\_youtube\_audio\_ga.sh](/scripts/datasources/youtube/download_youtube_audio_ga.sh) | Shell Script | 6 | 8 | 1 | 15 |
| [scripts/datasources/youtube/download\_youtube\_audio\_in.sh](/scripts/datasources/youtube/download_youtube_audio_in.sh) | Shell Script | 6 | 5 | 1 | 12 |
| [scripts/datasources/youtube/download\_youtube\_audio\_mt.sh](/scripts/datasources/youtube/download_youtube_audio_mt.sh) | Shell Script | 6 | 4 | 1 | 11 |
| [scripts/datasources/youtube/link\_youtube\_bronze\_from\_localview\_apply.sql](/scripts/datasources/youtube/link_youtube_bronze_from_localview_apply.sql) | MS SQL | 86 | 6 | 8 | 100 |
| [scripts/datasources/youtube/link\_youtube\_bronze\_from\_localview\_preview.sql](/scripts/datasources/youtube/link_youtube_bronze_from_localview_preview.sql) | MS SQL | 91 | 6 | 6 | 103 |
| [scripts/datasources/youtube/load\_channel\_candidates\_to\_catalog.py](/scripts/datasources/youtube/load_channel_candidates_to_catalog.py) | Python | 119 | 9 | 17 | 145 |
| [scripts/datasources/youtube/load\_missing\_county\_channels.py](/scripts/datasources/youtube/load_missing_county_channels.py) | Python | 285 | 7 | 38 | 330 |
| [scripts/datasources/youtube/load\_youtube\_channels\_bronze.py](/scripts/datasources/youtube/load_youtube_channels_bronze.py) | Python | 356 | 45 | 65 | 466 |
| [scripts/datasources/youtube/load\_youtube\_events\_colab.ipynb](/scripts/datasources/youtube/load_youtube_events_colab.ipynb) | JSON | 775 | 0 | 1 | 776 |
| [scripts/datasources/youtube/load\_youtube\_events\_to\_postgres.py](/scripts/datasources/youtube/load_youtube_events_to_postgres.py) | Python | 1,506 | 206 | 230 | 1,942 |
| [scripts/datasources/youtube/load\_youtube\_for\_jurisdiction.py](/scripts/datasources/youtube/load_youtube_for_jurisdiction.py) | Python | 164 | 19 | 18 | 201 |
| [scripts/datasources/youtube/normalize\_youtube\_jurisdiction\_ids.py](/scripts/datasources/youtube/normalize_youtube_jurisdiction_ids.py) | Python | 326 | 53 | 55 | 434 |
| [scripts/datasources/youtube/run\_audit\_ga\_jurisdiction\_youtube\_gaps.sh](/scripts/datasources/youtube/run_audit_ga_jurisdiction_youtube_gaps.sh) | Shell Script | 39 | 3 | 8 | 50 |
| [scripts/datasources/youtube/run\_audit\_ga\_youtube\_download\_filters.sh](/scripts/datasources/youtube/run_audit_ga_youtube_download_filters.sh) | Shell Script | 17 | 10 | 6 | 33 |
| [scripts/datasources/youtube/run\_audit\_localview\_youtube\_bronze\_overlap.sh](/scripts/datasources/youtube/run_audit_localview_youtube_bronze_overlap.sh) | Shell Script | 21 | 4 | 7 | 32 |
| [scripts/datasources/youtube/run\_audit\_youtube\_jurisdiction\_coverage.sh](/scripts/datasources/youtube/run_audit_youtube_jurisdiction_coverage.sh) | Shell Script | 23 | 6 | 9 | 38 |
| [scripts/datasources/youtube/run\_backfill\_bronze\_youtube\_publish\_dates.sh](/scripts/datasources/youtube/run_backfill_bronze_youtube_publish_dates.sh) | Shell Script | 9 | 12 | 5 | 26 |
| [scripts/datasources/youtube/run\_link\_youtube\_bronze\_from\_localview.sh](/scripts/datasources/youtube/run_link_youtube_bronze_from_localview.sh) | Shell Script | 23 | 8 | 8 | 39 |
| [scripts/datasources/youtube/run\_priority\_states\_channel\_pipeline.sh](/scripts/datasources/youtube/run_priority_states_channel_pipeline.sh) | Shell Script | 121 | 31 | 21 | 173 |
| [scripts/datasources/youtube/run\_priority\_states\_last\_n.sh](/scripts/datasources/youtube/run_priority_states_last_n.sh) | Shell Script | 321 | 28 | 25 | 374 |
| [scripts/datasources/youtube/setup\_channels\_bronze.sh](/scripts/datasources/youtube/setup_channels_bronze.sh) | Shell Script | 49 | 8 | 9 | 66 |
| [scripts/datasources/youtube/sql/preview\_bronze\_youtube\_blank\_publish\_dates.sql](/scripts/datasources/youtube/sql/preview_bronze_youtube_blank_publish_dates.sql) | MS SQL | 24 | 6 | 5 | 35 |
| [scripts/datasources/youtube/sync\_bronze\_youtube\_from\_localview.py](/scripts/datasources/youtube/sync_bronze_youtube_from_localview.py) | Python | 65 | 103 | 10 | 178 |
| [scripts/datasources/youtube/test\_cobb\_county\_scrape.py](/scripts/datasources/youtube/test_cobb_county_scrape.py) | Python | 37 | 2 | 13 | 52 |
| [scripts/datasources/youtube/transcript\_api\_client.py](/scripts/datasources/youtube/transcript_api_client.py) | Python | 33 | 12 | 10 | 55 |
| [scripts/datasources/youtube/youtube\_channel\_discovery.py](/scripts/datasources/youtube/youtube_channel_discovery.py) | Python | 681 | 198 | 130 | 1,009 |
| [scripts/dbt-root.sh](/scripts/dbt-root.sh) | Shell Script | 5 | 8 | 1 | 14 |
| [scripts/dbt.sh](/scripts/dbt.sh) | Shell Script | 5 | 8 | 1 | 14 |
| [scripts/dbt/README.md](/scripts/dbt/README.md) | Markdown | 265 | 0 | 83 | 348 |
| [scripts/dbt/export\_stats\_to\_open\_navigator.py](/scripts/dbt/export_stats_to_open_navigator.py) | Python | 108 | 21 | 29 | 158 |
| [scripts/dbt/rebuild\_stats\_aggregates\_fixed.py](/scripts/dbt/rebuild_stats_aggregates_fixed.py) | Python | 201 | 12 | 22 | 235 |
| [scripts/dbt/rebuild\_stats\_fixed.py](/scripts/dbt/rebuild_stats_fixed.py) | Python | 214 | 12 | 24 | 250 |
| [scripts/deployment/README.md](/scripts/deployment/README.md) | Markdown | 61 | 0 | 22 | 83 |
| [scripts/deployment/deploy-databricks-app.sh](/scripts/deployment/deploy-databricks-app.sh) | Shell Script | 50 | 10 | 13 | 73 |
| [scripts/deployment/install.sh](/scripts/deployment/install.sh) | Shell Script | 96 | 11 | 14 | 121 |
| [scripts/deployment/migrate\_neon\_to\_dev.sh](/scripts/deployment/migrate_neon_to_dev.sh) | Shell Script | 70 | 7 | 12 | 89 |
| [scripts/deployment/neon/README.md](/scripts/deployment/neon/README.md) | Markdown | 271 | 0 | 72 | 343 |
| [scripts/deployment/neon/SETUP\_YOUTUBE.md](/scripts/deployment/neon/SETUP_YOUTUBE.md) | Markdown | 119 | 0 | 45 | 164 |
| [scripts/deployment/neon/calculate\_stats\_only.py](/scripts/deployment/neon/calculate_stats_only.py) | Python | 131 | 21 | 40 | 192 |
| [scripts/deployment/neon/ensure\_bronze\_jurisdictions\_cloud.py](/scripts/deployment/neon/ensure_bronze_jurisdictions_cloud.py) | Python | 154 | 15 | 26 | 195 |
| [scripts/deployment/neon/load\_ocd\_jurisdictions\_to\_sql.sh](/scripts/deployment/neon/load_ocd_jurisdictions_to_sql.sh) | Shell Script | 74 | 5 | 16 | 95 |
| [scripts/deployment/neon/migrate.py](/scripts/deployment/neon/migrate.py) | Python | 892 | 108 | 182 | 1,182 |
| [scripts/deployment/neon/migrate\_all\_bronze\_tables.sh](/scripts/deployment/neon/migrate_all_bronze_tables.sh) | Shell Script | 49 | 7 | 14 | 70 |
| [scripts/deployment/neon/migrate\_bills.py](/scripts/deployment/neon/migrate_bills.py) | Python | 158 | 64 | 49 | 271 |
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
| [scripts/deployment/neon/migrations/018\_policy\_legislation\_linkage.sql](/scripts/deployment/neon/migrations/018_policy_legislation_linkage.sql) | MS SQL | 69 | 7 | 12 | 88 |
| [scripts/deployment/neon/migrations/018\_rename\_public\_core\_tables.sql](/scripts/deployment/neon/migrations/018_rename_public_core_tables.sql) | MS SQL | 25 | 10 | 6 | 41 |
| [scripts/deployment/neon/migrations/019\_recreate\_bronze\_events\_meetings\_scraped\_granular.sql](/scripts/deployment/neon/migrations/019_recreate_bronze_events_meetings_scraped_granular.sql) | MS SQL | 109 | 3 | 13 | 125 |
| [scripts/deployment/neon/migrations/019\_rename\_public\_entity\_tables.sql](/scripts/deployment/neon/migrations/019_rename_public_entity_tables.sql) | MS SQL | 9 | 9 | 5 | 23 |
| [scripts/deployment/neon/migrations/020\_recreate\_bronze\_events\_meetings\_scraped\_link\_document.sql](/scripts/deployment/neon/migrations/020_recreate_bronze_events_meetings_scraped_link_document.sql) | MS SQL | 123 | 2 | 13 | 138 |
| [scripts/deployment/neon/migrations/020\_rename\_public\_log\_sync\_tables.sql](/scripts/deployment/neon/migrations/020_rename_public_log_sync_tables.sql) | MS SQL | 4 | 6 | 4 | 14 |
| [scripts/deployment/neon/migrations/021\_create\_bronze\_dot\_public\_events.sql](/scripts/deployment/neon/migrations/021_create_bronze_dot_public_events.sql) | MS SQL | 24 | 2 | 5 | 31 |
| [scripts/deployment/neon/migrations/021\_rename\_oauth\_states\_to\_contact\_oauth\_states.sql](/scripts/deployment/neon/migrations/021_rename_oauth_states_to_contact_oauth_states.sql) | MS SQL | 3 | 5 | 4 | 12 |
| [scripts/deployment/neon/migrations/022\_add\_channel\_description.sql](/scripts/deployment/neon/migrations/022_add_channel_description.sql) | MS SQL | 4 | 2 | 4 | 10 |
| [scripts/deployment/neon/migrations/022\_rename\_organizations\_nonprofit\_search\_to\_organization\_nonprofit.sql](/scripts/deployment/neon/migrations/022_rename_organizations_nonprofit_search_to_organization_nonprofit.sql) | MS SQL | 17 | 6 | 5 | 28 |
| [scripts/deployment/neon/migrations/023\_drop\_channel\_view\_count.sql](/scripts/deployment/neon/migrations/023_drop_channel_view_count.sql) | MS SQL | 4 | 2 | 4 | 10 |
| [scripts/deployment/neon/migrations/023\_rename\_reference\_ntee\_codes\_to\_cause\_ntee.sql](/scripts/deployment/neon/migrations/023_rename_reference_ntee_codes_to_cause_ntee.sql) | MS SQL | 16 | 6 | 4 | 26 |
| [scripts/deployment/neon/migrations/024\_add\_view\_count\_bronze\_events\_channels.sql](/scripts/deployment/neon/migrations/024_add_view_count_bronze_events_channels.sql) | MS SQL | 4 | 2 | 4 | 10 |
| [scripts/deployment/neon/migrations/024\_rename\_contact\_oauth\_states\_to\_contact\_oauth\_state.sql](/scripts/deployment/neon/migrations/024_rename_contact_oauth_states_to_contact_oauth_state.sql) | MS SQL | 3 | 5 | 4 | 12 |
| [scripts/deployment/neon/migrations/025\_bronze\_events\_youtube\_video\_id\_unique.sql](/scripts/deployment/neon/migrations/025_bronze_events_youtube_video_id_unique.sql) | MS SQL | 11 | 11 | 7 | 29 |
| [scripts/deployment/neon/migrations/025\_rename\_nonprofits\_search\_to\_organization\_nonprofit.sql](/scripts/deployment/neon/migrations/025_rename_nonprofits_search_to_organization_nonprofit.sql) | MS SQL | 17 | 6 | 5 | 28 |
| [scripts/deployment/neon/migrations/026\_rename\_wikidata\_fips\_gnis\_map.sql](/scripts/deployment/neon/migrations/026_rename_wikidata_fips_gnis_map.sql) | MS SQL | 3 | 5 | 4 | 12 |
| [scripts/deployment/neon/migrations/027\_rename\_state\_aggregate\_to\_jurisdiction\_state\_aggregate.sql](/scripts/deployment/neon/migrations/027_rename_state_aggregate_to_jurisdiction_state_aggregate.sql) | MS SQL | 6 | 5 | 5 | 16 |
| [scripts/deployment/neon/migrations/028\_rename\_event\_columns.sql](/scripts/deployment/neon/migrations/028_rename_event_columns.sql) | MS SQL | 23 | 7 | 7 | 37 |
| [scripts/deployment/neon/migrations/029\_create\_bronze\_jurisdictions\_municipalities\_league.sql](/scripts/deployment/neon/migrations/029_create_bronze_jurisdictions_municipalities_league.sql) | MS SQL | 50 | 13 | 11 | 74 |
| [scripts/deployment/neon/migrations/029\_rename\_user\_id\_column.sql](/scripts/deployment/neon/migrations/029_rename_user_id_column.sql) | MS SQL | 3 | 5 | 4 | 12 |
| [scripts/deployment/neon/migrations/030\_league\_bronze\_columns\_raw\_row.sql](/scripts/deployment/neon/migrations/030_league_bronze_columns_raw_row.sql) | MS SQL | 33 | 4 | 5 | 42 |
| [scripts/deployment/neon/migrations/031\_rename\_league\_state\_columns.sql](/scripts/deployment/neon/migrations/031_rename_league_state_columns.sql) | MS SQL | 23 | 3 | 2 | 28 |
| [scripts/deployment/neon/migrations/032\_create\_bronze\_jurisdiction\_website\_accessibility.sql](/scripts/deployment/neon/migrations/032_create_bronze_jurisdiction_website_accessibility.sql) | MS SQL | 31 | 8 | 7 | 46 |
| [scripts/deployment/neon/migrations/033\_create\_bronze\_jurisdiction\_pdf\_verapdf.sql](/scripts/deployment/neon/migrations/033_create_bronze_jurisdiction_pdf_verapdf.sql) | MS SQL | 32 | 5 | 7 | 44 |
| [scripts/deployment/neon/migrations/034\_create\_bronze\_jurisdiction\_website\_lighthouse.sql](/scripts/deployment/neon/migrations/034_create_bronze_jurisdiction_website_lighthouse.sql) | MS SQL | 66 | 4 | 8 | 78 |
| [scripts/deployment/neon/migrations/035\_create\_bronze\_contacts\_scraped.sql](/scripts/deployment/neon/migrations/035_create_bronze_contacts_scraped.sql) | MS SQL | 32 | 6 | 6 | 44 |
| [scripts/deployment/neon/migrations/036\_add\_official\_website\_updated\_at\_bronze\_wikidata.sql](/scripts/deployment/neon/migrations/036_add_official_website_updated_at_bronze_wikidata.sql) | MS SQL | 8 | 2 | 5 | 15 |
| [scripts/deployment/neon/migrations/037\_bronze\_events\_youtube\_video\_url\_unique.sql](/scripts/deployment/neon/migrations/037_bronze_events_youtube_video_url_unique.sql) | MS SQL | 12 | 7 | 7 | 26 |
| [scripts/deployment/neon/migrations/038\_jurisdiction\_merge\_details\_search.sql](/scripts/deployment/neon/migrations/038_jurisdiction_merge_details_search.sql) | MS SQL | 170 | 14 | 15 | 199 |
| [scripts/deployment/neon/migrations/039\_create\_bronze\_jurisdiction\_youtube.sql](/scripts/deployment/neon/migrations/039_create_bronze_jurisdiction_youtube.sql) | MS SQL | 31 | 9 | 6 | 46 |
| [scripts/deployment/neon/migrations/040\_alter\_bronze\_jurisdiction\_youtube\_add\_signals.sql](/scripts/deployment/neon/migrations/040_alter_bronze_jurisdiction_youtube_add_signals.sql) | MS SQL | 15 | 13 | 5 | 33 |
| [scripts/deployment/neon/migrations/041\_add\_ocd\_ids.sql](/scripts/deployment/neon/migrations/041_add_ocd_ids.sql) | MS SQL | 25 | 16 | 14 | 55 |
| [scripts/deployment/neon/migrations/041\_create\_bronze\_jurisdictions\_county\_directory.sql](/scripts/deployment/neon/migrations/041_create_bronze_jurisdictions_county_directory.sql) | MS SQL | 32 | 9 | 6 | 47 |
| [scripts/deployment/neon/migrations/042\_create\_bronze\_jurisdiction\_ocd.sql](/scripts/deployment/neon/migrations/042_create_bronze_jurisdiction_ocd.sql) | MS SQL | 27 | 9 | 11 | 47 |
| [scripts/deployment/neon/migrations/042\_rename\_bronze\_jurisdiction\_youtube\_confidence.sql](/scripts/deployment/neon/migrations/042_rename_bronze_jurisdiction_youtube_confidence.sql) | MS SQL | 6 | 11 | 5 | 22 |
| [scripts/deployment/neon/psql\_resolved.sh](/scripts/deployment/neon/psql_resolved.sh) | Shell Script | 14 | 4 | 1 | 19 |
| [scripts/deployment/neon/regenerate\_bills\_map.py](/scripts/deployment/neon/regenerate_bills_map.py) | Python | 73 | 13 | 18 | 104 |
| [scripts/deployment/neon/run\_bronze\_jurisdictions\_to\_cloud.sh](/scripts/deployment/neon/run_bronze_jurisdictions_to_cloud.sh) | Shell Script | 15 | 13 | 7 | 35 |
| [scripts/deployment/neon/run\_jurisdiction\_id\_migration.sh](/scripts/deployment/neon/run_jurisdiction_id_migration.sh) | Shell Script | 82 | 29 | 15 | 126 |
| [scripts/deployment/neon/schema.sql](/scripts/deployment/neon/schema.sql) | MS SQL | 324 | 84 | 81 | 489 |
| [scripts/deployment/neon/schema\_bills.sql](/scripts/deployment/neon/schema_bills.sql) | MS SQL | 36 | 13 | 12 | 61 |
| [scripts/deployment/neon/setup\_youtube\_tables.sh](/scripts/deployment/neon/setup_youtube_tables.sh) | Shell Script | 234 | 52 | 38 | 324 |
| [scripts/deployment/neon/sync\_bronze\_tables.py](/scripts/deployment/neon/sync_bronze_tables.py) | Python | 81 | 274 | 16 | 371 |
| [scripts/deployment/neon/sync\_youtube\_to\_neon.py](/scripts/deployment/neon/sync_youtube_to_neon.py) | Python | 121 | 65 | 22 | 208 |
| [scripts/deployment/neon/update\_stats.py](/scripts/deployment/neon/update_stats.py) | Python | 141 | 24 | 41 | 206 |
| [scripts/deployment/set-pg-password.sh](/scripts/deployment/set-pg-password.sh) | Shell Script | 9 | 2 | 7 | 18 |
| [scripts/deployment/setup-database.sh](/scripts/deployment/setup-database.sh) | Shell Script | 174 | 26 | 36 | 236 |
| [scripts/deployment/setup-git-hooks.sh](/scripts/deployment/setup-git-hooks.sh) | Shell Script | 24 | 5 | 6 | 35 |
| [scripts/deployment/setup-local-postgres.sh](/scripts/deployment/setup-local-postgres.sh) | Shell Script | 49 | 8 | 11 | 68 |
| [scripts/deployment/setup-local.sh](/scripts/deployment/setup-local.sh) | Shell Script | 32 | 5 | 8 | 45 |
| [scripts/development/README.md](/scripts/development/README.md) | Markdown | 11 | 0 | 9 | 20 |
| [scripts/development/debug\_eboard.py](/scripts/development/debug_eboard.py) | Python | 89 | 15 | 30 | 134 |
| [scripts/development/export\_chrome\_cookies.py](/scripts/development/export_chrome_cookies.py) | Python | 58 | 15 | 16 | 89 |
| [scripts/development/try\_scrape\_with\_cookies.py](/scripts/development/try_scrape_with_cookies.py) | Python | 145 | 36 | 22 | 203 |
| [scripts/discovery/README.md](/scripts/discovery/README.md) | Markdown | 114 | 0 | 41 | 155 |
| [scripts/discovery/\_\_init\_\_.py](/scripts/discovery/__init__.py) | Python | 0 | 14 | 1 | 15 |
| [scripts/discovery/archive/\_\_init\_\_.py](/scripts/discovery/archive/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [scripts/discovery/archive/comprehensive\_discovery\_pipeline.py](/scripts/discovery/archive/comprehensive_discovery_pipeline.py) | Python | 771 | 139 | 138 | 1,048 |
| [scripts/discovery/archive/comprehensive\_discovery\_pipeline\_meetings.py](/scripts/discovery/archive/comprehensive_discovery_pipeline_meetings.py) | Python | 6 | 5 | 3 | 14 |
| [scripts/discovery/archive/discovery\_pipeline.py](/scripts/discovery/archive/discovery_pipeline.py) | Python | 26 | 9 | 6 | 41 |
| [scripts/discovery/batch\_processor.py](/scripts/discovery/batch_processor.py) | Python | 352 | 115 | 78 | 545 |
| [scripts/discovery/bronze\_contacts\_scraped\_persist.py](/scripts/discovery/bronze_contacts_scraped_persist.py) | Python | 74 | 40 | 8 | 122 |
| [scripts/discovery/bronze\_jurisdiction\_youtube\_persist.py](/scripts/discovery/bronze_jurisdiction_youtube_persist.py) | Python | 98 | 40 | 12 | 150 |
| [scripts/discovery/bronze\_jurisdictions\_county\_directory\_persist.py](/scripts/discovery/bronze_jurisdictions_county_directory_persist.py) | Python | 57 | 31 | 6 | 94 |
| [scripts/discovery/civicclerk\_meetings\_sync.py](/scripts/discovery/civicclerk_meetings_sync.py) | Python | 329 | 21 | 48 | 398 |
| [scripts/discovery/civicclerk\_public\_api.py](/scripts/discovery/civicclerk_public_api.py) | Python | 189 | 18 | 34 | 241 |
| [scripts/discovery/comprehensive\_discovery\_pipeline\_jurisdiction.py](/scripts/discovery/comprehensive_discovery_pipeline_jurisdiction.py) | Python | 3,124 | 517 | 284 | 3,925 |
| [scripts/discovery/contact\_directory\_heuristics.py](/scripts/discovery/contact_directory_heuristics.py) | Python | 130 | 11 | 15 | 156 |
| [scripts/discovery/contact\_extract\_crawl4ai.py](/scripts/discovery/contact_extract_crawl4ai.py) | Python | 326 | 68 | 42 | 436 |
| [scripts/discovery/contact\_extract\_from\_html.py](/scripts/discovery/contact_extract_from_html.py) | Python | 1,716 | 128 | 251 | 2,095 |
| [scripts/discovery/contact\_profile\_images.py](/scripts/discovery/contact_profile_images.py) | Python | 731 | 50 | 64 | 845 |
| [scripts/discovery/contacts\_bundle.py](/scripts/discovery/contacts_bundle.py) | Python | 175 | 14 | 22 | 211 |
| [scripts/discovery/curated\_sources.py](/scripts/discovery/curated_sources.py) | Python | 173 | 163 | 68 | 404 |
| [scripts/discovery/discover\_oral\_health\_states.sh](/scripts/discovery/discover_oral_health_states.sh) | Shell Script | 35 | 6 | 13 | 54 |
| [scripts/discovery/discover\_top\_cities.sh](/scripts/discovery/discover_top_cities.sh) | Shell Script | 27 | 5 | 10 | 42 |
| [scripts/discovery/download\_gomeet\_recordings.py](/scripts/discovery/download_gomeet_recordings.py) | Python | 853 | 76 | 109 | 1,038 |
| [scripts/discovery/external\_url\_datasets.py](/scripts/discovery/external_url_datasets.py) | Python | 362 | 74 | 64 | 500 |
| [scripts/discovery/fix\_scraped\_meetings\_manifest\_years.py](/scripts/discovery/fix_scraped_meetings_manifest_years.py) | Python | 81 | 15 | 17 | 113 |
| [scripts/discovery/gomeet\_mp4\_to\_opus.py](/scripts/discovery/gomeet_mp4_to_opus.py) | Python | 303 | 42 | 51 | 396 |
| [scripts/discovery/jurisdiction\_contact\_seed\_urls.py](/scripts/discovery/jurisdiction_contact_seed_urls.py) | Python | 86 | 35 | 6 | 127 |
| [scripts/discovery/jurisdiction\_discovery\_pipeline.py](/scripts/discovery/jurisdiction_discovery_pipeline.py) | Python | 704 | 351 | 58 | 1,113 |
| [scripts/discovery/jurisdiction\_meeting\_seed\_urls.py](/scripts/discovery/jurisdiction_meeting_seed_urls.py) | Python | 28 | 8 | 5 | 41 |
| [scripts/discovery/load\_scraped\_meetings\_manifests\_to\_bronze.py](/scripts/discovery/load_scraped_meetings_manifests_to_bronze.py) | Python | 521 | 28 | 65 | 614 |
| [scripts/discovery/meeting\_document\_naming.py](/scripts/discovery/meeting_document_naming.py) | Python | 662 | 55 | 87 | 804 |
| [scripts/discovery/meetings\_platform\_heuristics.py](/scripts/discovery/meetings_platform_heuristics.py) | Python | 1,033 | 146 | 159 | 1,338 |
| [scripts/discovery/meetings\_playwright\_fetch.py](/scripts/discovery/meetings_playwright_fetch.py) | Python | 433 | 59 | 63 | 555 |
| [scripts/discovery/meetings\_sitemap\_discovery.py](/scripts/discovery/meetings_sitemap_discovery.py) | Python | 760 | 34 | 86 | 880 |
| [scripts/discovery/platform\_detector.py](/scripts/discovery/platform_detector.py) | Python | 202 | 98 | 37 | 337 |
| [scripts/discovery/refresh\_contacts\_from\_crawl\_html.py](/scripts/discovery/refresh_contacts_from_crawl_html.py) | Python | 391 | 9 | 42 | 442 |
| [scripts/discovery/rename\_gomeet\_downloads.py](/scripts/discovery/rename_gomeet_downloads.py) | Python | 212 | 21 | 40 | 273 |
| [scripts/discovery/rename\_scraped\_meeting\_pdf\_files.py](/scripts/discovery/rename_scraped_meeting_pdf_files.py) | Python | 373 | 26 | 54 | 453 |
| [scripts/discovery/run\_jurisdiction\_discovery.sh](/scripts/discovery/run_jurisdiction_discovery.sh) | Shell Script | 20 | 4 | 3 | 27 |
| [scripts/discovery/scraped\_meetings\_crawl\_html\_pdfs.py](/scripts/discovery/scraped_meetings_crawl_html_pdfs.py) | Python | 169 | 16 | 28 | 213 |
| [scripts/discovery/sql/bronze\_jurisdictions\_scraped.sql](/scripts/discovery/sql/bronze_jurisdictions_scraped.sql) | MS SQL | 89 | 9 | 10 | 108 |
| [scripts/discovery/url\_discovery\_agent.py](/scripts/discovery/url_discovery_agent.py) | Python | 260 | 147 | 52 | 459 |
| [scripts/download\_bronze.py](/scripts/download_bronze.py) | Python | 363 | 49 | 67 | 479 |
| [scripts/enrichment/README.md](/scripts/enrichment/README.md) | Markdown | 32 | 0 | 15 | 47 |
| [scripts/enrichment/auto\_enrich\_nonprofits.sh](/scripts/enrichment/auto_enrich_nonprofits.sh) | Shell Script | 17 | 4 | 5 | 26 |
| [scripts/enrichment/batch\_download\_990s.py](/scripts/enrichment/batch_download_990s.py) | Python | 116 | 27 | 32 | 175 |
| [scripts/enrichment/build\_990\_local\_index.py](/scripts/enrichment/build_990_local_index.py) | Python | 154 | 32 | 42 | 228 |
| [scripts/enrichment/cleanup\_nonprofit\_files.py](/scripts/enrichment/cleanup_nonprofit_files.py) | Python | 113 | 25 | 42 | 180 |
| [scripts/enrichment/discover\_tuscaloosa\_nonprofits.py](/scripts/enrichment/discover_tuscaloosa_nonprofits.py) | Python | 79 | 19 | 21 | 119 |
| [scripts/enrichment/download\_990\_zips.sh](/scripts/enrichment/download_990_zips.sh) | Shell Script | 95 | 10 | 20 | 125 |
| [scripts/enrichment/enrich\_alabama\_nonprofits.sh](/scripts/enrichment/enrich_alabama_nonprofits.sh) | Shell Script | 18 | 3 | 7 | 28 |
| [scripts/enrichment/enrich\_all\_states\_local.sh](/scripts/enrichment/enrich_all_states_local.sh) | Shell Script | 74 | 8 | 16 | 98 |
| [scripts/enrichment/enrich\_jurisdiction\_websites\_search.py](/scripts/enrichment/enrich_jurisdiction_websites_search.py) | Python | 1,036 | 76 | 115 | 1,227 |
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
| [scripts/fix-cursor-state-bloat.sh](/scripts/fix-cursor-state-bloat.sh) | Shell Script | 27 | 4 | 7 | 38 |
| [scripts/frontend/sync\_state\_symbols\_to\_public.sh](/scripts/frontend/sync_state_symbols_to_public.sh) | Shell Script | 8 | 3 | 1 | 12 |
| [scripts/frontend/sync\_wikicommons\_plates\_public.sh](/scripts/frontend/sync_wikicommons_plates_public.sh) | Shell Script | 47 | 4 | 3 | 54 |
| [scripts/gemini/README.md](/scripts/gemini/README.md) | Markdown | 158 | 0 | 63 | 221 |
| [scripts/gemini/agenda\_presenter\_hints.py](/scripts/gemini/agenda_presenter_hints.py) | Python | 121 | 11 | 21 | 153 |
| [scripts/gemini/browser\_policy\_analysis.py](/scripts/gemini/browser_policy_analysis.py) | Python | 2,662 | 215 | 212 | 3,089 |
| [scripts/gemini/diarize\_postprocess.py](/scripts/gemini/diarize_postprocess.py) | Python | 141 | 23 | 23 | 187 |
| [scripts/gemini/enrich\_analysis\_places.py](/scripts/gemini/enrich_analysis_places.py) | Python | 298 | 16 | 36 | 350 |
| [scripts/gemini/enrich\_transcript\_diarization.py](/scripts/gemini/enrich_transcript_diarization.py) | Python | 184 | 19 | 22 | 225 |
| [scripts/gemini/exclude\_policy\_video.py](/scripts/gemini/exclude_policy_video.py) | Python | 69 | 24 | 15 | 108 |
| [scripts/gemini/genai\_text\_client.py](/scripts/gemini/genai_text_client.py) | Python | 247 | 11 | 44 | 302 |
| [scripts/gemini/legislation\_analysis.py](/scripts/gemini/legislation_analysis.py) | Python | 248 | 31 | 33 | 312 |
| [scripts/gemini/meeting\_transcript\_policy.py](/scripts/gemini/meeting_transcript_policy.py) | Python | 1,127 | 69 | 111 | 1,307 |
| [scripts/gemini/mermaid\_diagrams.py](/scripts/gemini/mermaid_diagrams.py) | Python | 431 | 25 | 70 | 526 |
| [scripts/gemini/mermaid\_validate.py](/scripts/gemini/mermaid_validate.py) | Python | 150 | 5 | 33 | 188 |
| [scripts/gemini/migrate\_policy\_cache\_channels.py](/scripts/gemini/migrate_policy_cache_channels.py) | Python | 29 | 2 | 12 | 43 |
| [scripts/gemini/migrate\_policy\_cache\_folder\_names.py](/scripts/gemini/migrate_policy_cache_folder_names.py) | Python | 43 | 2 | 13 | 58 |
| [scripts/gemini/migrate\_policy\_cache\_geography.py](/scripts/gemini/migrate_policy_cache_geography.py) | Python | 35 | 2 | 12 | 49 |
| [scripts/gemini/migrate\_policy\_cache\_layout.py](/scripts/gemini/migrate_policy_cache_layout.py) | Python | 31 | 2 | 13 | 46 |
| [scripts/gemini/migrate\_transcript\_cache\_names.py](/scripts/gemini/migrate_transcript_cache_names.py) | Python | 44 | 8 | 13 | 65 |
| [scripts/gemini/part2\_report\_normalize.py](/scripts/gemini/part2_report_normalize.py) | Python | 20 | 4 | 6 | 30 |
| [scripts/gemini/persist\_policy\_analysis\_bronze.py](/scripts/gemini/persist_policy_analysis_bronze.py) | Python | 196 | 57 | 30 | 283 |
| [scripts/gemini/policy\_exclusions.py](/scripts/gemini/policy_exclusions.py) | Python | 339 | 37 | 50 | 426 |
| [scripts/gemini/policy\_processing\_status\_report.py](/scripts/gemini/policy_processing_status_report.py) | Python | 413 | 705 | 57 | 1,175 |
| [scripts/gemini/print\_uncontested\_speakers.py](/scripts/gemini/print_uncontested_speakers.py) | Python | 107 | 3 | 20 | 130 |
| [scripts/gemini/reparse\_policy\_run.py](/scripts/gemini/reparse_policy_run.py) | Python | 176 | 3 | 30 | 209 |
| [scripts/gemini/speaker\_hints.py](/scripts/gemini/speaker_hints.py) | Python | 127 | 17 | 19 | 163 |
| [scripts/gemini/transcript\_cache\_paths.py](/scripts/gemini/transcript_cache_paths.py) | Python | 1,768 | 135 | 211 | 2,114 |
| [scripts/gemini/transcript\_fetch.py](/scripts/gemini/transcript_fetch.py) | Python | 43 | 8 | 10 | 61 |
| [scripts/gemini/validate\_analysis\_legislation.py](/scripts/gemini/validate_analysis_legislation.py) | Python | 32 | 2 | 11 | 45 |
| [scripts/gemini/validate\_mermaid\_fences.py](/scripts/gemini/validate_mermaid_fences.py) | Python | 29 | 2 | 9 | 40 |
| [scripts/gemini/validate\_mermaid\_reports.py](/scripts/gemini/validate_mermaid_reports.py) | Python | 111 | 18 | 18 | 147 |
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
| [scripts/huggingface/upload\_to\_huggingface.py](/scripts/huggingface/upload_to_huggingface.py) | Python | 294 | 184 | 80 | 558 |
| [scripts/huggingface/verify-hf-deployment.sh](/scripts/huggingface/verify-hf-deployment.sh) | Shell Script | 61 | 6 | 10 | 77 |
| [scripts/load\_bronze.py](/scripts/load_bronze.py) | Python | 429 | 57 | 85 | 571 |
| [scripts/localview/README.md](/scripts/localview/README.md) | Markdown | 121 | 0 | 52 | 173 |
| [scripts/localview/check\_meeting\_data.py](/scripts/localview/check_meeting_data.py) | Python | 205 | 24 | 60 | 289 |
| [scripts/localview/extract\_transcripts.py](/scripts/localview/extract_transcripts.py) | Python | 144 | 47 | 45 | 236 |
| [scripts/localview/load\_priority\_states.sh](/scripts/localview/load_priority_states.sh) | Shell Script | 133 | 16 | 26 | 175 |
| [scripts/localview/scrape\_youtube\_channels.py](/scripts/localview/scrape_youtube_channels.py) | Python | 573 | 105 | 108 | 786 |
| [scripts/localview/update\_all.sh](/scripts/localview/update_all.sh) | Shell Script | 39 | 9 | 11 | 59 |
| [scripts/localview/update\_municipality\_list.py](/scripts/localview/update_municipality_list.py) | Python | 202 | 45 | 52 | 299 |
| [scripts/maintenance/README.md](/scripts/maintenance/README.md) | Markdown | 98 | 0 | 32 | 130 |
| [scripts/maintenance/cleanup\_disk\_space.sh](/scripts/maintenance/cleanup_disk_space.sh) | Shell Script | 83 | 12 | 18 | 113 |
| [scripts/maintenance/cleanup\_frontend\_junk.sh](/scripts/maintenance/cleanup_frontend_junk.sh) | Shell Script | 24 | 4 | 4 | 32 |
| [scripts/maintenance/cleanup\_non\_gold\_files.py](/scripts/maintenance/cleanup_non_gold_files.py) | Python | 147 | 51 | 35 | 233 |
| [scripts/maintenance/clear\_notebook\_outputs.py](/scripts/maintenance/clear_notebook_outputs.py) | Python | 62 | 22 | 22 | 106 |
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
| [scripts/open-in-cursor.sh](/scripts/open-in-cursor.sh) | Shell Script | 3 | 2 | 1 | 6 |
| [scripts/scraping/\_\_init\_\_.py](/scripts/scraping/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [scripts/scraping/crawl\_llm\_sidecar.py](/scripts/scraping/crawl_llm_sidecar.py) | Python | 63 | 13 | 12 | 88 |
| [scripts/scraping/extract\_page\_structured.py](/scripts/scraping/extract_page_structured.py) | Python | 106 | 17 | 20 | 143 |
| [scripts/scraping/html\_to\_markdown.py](/scripts/scraping/html_to_markdown.py) | Python | 85 | 12 | 21 | 118 |
| [scripts/scraping/ollama\_extract.py](/scripts/scraping/ollama_extract.py) | Python | 161 | 11 | 33 | 205 |
| [scripts/scraping/schemas.py](/scripts/scraping/schemas.py) | Python | 42 | 2 | 10 | 54 |
| [scripts/scraping/setup\_ollama\_gemma.sh](/scripts/scraping/setup_ollama_gemma.sh) | Shell Script | 34 | 7 | 8 | 49 |
| [scripts/utils/\_\_init\_\_.py](/scripts/utils/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/utils/calendar\_year\_util.py](/scripts/utils/calendar_year_util.py) | Python | 43 | 2 | 6 | 51 |
| [scripts/utils/ensure\_governance\_pipeline\_drive\_layout.py](/scripts/utils/ensure_governance_pipeline_drive_layout.py) | Python | 27 | 15 | 8 | 50 |
| [scripts/utils/gdrive\_paths.py](/scripts/utils/gdrive_paths.py) | Python | 150 | 75 | 46 | 271 |
| [scripts/utils/http\_url\_normalize.py](/scripts/utils/http_url_normalize.py) | Python | 17 | 5 | 5 | 27 |
| [scripts/utils/log\_sync.py](/scripts/utils/log_sync.py) | Python | 67 | 33 | 16 | 116 |
| [scripts/wikicommons/README.md](/scripts/wikicommons/README.md) | Markdown | 25 | 0 | 11 | 36 |
| [scripts/wikicommons/download\_wikicommons\_assets.py](/scripts/wikicommons/download_wikicommons_assets.py) | Python | 490 | 24 | 55 | 569 |
| [scripts/wikicommons/download\_wikicommons\_assets.sh](/scripts/wikicommons/download_wikicommons_assets.sh) | Shell Script | 4 | 4 | 2 | 10 |
| [scripts/win-open-navigator-in-cursor.bat](/scripts/win-open-navigator-in-cursor.bat) | Batch | 2 | 1 | 1 | 4 |
| [setup.py](/setup.py) | Python | 96 | 2 | 3 | 101 |
| [sql/adhoc/matching.sql](/sql/adhoc/matching.sql) | MS SQL | 39 | 0 | 0 | 39 |
| [start-all.sh](/start-all.sh) | Shell Script | 156 | 26 | 37 | 219 |
| [stop-all.sh](/stop-all.sh) | Shell Script | 41 | 6 | 13 | 60 |
| [tests/fixtures/contact\_extract/applingcountyga\_commissioners.html](/tests/fixtures/contact_extract/applingcountyga_commissioners.html) | HTML | 389 | 4 | 42 | 435 |
| [tests/test\_agents.py](/tests/test_agents.py) | Python | 41 | 14 | 20 | 75 |
| [tests/test\_civicclerk\_public\_api.py](/tests/test_civicclerk_public_api.py) | Python | 34 | 1 | 12 | 47 |
| [tests/test\_civicplus\_contact\_extract.py](/tests/test_civicplus_contact_extract.py) | Python | 32 | 1 | 4 | 37 |
| [tests/test\_colab\_bootstrap.py](/tests/test_colab_bootstrap.py) | Python | 18 | 1 | 10 | 29 |
| [tests/test\_colab\_notebook\_ui.py](/tests/test_colab_notebook_ui.py) | Python | 15 | 1 | 13 | 29 |
| [tests/test\_colab\_runtime\_phases.py](/tests/test_colab_runtime_phases.py) | Python | 22 | 1 | 10 | 33 |
| [tests/test\_county\_portal\_host\_macros.py](/tests/test_county_portal_host_macros.py) | Python | 28 | 1 | 16 | 45 |
| [tests/test\_dedupe\_meeting\_videos.py](/tests/test_dedupe_meeting_videos.py) | Python | 56 | 1 | 11 | 68 |
| [tests/test\_ga\_contact\_scraper\_regression.py](/tests/test_ga_contact_scraper_regression.py) | Python | 385 | 113 | 68 | 566 |
| [tests/test\_jurisdiction\_contact\_seed\_urls.py](/tests/test_jurisdiction_contact_seed_urls.py) | Python | 9 | 1 | 4 | 14 |
| [tests/test\_jurisdiction\_mapping\_queries.py](/tests/test_jurisdiction_mapping_queries.py) | Python | 18 | 1 | 6 | 25 |
| [tests/test\_legislation\_analysis.py](/tests/test_legislation_analysis.py) | Python | 87 | 0 | 13 | 100 |
| [tests/test\_meeting\_consolidated\_summary.py](/tests/test_meeting_consolidated_summary.py) | Python | 75 | 1 | 11 | 87 |
| [tests/test\_meeting\_date\_from\_title.py](/tests/test_meeting_date_from_title.py) | Python | 31 | 0 | 12 | 43 |
| [tests/test\_meeting\_document\_naming.py](/tests/test_meeting_document_naming.py) | Python | 98 | 2 | 23 | 123 |
| [tests/test\_mermaid\_diagrams.py](/tests/test_mermaid_diagrams.py) | Python | 89 | 2 | 13 | 104 |
| [tests/test\_pipeline\_media\_scope.py](/tests/test_pipeline_media_scope.py) | Python | 118 | 1 | 33 | 152 |
| [tests/test\_state\_acs\_mapping\_quality.py](/tests/test_state_acs_mapping_quality.py) | Python | 20 | 1 | 6 | 27 |
| [tests/test\_transcript\_cache\_geography.py](/tests/test_transcript_cache_geography.py) | Python | 134 | 0 | 23 | 157 |
| [tests/test\_wikidata\_entity\_search.py](/tests/test_wikidata_entity_search.py) | Python | 115 | 11 | 36 | 162 |
| [tests/test\_youtube\_channel\_tabs.py](/tests/test_youtube_channel_tabs.py) | Python | 18 | 1 | 7 | 26 |
| [tests/test\_youtube\_site\_search\_scrape.py](/tests/test_youtube_site_search_scrape.py) | Python | 164 | 15 | 63 | 242 |
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
| [website/docs/data-sources/ballot-election-sources.md](/website/docs/data-sources/ballot-election-sources.md) | Markdown | 321 | 0 | 87 | 408 |
| [website/docs/data-sources/census-acs.md](/website/docs/data-sources/census-acs.md) | Markdown | 320 | 0 | 131 | 451 |
| [website/docs/data-sources/census-data.md](/website/docs/data-sources/census-data.md) | Markdown | 72 | 0 | 33 | 105 |
| [website/docs/data-sources/census-shapefiles.md](/website/docs/data-sources/census-shapefiles.md) | Markdown | 270 | 0 | 99 | 369 |
| [website/docs/data-sources/charity-navigator.md](/website/docs/data-sources/charity-navigator.md) | Markdown | 297 | 0 | 102 | 399 |
| [website/docs/data-sources/citations.md](/website/docs/data-sources/citations.md) | Markdown | 2,254 | 0 | 552 | 2,806 |
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
| [website/docs/deployment/variable-migration.md](/website/docs/deployment/variable-migration.md) | Markdown | 29 | 0 | 17 | 46 |
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
| [website/docs/for-advocates.md](/website/docs/for-advocates.md) | Markdown | 156 | 0 | 76 | 232 |
| [website/docs/for-developers.md](/website/docs/for-developers.md) | Markdown | 330 | 0 | 112 | 442 |
| [website/docs/for-families.md](/website/docs/for-families.md) | Markdown | 317 | 0 | 97 | 414 |
| [website/docs/guides/accessibility-testing.md](/website/docs/guides/accessibility-testing.md) | Markdown | 212 | 0 | 96 | 308 |
| [website/docs/guides/accountability-strategy.md](/website/docs/guides/accountability-strategy.md) | Markdown | 181 | 0 | 77 | 258 |
| [website/docs/guides/api-troubleshooting.md](/website/docs/guides/api-troubleshooting.md) | Markdown | 154 | 0 | 62 | 216 |
| [website/docs/guides/contacts-contacts\_officials.md](/website/docs/guides/contacts-contacts_officials.md) | Markdown | 370 | 0 | 143 | 513 |
| [website/docs/guides/county-aggregation.md](/website/docs/guides/county-aggregation.md) | Markdown | 236 | 0 | 78 | 314 |
| [website/docs/guides/document-libraries.md](/website/docs/guides/document-libraries.md) | Markdown | 118 | 0 | 44 | 162 |
| [website/docs/guides/enterprise-tech-integration.md](/website/docs/guides/enterprise-tech-integration.md) | Markdown | 213 | 0 | 85 | 298 |
| [website/docs/guides/form-990-enrichment.md](/website/docs/guides/form-990-enrichment.md) | Markdown | 182 | 0 | 52 | 234 |
| [website/docs/guides/gold-table-pipeline.md](/website/docs/guides/gold-table-pipeline.md) | Markdown | 201 | 0 | 92 | 293 |
| [website/docs/guides/google-colab-setup.md](/website/docs/guides/google-colab-setup.md) | Markdown | 400 | 0 | 137 | 537 |
| [website/docs/guides/hackathon-video-submission-ideas.md](/website/docs/guides/hackathon-video-submission-ideas.md) | Markdown | 595 | 0 | 320 | 915 |
| [website/docs/guides/hackathon/big-timber-tuscaloosa-jurisdiction-ids.md](/website/docs/guides/hackathon/big-timber-tuscaloosa-jurisdiction-ids.md) | Markdown | 36 | 0 | 17 | 53 |
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
| [website/docs/guides/local-llm-web-scraping.md](/website/docs/guides/local-llm-web-scraping.md) | Markdown | 100 | 0 | 36 | 136 |
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
| [website/docs/integrations/eboard-manual.md](/website/docs/integrations/eboard-manual.md) | Markdown | 157 | 0 | 44 | 201 |
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
| [website/docusaurus.config.ts](/website/docusaurus.config.ts) | TypeScript | 263 | 26 | 17 | 306 |
| [website/package-lock.json](/website/package-lock.json) | JSON | 21,150 | 0 | 1 | 21,151 |
| [website/package.json](/website/package.json) | JSON | 54 | 0 | 1 | 55 |
| [website/scripts/check-mermaid.mjs](/website/scripts/check-mermaid.mjs) | JavaScript | 48 | 7 | 4 | 59 |
| [website/scripts/dompurify-resolve-hook.mjs](/website/scripts/dompurify-resolve-hook.mjs) | JavaScript | 15 | 0 | 3 | 18 |
| [website/scripts/mermaid-dom-purify.mjs](/website/scripts/mermaid-dom-purify.mjs) | JavaScript | 9 | 1 | 3 | 13 |
| [website/scripts/register-dompurify.mjs](/website/scripts/register-dompurify.mjs) | JavaScript | 2 | 0 | 2 | 4 |
| [website/sidebars.ts](/website/sidebars.ts) | TypeScript | 469 | 22 | 9 | 500 |
| [website/src/clientModules/gtagSafeShim.ts](/website/src/clientModules/gtagSafeShim.ts) | TypeScript | 13 | 4 | 2 | 19 |
| [website/src/components/HomepageFeatures/index.tsx](/website/src/components/HomepageFeatures/index.tsx) | TypeScript JSX | 67 | 0 | 5 | 72 |
| [website/src/components/HomepageFeatures/styles.module.css](/website/src/components/HomepageFeatures/styles.module.css) | PostCSS | 10 | 0 | 2 | 12 |
| [website/src/components/StructuredData.tsx](/website/src/components/StructuredData.tsx) | TypeScript JSX | 101 | 4 | 5 | 110 |
| [website/src/components/ZoomableMermaid/index.tsx](/website/src/components/ZoomableMermaid/index.tsx) | TypeScript JSX | 64 | 0 | 3 | 67 |
| [website/src/components/ZoomableMermaid/styles.module.css](/website/src/components/ZoomableMermaid/styles.module.css) | PostCSS | 147 | 3 | 24 | 174 |
| [website/src/css/custom.css](/website/src/css/custom.css) | PostCSS | 196 | 25 | 37 | 258 |
| [website/src/pages/dashboard.tsx](/website/src/pages/dashboard.tsx) | TypeScript JSX | 72 | 2 | 8 | 82 |
| [website/src/pages/index.module.css](/website/src/pages/index.module.css) | PostCSS | 16 | 4 | 4 | 24 |
| [website/src/pages/index.tsx](/website/src/pages/index.tsx) | TypeScript JSX | 416 | 103 | 29 | 548 |
| [website/src/theme/Root.tsx](/website/src/theme/Root.tsx) | TypeScript JSX | 11 | 0 | 2 | 13 |
| [website/static/google6934fc6e3618949f.html](/website/static/google6934fc6e3618949f.html) | HTML | 1 | 0 | 0 | 1 |
| [website/static/img/communityone\_logo.svg](/website/static/img/communityone_logo.svg) | XML | 13 | 5 | 5 | 23 |
| [website/static/img/logo.svg](/website/static/img/logo.svg) | XML | 1 | 0 | 0 | 1 |
| [website/static/img/undraw\_docusaurus\_mountain.svg](/website/static/img/undraw_docusaurus_mountain.svg) | XML | 171 | 0 | 1 | 172 |
| [website/static/img/undraw\_docusaurus\_react.svg](/website/static/img/undraw_docusaurus_react.svg) | XML | 170 | 0 | 1 | 171 |
| [website/static/img/undraw\_docusaurus\_tree.svg](/website/static/img/undraw_docusaurus_tree.svg) | XML | 40 | 0 | 1 | 41 |
| [website/test-admonition.md](/website/test-admonition.md) | Markdown | 13 | 0 | 5 | 18 |
| [website/tsconfig.json](/website/tsconfig.json) | JSON with Comments | 9 | 3 | 1 | 13 |

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)