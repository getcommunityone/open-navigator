# Diff Details

Date : 2026-05-23 23:32:47

Directory /home/developer/projects/open-navigator

Total : 52 files,  4617 codes, 1213 comments, 685 blanks, all 6515 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [CITATIONS.md](/CITATIONS.md) | Markdown | 9 | 0 | 1 | 10 |
| [agents/base.py](/agents/base.py) | Python | -3 | 0 | 0 | -3 |
| [dbt\_project/models/intermediate/\_intermediate.yml](/dbt_project/models/intermediate/_intermediate.yml) | YAML | 21 | 0 | 1 | 22 |
| [dbt\_project/models/intermediate/int\_events\_channels.sql](/dbt_project/models/intermediate/int_events_channels.sql) | MS SQL | 507 | 0 | 22 | 529 |
| [dbt\_project/models/intermediate/int\_jurisdiction\_homepage\_youtube\_channels.sql](/dbt_project/models/intermediate/int_jurisdiction_homepage_youtube_channels.sql) | MS SQL | 259 | 7 | 15 | 281 |
| [pytest.ini](/pytest.ini) | Ini | 5 | 0 | 1 | 6 |
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
| [scripts/datasources/ma\_pilot/\_\_init\_\_.py](/scripts/datasources/ma_pilot/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/ma\_pilot/jurisdictions.py](/scripts/datasources/ma_pilot/jurisdictions.py) | Python | 142 | 22 | 7 | 171 |
| [scripts/datasources/ma\_pilot/mayor\_boost.py](/scripts/datasources/ma_pilot/mayor_boost.py) | Python | 35 | 23 | 11 | 69 |
| [scripts/datasources/ma\_pilot/scrape\_ma\_jurisdictions.py](/scripts/datasources/ma_pilot/scrape_ma_jurisdictions.py) | Python | 207 | 35 | 35 | 277 |
| [scripts/datasources/ma\_pilot/verify.sql](/scripts/datasources/ma_pilot/verify.sql) | MS SQL | 109 | 12 | 10 | 131 |
| [scripts/datasources/netronline/\_\_init\_\_.py](/scripts/datasources/netronline/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/netronline/crawl\_county\_directory.py](/scripts/datasources/netronline/crawl_county_directory.py) | Python | 346 | 71 | 70 | 487 |
| [scripts/datasources/youtube/load\_channel\_candidates\_to\_catalog.py](/scripts/datasources/youtube/load_channel_candidates_to_catalog.py) | Python | 56 | 0 | 2 | 58 |
| [scripts/datasources/youtube/load\_missing\_county\_channels.py](/scripts/datasources/youtube/load_missing_county_channels.py) | Python | 34 | 1 | 4 | 39 |
| [scripts/datasources/youtube/load\_youtube\_events\_to\_postgres.py](/scripts/datasources/youtube/load_youtube_events_to_postgres.py) | Python | 120 | 5 | 9 | 134 |
| [scripts/datasources/youtube/load\_youtube\_for\_jurisdiction.py](/scripts/datasources/youtube/load_youtube_for_jurisdiction.py) | Python | 38 | 0 | 1 | 39 |
| [scripts/datasources/youtube/run\_priority\_states\_channel\_pipeline.sh](/scripts/datasources/youtube/run_priority_states_channel_pipeline.sh) | Shell Script | 121 | 31 | 21 | 173 |
| [scripts/datasources/youtube/test\_cobb\_county\_scrape.py](/scripts/datasources/youtube/test_cobb_county_scrape.py) | Python | 37 | 2 | 13 | 52 |
| [scripts/datasources/youtube/youtube\_channel\_discovery.py](/scripts/datasources/youtube/youtube_channel_discovery.py) | Python | 296 | 67 | 38 | 401 |
| [scripts/deployment/neon/load\_ocd\_jurisdictions\_to\_sql.sh](/scripts/deployment/neon/load_ocd_jurisdictions_to_sql.sh) | Shell Script | 74 | 5 | 16 | 95 |
| [scripts/deployment/neon/migrations/039\_create\_bronze\_jurisdiction\_youtube.sql](/scripts/deployment/neon/migrations/039_create_bronze_jurisdiction_youtube.sql) | MS SQL | 31 | 9 | 6 | 46 |
| [scripts/deployment/neon/migrations/040\_alter\_bronze\_jurisdiction\_youtube\_add\_signals.sql](/scripts/deployment/neon/migrations/040_alter_bronze_jurisdiction_youtube_add_signals.sql) | MS SQL | 15 | 13 | 5 | 33 |
| [scripts/deployment/neon/migrations/041\_add\_ocd\_ids.sql](/scripts/deployment/neon/migrations/041_add_ocd_ids.sql) | MS SQL | 25 | 16 | 14 | 55 |
| [scripts/deployment/neon/migrations/041\_create\_bronze\_jurisdictions\_county\_directory.sql](/scripts/deployment/neon/migrations/041_create_bronze_jurisdictions_county_directory.sql) | MS SQL | 32 | 9 | 6 | 47 |
| [scripts/deployment/neon/migrations/042\_create\_bronze\_jurisdiction\_ocd.sql](/scripts/deployment/neon/migrations/042_create_bronze_jurisdiction_ocd.sql) | MS SQL | 27 | 9 | 11 | 47 |
| [scripts/deployment/neon/migrations/042\_rename\_bronze\_jurisdiction\_youtube\_confidence.sql](/scripts/deployment/neon/migrations/042_rename_bronze_jurisdiction_youtube_confidence.sql) | MS SQL | 6 | 11 | 5 | 22 |
| [scripts/discovery/bronze\_contacts\_scraped\_persist.py](/scripts/discovery/bronze_contacts_scraped_persist.py) | Python | 11 | 6 | 2 | 19 |
| [scripts/discovery/bronze\_jurisdiction\_youtube\_persist.py](/scripts/discovery/bronze_jurisdiction_youtube_persist.py) | Python | 98 | 40 | 12 | 150 |
| [scripts/discovery/bronze\_jurisdictions\_county\_directory\_persist.py](/scripts/discovery/bronze_jurisdictions_county_directory_persist.py) | Python | 57 | 31 | 6 | 94 |
| [scripts/discovery/jurisdiction\_contact\_seed\_urls.py](/scripts/discovery/jurisdiction_contact_seed_urls.py) | Python | 46 | 16 | 0 | 62 |
| [scripts/gemini/policy\_processing\_status\_report.py](/scripts/gemini/policy_processing_status_report.py) | Python | 37 | 82 | 2 | 121 |
| [scripts/localview/scrape\_youtube\_channels.py](/scripts/localview/scrape_youtube_channels.py) | Python | 58 | 2 | 7 | 67 |
| [tests/test\_agents.py](/tests/test_agents.py) | Python | -16 | -2 | -4 | -22 |
| [tests/test\_demo3\_text\_input.py](/tests/test_demo3_text_input.py) | Python | -39 | -1 | -12 | -52 |
| [tests/test\_demo4\_gemma\_opus.py](/tests/test_demo4_gemma_opus.py) | Python | -112 | -2 | -37 | -151 |
| [tests/test\_ga\_contact\_scraper\_regression.py](/tests/test_ga_contact_scraper_regression.py) | Python | 47 | 5 | 7 | 59 |
| [tests/test\_jurisdiction\_contact\_seed\_urls.py](/tests/test_jurisdiction_contact_seed_urls.py) | Python | 9 | 1 | 4 | 14 |
| [tests/test\_part2\_report\_normalize.py](/tests/test_part2_report_normalize.py) | Python | -10 | 0 | -3 | -13 |
| [tests/test\_youtube\_site\_search\_scrape.py](/tests/test_youtube_site_search_scrape.py) | Python | 164 | 15 | 63 | 242 |
| [website/docs/data-sources/citations.md](/website/docs/data-sources/citations.md) | Markdown | 22 | 0 | 6 | 28 |

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details