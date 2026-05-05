# Diff Details

Date : 2026-05-05 07:19:18

Directory /home/developer/projects/open-navigator

Total : 55 files,  8087 codes, 2374 comments, 1605 blanks, all 12066 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [.github/copilot-instructions.md](/.github/copilot-instructions.md) | Markdown | 32 | 0 | 9 | 41 |
| [CITATIONS.md](/CITATIONS.md) | Markdown | 242 | 0 | 47 | 289 |
| [docs/GSA\_DOMAIN\_INTEGRATION.md](/docs/GSA_DOMAIN_INTEGRATION.md) | Markdown | 262 | 0 | 65 | 327 |
| [docs/MEETING\_DATA\_SUMMARY.md](/docs/MEETING_DATA_SUMMARY.md) | Markdown | -192 | 0 | -62 | -254 |
| [download\_acs.sh](/download_acs.sh) | Shell Script | -9 | -6 | -4 | -19 |
| [neon/DEPLOYMENT\_CHECKLIST.md](/neon/DEPLOYMENT_CHECKLIST.md) | Markdown | -148 | 0 | -55 | -203 |
| [prompts/polcy\_analysis\_readable.md](/prompts/polcy_analysis_readable.md) | Markdown | 228 | 0 | 44 | 272 |
| [prompts/policy\_analysis.md](/prompts/policy_analysis.md) | Markdown | 436 | 0 | 44 | 480 |
| [prompts/policy\_analysis\_sample\_inputs.md](/prompts/policy_analysis_sample_inputs.md) | Markdown | 10 | 0 | 0 | 10 |
| [requirements.txt](/requirements.txt) | pip requirements | 1 | 0 | 0 | 1 |
| [scripts/datasources/README.md](/scripts/datasources/README.md) | Markdown | 82 | 0 | 33 | 115 |
| [scripts/datasources/census/download\_acs.sh](/scripts/datasources/census/download_acs.sh) | Shell Script | 9 | 6 | 4 | 19 |
| [scripts/datasources/census/link\_cities\_counties\_to\_search.py](/scripts/datasources/census/link_cities_counties_to_search.py) | Python | 114 | 203 | 12 | 329 |
| [scripts/datasources/census/load\_states\_to\_search.py](/scripts/datasources/census/load_states_to_search.py) | Python | 122 | 16 | 19 | 157 |
| [scripts/datasources/gemini/README.md](/scripts/datasources/gemini/README.md) | Markdown | 193 | 0 | 56 | 249 |
| [scripts/datasources/gemini/\_\_init\_\_.py](/scripts/datasources/gemini/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [scripts/datasources/gemini/analyze\_meeting\_transcripts.py](/scripts/datasources/gemini/analyze_meeting_transcripts.py) | Python | 501 | 188 | 49 | 738 |
| [scripts/datasources/gemini/analyze\_with\_multi\_models.py](/scripts/datasources/gemini/analyze_with_multi_models.py) | Python | 157 | 44 | 36 | 237 |
| [scripts/datasources/gemini/check\_models\_used.py](/scripts/datasources/gemini/check_models_used.py) | Python | 62 | 9 | 19 | 90 |
| [scripts/datasources/gemini/cleanup\_null\_records.py](/scripts/datasources/gemini/cleanup_null_records.py) | Python | 88 | 20 | 35 | 143 |
| [scripts/datasources/gemini/extract\_to\_bronze.py](/scripts/datasources/gemini/extract_to_bronze.py) | Python | 530 | 54 | 70 | 654 |
| [scripts/datasources/govwebsites/README.md](/scripts/datasources/govwebsites/README.md) | Markdown | 82 | 0 | 28 | 110 |
| [scripts/datasources/govwebsites/scrape\_gov\_websites.py](/scripts/datasources/govwebsites/scrape_gov_websites.py) | Python | 142 | 108 | 38 | 288 |
| [scripts/datasources/gsa/load\_gsa\_domains\_to\_postgres.py](/scripts/datasources/gsa/load_gsa_domains_to_postgres.py) | Python | 183 | 435 | 45 | 663 |
| [scripts/datasources/hifld/README.md](/scripts/datasources/hifld/README.md) | Markdown | 157 | 0 | 58 | 215 |
| [scripts/datasources/hifld/download\_and\_load\_hifld.sh](/scripts/datasources/hifld/download_and_load_hifld.sh) | Shell Script | 44 | 36 | 12 | 92 |
| [scripts/datasources/hifld/download\_arcgis\_dataset.py](/scripts/datasources/hifld/download_arcgis_dataset.py) | Python | 193 | 88 | 52 | 333 |
| [scripts/datasources/hifld/load\_hifld\_to\_postgres.py](/scripts/datasources/hifld/load_hifld_to_postgres.py) | Python | 261 | 81 | 64 | 406 |
| [scripts/datasources/master\_data/README.md](/scripts/datasources/master_data/README.md) | Markdown | 310 | 0 | 79 | 389 |
| [scripts/datasources/master\_data/create\_jurisdiction\_master.py](/scripts/datasources/master_data/create_jurisdiction_master.py) | Python | 1,005 | 182 | 144 | 1,331 |
| [scripts/datasources/master\_data/query\_examples.sql](/scripts/datasources/master_data/query_examples.sql) | MS SQL | 281 | 72 | 52 | 405 |
| [scripts/datasources/naco/README.md](/scripts/datasources/naco/README.md) | Markdown | 37 | 0 | 18 | 55 |
| [scripts/datasources/naco/scrape\_naco\_counties.py](/scripts/datasources/naco/scrape_naco_counties.py) | Python | 133 | 71 | 44 | 248 |
| [scripts/datasources/nces/README.md](/scripts/datasources/nces/README.md) | Markdown | 77 | 0 | 30 | 107 |
| [scripts/datasources/nces/README\_ENRICHMENT.md](/scripts/datasources/nces/README_ENRICHMENT.md) | Markdown | 160 | 0 | 46 | 206 |
| [scripts/datasources/nces/enrich\_jurisdictions\_from\_nces.py](/scripts/datasources/nces/enrich_jurisdictions_from_nces.py) | Python | 284 | 53 | 60 | 397 |
| [scripts/datasources/nces/fix\_and\_enrich\_school\_districts.py](/scripts/datasources/nces/fix_and_enrich_school_districts.py) | Python | 144 | 167 | 22 | 333 |
| [scripts/datasources/nces/load\_nces\_to\_postgres.py](/scripts/datasources/nces/load_nces_to_postgres.py) | Python | 301 | 40 | 57 | 398 |
| [scripts/datasources/nces/migrate\_schools\_to\_orgloc.py](/scripts/datasources/nces/migrate_schools_to_orgloc.py) | Python | 123 | 18 | 28 | 169 |
| [scripts/datasources/nces/nces\_ingestion.py](/scripts/datasources/nces/nces_ingestion.py) | Python | 172 | 85 | 26 | 283 |
| [scripts/datasources/nces/update\_jurisdictions\_from\_nces\_simple.py](/scripts/datasources/nces/update_jurisdictions_from_nces_simple.py) | Python | 92 | 163 | 12 | 267 |
| [scripts/datasources/usmayors/README.md](/scripts/datasources/usmayors/README.md) | Markdown | 69 | 0 | 30 | 99 |
| [scripts/datasources/usmayors/add\_mayor\_columns.sql](/scripts/datasources/usmayors/add_mayor_columns.sql) | MS SQL | 9 | 1 | 4 | 14 |
| [scripts/datasources/usmayors/scrape\_mayor\_elections.py](/scripts/datasources/usmayors/scrape_mayor_elections.py) | Python | 207 | 53 | 55 | 315 |
| [scripts/datasources/wikidata/generate\_mapping\_report.sql](/scripts/datasources/wikidata/generate_mapping_report.sql) | MS SQL | 108 | 13 | 10 | 131 |
| [scripts/datasources/youtube/BYPASS\_IP\_BLOCK.md](/scripts/datasources/youtube/BYPASS_IP_BLOCK.md) | Markdown | 119 | 0 | 40 | 159 |
| [scripts/datasources/youtube/load\_channels.py](/scripts/datasources/youtube/load_channels.py) | Python | 129 | 138 | -34 | 233 |
| [scripts/datasources/youtube/load\_youtube\_events\_to\_postgres.py](/scripts/datasources/youtube/load_youtube_events_to_postgres.py) | Python | 81 | 18 | 12 | 111 |
| [scripts/development/export\_chrome\_cookies.py](/scripts/development/export_chrome_cookies.py) | Python | 58 | 15 | 16 | 89 |
| [scripts/localview/scrape\_youtube\_channels.py](/scripts/localview/scrape_youtube_channels.py) | Python | 6 | 2 | 2 | 10 |
| [website/docs/data-sources/citations.md](/website/docs/data-sources/citations.md) | Markdown | 57 | 0 | 14 | 71 |
| [website/docs/data-sources/meeting-data.md](/website/docs/data-sources/meeting-data.md) | Markdown | 194 | 0 | 63 | 257 |
| [website/docs/deployment/neon-deployment.md](/website/docs/deployment/neon-deployment.md) | Markdown | 149 | 0 | 56 | 205 |
| [website/docs/guides/contacts-contacts\_officials.md](/website/docs/guides/contacts-contacts_officials.md) | Markdown | 370 | 0 | 143 | 513 |
| [website/docs/guides/contacts-officials.md](/website/docs/guides/contacts-officials.md) | Markdown | -370 | 0 | -143 | -513 |

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details