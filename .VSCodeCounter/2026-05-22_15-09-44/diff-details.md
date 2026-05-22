# Diff Details

Date : 2026-05-22 15:09:44

Directory /home/developer/projects/open-navigator

Total : 277 files,  49223 codes, 5826 comments, 6220 blanks, all 61269 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [.github/copilot-instructions.md](/.github/copilot-instructions.md) | Markdown | 12 | 0 | 5 | 17 |
| [agents/scraper.py](/agents/scraper.py) | Python | 34 | 7 | 10 | 51 |
| [api/main.py](/api/main.py) | Python | 6 | 0 | 0 | 6 |
| [api/routes/jurisdiction\_mapping.py](/api/routes/jurisdiction_mapping.py) | Python | 108 | 40 | 14 | 162 |
| [api/routes/lighthouse\_reports.py](/api/routes/lighthouse_reports.py) | Python | 167 | 54 | 31 | 252 |
| [api/routes/locations.py](/api/routes/locations.py) | Python | 110 | 57 | 22 | 189 |
| [api/routes/stats\_neon.py](/api/routes/stats_neon.py) | Python | 16 | -2 | 0 | 14 |
| [api/static/assets/index-7vzWAgiE.css](/api/static/assets/index-7vzWAgiE.css) | PostCSS | 1 | 0 | 1 | 2 |
| [api/static/assets/index-BqWDe\_X1.css](/api/static/assets/index-BqWDe_X1.css) | PostCSS | -1 | 0 | -1 | -2 |
| [api/static/assets/index-CQteqSZT.js](/api/static/assets/index-CQteqSZT.js) | JavaScript | -223 | 0 | -21 | -244 |
| [api/static/assets/index-CuLxv8We.js](/api/static/assets/index-CuLxv8We.js) | JavaScript | 223 | 0 | 21 | 244 |
| [calendar\_year\_util.py](/calendar_year_util.py) | Python | -43 | -2 | -6 | -51 |
| [dbt\_project/macros/jurisdiction\_mapping\_primary\_from\_source\_columns.sql](/dbt_project/macros/jurisdiction_mapping_primary_from_source_columns.sql) | MS SQL | 1 | 0 | 0 | 1 |
| [dbt\_project/macros/municipality\_name\_allows\_county\_portal\_url.sql](/dbt_project/macros/municipality_name_allows_county_portal_url.sql) | MS SQL | 9 | 0 | 1 | 10 |
| [dbt\_project/macros/uscm\_league\_county\_portal\_blocked.sql](/dbt_project/macros/uscm_league_county_portal_blocked.sql) | MS SQL | 6 | 0 | 1 | 7 |
| [dbt\_project/macros/website\_domain\_is\_county\_portal\_host.sql](/dbt_project/macros/website_domain_is_county_portal_host.sql) | MS SQL | 6 | 0 | 1 | 7 |
| [dbt\_project/models/intermediate/\_intermediate.yml](/dbt_project/models/intermediate/_intermediate.yml) | YAML | 8 | 0 | 0 | 8 |
| [dbt\_project/models/intermediate/int\_events\_channels.sql](/dbt_project/models/intermediate/int_events_channels.sql) | MS SQL | 4 | 0 | 0 | 4 |
| [dbt\_project/models/intermediate/int\_jurisdiction\_websites.sql](/dbt_project/models/intermediate/int_jurisdiction_websites.sql) | MS SQL | 126 | 3 | 7 | 136 |
| [dbt\_project/models/marts/event.sql](/dbt_project/models/marts/event.sql) | MS SQL | 113 | 29 | 13 | 155 |
| [dbt\_project/models/marts/events\_search.sql](/dbt_project/models/marts/events_search.sql) | MS SQL | -113 | -29 | -13 | -155 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_analysis.sql](/dbt_project/models/marts/jurisdiction_mapping_analysis.sql) | MS SQL | 19 | 1 | 0 | 20 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary.sql) | MS SQL | 1 | 0 | 0 | 1 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary\_by\_acs\_income\_level.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary_by_acs_income_level.sql) | MS SQL | 1 | 0 | 0 | 1 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary\_by\_acs\_population\_tier.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary_by_acs_population_tier.sql) | MS SQL | 1 | 0 | 0 | 1 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary\_municipality\_places.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary_municipality_places.sql) | MS SQL | 1 | 0 | 0 | 1 |
| [dbt\_project/models/marts/jurisdiction\_state\_aggregate.sql](/dbt_project/models/marts/jurisdiction_state_aggregate.sql) | MS SQL | 268 | 44 | 29 | 341 |
| [dbt\_project/models/marts/organization\_nonprofit.sql](/dbt_project/models/marts/organization_nonprofit.sql) | MS SQL | 148 | 16 | 6 | 170 |
| [dbt\_project/models/marts/organizations\_nonprofit\_search.sql](/dbt_project/models/marts/organizations_nonprofit_search.sql) | MS SQL | -148 | -16 | -6 | -170 |
| [dbt\_project/models/marts/stats\_aggregates.sql](/dbt_project/models/marts/stats_aggregates.sql) | MS SQL | -268 | -44 | -29 | -341 |
| [dbt\_project/models/staging/\_staging.yml](/dbt_project/models/staging/_staging.yml) | YAML | 4 | 0 | 0 | 4 |
| [debug-dropdown.html](/debug-dropdown.html) | HTML | -80 | 0 | -13 | -93 |
| [docker-compose.verapdf.example.yml](/docker-compose.verapdf.example.yml) | YAML | 19 | 7 | 2 | 28 |
| [docs/meetings\_scrape\_big\_timber\_tuscaloosa\_inventory.md](/docs/meetings_scrape_big_timber_tuscaloosa_inventory.md) | Markdown | 13 | 0 | 4 | 17 |
| [frontend/src/App.tsx](/frontend/src/App.tsx) | TypeScript JSX | 2 | 0 | 0 | 2 |
| [frontend/src/api/jurisdictionMappingUnmapped.ts](/frontend/src/api/jurisdictionMappingUnmapped.ts) | TypeScript | 60 | 2 | 7 | 69 |
| [frontend/src/components/DataExplorerLayout.tsx](/frontend/src/components/DataExplorerLayout.tsx) | TypeScript JSX | 12 | 0 | 0 | 12 |
| [frontend/src/index.css](/frontend/src/index.css) | PostCSS | 10 | 0 | 0 | 10 |
| [frontend/src/pages/Hackathons.tsx](/frontend/src/pages/Hackathons.tsx) | TypeScript JSX | 36 | 1 | 1 | 38 |
| [frontend/src/pages/LighthouseReportPage.tsx](/frontend/src/pages/LighthouseReportPage.tsx) | TypeScript JSX | 300 | 1 | 22 | 323 |
| [frontend/src/pages/jurisdiction-quality/EntityQualityDashboard.tsx](/frontend/src/pages/jurisdiction-quality/EntityQualityDashboard.tsx) | TypeScript JSX | -25 | 0 | -4 | -29 |
| [frontend/src/utils/dataExplorerPaths.ts](/frontend/src/utils/dataExplorerPaths.ts) | TypeScript | 1 | 1 | 1 | 3 |
| [prompts/applying\_wicked\_to\_communityone.md](/prompts/applying_wicked_to_communityone.md) | Markdown | -21 | 0 | -21 | -42 |
| [prompts/polcy\_analysis\_readable.md](/prompts/polcy_analysis_readable.md) | Markdown | 5 | 0 | 1 | 6 |
| [prompts/policy\_analysis.md](/prompts/policy_analysis.md) | Markdown | 104 | 0 | -4 | 100 |
| [prompts/policy\_analysis\_part\_1.md](/prompts/policy_analysis_part_1.md) | Markdown | 275 | 0 | 29 | 304 |
| [prompts/policy\_analysis\_part\_2.md](/prompts/policy_analysis_part_2.md) | Markdown | 63 | 0 | 27 | 90 |
| [prompts/policy\_analysis\_v1.md](/prompts/policy_analysis_v1.md) | Markdown | 788 | 0 | 76 | 864 |
| [requirements.txt](/requirements.txt) | pip requirements | 3 | 0 | 0 | 3 |
| [scripts/README.md](/scripts/README.md) | Markdown | 1 | 0 | 0 | 1 |
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
| [scripts/datasources/census/link\_cities\_counties\_to\_search.py](/scripts/datasources/census/link_cities_counties_to_search.py) | Python | -2 | 0 | 0 | -2 |
| [scripts/datasources/fec/README.md](/scripts/datasources/fec/README.md) | Markdown | 10 | 0 | -3 | 7 |
| [scripts/datasources/fec/fec\_paths.py](/scripts/datasources/fec/fec_paths.py) | Python | 10 | 6 | 6 | 22 |
| [scripts/datasources/fec/load\_fec\_bulk.py](/scripts/datasources/fec/load_fec_bulk.py) | Python | 2 | 0 | 2 | 4 |
| [scripts/datasources/fec/load\_fec\_individual\_contributions\_by\_date\_to\_bronze.py](/scripts/datasources/fec/load_fec_individual_contributions_by_date_to_bronze.py) | Python | 177 | 298 | 22 | 497 |
| [scripts/datasources/fec/run\_bulk\_download.sh](/scripts/datasources/fec/run_bulk_download.sh) | Shell Script | 12 | 7 | 7 | 26 |
| [scripts/datasources/fec/unzip\_fec\_data.py](/scripts/datasources/fec/unzip_fec_data.py) | Python | 3 | -4 | 1 | 0 |
| [scripts/datasources/jurisdictions/export\_jurisdiction\_mapping\_quality\_json.py](/scripts/datasources/jurisdictions/export_jurisdiction_mapping_quality_json.py) | Python | -14 | 4 | -3 | -13 |
| [scripts/datasources/jurisdictions/jurisdiction\_mapping\_queries.py](/scripts/datasources/jurisdictions/jurisdiction_mapping_queries.py) | Python | 86 | 3 | 9 | 98 |
| [scripts/datasources/jurisdictions/load\_counties\_to\_postgres.py](/scripts/datasources/jurisdictions/load_counties_to_postgres.py) | Python | 3 | 0 | 0 | 3 |
| [scripts/datasources/jurisdictions/load\_details\_to\_postgres.py](/scripts/datasources/jurisdictions/load_details_to_postgres.py) | Python | -44 | -14 | -18 | -76 |
| [scripts/datasources/jurisdictions/public\_jurisdiction\_columns.py](/scripts/datasources/jurisdictions/public_jurisdiction_columns.py) | Python | 7 | 2 | 4 | 13 |
| [scripts/datasources/jurisdictions/publish\_jurisdiction\_mapping\_analysis\_to\_hf.py](/scripts/datasources/jurisdictions/publish_jurisdiction_mapping_analysis_to_hf.py) | Python | 87 | 119 | 24 | 230 |
| [scripts/datasources/leagueofcities/download\_league\_city\_directories.py](/scripts/datasources/leagueofcities/download_league_city_directories.py) | Python | 171 | 9 | 9 | 189 |
| [scripts/datasources/leagueofcities/league\_website\_sanitize.py](/scripts/datasources/leagueofcities/league_website_sanitize.py) | Python | 58 | 11 | 15 | 84 |
| [scripts/datasources/leagueofcities/load\_league\_city\_directories\_to\_bronze.py](/scripts/datasources/leagueofcities/load_league_city_directories_to_bronze.py) | Python | 10 | -6 | 5 | 9 |
| [scripts/datasources/leagueofcities/sanitize\_league\_cache\_websites.py](/scripts/datasources/leagueofcities/sanitize_league_cache_websites.py) | Python | 45 | 8 | 10 | 63 |
| [scripts/datasources/localview/enrich\_from\_localview.py](/scripts/datasources/localview/enrich_from_localview.py) | Python | 0 | -1 | 0 | -1 |
| [scripts/datasources/nces/enrich\_jurisdictions\_from\_nces.py](/scripts/datasources/nces/enrich_jurisdictions_from_nces.py) | Python | 4 | 0 | -2 | 2 |
| [scripts/datasources/nces/fix\_and\_enrich\_school\_districts.py](/scripts/datasources/nces/fix_and_enrich_school_districts.py) | Python | 0 | -1 | 0 | -1 |
| [scripts/datasources/uscm/scrape\_mayor\_elections.py](/scripts/datasources/uscm/scrape_mayor_elections.py) | Python | -1 | -1 | 0 | -2 |
| [scripts/datasources/wikidata/README.md](/scripts/datasources/wikidata/README.md) | Markdown | 126 | 0 | 29 | 155 |
| [scripts/datasources/wikidata/discover\_municipality\_website\_gaps.py](/scripts/datasources/wikidata/discover_municipality_website_gaps.py) | Python | 59 | 2 | 15 | 76 |
| [scripts/datasources/wikidata/hydrate\_county\_websites\_from\_wikidata.py](/scripts/datasources/wikidata/hydrate_county_websites_from_wikidata.py) | Python | 45 | 166 | 8 | 219 |
| [scripts/datasources/wikidata/hydrate\_municipality\_websites\_from\_wikidata.py](/scripts/datasources/wikidata/hydrate_municipality_websites_from_wikidata.py) | Python | 46 | 169 | 9 | 224 |
| [scripts/datasources/wikidata/load\_jurisdictions\_wikidata.py](/scripts/datasources/wikidata/load_jurisdictions_wikidata.py) | Python | 192 | 79 | 14 | 285 |
| [scripts/datasources/wikidata/parquet\_qid\_lookup.py](/scripts/datasources/wikidata/parquet_qid_lookup.py) | Python | 221 | 73 | 34 | 328 |
| [scripts/datasources/wikidata/run\_hydrate\_county\_websites.sh](/scripts/datasources/wikidata/run_hydrate_county_websites.sh) | Shell Script | 11 | 9 | 5 | 25 |
| [scripts/datasources/wikidata/run\_hydrate\_municipality\_websites.sh](/scripts/datasources/wikidata/run_hydrate_municipality_websites.sh) | Shell Script | 11 | 10 | 5 | 26 |
| [scripts/datasources/wikidata/run\_municipality\_websites\_gap\_states.sh](/scripts/datasources/wikidata/run_municipality_websites_gap_states.sh) | Shell Script | 76 | 14 | 15 | 105 |
| [scripts/datasources/wikidata/warm\_geography\_cache\_from\_parquet.py](/scripts/datasources/wikidata/warm_geography_cache_from_parquet.py) | Python | 87 | 21 | 20 | 128 |
| [scripts/datasources/wikidata/wikidata\_fips\_gnis\_extract\_local.py](/scripts/datasources/wikidata/wikidata_fips_gnis_extract_local.py) | Python | 35 | 7 | 0 | 42 |
| [scripts/datasources/youtube/backfill\_jurisdiction\_transcripts.py](/scripts/datasources/youtube/backfill_jurisdiction_transcripts.py) | Python | 1,055 | 128 | 95 | 1,278 |
| [scripts/datasources/youtube/dedupe\_meeting\_videos.py](/scripts/datasources/youtube/dedupe_meeting_videos.py) | Python | 210 | 15 | 43 | 268 |
| [scripts/datasources/youtube/download\_audio\_to\_drive.py](/scripts/datasources/youtube/download_audio_to_drive.py) | Python | 33 | 11 | 0 | 44 |
| [scripts/datasources/youtube/download\_tuscaloosa\_city\_meeting\_audio.py](/scripts/datasources/youtube/download_tuscaloosa_city_meeting_audio.py) | Python | 225 | 28 | 34 | 287 |
| [scripts/datasources/youtube/load\_channel\_candidates\_to\_catalog.py](/scripts/datasources/youtube/load_channel_candidates_to_catalog.py) | Python | 63 | 9 | 15 | 87 |
| [scripts/datasources/youtube/load\_missing\_county\_channels.py](/scripts/datasources/youtube/load_missing_county_channels.py) | Python | 251 | 6 | 34 | 291 |
| [scripts/datasources/youtube/load\_youtube\_events\_to\_postgres.py](/scripts/datasources/youtube/load_youtube_events_to_postgres.py) | Python | 273 | -7 | 13 | 279 |
| [scripts/datasources/youtube/load\_youtube\_for\_jurisdiction.py](/scripts/datasources/youtube/load_youtube_for_jurisdiction.py) | Python | 126 | 19 | 17 | 162 |
| [scripts/datasources/youtube/normalize\_youtube\_jurisdiction\_ids.py](/scripts/datasources/youtube/normalize_youtube_jurisdiction_ids.py) | Python | 326 | 53 | 55 | 434 |
| [scripts/datasources/youtube/run\_audit\_ga\_jurisdiction\_youtube\_gaps.sh](/scripts/datasources/youtube/run_audit_ga_jurisdiction_youtube_gaps.sh) | Shell Script | 5 | 0 | 0 | 5 |
| [scripts/datasources/youtube/run\_priority\_states\_last\_n.sh](/scripts/datasources/youtube/run_priority_states_last_n.sh) | Shell Script | 321 | 28 | 25 | 374 |
| [scripts/datasources/youtube/transcript\_api\_client.py](/scripts/datasources/youtube/transcript_api_client.py) | Python | 33 | 12 | 10 | 55 |
| [scripts/deployment/neon/README.md](/scripts/deployment/neon/README.md) | Markdown | 1 | 0 | 0 | 1 |
| [scripts/deployment/neon/ensure\_bronze\_jurisdictions\_cloud.py](/scripts/deployment/neon/ensure_bronze_jurisdictions_cloud.py) | Python | 1 | 0 | 0 | 1 |
| [scripts/deployment/neon/migrations/018\_policy\_legislation\_linkage.sql](/scripts/deployment/neon/migrations/018_policy_legislation_linkage.sql) | MS SQL | 69 | 7 | 12 | 88 |
| [scripts/deployment/neon/migrations/018\_rename\_public\_core\_tables.sql](/scripts/deployment/neon/migrations/018_rename_public_core_tables.sql) | MS SQL | 25 | 10 | 6 | 41 |
| [scripts/deployment/neon/migrations/019\_rename\_public\_entity\_tables.sql](/scripts/deployment/neon/migrations/019_rename_public_entity_tables.sql) | MS SQL | 9 | 9 | 5 | 23 |
| [scripts/deployment/neon/migrations/020\_rename\_public\_log\_sync\_tables.sql](/scripts/deployment/neon/migrations/020_rename_public_log_sync_tables.sql) | MS SQL | 4 | 6 | 4 | 14 |
| [scripts/deployment/neon/migrations/021\_rename\_oauth\_states\_to\_contact\_oauth\_states.sql](/scripts/deployment/neon/migrations/021_rename_oauth_states_to_contact_oauth_states.sql) | MS SQL | 3 | 5 | 4 | 12 |
| [scripts/deployment/neon/migrations/022\_rename\_organizations\_nonprofit\_search\_to\_organization\_nonprofit.sql](/scripts/deployment/neon/migrations/022_rename_organizations_nonprofit_search_to_organization_nonprofit.sql) | MS SQL | 17 | 6 | 5 | 28 |
| [scripts/deployment/neon/migrations/023\_rename\_reference\_ntee\_codes\_to\_cause\_ntee.sql](/scripts/deployment/neon/migrations/023_rename_reference_ntee_codes_to_cause_ntee.sql) | MS SQL | 16 | 6 | 4 | 26 |
| [scripts/deployment/neon/migrations/024\_rename\_contact\_oauth\_states\_to\_contact\_oauth\_state.sql](/scripts/deployment/neon/migrations/024_rename_contact_oauth_states_to_contact_oauth_state.sql) | MS SQL | 3 | 5 | 4 | 12 |
| [scripts/deployment/neon/migrations/025\_rename\_nonprofits\_search\_to\_organization\_nonprofit.sql](/scripts/deployment/neon/migrations/025_rename_nonprofits_search_to_organization_nonprofit.sql) | MS SQL | 17 | 6 | 5 | 28 |
| [scripts/deployment/neon/migrations/026\_rename\_wikidata\_fips\_gnis\_map.sql](/scripts/deployment/neon/migrations/026_rename_wikidata_fips_gnis_map.sql) | MS SQL | 3 | 5 | 4 | 12 |
| [scripts/deployment/neon/migrations/027\_rename\_state\_aggregate\_to\_jurisdiction\_state\_aggregate.sql](/scripts/deployment/neon/migrations/027_rename_state_aggregate_to_jurisdiction_state_aggregate.sql) | MS SQL | 6 | 5 | 5 | 16 |
| [scripts/deployment/neon/migrations/028\_rename\_event\_columns.sql](/scripts/deployment/neon/migrations/028_rename_event_columns.sql) | MS SQL | 23 | 7 | 7 | 37 |
| [scripts/deployment/neon/migrations/029\_rename\_user\_id\_column.sql](/scripts/deployment/neon/migrations/029_rename_user_id_column.sql) | MS SQL | 3 | 5 | 4 | 12 |
| [scripts/deployment/neon/migrations/032\_create\_bronze\_jurisdiction\_website\_accessibility.sql](/scripts/deployment/neon/migrations/032_create_bronze_jurisdiction_website_accessibility.sql) | MS SQL | 31 | 8 | 7 | 46 |
| [scripts/deployment/neon/migrations/033\_create\_bronze\_jurisdiction\_pdf\_verapdf.sql](/scripts/deployment/neon/migrations/033_create_bronze_jurisdiction_pdf_verapdf.sql) | MS SQL | 32 | 5 | 7 | 44 |
| [scripts/deployment/neon/migrations/034\_create\_bronze\_jurisdiction\_website\_lighthouse.sql](/scripts/deployment/neon/migrations/034_create_bronze_jurisdiction_website_lighthouse.sql) | MS SQL | 66 | 4 | 8 | 78 |
| [scripts/deployment/neon/migrations/035\_create\_bronze\_contacts\_scraped.sql](/scripts/deployment/neon/migrations/035_create_bronze_contacts_scraped.sql) | MS SQL | 32 | 6 | 6 | 44 |
| [scripts/deployment/neon/migrations/036\_add\_official\_website\_updated\_at\_bronze\_wikidata.sql](/scripts/deployment/neon/migrations/036_add_official_website_updated_at_bronze_wikidata.sql) | MS SQL | 8 | 2 | 5 | 15 |
| [scripts/deployment/neon/migrations/037\_bronze\_events\_youtube\_video\_url\_unique.sql](/scripts/deployment/neon/migrations/037_bronze_events_youtube_video_url_unique.sql) | MS SQL | 12 | 7 | 7 | 26 |
| [scripts/deployment/neon/migrations/038\_jurisdiction\_merge\_details\_search.sql](/scripts/deployment/neon/migrations/038_jurisdiction_merge_details_search.sql) | MS SQL | 170 | 14 | 15 | 199 |
| [scripts/deployment/neon/psql\_resolved.sh](/scripts/deployment/neon/psql_resolved.sh) | Shell Script | 14 | 4 | 1 | 19 |
| [scripts/deployment/neon/schema.sql](/scripts/deployment/neon/schema.sql) | MS SQL | 36 | 2 | 3 | 41 |
| [scripts/deployment/neon/schema\_bills.sql](/scripts/deployment/neon/schema_bills.sql) | MS SQL | 1 | 0 | 0 | 1 |
| [scripts/discovery/README.md](/scripts/discovery/README.md) | Markdown | 1 | 0 | 1 | 2 |
| [scripts/discovery/archive/\_\_init\_\_.py](/scripts/discovery/archive/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [scripts/discovery/archive/comprehensive\_discovery\_pipeline\_meetings.py](/scripts/discovery/archive/comprehensive_discovery_pipeline_meetings.py) | Python | 6 | 5 | 3 | 14 |
| [scripts/discovery/bronze\_contacts\_scraped\_persist.py](/scripts/discovery/bronze_contacts_scraped_persist.py) | Python | 63 | 34 | 6 | 103 |
| [scripts/discovery/civicclerk\_meetings\_sync.py](/scripts/discovery/civicclerk_meetings_sync.py) | Python | 329 | 21 | 48 | 398 |
| [scripts/discovery/civicclerk\_public\_api.py](/scripts/discovery/civicclerk_public_api.py) | Python | 189 | 18 | 34 | 241 |
| [scripts/discovery/comprehensive\_discovery\_pipeline.py](/scripts/discovery/comprehensive_discovery_pipeline.py) | Python | -1 | -1 | -1 | -3 |
| [scripts/discovery/comprehensive\_discovery\_pipeline\_jurisdiction.py](/scripts/discovery/comprehensive_discovery_pipeline_jurisdiction.py) | Python | 3,124 | 517 | 284 | 3,925 |
| [scripts/discovery/comprehensive\_discovery\_pipeline\_meetings.py](/scripts/discovery/comprehensive_discovery_pipeline_meetings.py) | Python | -1,762 | -384 | -176 | -2,322 |
| [scripts/discovery/contact\_directory\_heuristics.py](/scripts/discovery/contact_directory_heuristics.py) | Python | 130 | 11 | 15 | 156 |
| [scripts/discovery/contact\_extract\_crawl4ai.py](/scripts/discovery/contact_extract_crawl4ai.py) | Python | 326 | 68 | 42 | 436 |
| [scripts/discovery/contact\_extract\_from\_html.py](/scripts/discovery/contact_extract_from_html.py) | Python | 1,624 | 114 | 234 | 1,972 |
| [scripts/discovery/contact\_profile\_images.py](/scripts/discovery/contact_profile_images.py) | Python | 731 | 50 | 64 | 845 |
| [scripts/discovery/contacts\_bundle.py](/scripts/discovery/contacts_bundle.py) | Python | 175 | 14 | 22 | 211 |
| [scripts/discovery/download\_gomeet\_recordings.py](/scripts/discovery/download_gomeet_recordings.py) | Python | 853 | 76 | 109 | 1,038 |
| [scripts/discovery/gomeet\_mp4\_to\_opus.py](/scripts/discovery/gomeet_mp4_to_opus.py) | Python | 303 | 42 | 51 | 396 |
| [scripts/discovery/jurisdiction\_contact\_seed\_urls.py](/scripts/discovery/jurisdiction_contact_seed_urls.py) | Python | 40 | 19 | 6 | 65 |
| [scripts/discovery/jurisdiction\_discovery\_pipeline.py](/scripts/discovery/jurisdiction_discovery_pipeline.py) | Python | 2 | 0 | 0 | 2 |
| [scripts/discovery/jurisdiction\_meeting\_seed\_urls.py](/scripts/discovery/jurisdiction_meeting_seed_urls.py) | Python | 28 | 8 | 5 | 41 |
| [scripts/discovery/load\_scraped\_meetings\_manifests\_to\_bronze.py](/scripts/discovery/load_scraped_meetings_manifests_to_bronze.py) | Python | -66 | -1 | -16 | -83 |
| [scripts/discovery/meeting\_document\_naming.py](/scripts/discovery/meeting_document_naming.py) | Python | 662 | 55 | 87 | 804 |
| [scripts/discovery/meetings\_platform\_heuristics.py](/scripts/discovery/meetings_platform_heuristics.py) | Python | 212 | 40 | 31 | 283 |
| [scripts/discovery/meetings\_playwright\_fetch.py](/scripts/discovery/meetings_playwright_fetch.py) | Python | 104 | 8 | 12 | 124 |
| [scripts/discovery/meetings\_sitemap\_discovery.py](/scripts/discovery/meetings_sitemap_discovery.py) | Python | 3 | 0 | 0 | 3 |
| [scripts/discovery/refresh\_contacts\_from\_crawl\_html.py](/scripts/discovery/refresh_contacts_from_crawl_html.py) | Python | 391 | 9 | 42 | 442 |
| [scripts/discovery/rename\_gomeet\_downloads.py](/scripts/discovery/rename_gomeet_downloads.py) | Python | 212 | 21 | 40 | 273 |
| [scripts/discovery/rename\_scraped\_meeting\_pdf\_files.py](/scripts/discovery/rename_scraped_meeting_pdf_files.py) | Python | 373 | 26 | 54 | 453 |
| [scripts/discovery/scraped\_meetings\_crawl\_html\_pdfs.py](/scripts/discovery/scraped_meetings_crawl_html_pdfs.py) | Python | 169 | 16 | 28 | 213 |
| [scripts/fix-cursor-state-bloat.sh](/scripts/fix-cursor-state-bloat.sh) | Shell Script | 27 | 4 | 7 | 38 |
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
| [scripts/gemini/policy\_processing\_status\_report.py](/scripts/gemini/policy_processing_status_report.py) | Python | 376 | 623 | 55 | 1,054 |
| [scripts/gemini/print\_uncontested\_speakers.py](/scripts/gemini/print_uncontested_speakers.py) | Python | 107 | 3 | 20 | 130 |
| [scripts/gemini/reparse\_policy\_run.py](/scripts/gemini/reparse_policy_run.py) | Python | 176 | 3 | 30 | 209 |
| [scripts/gemini/speaker\_hints.py](/scripts/gemini/speaker_hints.py) | Python | 127 | 17 | 19 | 163 |
| [scripts/gemini/transcript\_cache\_paths.py](/scripts/gemini/transcript_cache_paths.py) | Python | 1,768 | 135 | 211 | 2,114 |
| [scripts/gemini/transcript\_fetch.py](/scripts/gemini/transcript_fetch.py) | Python | 43 | 8 | 10 | 61 |
| [scripts/gemini/validate\_analysis\_legislation.py](/scripts/gemini/validate_analysis_legislation.py) | Python | 32 | 2 | 11 | 45 |
| [scripts/gemini/validate\_mermaid\_fences.py](/scripts/gemini/validate_mermaid_fences.py) | Python | 29 | 2 | 9 | 40 |
| [scripts/gemini/validate\_mermaid\_reports.py](/scripts/gemini/validate_mermaid_reports.py) | Python | 111 | 18 | 18 | 147 |
| [scripts/huggingface/upload\_to\_huggingface.py](/scripts/huggingface/upload_to_huggingface.py) | Python | 0 | -1 | 0 | -1 |
| [scripts/localview/scrape\_youtube\_channels.py](/scripts/localview/scrape_youtube_channels.py) | Python | 118 | -20 | -2 | 96 |
| [scripts/open-in-cursor.sh](/scripts/open-in-cursor.sh) | Shell Script | 3 | 2 | 1 | 6 |
| [scripts/scraping/\_\_init\_\_.py](/scripts/scraping/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [scripts/scraping/crawl\_llm\_sidecar.py](/scripts/scraping/crawl_llm_sidecar.py) | Python | 63 | 13 | 12 | 88 |
| [scripts/scraping/extract\_page\_structured.py](/scripts/scraping/extract_page_structured.py) | Python | 106 | 17 | 20 | 143 |
| [scripts/scraping/html\_to\_markdown.py](/scripts/scraping/html_to_markdown.py) | Python | 85 | 12 | 21 | 118 |
| [scripts/scraping/ollama\_extract.py](/scripts/scraping/ollama_extract.py) | Python | 161 | 11 | 33 | 205 |
| [scripts/scraping/schemas.py](/scripts/scraping/schemas.py) | Python | 42 | 2 | 10 | 54 |
| [scripts/scraping/setup\_ollama\_gemma.sh](/scripts/scraping/setup_ollama_gemma.sh) | Shell Script | 34 | 7 | 8 | 49 |
| [scripts/utils/calendar\_year\_util.py](/scripts/utils/calendar_year_util.py) | Python | 43 | 2 | 6 | 51 |
| [scripts/utils/ensure\_governance\_pipeline\_drive\_layout.py](/scripts/utils/ensure_governance_pipeline_drive_layout.py) | Python | 27 | 15 | 8 | 50 |
| [scripts/utils/gdrive\_paths.py](/scripts/utils/gdrive_paths.py) | Python | 131 | 56 | 34 | 221 |
| [scripts/utils/log\_sync.py](/scripts/utils/log_sync.py) | Python | 0 | 4 | 0 | 4 |
| [scripts/win-open-navigator-in-cursor.bat](/scripts/win-open-navigator-in-cursor.bat) | Batch | 2 | 1 | 1 | 4 |
| [sql/adhoc/matching.sql](/sql/adhoc/matching.sql) | MS SQL | 39 | 0 | 0 | 39 |
| [tests/fixtures/contact\_extract/applingcountyga\_commissioners.html](/tests/fixtures/contact_extract/applingcountyga_commissioners.html) | HTML | 389 | 4 | 42 | 435 |
| [tests/test\_civicclerk\_public\_api.py](/tests/test_civicclerk_public_api.py) | Python | 34 | 1 | 12 | 47 |
| [tests/test\_civicplus\_contact\_extract.py](/tests/test_civicplus_contact_extract.py) | Python | 32 | 1 | 4 | 37 |
| [tests/test\_colab\_bootstrap.py](/tests/test_colab_bootstrap.py) | Python | 18 | 1 | 10 | 29 |
| [tests/test\_colab\_notebook\_ui.py](/tests/test_colab_notebook_ui.py) | Python | 15 | 1 | 13 | 29 |
| [tests/test\_colab\_runtime\_phases.py](/tests/test_colab_runtime_phases.py) | Python | 22 | 1 | 10 | 33 |
| [tests/test\_county\_portal\_host\_macros.py](/tests/test_county_portal_host_macros.py) | Python | 28 | 1 | 16 | 45 |
| [tests/test\_dedupe\_meeting\_videos.py](/tests/test_dedupe_meeting_videos.py) | Python | 56 | 1 | 11 | 68 |
| [tests/test\_demo3\_text\_input.py](/tests/test_demo3_text_input.py) | Python | 39 | 1 | 12 | 52 |
| [tests/test\_demo4\_gemma\_opus.py](/tests/test_demo4_gemma_opus.py) | Python | 112 | 2 | 37 | 151 |
| [tests/test\_ga\_contact\_scraper\_regression.py](/tests/test_ga_contact_scraper_regression.py) | Python | 338 | 108 | 61 | 507 |
| [tests/test\_jurisdiction\_mapping\_queries.py](/tests/test_jurisdiction_mapping_queries.py) | Python | 18 | 1 | 6 | 25 |
| [tests/test\_legislation\_analysis.py](/tests/test_legislation_analysis.py) | Python | 87 | 0 | 13 | 100 |
| [tests/test\_meeting\_consolidated\_summary.py](/tests/test_meeting_consolidated_summary.py) | Python | 75 | 1 | 11 | 87 |
| [tests/test\_meeting\_date\_from\_title.py](/tests/test_meeting_date_from_title.py) | Python | 31 | 0 | 12 | 43 |
| [tests/test\_meeting\_document\_naming.py](/tests/test_meeting_document_naming.py) | Python | 98 | 2 | 23 | 123 |
| [tests/test\_mermaid\_diagrams.py](/tests/test_mermaid_diagrams.py) | Python | 89 | 2 | 13 | 104 |
| [tests/test\_part2\_report\_normalize.py](/tests/test_part2_report_normalize.py) | Python | 10 | 0 | 3 | 13 |
| [tests/test\_pipeline\_media\_scope.py](/tests/test_pipeline_media_scope.py) | Python | 118 | 1 | 33 | 152 |
| [tests/test\_transcript\_cache\_geography.py](/tests/test_transcript_cache_geography.py) | Python | 134 | 0 | 23 | 157 |
| [tests/test\_youtube\_channel\_tabs.py](/tests/test_youtube_channel_tabs.py) | Python | 18 | 1 | 7 | 26 |
| [website/docs/deployment/variable-migration.md](/website/docs/deployment/variable-migration.md) | Markdown | -92 | 0 | -39 | -131 |
| [website/docs/guides/accessibility-testing.md](/website/docs/guides/accessibility-testing.md) | Markdown | 212 | 0 | 96 | 308 |
| [website/docs/guides/hackathon-video-submission-ideas.md](/website/docs/guides/hackathon-video-submission-ideas.md) | Markdown | 484 | 0 | 220 | 704 |
| [website/docs/guides/hackathon/big-timber-tuscaloosa-jurisdiction-ids.md](/website/docs/guides/hackathon/big-timber-tuscaloosa-jurisdiction-ids.md) | Markdown | 36 | 0 | 17 | 53 |
| [website/docs/guides/local-llm-web-scraping.md](/website/docs/guides/local-llm-web-scraping.md) | Markdown | 100 | 0 | 36 | 136 |
| [website/package-lock.json](/website/package-lock.json) | JSON | 348 | 0 | 0 | 348 |
| [website/package.json](/website/package.json) | JSON | 2 | 0 | 0 | 2 |
| [website/scripts/check-mermaid.mjs](/website/scripts/check-mermaid.mjs) | JavaScript | 48 | 7 | 4 | 59 |
| [website/scripts/dompurify-resolve-hook.mjs](/website/scripts/dompurify-resolve-hook.mjs) | JavaScript | 15 | 0 | 3 | 18 |
| [website/scripts/mermaid-dom-purify.mjs](/website/scripts/mermaid-dom-purify.mjs) | JavaScript | 9 | 1 | 3 | 13 |
| [website/scripts/register-dompurify.mjs](/website/scripts/register-dompurify.mjs) | JavaScript | 2 | 0 | 2 | 4 |
| [website/sidebars.ts](/website/sidebars.ts) | TypeScript | 14 | 0 | 0 | 14 |

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details