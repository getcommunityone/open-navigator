# Diff Details

Date : 2026-06-01 09:50:49

Directory /home/developer/projects/open-navigator

Total : 159 files,  5268 codes, 1749 comments, 888 blanks, all 7905 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [.claude/agents/api-specialist.md](/.claude/agents/api-specialist.md) | Markdown | -39 | 0 | -6 | -45 |
| [.claude/agents/data-dbt-specialist.md](/.claude/agents/data-dbt-specialist.md) | Markdown | -45 | 0 | -6 | -51 |
| [.claude/agents/frontend-specialist.md](/.claude/agents/frontend-specialist.md) | Markdown | -36 | 0 | -6 | -42 |
| [.claude/agents/python-packages-specialist.md](/.claude/agents/python-packages-specialist.md) | Markdown | -65 | 0 | -8 | -73 |
| [.claude/settings.json](/.claude/settings.json) | JSON with Comments | -26 | 0 | -1 | -27 |
| [.github/workflows/ci-build-test.yml](/.github/workflows/ci-build-test.yml) | YAML | 0 | 3 | 0 | 3 |
| [.pre-commit-config.yaml](/.pre-commit-config.yaml) | YAML | 13 | 6 | 3 | 22 |
| [CITATIONS.md](/CITATIONS.md) | Markdown | 78 | 0 | 26 | 104 |
| [CLAUDE.md](/CLAUDE.md) | Markdown | 3 | 0 | 0 | 3 |
| [api/batch\_jobs/batch\_job\_db.py](/api/batch_jobs/batch_job_db.py) | Python | 10 | 92 | 0 | 102 |
| [api/models.py](/api/models.py) | Python | -34 | 3 | -14 | -45 |
| [api/routes/batch\_jobs.py](/api/routes/batch_jobs.py) | Python | 5 | 3 | 2 | 10 |
| [api/routes/bills.py](/api/routes/bills.py) | Python | -294 | -558 | -42 | -894 |
| [api/routes/bills\_neon.py](/api/routes/bills_neon.py) | Python | 0 | 4 | 0 | 4 |
| [api/routes/search\_postgres.py](/api/routes/search_postgres.py) | Python | 14 | 9 | 1 | 24 |
| [api/routes/social.py](/api/routes/social.py) | Python | 61 | 20 | 0 | 81 |
| [api/routes/trending.py](/api/routes/trending.py) | Python | 0 | 1 | 0 | 1 |
| [dbt\_project/analyses/audit\_mdm\_keys.sql](/dbt_project/analyses/audit_mdm_keys.sql) | MS SQL | 65 | 9 | 10 | 84 |
| [dbt\_project/macros/address\_match\_key.sql](/dbt_project/macros/address_match_key.sql) | MS SQL | 11 | 15 | 1 | 27 |
| [dbt\_project/macros/canonical\_org\_type.sql](/dbt_project/macros/canonical_org_type.sql) | MS SQL | 13 | 9 | 1 | 23 |
| [dbt\_project/macros/classify\_name\_entity\_type.sql](/dbt_project/macros/classify_name_entity_type.sql) | MS SQL | 10 | 9 | 1 | 20 |
| [dbt\_project/macros/display\_org\_name.sql](/dbt_project/macros/display_org_name.sql) | MS SQL | 6 | 9 | 1 | 16 |
| [dbt\_project/macros/enable\_mdm\_extensions.sql](/dbt_project/macros/enable_mdm_extensions.sql) | MS SQL | 9 | 15 | 1 | 25 |
| [dbt\_project/macros/event\_extractions.sql](/dbt_project/macros/event_extractions.sql) | MS SQL | 23 | 6 | 2 | 31 |
| [dbt\_project/macros/name\_phonetic\_first.sql](/dbt_project/macros/name_phonetic_first.sql) | MS SQL | 8 | 8 | 1 | 17 |
| [dbt\_project/macros/name\_phonetic\_key.sql](/dbt_project/macros/name_phonetic_key.sql) | MS SQL | 8 | 11 | 1 | 20 |
| [dbt\_project/macros/normalize\_address.sql](/dbt_project/macros/normalize_address.sql) | MS SQL | 32 | 17 | 1 | 50 |
| [dbt\_project/macros/normalize\_org\_name.sql](/dbt_project/macros/normalize_org_name.sql) | MS SQL | 21 | 8 | 1 | 30 |
| [dbt\_project/macros/normalize\_person\_name.sql](/dbt_project/macros/normalize_person_name.sql) | MS SQL | 32 | 13 | 1 | 46 |
| [dbt\_project/macros/zip5.sql](/dbt_project/macros/zip5.sql) | MS SQL | 9 | 6 | 1 | 16 |
| [dbt\_project/models/bronze/bronze\_event\_youtube.sql](/dbt_project/models/bronze/bronze_event_youtube.sql) | MS SQL | 41 | 20 | 15 | 76 |
| [dbt\_project/models/bronze/bronze\_events\_youtube.sql](/dbt_project/models/bronze/bronze_events_youtube.sql) | MS SQL | -41 | -20 | -15 | -76 |
| [dbt\_project/models/intermediate/\_intermediate.yml](/dbt_project/models/intermediate/_intermediate.yml) | YAML | 27 | 0 | 1 | 28 |
| [dbt\_project/models/intermediate/\_schema\_int\_events\_localview\_enriched.yml](/dbt_project/models/intermediate/_schema_int_events_localview_enriched.yml) | YAML | 49 | 0 | 3 | 52 |
| [dbt\_project/models/intermediate/int\_990\_officers\_\_org\_linked.sql](/dbt_project/models/intermediate/int_990_officers__org_linked.sql) | MS SQL | 61 | 26 | 6 | 93 |
| [dbt\_project/models/intermediate/int\_addresses\_\_clustered.sql](/dbt_project/models/intermediate/int_addresses__clustered.sql) | MS SQL | 5 | 12 | 3 | 20 |
| [dbt\_project/models/intermediate/int\_addresses\_\_unioned.sql](/dbt_project/models/intermediate/int_addresses__unioned.sql) | MS SQL | 24 | 16 | 4 | 44 |
| [dbt\_project/models/intermediate/int\_events\_civicsearch\_\_localview\_xref.sql](/dbt_project/models/intermediate/int_events_civicsearch__localview_xref.sql) | MS SQL | 47 | 12 | 9 | 68 |
| [dbt\_project/models/intermediate/int\_events\_localview\_enriched.sql](/dbt_project/models/intermediate/int_events_localview_enriched.sql) | MS SQL | 66 | 24 | 7 | 97 |
| [dbt\_project/models/intermediate/int\_organizations\_\_clustered.sql](/dbt_project/models/intermediate/int_organizations__clustered.sql) | MS SQL | 14 | 11 | 3 | 28 |
| [dbt\_project/models/intermediate/int\_organizations\_\_unioned.sql](/dbt_project/models/intermediate/int_organizations__unioned.sql) | MS SQL | 33 | 17 | 4 | 54 |
| [dbt\_project/models/intermediate/int\_persons\_\_clustered.sql](/dbt_project/models/intermediate/int_persons__clustered.sql) | MS SQL | 8 | 20 | 3 | 31 |
| [dbt\_project/models/intermediate/int\_persons\_\_unioned.sql](/dbt_project/models/intermediate/int_persons__unioned.sql) | MS SQL | 39 | 23 | 4 | 66 |
| [dbt\_project/models/intermediate/int\_tags\_\_closure.sql](/dbt_project/models/intermediate/int_tags__closure.sql) | MS SQL | 28 | 23 | 8 | 59 |
| [dbt\_project/models/intermediate/int\_tags\_\_unified.sql](/dbt_project/models/intermediate/int_tags__unified.sql) | MS SQL | 70 | 22 | 10 | 102 |
| [dbt\_project/models/marts/\_mdm\_marts.yml](/dbt_project/models/marts/_mdm_marts.yml) | YAML | 454 | 0 | 11 | 465 |
| [dbt\_project/models/marts/\_schema\_event.yml](/dbt_project/models/marts/_schema_event.yml) | YAML | 186 | 0 | 4 | 190 |
| [dbt\_project/models/marts/\_schema\_event\_extractions.yml](/dbt_project/models/marts/_schema_event_extractions.yml) | YAML | 12 | 0 | 0 | 12 |
| [dbt\_project/models/marts/\_schema\_localview\_events.yml](/dbt_project/models/marts/_schema_localview_events.yml) | YAML | -49 | 0 | -3 | -52 |
| [dbt\_project/models/marts/\_schema\_mdm\_organization\_nonprofit.yml](/dbt_project/models/marts/_schema_mdm_organization_nonprofit.yml) | YAML | 97 | 0 | 2 | 99 |
| [dbt\_project/models/marts/\_schema\_tags.yml](/dbt_project/models/marts/_schema_tags.yml) | YAML | 188 | 0 | 4 | 192 |
| [dbt\_project/models/marts/dq\_jurisdiction\_mapping\_summary.sql](/dbt_project/models/marts/dq_jurisdiction_mapping_summary.sql) | MS SQL | 52 | 9 | 3 | 64 |
| [dbt\_project/models/marts/dq\_jurisdiction\_mapping\_summary\_by\_acs\_income\_level.sql](/dbt_project/models/marts/dq_jurisdiction_mapping_summary_by_acs_income_level.sql) | MS SQL | 54 | 5 | 3 | 62 |
| [dbt\_project/models/marts/dq\_jurisdiction\_mapping\_summary\_by\_acs\_population\_tier.sql](/dbt_project/models/marts/dq_jurisdiction_mapping_summary_by_acs_population_tier.sql) | MS SQL | 54 | 5 | 3 | 62 |
| [dbt\_project/models/marts/dq\_jurisdiction\_mapping\_summary\_municipality\_places.sql](/dbt_project/models/marts/dq_jurisdiction_mapping_summary_municipality_places.sql) | MS SQL | 54 | 11 | 3 | 68 |
| [dbt\_project/models/marts/event.sql](/dbt_project/models/marts/event.sql) | MS SQL | 6 | 8 | 1 | 15 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary.sql) | MS SQL | -52 | -9 | -3 | -64 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary\_by\_acs\_income\_level.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary_by_acs_income_level.sql) | MS SQL | -54 | -5 | -3 | -62 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary\_by\_acs\_population\_tier.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary_by_acs_population_tier.sql) | MS SQL | -54 | -5 | -3 | -62 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary\_municipality\_places.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary_municipality_places.sql) | MS SQL | -54 | -11 | -3 | -68 |
| [dbt\_project/models/marts/localview\_events.sql](/dbt_project/models/marts/localview_events.sql) | MS SQL | -66 | -22 | -7 | -95 |
| [dbt\_project/models/marts/mdm\_address.sql](/dbt_project/models/marts/mdm_address.sql) | MS SQL | 48 | 10 | 7 | 65 |
| [dbt\_project/models/marts/mdm\_bridge\_address\_county.sql](/dbt_project/models/marts/mdm_bridge_address_county.sql) | MS SQL | 28 | 14 | 5 | 47 |
| [dbt\_project/models/marts/mdm\_bridge\_address\_xref.sql](/dbt_project/models/marts/mdm_bridge_address_xref.sql) | MS SQL | 9 | 11 | 3 | 23 |
| [dbt\_project/models/marts/mdm\_bridge\_event\_analysis.sql](/dbt_project/models/marts/mdm_bridge_event_analysis.sql) | MS SQL | 48 | 29 | 6 | 83 |
| [dbt\_project/models/marts/mdm\_bridge\_event\_source.sql](/dbt_project/models/marts/mdm_bridge_event_source.sql) | MS SQL | 56 | 16 | 7 | 79 |
| [dbt\_project/models/marts/mdm\_bridge\_org\_address.sql](/dbt_project/models/marts/mdm_bridge_org_address.sql) | MS SQL | 48 | 20 | 6 | 74 |
| [dbt\_project/models/marts/mdm\_bridge\_person\_address.sql](/dbt_project/models/marts/mdm_bridge_person_address.sql) | MS SQL | 23 | 17 | 5 | 45 |
| [dbt\_project/models/marts/mdm\_bridge\_person\_organization.sql](/dbt_project/models/marts/mdm_bridge_person_organization.sql) | MS SQL | 28 | 13 | 3 | 44 |
| [dbt\_project/models/marts/mdm\_organization.sql](/dbt_project/models/marts/mdm_organization.sql) | MS SQL | 139 | 37 | 13 | 189 |
| [dbt\_project/models/marts/mdm\_organization\_nonprofit.sql](/dbt_project/models/marts/mdm_organization_nonprofit.sql) | MS SQL | 85 | 19 | 8 | 112 |
| [dbt\_project/models/marts/mdm\_person.sql](/dbt_project/models/marts/mdm_person.sql) | MS SQL | 33 | 29 | 3 | 65 |
| [dbt\_project/models/marts/mdm\_person\_source\_link.sql](/dbt_project/models/marts/mdm_person_source_link.sql) | MS SQL | 45 | 13 | 6 | 64 |
| [dbt\_project/models/marts/organization\_nonprofit.sql](/dbt_project/models/marts/organization_nonprofit.sql) | MS SQL | -159 | -17 | -6 | -182 |
| [dbt\_project/models/marts/pending\_mdm\_person.sql](/dbt_project/models/marts/pending_mdm_person.sql) | MS SQL | 69 | 23 | 8 | 100 |
| [dbt\_project/models/marts/tag.sql](/dbt_project/models/marts/tag.sql) | MS SQL | 31 | 13 | 6 | 50 |
| [dbt\_project/models/marts/tag\_closure.sql](/dbt_project/models/marts/tag_closure.sql) | MS SQL | 7 | 14 | 3 | 24 |
| [dbt\_project/models/marts/tag\_organization.sql](/dbt_project/models/marts/tag_organization.sql) | MS SQL | 52 | 21 | 9 | 82 |
| [dbt\_project/models/staging/\_schema\_stg\_civicsearch.yml](/dbt_project/models/staging/_schema_stg_civicsearch.yml) | YAML | 105 | 0 | 3 | 108 |
| [dbt\_project/models/staging/\_staging.yml](/dbt_project/models/staging/_staging.yml) | YAML | 288 | 1 | 3 | 292 |
| [dbt\_project/models/staging/stg\_990\_officers.sql](/dbt_project/models/staging/stg_990_officers.sql) | MS SQL | 27 | 16 | 4 | 47 |
| [dbt\_project/models/staging/stg\_bronze\_event\_youtube\_transcript.sql](/dbt_project/models/staging/stg_bronze_event_youtube_transcript.sql) | MS SQL | 65 | 21 | 17 | 103 |
| [dbt\_project/models/staging/stg\_bronze\_events\_text\_ai.sql](/dbt_project/models/staging/stg_bronze_events_text_ai.sql) | MS SQL | -47 | -20 | -16 | -83 |
| [dbt\_project/models/staging/stg\_civicsearch\_\_event.sql](/dbt_project/models/staging/stg_civicsearch__event.sql) | MS SQL | 56 | 14 | 8 | 78 |
| [dbt\_project/models/staging/stg\_civicsearch\_\_snippet.sql](/dbt_project/models/staging/stg_civicsearch__snippet.sql) | MS SQL | 40 | 12 | 7 | 59 |
| [dbt\_project/models/staging/stg\_contributions\_\_person.sql](/dbt_project/models/staging/stg_contributions__person.sql) | MS SQL | 57 | 18 | 8 | 83 |
| [dbt\_project/models/staging/stg\_irs\_\_org.sql](/dbt_project/models/staging/stg_irs__org.sql) | MS SQL | 22 | 14 | 4 | 40 |
| [dbt\_project/models/staging/stg\_jurisdictions\_\_org.sql](/dbt_project/models/staging/stg_jurisdictions__org.sql) | MS SQL | 21 | 7 | 4 | 32 |
| [dbt\_project/models/staging/stg\_locations\_\_address.sql](/dbt_project/models/staging/stg_locations__address.sql) | MS SQL | 35 | 14 | 13 | 62 |
| [dbt\_project/models/staging/stg\_locations\_\_org.sql](/dbt_project/models/staging/stg_locations__org.sql) | MS SQL | 21 | 6 | 4 | 31 |
| [dbt\_project/models/staging/stg\_nccs\_\_org.sql](/dbt_project/models/staging/stg_nccs__org.sql) | MS SQL | 21 | 6 | 4 | 31 |
| [dbt\_project/models/staging/stg\_openstates\_\_person.sql](/dbt_project/models/staging/stg_openstates__person.sql) | MS SQL | 33 | 16 | 11 | 60 |
| [dbt\_project/models/staging/stg\_orgs\_ai\_\_org.sql](/dbt_project/models/staging/stg_orgs_ai__org.sql) | MS SQL | 21 | 5 | 4 | 30 |
| [dbt\_project/models/staging/stg\_osf\_ledb\_\_person.sql](/dbt_project/models/staging/stg_osf_ledb__person.sql) | MS SQL | 47 | 14 | 8 | 69 |
| [dbt\_project/models/staging/stg\_parcels\_\_address.sql](/dbt_project/models/staging/stg_parcels__address.sql) | MS SQL | 36 | 14 | 13 | 63 |
| [dbt\_project/models/staging/stg\_parcels\_\_org.sql](/dbt_project/models/staging/stg_parcels__org.sql) | MS SQL | 28 | 18 | 5 | 51 |
| [dbt\_project/models/staging/stg\_parcels\_\_person.sql](/dbt_project/models/staging/stg_parcels__person.sql) | MS SQL | 54 | 17 | 13 | 84 |
| [dbt\_project/models/staging/stg\_persons\_ai\_\_person.sql](/dbt_project/models/staging/stg_persons_ai__person.sql) | MS SQL | 34 | 15 | 11 | 60 |
| [dbt\_project/models/staging/stg\_places\_\_address.sql](/dbt_project/models/staging/stg_places__address.sql) | MS SQL | 36 | 13 | 13 | 62 |
| [dbt\_project/models/staging/stg\_schools\_\_org.sql](/dbt_project/models/staging/stg_schools__org.sql) | MS SQL | 21 | 6 | 4 | 31 |
| [dbt\_project/tests/assert\_tag\_closure\_self\_rows.sql](/dbt_project/tests/assert_tag_closure_self_rows.sql) | MS SQL | 7 | 3 | 2 | 12 |
| [packages/core-lib/src/core\_lib/http/client.py](/packages/core-lib/src/core_lib/http/client.py) | Python | 0 | 7 | 0 | 7 |
| [packages/hosting/scripts/neon/migrations/088\_rename\_bronze\_schools\_nces\_to\_jurisdictions\_schools.sql](/packages/hosting/scripts/neon/migrations/088_rename_bronze_schools_nces_to_jurisdictions_schools.sql) | MS SQL | 12 | 19 | 7 | 38 |
| [packages/hosting/scripts/neon/migrations/089\_drop\_public\_organization\_location.sql](/packages/hosting/scripts/neon/migrations/089_drop_public_organization_location.sql) | MS SQL | 9 | 19 | 5 | 33 |
| [packages/hosting/scripts/neon/migrations/090\_rename\_bill\_map\_aggregate\_to\_rpt.sql](/packages/hosting/scripts/neon/migrations/090_rename_bill_map_aggregate_to_rpt.sql) | MS SQL | 10 | 7 | 6 | 23 |
| [packages/hosting/scripts/neon/migrations/091\_replace\_cause\_ntee\_with\_tag.sql](/packages/hosting/scripts/neon/migrations/091_replace_cause_ntee_with_tag.sql) | MS SQL | 48 | 12 | 10 | 70 |
| [packages/hosting/scripts/neon/migrations/092\_backfill\_text\_ai\_from\_localview\_captions.sql](/packages/hosting/scripts/neon/migrations/092_backfill_text_ai_from_localview_captions.sql) | MS SQL | 37 | 38 | 4 | 79 |
| [packages/hosting/scripts/neon/migrations/092\_consolidate\_org\_serving\_into\_mdm.sql](/packages/hosting/scripts/neon/migrations/092_consolidate_org_serving_into_mdm.sql) | MS SQL | 9 | 11 | 5 | 25 |
| [packages/hosting/scripts/neon/migrations/093\_migrate\_org\_follows\_to\_mdm.sql](/packages/hosting/scripts/neon/migrations/093_migrate_org_follows_to_mdm.sql) | MS SQL | 38 | 24 | 14 | 76 |
| [packages/hosting/scripts/neon/migrations/094\_drop\_mdm\_person\_preview.sql](/packages/hosting/scripts/neon/migrations/094_drop_mdm_person_preview.sql) | MS SQL | 3 | 14 | 4 | 21 |
| [packages/hosting/scripts/neon/migrations/095\_create\_bronze\_events\_civicsearch.sql](/packages/hosting/scripts/neon/migrations/095_create_bronze_events_civicsearch.sql) | MS SQL | 37 | 21 | 12 | 70 |
| [packages/hosting/scripts/neon/migrations/097\_create\_bronze\_events\_civicsearch\_schools.sql](/packages/hosting/scripts/neon/migrations/097_create_bronze_events_civicsearch_schools.sql) | MS SQL | 38 | 24 | 12 | 74 |
| [packages/hosting/scripts/neon/migrations/098\_text\_ai\_localview\_meeting\_metadata.sql](/packages/hosting/scripts/neon/migrations/098_text_ai_localview_meeting_metadata.sql) | MS SQL | 80 | 65 | 6 | 151 |
| [packages/hosting/scripts/neon/migrations/099\_migrate\_cause\_follows\_to\_tag.sql](/packages/hosting/scripts/neon/migrations/099_migrate_cause_follows_to_tag.sql) | MS SQL | 27 | 23 | 7 | 57 |
| [packages/hosting/scripts/neon/migrations/100\_rename\_c1\_to\_civic\_and\_add\_keys.sql](/packages/hosting/scripts/neon/migrations/100_rename_c1_to_civic_and_add_keys.sql) | MS SQL | 161 | 100 | 23 | 284 |
| [packages/hosting/scripts/neon/migrations/101\_create\_bronze\_events\_civicsearch\_topic.sql](/packages/hosting/scripts/neon/migrations/101_create_bronze_events_civicsearch_topic.sql) | MS SQL | 37 | 30 | 13 | 80 |
| [packages/hosting/scripts/neon/migrations/102\_rename\_youtube\_tables\_and\_merge.sql](/packages/hosting/scripts/neon/migrations/102_rename_youtube_tables_and_merge.sql) | MS SQL | 197 | 95 | 17 | 309 |
| [packages/hosting/scripts/neon/migrations/103\_promote\_civicsearch\_to\_bronze\_event\_youtube.sql](/packages/hosting/scripts/neon/migrations/103_promote_civicsearch_to_bronze_event_youtube.sql) | MS SQL | 39 | 32 | 4 | 75 |
| [packages/hosting/src/hosting/neon/migrate.py](/packages/hosting/src/hosting/neon/migrate.py) | Python | 10 | 3 | 1 | 14 |
| [packages/hosting/src/hosting/neon/schema.sql](/packages/hosting/src/hosting/neon/schema.sql) | MS SQL | -12 | 2 | -2 | -12 |
| [packages/ingestion/src/ingestion/civicsearch/\_\_init\_\_.py](/packages/ingestion/src/ingestion/civicsearch/__init__.py) | Python | 0 | 6 | 1 | 7 |
| [packages/ingestion/src/ingestion/civicsearch/events.py](/packages/ingestion/src/ingestion/civicsearch/events.py) | Python | 86 | 171 | 14 | 271 |
| [packages/ingestion/src/ingestion/civicsearch/topics.py](/packages/ingestion/src/ingestion/civicsearch/topics.py) | Python | 39 | 135 | 11 | 185 |
| [packages/ingestion/src/ingestion/everyorg/causes.py](/packages/ingestion/src/ingestion/everyorg/causes.py) | Python | 1 | 0 | 1 | 2 |
| [packages/ingestion/src/ingestion/mdm/\_\_init\_\_.py](/packages/ingestion/src/ingestion/mdm/__init__.py) | Python | 11 | 15 | 8 | 34 |
| [packages/ingestion/src/ingestion/mdm/\_\_main\_\_.py](/packages/ingestion/src/ingestion/mdm/__main__.py) | Python | 26 | 1 | 10 | 37 |
| [packages/ingestion/src/ingestion/mdm/db.py](/packages/ingestion/src/ingestion/mdm/db.py) | Python | 17 | 14 | 11 | 42 |
| [packages/ingestion/src/ingestion/mdm/linker.py](/packages/ingestion/src/ingestion/mdm/linker.py) | Python | 124 | 52 | 27 | 203 |
| [packages/ingestion/src/ingestion/mdm/settings.py](/packages/ingestion/src/ingestion/mdm/settings.py) | Python | 89 | 39 | 7 | 135 |
| [packages/ingestion/src/ingestion/nces/schools.py](/packages/ingestion/src/ingestion/nces/schools.py) | Python | 63 | 18 | 16 | 97 |
| [packages/ingestion/src/ingestion/openstates/README.md](/packages/ingestion/src/ingestion/openstates/README.md) | Markdown | -3 | 0 | -1 | -4 |
| [packages/ingestion/src/ingestion/openstates/aggregate\_bills\_from\_postgres.py](/packages/ingestion/src/ingestion/openstates/aggregate_bills_from_postgres.py) | Python | -241 | -170 | -33 | -444 |
| [packages/ingestion/src/ingestion/publication/gold/aggregate\_bill\_statistics.py](/packages/ingestion/src/ingestion/publication/gold/aggregate_bill_statistics.py) | Python | -117 | -34 | -39 | -190 |
| [packages/ingestion/tests/test\_civicsearch\_events\_pipeline.py](/packages/ingestion/tests/test_civicsearch_events_pipeline.py) | Python | 98 | 4 | 23 | 125 |
| [packages/ingestion/tests/test\_civicsearch\_topics\_pipeline.py](/packages/ingestion/tests/test_civicsearch_topics_pipeline.py) | Python | 72 | 2 | 23 | 97 |
| [packages/scrapers/src/scrapers/civicsearch/\_\_init\_\_.py](/packages/scrapers/src/scrapers/civicsearch/__init__.py) | Python | 0 | 12 | 1 | 13 |
| [packages/scrapers/src/scrapers/civicsearch/client.py](/packages/scrapers/src/scrapers/civicsearch/client.py) | Python | 78 | 48 | 13 | 139 |
| [packages/scrapers/src/scrapers/civicsearch/harvest.py](/packages/scrapers/src/scrapers/civicsearch/harvest.py) | Python | 441 | 181 | 53 | 675 |
| [packages/scrapers/src/scrapers/civicsearch/topics.py](/packages/scrapers/src/scrapers/civicsearch/topics.py) | Python | 126 | 50 | 28 | 204 |
| [packages/scrapers/src/scrapers/wikidata/load\_jurisdictions\_wikidata\_colab.ipynb](/packages/scrapers/src/scrapers/wikidata/load_jurisdictions_wikidata_colab.ipynb) | JSON | -72 | 0 | 0 | -72 |
| [packages/scrapers/src/scrapers/wikidata/wikidata\_fips\_gnis\_extract\_colab.ipynb](/packages/scrapers/src/scrapers/wikidata/wikidata_fips_gnis_extract_colab.ipynb) | JSON | 40 | 0 | 1 | 41 |
| [packages/scrapers/src/scrapers/youtube/backfill\_transcripts.py](/packages/scrapers/src/scrapers/youtube/backfill_transcripts.py) | Python | 142 | 86 | 22 | 250 |
| [packages/scrapers/src/scrapers/youtube/download\_audio\_colab.ipynb](/packages/scrapers/src/scrapers/youtube/download_audio_colab.ipynb) | JSON | -544 | 0 | 1 | -543 |
| [packages/scrapers/tests/test\_civicsearch\_harvest.py](/packages/scrapers/tests/test_civicsearch_harvest.py) | Python | 226 | 25 | 67 | 318 |
| [packages/scrapers/tests/test\_civicsearch\_topics.py](/packages/scrapers/tests/test_civicsearch_topics.py) | Python | 36 | 6 | 12 | 54 |
| [r/local\_view/map.R](/r/local_view/map.R) | R | 168 | 39 | 29 | 236 |
| [r/local\_view/stats.R](/r/local_view/stats.R) | R | 54 | 8 | 18 | 80 |
| [r/local\_view/supplementary.R](/r/local_view/supplementary.R) | R | 192 | 19 | 34 | 245 |
| [r/local\_view/tables.R](/r/local_view/tables.R) | R | 131 | 28 | 36 | 195 |
| [scripts/enrichment/regen\_simple.py](/scripts/enrichment/regen_simple.py) | Python | -12 | -6 | -5 | -23 |
| [scripts/run\_civicsearch\_harvest\_supervised.sh](/scripts/run_civicsearch_harvest_supervised.sh) | Shell Script | 30 | 10 | 4 | 44 |
| [scripts/run\_civicsearch\_land\_periodic.sh](/scripts/run_civicsearch_land_periodic.sh) | Shell Script | 24 | 13 | 6 | 43 |
| [tests/test\_core\_lib\_http\_client.py](/tests/test_core_lib_http_client.py) | Python | 0 | 4 | 0 | 4 |
| [web\_app/src/api/batchJobs.ts](/web_app/src/api/batchJobs.ts) | TypeScript | 7 | 2 | 1 | 10 |
| [web\_app/src/components/FollowButton.tsx](/web_app/src/components/FollowButton.tsx) | TypeScript JSX | 0 | 2 | 0 | 2 |
| [web\_app/src/pages/BatchJobStatusPage.tsx](/web_app/src/pages/BatchJobStatusPage.tsx) | TypeScript JSX | 46 | 1 | 0 | 47 |
| [web\_app/src/pages/Profile.tsx](/web_app/src/pages/Profile.tsx) | TypeScript JSX | -6 | 0 | 0 | -6 |
| [web\_docs/docs/dbt/conventions.md](/web_docs/docs/dbt/conventions.md) | Markdown | 0 | 0 | 1 | 1 |
| [web\_docs/docs/dbt/entity-resolution-mdm.md](/web_docs/docs/dbt/entity-resolution-mdm.md) | Markdown | 307 | 0 | 51 | 358 |

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details