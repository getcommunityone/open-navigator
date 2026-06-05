# Diff Details

Date : 2026-06-04 22:33:55

Directory /home/developer/projects/open-navigator

Total : 103 files,  4899 codes, 2395 comments, 714 blanks, all 8008 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [.github/workflows/ci-build-test.yml](/.github/workflows/ci-build-test.yml) | YAML | 20 | 5 | 1 | 26 |
| [CLAUDE.md](/CLAUDE.md) | Markdown | 4 | 0 | 0 | 4 |
| [SECURITY.md](/SECURITY.md) | Markdown | 15 | 0 | 7 | 22 |
| [api/batch\_jobs/batch\_job\_db.py](/api/batch_jobs/batch_job_db.py) | Python | 3 | 17 | 0 | 20 |
| [api/main.py](/api/main.py) | Python | 40 | 11 | 4 | 55 |
| [api/models.py](/api/models.py) | Python | -39 | -4 | -11 | -54 |
| [api/routes/people.py](/api/routes/people.py) | Python | 100 | 26 | 22 | 148 |
| [api/routes/search.py](/api/routes/search.py) | Python | -644 | -220 | -119 | -983 |
| [api/routes/search\_postgres.py](/api/routes/search_postgres.py) | Python | 329 | 515 | 27 | 871 |
| [api/routes/social.py](/api/routes/social.py) | Python | -87 | -8 | -23 | -118 |
| [api/routes/stats.py](/api/routes/stats.py) | Python | -10 | 14 | -2 | 2 |
| [api/routes/stats\_neon.py](/api/routes/stats_neon.py) | Python | 10 | 11 | 0 | 21 |
| [api/static/assets/index-BdQvQsgI.js](/api/static/assets/index-BdQvQsgI.js) | JavaScript | -229 | 0 | -26 | -255 |
| [api/static/assets/index-CRfiMS1I.css](/api/static/assets/index-CRfiMS1I.css) | PostCSS | -1 | 0 | -1 | -2 |
| [api/static/assets/index-DE2vn\_JD.js](/api/static/assets/index-DE2vn_JD.js) | JavaScript | 126 | 17 | 2 | 145 |
| [api/static/assets/index-D\_wWyK4E.css](/api/static/assets/index-D_wWyK4E.css) | PostCSS | 1 | 0 | 1 | 2 |
| [api/telemetry.py](/api/telemetry.py) | Python | 71 | 64 | 19 | 154 |
| [dbt\_project/macros/classify\_name\_entity\_type.sql](/dbt_project/macros/classify_name_entity_type.sql) | MS SQL | 0 | 8 | 0 | 8 |
| [dbt\_project/models/intermediate/\_intermediate.yml](/dbt_project/models/intermediate/_intermediate.yml) | YAML | 15 | 0 | 0 | 15 |
| [dbt\_project/models/intermediate/\_schema\_int\_event\_youtube\_\_jurisdiction\_resolved.yml](/dbt_project/models/intermediate/_schema_int_event_youtube__jurisdiction_resolved.yml) | YAML | 60 | 0 | 4 | 64 |
| [dbt\_project/models/intermediate/int\_event\_youtube\_\_jurisdiction\_resolved.sql](/dbt_project/models/intermediate/int_event_youtube__jurisdiction_resolved.sql) | MS SQL | 200 | 61 | 19 | 280 |
| [dbt\_project/models/intermediate/int\_events\_union.sql](/dbt_project/models/intermediate/int_events_union.sql) | MS SQL | 48 | 16 | 3 | 67 |
| [dbt\_project/models/intermediate/int\_persons\_\_unioned.sql](/dbt_project/models/intermediate/int_persons__unioned.sql) | MS SQL | 2 | 2 | 0 | 4 |
| [dbt\_project/models/marts/\_mdm\_marts.yml](/dbt_project/models/marts/_mdm_marts.yml) | YAML | 98 | 0 | 2 | 100 |
| [dbt\_project/models/marts/\_schema\_contact\_official.yml](/dbt_project/models/marts/_schema_contact_official.yml) | YAML | 75 | 0 | 2 | 77 |
| [dbt\_project/models/marts/\_schema\_event.yml](/dbt_project/models/marts/_schema_event.yml) | YAML | 100 | 0 | 1 | 101 |
| [dbt\_project/models/marts/\_schema\_event\_policy\_bill.yml](/dbt_project/models/marts/_schema_event_policy_bill.yml) | YAML | 39 | 0 | 3 | 42 |
| [dbt\_project/models/marts/\_schema\_event\_policy\_decision.yml](/dbt_project/models/marts/_schema_event_policy_decision.yml) | YAML | 36 | 0 | 3 | 39 |
| [dbt\_project/models/marts/\_schema\_event\_youtube\_with\_jurisdiction.yml](/dbt_project/models/marts/_schema_event_youtube_with_jurisdiction.yml) | YAML | 36 | 0 | 4 | 40 |
| [dbt\_project/models/marts/\_schema\_grant.yml](/dbt_project/models/marts/_schema_grant.yml) | YAML | 109 | 0 | 2 | 111 |
| [dbt\_project/models/marts/\_schema\_jurisdictions.yml](/dbt_project/models/marts/_schema_jurisdictions.yml) | YAML | 92 | 0 | 2 | 94 |
| [dbt\_project/models/marts/contact\_official.sql](/dbt_project/models/marts/contact_official.sql) | MS SQL | 37 | 34 | 4 | 75 |
| [dbt\_project/models/marts/event.sql](/dbt_project/models/marts/event.sql) | MS SQL | 14 | 0 | 0 | 14 |
| [dbt\_project/models/marts/event\_documents.sql](/dbt_project/models/marts/event_documents.sql) | MS SQL | 90 | 35 | 5 | 130 |
| [dbt\_project/models/marts/event\_policy\_bill.sql](/dbt_project/models/marts/event_policy_bill.sql) | MS SQL | 42 | 19 | 10 | 71 |
| [dbt\_project/models/marts/event\_policy\_decision.sql](/dbt_project/models/marts/event_policy_decision.sql) | MS SQL | 41 | 18 | 10 | 69 |
| [dbt\_project/models/marts/event\_youtube\_with\_jurisdiction.sql](/dbt_project/models/marts/event_youtube_with_jurisdiction.sql) | MS SQL | 66 | 31 | 19 | 116 |
| [dbt\_project/models/marts/grant.sql](/dbt_project/models/marts/grant.sql) | MS SQL | 72 | 47 | 8 | 127 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_analysis.sql](/dbt_project/models/marts/jurisdiction_mapping_analysis.sql) | MS SQL | 0 | 1 | 0 | 1 |
| [dbt\_project/models/marts/jurisdiction\_state\_aggregate.sql](/dbt_project/models/marts/jurisdiction_state_aggregate.sql) | MS SQL | 35 | 15 | 2 | 52 |
| [dbt\_project/models/marts/jurisdictions.sql](/dbt_project/models/marts/jurisdictions.sql) | MS SQL | 86 | 11 | 2 | 99 |
| [dbt\_project/models/marts/mdm\_bridge\_org\_jurisdiction.sql](/dbt_project/models/marts/mdm_bridge_org_jurisdiction.sql) | MS SQL | 120 | 30 | 14 | 164 |
| [dbt\_project/models/marts/mdm\_bridge\_person\_jurisdiction.sql](/dbt_project/models/marts/mdm_bridge_person_jurisdiction.sql) | MS SQL | 120 | 28 | 14 | 162 |
| [dbt\_project/models/marts/mdm\_bridge\_person\_organization.sql](/dbt_project/models/marts/mdm_bridge_person_organization.sql) | MS SQL | 7 | 0 | 0 | 7 |
| [dbt\_project/models/marts/mdm\_organization.sql](/dbt_project/models/marts/mdm_organization.sql) | MS SQL | 9 | 8 | 0 | 17 |
| [dbt\_project/models/marts/mdm\_organization\_nonprofit.sql](/dbt_project/models/marts/mdm_organization_nonprofit.sql) | MS SQL | 13 | 0 | 0 | 13 |
| [dbt\_project/models/marts/mdm\_person.sql](/dbt_project/models/marts/mdm_person.sql) | MS SQL | 12 | 0 | 0 | 12 |
| [dbt\_project/models/staging/\_schema\_stg\_givingtuesday.yml](/dbt_project/models/staging/_schema_stg_givingtuesday.yml) | YAML | 21 | 0 | 1 | 22 |
| [dbt\_project/models/staging/\_staging.yml](/dbt_project/models/staging/_staging.yml) | YAML | 151 | 0 | 5 | 156 |
| [dbt\_project/models/staging/stg\_990\_officers.sql](/dbt_project/models/staging/stg_990_officers.sql) | MS SQL | 0 | 4 | 0 | 4 |
| [dbt\_project/models/staging/stg\_990\_officers\_\_person.sql](/dbt_project/models/staging/stg_990_officers__person.sql) | MS SQL | 55 | 35 | 8 | 98 |
| [dbt\_project/models/staging/stg\_grants\_gt990\_\_schedule\_i.sql](/dbt_project/models/staging/stg_grants_gt990__schedule_i.sql) | MS SQL | 35 | 12 | 8 | 55 |
| [dbt\_project/models/staging/stg\_nccs\_\_organization.sql](/dbt_project/models/staging/stg_nccs__organization.sql) | MS SQL | 0 | 2 | 0 | 2 |
| [dbt\_project/models/staging/stg\_openstates\_\_official.sql](/dbt_project/models/staging/stg_openstates__official.sql) | MS SQL | 70 | 27 | 19 | 116 |
| [dbt\_project/models/staging/stg\_parcels\_\_person.sql](/dbt_project/models/staging/stg_parcels__person.sql) | MS SQL | 70 | 63 | 5 | 138 |
| [dbt\_project/models/staging/stg\_policy\_bill.sql](/dbt_project/models/staging/stg_policy_bill.sql) | MS SQL | 24 | 16 | 10 | 50 |
| [dbt\_project/models/staging/stg\_policy\_decisions.sql](/dbt_project/models/staging/stg_policy_decisions.sql) | MS SQL | 22 | 13 | 9 | 44 |
| [dbt\_project/scripts/backfill\_persons\_leaders\_counts.py](/dbt_project/scripts/backfill_persons_leaders_counts.py) | Python | 69 | 173 | 9 | 251 |
| [dbt\_project/scripts/export\_stats\_to\_open\_navigator.py](/dbt_project/scripts/export_stats_to_open_navigator.py) | Python | 2 | 0 | 0 | 2 |
| [dbt\_project/tests/assert\_mdm\_person\_not\_overmerged.sql](/dbt_project/tests/assert_mdm_person_not_overmerged.sql) | MS SQL | 8 | 19 | 3 | 30 |
| [packages/accessibility/src/accessibility/package-lock.json](/packages/accessibility/src/accessibility/package-lock.json) | JSON | -525 | 0 | 0 | -525 |
| [packages/hosting/scripts/neon/migrations/103\_promote\_civicsearch\_to\_bronze\_event\_youtube.sql](/packages/hosting/scripts/neon/migrations/103_promote_civicsearch_to_bronze_event_youtube.sql) | MS SQL | 0 | 9 | 0 | 9 |
| [packages/hosting/scripts/neon/migrations/104\_create\_bronze\_bills\_openstates.sql](/packages/hosting/scripts/neon/migrations/104_create_bronze_bills_openstates.sql) | MS SQL | 43 | 18 | 7 | 68 |
| [packages/hosting/scripts/neon/migrations/105\_stats\_aggregate\_persons\_leaders\_counts.sql](/packages/hosting/scripts/neon/migrations/105_stats_aggregate_persons_leaders_counts.sql) | MS SQL | 17 | 25 | 4 | 46 |
| [packages/hosting/src/hosting/neon/schema.sql](/packages/hosting/src/hosting/neon/schema.sql) | MS SQL | 1 | 0 | 0 | 1 |
| [packages/ingestion/src/ingestion/civicsearch/events.py](/packages/ingestion/src/ingestion/civicsearch/events.py) | Python | 0 | 5 | 0 | 5 |
| [packages/ingestion/src/ingestion/givingtuesday/load.py](/packages/ingestion/src/ingestion/givingtuesday/load.py) | Python | 135 | 78 | 21 | 234 |
| [packages/ingestion/src/ingestion/mdm/settings.py](/packages/ingestion/src/ingestion/mdm/settings.py) | Python | 0 | 14 | 0 | 14 |
| [packages/ingestion/src/ingestion/openstates/bills.py](/packages/ingestion/src/ingestion/openstates/bills.py) | Python | 304 | 261 | 36 | 601 |
| [packages/ingestion/src/ingestion/openstates/officials.py](/packages/ingestion/src/ingestion/openstates/officials.py) | Python | 232 | 267 | 35 | 534 |
| [packages/ingestion/tests/test\_openstates\_bills.py](/packages/ingestion/tests/test_openstates_bills.py) | Python | 241 | 43 | 64 | 348 |
| [packages/ingestion/tests/test\_openstates\_officials.py](/packages/ingestion/tests/test_openstates_officials.py) | Python | 179 | 30 | 47 | 256 |
| [packages/llm/src/llm/gemini/analyze\_backlog.py](/packages/llm/src/llm/gemini/analyze_backlog.py) | Python | 497 | 206 | 89 | 792 |
| [packages/llm/src/llm/gemini/browser\_policy\_analysis.py](/packages/llm/src/llm/gemini/browser_policy_analysis.py) | Python | 6 | 1 | 0 | 7 |
| [packages/llm/src/llm/gemini/genai\_text\_client.py](/packages/llm/src/llm/gemini/genai_text_client.py) | Python | 78 | 58 | 14 | 150 |
| [packages/llm/src/llm/gemini/meeting\_transcript\_policy.py](/packages/llm/src/llm/gemini/meeting_transcript_policy.py) | Python | 48 | 14 | 5 | 67 |
| [packages/llm/src/llm/gemini/tests/test\_analyze\_backlog.py](/packages/llm/src/llm/gemini/tests/test_analyze_backlog.py) | Python | 235 | 51 | 86 | 372 |
| [packages/llm/src/llm/gemini/tests/test\_genai\_text\_client.py](/packages/llm/src/llm/gemini/tests/test_genai_text_client.py) | Python | 35 | 11 | 14 | 60 |
| [packages/llm/src/llm/gemini/tests/test\_transcript\_db.py](/packages/llm/src/llm/gemini/tests/test_transcript_db.py) | Python | 55 | 1 | 21 | 77 |
| [packages/llm/src/llm/gemini/transcript\_db.py](/packages/llm/src/llm/gemini/transcript_db.py) | Python | 102 | 33 | 18 | 153 |
| [packages/scrapers/src/scrapers/youtube/backfill\_transcripts.py](/packages/scrapers/src/scrapers/youtube/backfill_transcripts.py) | Python | 3 | 5 | 0 | 8 |
| [packages/scrapers/src/scrapers/youtube/enrich\_civicsearch\_jurisdictions.py](/packages/scrapers/src/scrapers/youtube/enrich_civicsearch_jurisdictions.py) | Python | 416 | 157 | 69 | 642 |
| [packages/scrapers/tests/test\_enrich\_civicsearch\_jurisdictions.py](/packages/scrapers/tests/test_enrich_civicsearch_jurisdictions.py) | Python | 69 | 11 | 14 | 94 |
| [requirements.txt](/requirements.txt) | pip requirements | 32 | -27 | 1 | 6 |
| [scripts/datasources/dbpedia/README.md](/scripts/datasources/dbpedia/README.md) | Markdown | -4 | 0 | -4 | -8 |
| [scripts/datasources/dbpedia/dbpedia\_integration.py](/scripts/datasources/dbpedia/dbpedia_integration.py) | Python | -226 | -167 | -24 | -417 |
| [scripts/datasources/govwebsites/README.md](/scripts/datasources/govwebsites/README.md) | Markdown | -82 | 0 | -28 | -110 |
| [uv.lock](/uv.lock) | toml | 729 | 0 | 46 | 775 |
| [web\_app/package-lock.json](/web_app/package-lock.json) | JSON | -247 | 0 | 0 | -247 |
| [web\_app/package.json](/web_app/package.json) | JSON | 5 | 0 | 0 | 5 |
| [web\_app/policy-dashboards/package-lock.json](/web_app/policy-dashboards/package-lock.json) | JSON | -32 | 0 | 0 | -32 |
| [web\_app/src/App.tsx](/web_app/src/App.tsx) | TypeScript JSX | 17 | 5 | 1 | 23 |
| [web\_app/src/api/batchJobs.ts](/web_app/src/api/batchJobs.ts) | TypeScript | 5 | 3 | 0 | 8 |
| [web\_app/src/instrumentation.ts](/web_app/src/instrumentation.ts) | TypeScript | 64 | 33 | 17 | 114 |
| [web\_app/src/lib/api.ts](/web_app/src/lib/api.ts) | TypeScript | 22 | 7 | 2 | 31 |
| [web\_app/src/main.tsx](/web_app/src/main.tsx) | TypeScript JSX | 1 | 1 | 0 | 2 |
| [web\_app/src/pages/BatchJobStatusPage.tsx](/web_app/src/pages/BatchJobStatusPage.tsx) | TypeScript JSX | 6 | 9 | 0 | 15 |
| [web\_app/src/pages/Home.tsx](/web_app/src/pages/Home.tsx) | TypeScript JSX | 321 | 44 | 23 | 388 |
| [web\_app/src/pages/PeopleFinder.tsx](/web_app/src/pages/PeopleFinder.tsx) | TypeScript JSX | 1 | 0 | 0 | 1 |
| [web\_app/src/pages/PersonDetail.tsx](/web_app/src/pages/PersonDetail.tsx) | TypeScript JSX | 188 | 3 | 19 | 210 |
| [web\_app/src/pages/UnifiedSearch.tsx](/web_app/src/pages/UnifiedSearch.tsx) | TypeScript JSX | 146 | 8 | 6 | 160 |
| [web\_app/src/vite-env.d.ts](/web_app/src/vite-env.d.ts) | TypeScript | 3 | 2 | 0 | 5 |
| [web\_docs/package-lock.json](/web_docs/package-lock.json) | JSON | -131 | 0 | 0 | -131 |

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details