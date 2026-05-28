# Diff Details

Date : 2026-05-26 17:49:45

Directory /home/developer/projects/open-navigator

Total : 419 files,  117703 codes, 6182 comments, 25283 blanks, all 149168 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [CITATIONS.md](/CITATIONS.md) | Markdown | 81 | 0 | 15 | 96 |
| [agents/base.py](/agents/base.py) | Python | -1 | 0 | -1 | -2 |
| [api/app.py](/api/app.py) | Python | 2 | 1 | 2 | 5 |
| [api/main.py](/api/main.py) | Python | 2 | 0 | 0 | 2 |
| [api/routes/batch\_jobs.py](/api/routes/batch_jobs.py) | Python | 355 | 12 | 53 | 420 |
| [api/routes/jurisdiction\_mapping.py](/api/routes/jurisdiction_mapping.py) | Python | 25 | 362 | 0 | 387 |
| [api/routes/stats\_neon.py](/api/routes/stats_neon.py) | Python | 26 | 156 | -1 | 181 |
| [dbt\_project/macros/int\_events\_channels\_jurisdiction\_exists.sql](/dbt_project/macros/int_events_channels_jurisdiction_exists.sql) | MS SQL | 18 | 0 | 1 | 19 |
| [dbt\_project/macros/jurisdiction\_mapping\_youtube\_summary\_columns.sql](/dbt_project/macros/jurisdiction_mapping_youtube_summary_columns.sql) | MS SQL | 8 | 0 | 1 | 9 |
| [dbt\_project/models/bronze/bronze\_ballot\_measures\_from\_ai.sql](/dbt_project/models/bronze/bronze_ballot_measures_from_ai.sql) | MS SQL | 14 | 5 | 3 | 22 |
| [dbt\_project/models/bronze/bronze\_ballot\_measures\_nist.sql](/dbt_project/models/bronze/bronze_ballot_measures_nist.sql) | MS SQL | 92 | 29 | 13 | 134 |
| [dbt\_project/models/intermediate/\_intermediate.yml](/dbt_project/models/intermediate/_intermediate.yml) | YAML | -5 | 0 | 1 | -4 |
| [dbt\_project/models/intermediate/int\_events\_channels.sql](/dbt_project/models/intermediate/int_events_channels.sql) | MS SQL | -671 | -32 | -47 | -750 |
| [dbt\_project/models/intermediate/int\_events\_channels\_registry.sql](/dbt_project/models/intermediate/int_events_channels_registry.sql) | MS SQL | 689 | 39 | 49 | 777 |
| [dbt\_project/models/intermediate/int\_jurisdiction\_homepage\_youtube\_channels.sql](/dbt_project/models/intermediate/int_jurisdiction_homepage_youtube_channels.sql) | MS SQL | 58 | 0 | 3 | 61 |
| [dbt\_project/models/intermediate/int\_jurisdiction\_meetings\_scrape\_youtube\_channels.sql](/dbt_project/models/intermediate/int_jurisdiction_meetings_scrape_youtube_channels.sql) | MS SQL | 180 | 10 | 13 | 203 |
| [dbt\_project/models/intermediate/int\_jurisdictions.sql](/dbt_project/models/intermediate/int_jurisdictions.sql) | MS SQL | 5 | 3 | 1 | 9 |
| [dbt\_project/models/marts/ballot\_measures.sql](/dbt_project/models/marts/ballot_measures.sql) | MS SQL | 84 | 41 | 15 | 140 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_analysis.sql](/dbt_project/models/marts/jurisdiction_mapping_analysis.sql) | MS SQL | 49 | 3 | 3 | 55 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary.sql) | MS SQL | 1 | 0 | 0 | 1 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary\_by\_acs\_income\_level.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary_by_acs_income_level.sql) | MS SQL | 1 | 0 | 0 | 1 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary\_by\_acs\_population\_tier.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary_by_acs_population_tier.sql) | MS SQL | 1 | 0 | 0 | 1 |
| [dbt\_project/models/marts/jurisdiction\_mapping\_quality\_summary\_municipality\_places.sql](/dbt_project/models/marts/jurisdiction_mapping_quality_summary_municipality_places.sql) | MS SQL | 1 | 0 | 0 | 1 |
| [dbt\_project/models/staging/\_staging.yml](/dbt_project/models/staging/_staging.yml) | YAML | 89 | 0 | 6 | 95 |
| [django\_ocd/civic\_odata/\_\_init\_\_.py](/django_ocd/civic_odata/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [django\_ocd/civic\_odata/asgi.py](/django_ocd/civic_odata/asgi.py) | Python | 4 | 8 | 5 | 17 |
| [django\_ocd/civic\_odata/settings.py](/django_ocd/civic_odata/settings.py) | Python | 78 | 27 | 31 | 136 |
| [django\_ocd/civic\_odata/urls.py](/django_ocd/civic_odata/urls.py) | Python | 5 | 16 | 2 | 23 |
| [django\_ocd/civic\_odata/wsgi.py](/django_ocd/civic_odata/wsgi.py) | Python | 4 | 8 | 5 | 17 |
| [django\_ocd/manage.py](/django_ocd/manage.py) | Python | 15 | 3 | 5 | 23 |
| [frontend/README.md](/frontend/README.md) | Markdown | 7 | 0 | 5 | 12 |
| [frontend/index.html](/frontend/index.html) | HTML | 2 | 0 | 0 | 2 |
| [frontend/public/wikimedia/AK\_silhouette.svg](/frontend/public/wikimedia/AK_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/AK\_silhouette\_locator.svg](/frontend/public/wikimedia/AK_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/AL\_silhouette.svg](/frontend/public/wikimedia/AL_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/AL\_silhouette\_locator.svg](/frontend/public/wikimedia/AL_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/AR\_silhouette.svg](/frontend/public/wikimedia/AR_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/AR\_silhouette\_locator.svg](/frontend/public/wikimedia/AR_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/AZ\_silhouette.svg](/frontend/public/wikimedia/AZ_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/AZ\_silhouette\_locator.svg](/frontend/public/wikimedia/AZ_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/CA\_silhouette.svg](/frontend/public/wikimedia/CA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/CA\_silhouette\_locator.svg](/frontend/public/wikimedia/CA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/CO\_silhouette.svg](/frontend/public/wikimedia/CO_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/CO\_silhouette\_locator.svg](/frontend/public/wikimedia/CO_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/CT\_silhouette.svg](/frontend/public/wikimedia/CT_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/CT\_silhouette\_locator.svg](/frontend/public/wikimedia/CT_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/DE\_silhouette.svg](/frontend/public/wikimedia/DE_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/DE\_silhouette\_locator.svg](/frontend/public/wikimedia/DE_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/FL\_silhouette.svg](/frontend/public/wikimedia/FL_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/FL\_silhouette\_locator.svg](/frontend/public/wikimedia/FL_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/GA\_silhouette.svg](/frontend/public/wikimedia/GA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/GA\_silhouette\_locator.svg](/frontend/public/wikimedia/GA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/GA\_silhouette\_state.svg](/frontend/public/wikimedia/GA_silhouette_state.svg) | XML | 76 | 0 | 1 | 77 |
| [frontend/public/wikimedia/HI\_silhouette.svg](/frontend/public/wikimedia/HI_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/HI\_silhouette\_locator.svg](/frontend/public/wikimedia/HI_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/IA\_silhouette.svg](/frontend/public/wikimedia/IA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/IA\_silhouette\_locator.svg](/frontend/public/wikimedia/IA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/ID\_silhouette.svg](/frontend/public/wikimedia/ID_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/ID\_silhouette\_locator.svg](/frontend/public/wikimedia/ID_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/IL\_silhouette.svg](/frontend/public/wikimedia/IL_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/IL\_silhouette\_locator.svg](/frontend/public/wikimedia/IL_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/IN\_silhouette.svg](/frontend/public/wikimedia/IN_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/IN\_silhouette\_locator.svg](/frontend/public/wikimedia/IN_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/KS\_silhouette.svg](/frontend/public/wikimedia/KS_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/KS\_silhouette\_locator.svg](/frontend/public/wikimedia/KS_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/KY\_silhouette.svg](/frontend/public/wikimedia/KY_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/KY\_silhouette\_locator.svg](/frontend/public/wikimedia/KY_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/LA\_silhouette.svg](/frontend/public/wikimedia/LA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/LA\_silhouette\_locator.svg](/frontend/public/wikimedia/LA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MA\_silhouette.svg](/frontend/public/wikimedia/MA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MA\_silhouette\_locator.svg](/frontend/public/wikimedia/MA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MD\_silhouette.svg](/frontend/public/wikimedia/MD_silhouette.svg) | XML | 882 | 1 | 209 | 1,092 |
| [frontend/public/wikimedia/MD\_silhouette\_locator.svg](/frontend/public/wikimedia/MD_silhouette_locator.svg) | XML | 882 | 1 | 209 | 1,092 |
| [frontend/public/wikimedia/ME\_silhouette.svg](/frontend/public/wikimedia/ME_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/ME\_silhouette\_locator.svg](/frontend/public/wikimedia/ME_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MI\_silhouette.svg](/frontend/public/wikimedia/MI_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MI\_silhouette\_locator.svg](/frontend/public/wikimedia/MI_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MN\_silhouette.svg](/frontend/public/wikimedia/MN_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MN\_silhouette\_locator.svg](/frontend/public/wikimedia/MN_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MO\_silhouette.svg](/frontend/public/wikimedia/MO_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MO\_silhouette\_locator.svg](/frontend/public/wikimedia/MO_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MS\_silhouette.svg](/frontend/public/wikimedia/MS_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MS\_silhouette\_locator.svg](/frontend/public/wikimedia/MS_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MT\_silhouette.svg](/frontend/public/wikimedia/MT_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/MT\_silhouette\_locator.svg](/frontend/public/wikimedia/MT_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NC\_silhouette.svg](/frontend/public/wikimedia/NC_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NC\_silhouette\_locator.svg](/frontend/public/wikimedia/NC_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/ND\_silhouette.svg](/frontend/public/wikimedia/ND_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/ND\_silhouette\_locator.svg](/frontend/public/wikimedia/ND_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NE\_silhouette.svg](/frontend/public/wikimedia/NE_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NE\_silhouette\_locator.svg](/frontend/public/wikimedia/NE_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NH\_silhouette.svg](/frontend/public/wikimedia/NH_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NH\_silhouette\_locator.svg](/frontend/public/wikimedia/NH_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NJ\_silhouette.svg](/frontend/public/wikimedia/NJ_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NJ\_silhouette\_locator.svg](/frontend/public/wikimedia/NJ_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NM\_silhouette.svg](/frontend/public/wikimedia/NM_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NM\_silhouette\_locator.svg](/frontend/public/wikimedia/NM_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NV\_silhouette.svg](/frontend/public/wikimedia/NV_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NV\_silhouette\_locator.svg](/frontend/public/wikimedia/NV_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NY\_silhouette.svg](/frontend/public/wikimedia/NY_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/NY\_silhouette\_locator.svg](/frontend/public/wikimedia/NY_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/OH\_silhouette.svg](/frontend/public/wikimedia/OH_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/OH\_silhouette\_locator.svg](/frontend/public/wikimedia/OH_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/OK\_silhouette.svg](/frontend/public/wikimedia/OK_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/OK\_silhouette\_locator.svg](/frontend/public/wikimedia/OK_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/OR\_silhouette.svg](/frontend/public/wikimedia/OR_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/OR\_silhouette\_locator.svg](/frontend/public/wikimedia/OR_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/PA\_silhouette.svg](/frontend/public/wikimedia/PA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/PA\_silhouette\_locator.svg](/frontend/public/wikimedia/PA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/RI\_silhouette.svg](/frontend/public/wikimedia/RI_silhouette.svg) | XML | 948 | 1 | 208 | 1,157 |
| [frontend/public/wikimedia/RI\_silhouette\_locator.svg](/frontend/public/wikimedia/RI_silhouette_locator.svg) | XML | 948 | 1 | 208 | 1,157 |
| [frontend/public/wikimedia/SC\_silhouette.svg](/frontend/public/wikimedia/SC_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/SC\_silhouette\_locator.svg](/frontend/public/wikimedia/SC_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/SD\_silhouette.svg](/frontend/public/wikimedia/SD_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/SD\_silhouette\_locator.svg](/frontend/public/wikimedia/SD_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/TN\_silhouette.svg](/frontend/public/wikimedia/TN_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/TN\_silhouette\_locator.svg](/frontend/public/wikimedia/TN_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/TX\_silhouette.svg](/frontend/public/wikimedia/TX_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/TX\_silhouette\_locator.svg](/frontend/public/wikimedia/TX_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/USA\_silhouette.svg](/frontend/public/wikimedia/USA_silhouette.svg) | XML | 78 | 1 | 0 | 79 |
| [frontend/public/wikimedia/UT\_silhouette.svg](/frontend/public/wikimedia/UT_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/UT\_silhouette\_locator.svg](/frontend/public/wikimedia/UT_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/VA\_silhouette.svg](/frontend/public/wikimedia/VA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/VA\_silhouette\_locator.svg](/frontend/public/wikimedia/VA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/VT\_silhouette.svg](/frontend/public/wikimedia/VT_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/VT\_silhouette\_locator.svg](/frontend/public/wikimedia/VT_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/WA\_silhouette.svg](/frontend/public/wikimedia/WA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/WA\_silhouette\_locator.svg](/frontend/public/wikimedia/WA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/WI\_silhouette.svg](/frontend/public/wikimedia/WI_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/WI\_silhouette\_locator.svg](/frontend/public/wikimedia/WI_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/WV\_silhouette.svg](/frontend/public/wikimedia/WV_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/WV\_silhouette\_locator.svg](/frontend/public/wikimedia/WV_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/WY\_silhouette.svg](/frontend/public/wikimedia/WY_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/WY\_silhouette\_locator.svg](/frontend/public/wikimedia/WY_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [frontend/public/wikimedia/outlines/AK\_outline.svg](/frontend/public/wikimedia/outlines/AK_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/AL\_outline.svg](/frontend/public/wikimedia/outlines/AL_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/AR\_outline.svg](/frontend/public/wikimedia/outlines/AR_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/AS\_outline.svg](/frontend/public/wikimedia/outlines/AS_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/AZ\_outline.svg](/frontend/public/wikimedia/outlines/AZ_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/CA\_outline.svg](/frontend/public/wikimedia/outlines/CA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/CO\_outline.svg](/frontend/public/wikimedia/outlines/CO_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/CT\_outline.svg](/frontend/public/wikimedia/outlines/CT_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/DE\_outline.svg](/frontend/public/wikimedia/outlines/DE_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/FL\_outline.svg](/frontend/public/wikimedia/outlines/FL_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/GA\_outline.svg](/frontend/public/wikimedia/outlines/GA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/GU\_outline.svg](/frontend/public/wikimedia/outlines/GU_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/HI\_outline.svg](/frontend/public/wikimedia/outlines/HI_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/IA\_outline.svg](/frontend/public/wikimedia/outlines/IA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/ID\_outline.svg](/frontend/public/wikimedia/outlines/ID_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/IL\_outline.svg](/frontend/public/wikimedia/outlines/IL_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/IN\_outline.svg](/frontend/public/wikimedia/outlines/IN_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/KS\_outline.svg](/frontend/public/wikimedia/outlines/KS_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/KY\_outline.svg](/frontend/public/wikimedia/outlines/KY_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/LA\_outline.svg](/frontend/public/wikimedia/outlines/LA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/MA\_outline.svg](/frontend/public/wikimedia/outlines/MA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/MD\_outline.svg](/frontend/public/wikimedia/outlines/MD_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/ME\_outline.svg](/frontend/public/wikimedia/outlines/ME_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/MI\_outline.svg](/frontend/public/wikimedia/outlines/MI_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/MN\_outline.svg](/frontend/public/wikimedia/outlines/MN_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/MO\_outline.svg](/frontend/public/wikimedia/outlines/MO_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/MP\_outline.svg](/frontend/public/wikimedia/outlines/MP_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/MS\_outline.svg](/frontend/public/wikimedia/outlines/MS_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/MT\_outline.svg](/frontend/public/wikimedia/outlines/MT_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/NC\_outline.svg](/frontend/public/wikimedia/outlines/NC_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/ND\_outline.svg](/frontend/public/wikimedia/outlines/ND_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/NE\_outline.svg](/frontend/public/wikimedia/outlines/NE_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/NH\_outline.svg](/frontend/public/wikimedia/outlines/NH_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/NJ\_outline.svg](/frontend/public/wikimedia/outlines/NJ_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/NM\_outline.svg](/frontend/public/wikimedia/outlines/NM_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/NV\_outline.svg](/frontend/public/wikimedia/outlines/NV_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/NY\_outline.svg](/frontend/public/wikimedia/outlines/NY_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/OH\_outline.svg](/frontend/public/wikimedia/outlines/OH_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/OK\_outline.svg](/frontend/public/wikimedia/outlines/OK_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/OR\_outline.svg](/frontend/public/wikimedia/outlines/OR_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/PA\_outline.svg](/frontend/public/wikimedia/outlines/PA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/PR\_outline.svg](/frontend/public/wikimedia/outlines/PR_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/RI\_outline.svg](/frontend/public/wikimedia/outlines/RI_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/SC\_outline.svg](/frontend/public/wikimedia/outlines/SC_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/SD\_outline.svg](/frontend/public/wikimedia/outlines/SD_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/TN\_outline.svg](/frontend/public/wikimedia/outlines/TN_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/TX\_outline.svg](/frontend/public/wikimedia/outlines/TX_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/UT\_outline.svg](/frontend/public/wikimedia/outlines/UT_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/VA\_outline.svg](/frontend/public/wikimedia/outlines/VA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/VI\_outline.svg](/frontend/public/wikimedia/outlines/VI_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/VT\_outline.svg](/frontend/public/wikimedia/outlines/VT_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/WA\_outline.svg](/frontend/public/wikimedia/outlines/WA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/WI\_outline.svg](/frontend/public/wikimedia/outlines/WI_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/WV\_outline.svg](/frontend/public/wikimedia/outlines/WV_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/public/wikimedia/outlines/WY\_outline.svg](/frontend/public/wikimedia/outlines/WY_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [frontend/src/App.tsx](/frontend/src/App.tsx) | TypeScript JSX | 2 | 0 | 0 | 2 |
| [frontend/src/api/batchJobs.ts](/frontend/src/api/batchJobs.ts) | TypeScript | 171 | 6 | 17 | 194 |
| [frontend/src/api/jurisdictionMappingMissingYoutube.ts](/frontend/src/api/jurisdictionMappingMissingYoutube.ts) | TypeScript | 55 | 2 | 7 | 64 |
| [frontend/src/api/jurisdictionMappingYoutubeDiagnostics.ts](/frontend/src/api/jurisdictionMappingYoutubeDiagnostics.ts) | TypeScript | 105 | 3 | 13 | 121 |
| [frontend/src/components/CensusRaceBarChart.tsx](/frontend/src/components/CensusRaceBarChart.tsx) | TypeScript JSX | -7 | 1 | 0 | -6 |
| [frontend/src/components/DataExplorerLayout.tsx](/frontend/src/components/DataExplorerLayout.tsx) | TypeScript JSX | 12 | 0 | 0 | 12 |
| [frontend/src/components/HeroStateSilhouetteBadge.tsx](/frontend/src/components/HeroStateSilhouetteBadge.tsx) | TypeScript JSX | 83 | 0 | 8 | 91 |
| [frontend/src/lib/api.ts](/frontend/src/lib/api.ts) | TypeScript | 4 | -2 | 0 | 2 |
| [frontend/src/main.tsx](/frontend/src/main.tsx) | TypeScript JSX | 2 | 0 | 1 | 3 |
| [frontend/src/pages/BatchJobStatusPage.tsx](/frontend/src/pages/BatchJobStatusPage.tsx) | TypeScript JSX | 1,422 | 1 | 69 | 1,492 |
| [frontend/src/pages/CensusMapPage.tsx](/frontend/src/pages/CensusMapPage.tsx) | TypeScript JSX | -1 | 0 | 0 | -1 |
| [frontend/src/pages/Home.tsx](/frontend/src/pages/Home.tsx) | TypeScript JSX | 1 | 0 | 0 | 1 |
| [frontend/src/pages/HomeModern.tsx](/frontend/src/pages/HomeModern.tsx) | TypeScript JSX | 9 | 0 | 1 | 10 |
| [frontend/src/pages/jurisdiction-quality/CountyYoutubeDiagnosticsSection.tsx](/frontend/src/pages/jurisdiction-quality/CountyYoutubeDiagnosticsSection.tsx) | TypeScript JSX | 393 | 1 | 20 | 414 |
| [frontend/src/pages/jurisdiction-quality/EntityQualityDashboard.tsx](/frontend/src/pages/jurisdiction-quality/EntityQualityDashboard.tsx) | TypeScript JSX | 368 | 0 | 17 | 385 |
| [frontend/src/pages/jurisdiction-quality/StateYoutubeCategorySection.tsx](/frontend/src/pages/jurisdiction-quality/StateYoutubeCategorySection.tsx) | TypeScript JSX | 274 | 0 | 20 | 294 |
| [frontend/src/utils/batchJobTiming.ts](/frontend/src/utils/batchJobTiming.ts) | TypeScript | 308 | 11 | 36 | 355 |
| [frontend/src/utils/dataExplorerPaths.ts](/frontend/src/utils/dataExplorerPaths.ts) | TypeScript | 1 | 1 | 1 | 3 |
| [frontend/src/utils/dateTime.ts](/frontend/src/utils/dateTime.ts) | TypeScript | 58 | 4 | 6 | 68 |
| [frontend/src/utils/devLog.ts](/frontend/src/utils/devLog.ts) | TypeScript | 8 | 1 | 2 | 11 |
| [frontend/src/utils/filterExtensionConsoleNoise.ts](/frontend/src/utils/filterExtensionConsoleNoise.ts) | TypeScript | 42 | 6 | 7 | 55 |
| [frontend/src/utils/formatCompact.ts](/frontend/src/utils/formatCompact.ts) | TypeScript | 52 | 3 | 6 | 61 |
| [frontend/src/utils/linkifiedText.tsx](/frontend/src/utils/linkifiedText.tsx) | TypeScript JSX | 51 | 1 | 7 | 59 |
| [frontend/src/utils/stateMapping.ts](/frontend/src/utils/stateMapping.ts) | TypeScript | 1 | 1 | 1 | 3 |
| [frontend/src/utils/wikimediaStateSilhouette.ts](/frontend/src/utils/wikimediaStateSilhouette.ts) | TypeScript | 40 | 16 | 8 | 64 |
| [frontend/vite.config.ts](/frontend/vite.config.ts) | TypeScript | 2 | 0 | 0 | 2 |
| [requirements.txt](/requirements.txt) | pip requirements | 25 | -25 | 0 | 0 |
| [scripts/datasources/ballotpedia/README.md](/scripts/datasources/ballotpedia/README.md) | Markdown | 53 | 0 | 18 | 71 |
| [scripts/datasources/ballotpedia/\_\_init\_\_.py](/scripts/datasources/ballotpedia/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [scripts/datasources/ballotpedia/ballotpedia\_integration.py](/scripts/datasources/ballotpedia/ballotpedia_integration.py) | Python | 760 | 80 | 51 | 891 |
| [scripts/datasources/ballotpedia/download\_ballotpedia\_measures.py](/scripts/datasources/ballotpedia/download_ballotpedia_measures.py) | Python | 252 | 90 | 15 | 357 |
| [scripts/datasources/ballotpedia/load\_ballotpedia\_measures\_to\_bronze.py](/scripts/datasources/ballotpedia/load_ballotpedia_measures_to_bronze.py) | Python | 356 | 68 | 53 | 477 |
| [scripts/datasources/gemini/load\_meeting\_transcripts.py](/scripts/datasources/gemini/load_meeting_transcripts.py) | Python | 7 | 3 | 0 | 10 |
| [scripts/datasources/google\_civic/google\_civic\_integration.py](/scripts/datasources/google_civic/google_civic_integration.py) | Python | 46 | -58 | -8 | -20 |
| [scripts/datasources/google\_civic/jurisdiction\_elections.py](/scripts/datasources/google_civic/jurisdiction_elections.py) | Python | 8 | 5 | 3 | 16 |
| [scripts/datasources/google\_civic/load\_google\_civic\_officials\_to\_c1.py](/scripts/datasources/google_civic/load_google_civic_officials_to_c1.py) | Python | 1,000 | 77 | 71 | 1,148 |
| [scripts/datasources/google\_civic/prune\_legacy\_flat\_source\_cache.py](/scripts/datasources/google_civic/prune_legacy_flat_source_cache.py) | Python | 20 | 2 | 9 | 31 |
| [scripts/datasources/jurisdiction\_pilot/county\_municipality\_websites.py](/scripts/datasources/jurisdiction_pilot/county_municipality_websites.py) | Python | 263 | 16 | 36 | 315 |
| [scripts/datasources/jurisdiction\_pilot/debug\_youtube\_discovery.py](/scripts/datasources/jurisdiction_pilot/debug_youtube_discovery.py) | Python | 104 | 10 | 19 | 133 |
| [scripts/datasources/jurisdiction\_pilot/http\_fetch.py](/scripts/datasources/jurisdiction_pilot/http_fetch.py) | Python | 77 | 8 | 14 | 99 |
| [scripts/datasources/jurisdiction\_pilot/mayor\_url\_discovery.py](/scripts/datasources/jurisdiction_pilot/mayor_url_discovery.py) | Python | 109 | 8 | 13 | 130 |
| [scripts/datasources/jurisdiction\_pilot/run\_scrape\_priority\_states\_debug.sh](/scripts/datasources/jurisdiction_pilot/run_scrape_priority_states_debug.sh) | Shell Script | 40 | 25 | 5 | 70 |
| [scripts/datasources/jurisdiction\_pilot/run\_scrape\_priority\_states\_terminal.sh](/scripts/datasources/jurisdiction_pilot/run_scrape_priority_states_terminal.sh) | Shell Script | 29 | 16 | 4 | 49 |
| [scripts/datasources/jurisdiction\_pilot/scrape\_priority\_states.py](/scripts/datasources/jurisdiction_pilot/scrape_priority_states.py) | Python | 502 | 109 | 54 | 665 |
| [scripts/datasources/jurisdiction\_pilot/verify.sql](/scripts/datasources/jurisdiction_pilot/verify.sql) | MS SQL | 134 | -2 | 8 | 140 |
| [scripts/datasources/jurisdiction\_pilot/website\_civicplus\_meetings.py](/scripts/datasources/jurisdiction_pilot/website_civicplus_meetings.py) | Python | 252 | 14 | 40 | 306 |
| [scripts/datasources/jurisdiction\_pilot/website\_elections.py](/scripts/datasources/jurisdiction_pilot/website_elections.py) | Python | 276 | 25 | 37 | 338 |
| [scripts/datasources/jurisdiction\_pilot/website\_youtube\_search.py](/scripts/datasources/jurisdiction_pilot/website_youtube_search.py) | Python | 36 | 3 | 3 | 42 |
| [scripts/datasources/jurisdiction\_pilot/youtube\_channel\_enrich.py](/scripts/datasources/jurisdiction_pilot/youtube_channel_enrich.py) | Python | 107 | 1 | 19 | 127 |
| [scripts/datasources/jurisdictions/export\_jurisdiction\_mapping\_quality\_json.py](/scripts/datasources/jurisdictions/export_jurisdiction_mapping_quality_json.py) | Python | 64 | 77 | 6 | 147 |
| [scripts/datasources/jurisdictions/jurisdiction\_mapping\_queries.py](/scripts/datasources/jurisdictions/jurisdiction_mapping_queries.py) | Python | 66 | 2 | 5 | 73 |
| [scripts/datasources/jurisdictions/load\_counties\_to\_postgres.py](/scripts/datasources/jurisdictions/load_counties_to_postgres.py) | Python | 3 | -1 | 1 | 3 |
| [scripts/datasources/jurisdictions/state\_youtube\_category\_rollup.py](/scripts/datasources/jurisdictions/state_youtube_category_rollup.py) | Python | 102 | 47 | 20 | 169 |
| [scripts/datasources/jurisdictions/youtube\_channel\_diagnostics.py](/scripts/datasources/jurisdictions/youtube_channel_diagnostics.py) | Python | 232 | 20 | 14 | 266 |
| [scripts/datasources/ma\_pilot/jurisdictions.py](/scripts/datasources/ma_pilot/jurisdictions.py) | Python | 0 | -8 | 0 | -8 |
| [scripts/datasources/openstates/sync\_elections\_to\_c1.py](/scripts/datasources/openstates/sync_elections_to_c1.py) | Python | 340 | 389 | 33 | 762 |
| [scripts/datasources/openstates/sync\_persons\_to\_c1.py](/scripts/datasources/openstates/sync_persons_to_c1.py) | Python | 79 | 156 | 17 | 252 |
| [scripts/datasources/parcels/README.md](/scripts/datasources/parcels/README.md) | Markdown | 97 | 0 | 39 | 136 |
| [scripts/datasources/parcels/\_\_init\_\_.py](/scripts/datasources/parcels/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [scripts/datasources/parcels/batch\_state\_parcels.py](/scripts/datasources/parcels/batch_state_parcels.py) | Python | 233 | 9 | 39 | 281 |
| [scripts/datasources/parcels/esri\_endpoints.py](/scripts/datasources/parcels/esri_endpoints.py) | Python | 81 | 14 | 21 | 116 |
| [scripts/datasources/parcels/extract\_parcel\_attributes.py](/scripts/datasources/parcels/extract_parcel_attributes.py) | Python | 188 | 23 | 34 | 245 |
| [scripts/datasources/parcels/field\_mappings.py](/scripts/datasources/parcels/field_mappings.py) | Python | 95 | 9 | 9 | 113 |
| [scripts/datasources/parcels/load\_parcel\_addresses\_to\_bronze.py](/scripts/datasources/parcels/load_parcel_addresses_to_bronze.py) | Python | 87 | 241 | 8 | 336 |
| [scripts/datasources/parcels/parse\_openaddresses\_sources.py](/scripts/datasources/parcels/parse_openaddresses_sources.py) | Python | 231 | 16 | 38 | 285 |
| [scripts/datasources/parcels/scout\_arcgis\_hub.py](/scripts/datasources/parcels/scout_arcgis_hub.py) | Python | 147 | 13 | 22 | 182 |
| [scripts/datasources/parcels/seeds/al\_manual\_overrides.json](/scripts/datasources/parcels/seeds/al_manual_overrides.json) | JSON | 8 | 0 | 1 | 9 |
| [scripts/datasources/parcels/seeds/al\_tuscaloosa\_county.json](/scripts/datasources/parcels/seeds/al_tuscaloosa_county.json) | JSON | 9 | 0 | 1 | 10 |
| [scripts/datasources/parcels/validate\_parcel\_seeds.py](/scripts/datasources/parcels/validate_parcel_seeds.py) | Python | 76 | 12 | 18 | 106 |
| [scripts/datasources/powerbi\_ballot\_measures/\_\_init\_\_.py](/scripts/datasources/powerbi_ballot_measures/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [scripts/datasources/powerbi\_ballot\_measures/download\_powerbi\_ballot\_measures.py](/scripts/datasources/powerbi_ballot_measures/download_powerbi_ballot_measures.py) | Python | 368 | 46 | 56 | 470 |
| [scripts/datasources/powerbi\_ballot\_measures/load\_powerbi\_ballot\_measures\_to\_bronze.py](/scripts/datasources/powerbi_ballot_measures/load_powerbi_ballot_measures_to_bronze.py) | Python | 358 | 157 | 52 | 567 |
| [scripts/datasources/social\_media/social\_media\_discovery.py](/scripts/datasources/social_media/social_media_discovery.py) | Python | 1 | 0 | 1 | 2 |
| [packages/scrapers/src/scrapers/wikidata/load\_channels.py](/packages/scrapers/src/scrapers/wikidata/load_channels.py) | Python | -49 | 5 | -4 | -48 |
| [packages/scrapers/src/scrapers/wikidata/load\_jurisdictions\_wikidata.py](/packages/scrapers/src/scrapers/wikidata/load_jurisdictions_wikidata.py) | Python | 27 | 0 | 0 | 27 |
| [packages/scrapers/src/scrapers/youtube/BYPASS\_IP\_BLOCK.md](/packages/scrapers/src/scrapers/youtube/BYPASS_IP_BLOCK.md) | Markdown | 11 | 0 | 7 | 18 |
| [packages/scrapers/src/scrapers/youtube/analyze\_channels.py](/packages/scrapers/src/scrapers/youtube/analyze_channels.py) | Python | 1 | 0 | 0 | 1 |
| [packages/scrapers/src/scrapers/youtube/backfill\_jurisdiction\_transcripts.py](/packages/scrapers/src/scrapers/youtube/backfill_jurisdiction_transcripts.py) | Python | 370 | 2 | 25 | 397 |
| [packages/scrapers/src/scrapers/youtube/batch\_job\_dashboard.py](/packages/scrapers/src/scrapers/youtube/batch_job_dashboard.py) | Python | 844 | 110 | 71 | 1,025 |
| [packages/scrapers/src/scrapers/youtube/batch\_job\_db.py](/packages/scrapers/src/scrapers/youtube/batch_job_db.py) | Python | 423 | 296 | 52 | 771 |
| [packages/scrapers/src/scrapers/youtube/batch\_job\_status.py](/packages/scrapers/src/scrapers/youtube/batch_job_status.py) | Python | 1,235 | 118 | 160 | 1,513 |
| [packages/scrapers/src/scrapers/youtube/bronze\_transcript\_tracking.py](/packages/scrapers/src/scrapers/youtube/bronze_transcript_tracking.py) | Python | 73 | 40 | 14 | 127 |
| [packages/scrapers/src/scrapers/youtube/clear\_pattern\_match\_youtube\_primaries.sql](/packages/scrapers/src/scrapers/youtube/clear_pattern_match_youtube_primaries.sql) | MS SQL | 17 | 5 | 5 | 27 |
| [packages/scrapers/src/scrapers/youtube/fetch\_transcript\_playwright.py](/packages/scrapers/src/scrapers/youtube/fetch_transcript_playwright.py) | Python | 295 | 31 | 44 | 370 |
| [packages/scrapers/src/scrapers/youtube/load\_youtube\_events\_to\_postgres.py](/packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py) | Python | 1,306 | 122 | 75 | 1,503 |
| [packages/scrapers/src/scrapers/youtube/pattern\_match\_gate.py](/packages/scrapers/src/scrapers/youtube/pattern_match_gate.py) | Python | 157 | 20 | 24 | 201 |
| [packages/scrapers/src/scrapers/youtube/policy\_transcript\_cache.py](/packages/scrapers/src/scrapers/youtube/policy_transcript_cache.py) | Python | 100 | 17 | 22 | 139 |
| [packages/scrapers/src/scrapers/youtube/repair\_scraped\_youtube\_channels.py](/packages/scrapers/src/scrapers/youtube/repair_scraped_youtube_channels.py) | Python | 237 | 247 | 35 | 519 |
| [packages/scrapers/src/scrapers/youtube/run\_load\_youtube\_events\_terminal.sh](/packages/scrapers/src/scrapers/youtube/run_load_youtube_events_terminal.sh) | Shell Script | 42 | 23 | 4 | 69 |
| [packages/scrapers/src/scrapers/youtube/run\_priority\_states\_last\_n.sh](/packages/scrapers/src/scrapers/youtube/run_priority_states_last_n.sh) | Shell Script | 92 | 12 | 4 | 108 |
| [packages/scrapers/src/scrapers/youtube/transcript\_api\_client.py](/packages/scrapers/src/scrapers/youtube/transcript_api_client.py) | Python | 482 | 67 | 63 | 612 |
| [packages/scrapers/src/scrapers/youtube/verify\_webshare\_proxy.py](/packages/scrapers/src/scrapers/youtube/verify_webshare_proxy.py) | Python | 33 | 2 | 11 | 46 |
| [packages/scrapers/src/scrapers/youtube/youtube\_channel\_discovery.py](/packages/scrapers/src/scrapers/youtube/youtube_channel_discovery.py) | Python | 212 | -12 | 27 | 227 |
| [packages/scrapers/src/scrapers/youtube/youtube\_channel\_page.py](/packages/scrapers/src/scrapers/youtube/youtube_channel_page.py) | Python | 255 | 19 | 31 | 305 |
| [packages/scrapers/src/scrapers/youtube/youtube\_loader\_logging.py](/packages/scrapers/src/scrapers/youtube/youtube_loader_logging.py) | Python | 86 | 14 | 21 | 121 |
| [scripts/deployment/neon/migrate.py](/scripts/deployment/neon/migrate.py) | Python | -2 | 0 | 0 | -2 |
| [scripts/deployment/neon/migrations/049\_rename\_organization\_to\_c1\_and\_contact\_to\_person.sql](/scripts/deployment/neon/migrations/049_rename_organization_to_c1_and_contact_to_person.sql) | MS SQL | 50 | 31 | 16 | 97 |
| [scripts/deployment/neon/migrations/050\_fold\_organization\_nonprofit\_into\_c1\_organization.sql](/scripts/deployment/neon/migrations/050_fold_organization_nonprofit_into_c1_organization.sql) | MS SQL | 99 | 41 | 15 | 155 |
| [scripts/deployment/neon/migrations/051\_create\_c1\_event\_child\_tables.sql](/scripts/deployment/neon/migrations/051_create_c1_event_child_tables.sql) | MS SQL | 103 | 40 | 16 | 159 |
| [scripts/deployment/neon/migrations/052\_drop\_events\_channels\_search\_and\_contact\_official.sql](/scripts/deployment/neon/migrations/052_drop_events_channels_search_and_contact_official.sql) | MS SQL | 4 | 17 | 4 | 25 |
| [scripts/deployment/neon/migrations/053\_wikidata\_to\_bronze\_and\_c1\_person\_children.sql](/scripts/deployment/neon/migrations/053_wikidata_to_bronze_and_c1_person_children.sql) | MS SQL | 71 | 32 | 20 | 123 |
| [scripts/deployment/neon/migrations/054a\_add\_lat\_lon\_to\_c1\_organization.sql](/scripts/deployment/neon/migrations/054a_add_lat_lon_to_c1_organization.sql) | MS SQL | 13 | 5 | 6 | 24 |
| [scripts/deployment/neon/migrations/055\_bronze\_websites\_ballotpedia.sql](/scripts/deployment/neon/migrations/055_bronze_websites_ballotpedia.sql) | MS SQL | 35 | 14 | 10 | 59 |
| [scripts/deployment/neon/migrations/055\_create\_c1\_election\_tables.sql](/scripts/deployment/neon/migrations/055_create_c1_election_tables.sql) | MS SQL | 135 | 4 | 11 | 150 |
| [scripts/deployment/neon/migrations/056\_create\_bronze\_ballot\_measures\_powerbi.sql](/scripts/deployment/neon/migrations/056_create_bronze_ballot_measures_powerbi.sql) | MS SQL | 50 | 15 | 11 | 76 |
| [scripts/deployment/neon/migrations/057\_create\_bronze\_ballot\_measures\_ballotpedia.sql](/scripts/deployment/neon/migrations/057_create_bronze_ballot_measures_ballotpedia.sql) | MS SQL | 55 | 14 | 16 | 85 |
| [scripts/deployment/neon/migrations/058\_rename\_ballotpedia\_bronze\_tables.sql](/scripts/deployment/neon/migrations/058_rename_ballotpedia_bronze_tables.sql) | MS SQL | 54 | 9 | 7 | 70 |
| [scripts/deployment/neon/migrations/059\_alter\_bronze\_ballot\_measures\_powerbi\_jurisdiction.sql](/scripts/deployment/neon/migrations/059_alter_bronze_ballot_measures_powerbi_jurisdiction.sql) | MS SQL | 33 | 6 | 7 | 46 |
| [scripts/deployment/neon/migrations/060\_add\_youtube\_primary\_to\_bronze\_jurisdictions\_scraped.sql](/scripts/deployment/neon/migrations/060_add_youtube_primary_to_bronze_jurisdictions_scraped.sql) | MS SQL | 22 | 7 | 7 | 36 |
| [scripts/deployment/neon/migrations/061\_jurisdiction\_id\_place\_slug\_geoid.sql](/scripts/deployment/neon/migrations/061_jurisdiction_id_place_slug_geoid.sql) | MS SQL | 187 | 15 | 22 | 224 |
| [scripts/deployment/neon/migrations/062\_add\_youtube\_channel\_id\_to\_scraped.sql](/scripts/deployment/neon/migrations/062_add_youtube_channel_id_to_scraped.sql) | MS SQL | 16 | 4 | 8 | 28 |
| [scripts/deployment/neon/migrations/063\_drop\_discovery\_confidence\_from\_jurisdiction\_youtube.sql](/scripts/deployment/neon/migrations/063_drop_discovery_confidence_from_jurisdiction_youtube.sql) | MS SQL | 4 | 5 | 4 | 13 |
| [scripts/deployment/neon/migrations/064\_remap\_legacy\_jurisdiction\_id\_fks.sql](/scripts/deployment/neon/migrations/064_remap_legacy_jurisdiction_id_fks.sql) | MS SQL | 111 | 10 | 10 | 131 |
| [scripts/deployment/neon/migrations/065\_bronze\_jurisdiction\_youtube\_candidates.sql](/scripts/deployment/neon/migrations/065_bronze_jurisdiction_youtube_candidates.sql) | MS SQL | 112 | 14 | 15 | 141 |
| [scripts/deployment/neon/migrations/066\_add\_jurisdiction\_type\_to\_bronze\_jurisdiction\_youtube.sql](/scripts/deployment/neon/migrations/066_add_jurisdiction_type_to_bronze_jurisdiction_youtube.sql) | MS SQL | 42 | 6 | 13 | 61 |
| [scripts/deployment/neon/migrations/067\_remap\_legacy\_jurisdiction\_youtube\_ids.sql](/scripts/deployment/neon/migrations/067_remap_legacy_jurisdiction_youtube_ids.sql) | MS SQL | 61 | 7 | 9 | 77 |
| [scripts/deployment/neon/migrations/068\_add\_jurisdiction\_website\_back\_links\_youtube.sql](/scripts/deployment/neon/migrations/068_add_jurisdiction_website_back_links_youtube.sql) | MS SQL | 48 | 8 | 9 | 65 |
| [scripts/deployment/neon/migrations/069\_add\_channel\_purpose\_youtube.sql](/scripts/deployment/neon/migrations/069_add_channel_purpose_youtube.sql) | MS SQL | 14 | 7 | 9 | 30 |
| [scripts/deployment/neon/migrations/070\_int\_youtube\_channel\_metadata.sql](/scripts/deployment/neon/migrations/070_int_youtube_channel_metadata.sql) | MS SQL | 22 | 4 | 7 | 33 |
| [scripts/deployment/neon/migrations/071\_int\_events\_channels\_jurisdiction\_merge.sql](/scripts/deployment/neon/migrations/071_int_events_channels_jurisdiction_merge.sql) | MS SQL | 159 | 17 | 14 | 190 |
| [scripts/deployment/neon/migrations/072\_add\_transcript\_download\_tracking.sql](/scripts/deployment/neon/migrations/072_add_transcript_download_tracking.sql) | MS SQL | 18 | 6 | 6 | 30 |
| [scripts/deployment/neon/migrations/073\_youtube\_batch\_job\_runs.sql](/scripts/deployment/neon/migrations/073_youtube_batch_job_runs.sql) | MS SQL | 22 | 7 | 7 | 36 |
| [scripts/deployment/neon/migrations/074\_create\_bronze\_addresses.sql](/scripts/deployment/neon/migrations/074_create_bronze_addresses.sql) | MS SQL | 42 | 4 | 7 | 53 |
| [scripts/deployment/neon/migrations/075\_transcript\_download\_attempts.sql](/scripts/deployment/neon/migrations/075_transcript_download_attempts.sql) | MS SQL | 13 | 7 | 7 | 27 |
| [scripts/discovery/archive/comprehensive\_discovery\_pipeline.py](/scripts/discovery/archive/comprehensive_discovery_pipeline.py) | Python | 3 | 0 | 1 | 4 |
| [scripts/discovery/backfill\_youtube\_channel\_purpose.py](/scripts/discovery/backfill_youtube_channel_purpose.py) | Python | 49 | 71 | 11 | 131 |
| [scripts/discovery/backfill\_youtube\_primary\_on\_scraped.py](/scripts/discovery/backfill_youtube_primary_on_scraped.py) | Python | 78 | 56 | 13 | 147 |
| [scripts/discovery/bronze\_jurisdiction\_youtube\_persist.py](/scripts/discovery/bronze_jurisdiction_youtube_persist.py) | Python | -84 | -39 | -9 | -132 |
| [scripts/discovery/bronze\_persons\_scraped\_persist.py](/scripts/discovery/bronze_persons_scraped_persist.py) | Python | 6 | 3 | 1 | 10 |
| [scripts/discovery/bronze\_websites\_ballotpedia\_persist.py](/scripts/discovery/bronze_websites_ballotpedia_persist.py) | Python | 58 | 10 | 9 | 77 |
| [scripts/discovery/champds\_client.py](/scripts/discovery/champds_client.py) | Python | 234 | 14 | 40 | 288 |
| [scripts/discovery/civicclerk\_meetings\_sync.py](/scripts/discovery/civicclerk_meetings_sync.py) | Python | 4 | 0 | 1 | 5 |
| [scripts/discovery/comprehensive\_discovery\_pipeline\_jurisdiction.py](/scripts/discovery/comprehensive_discovery_pipeline_jurisdiction.py) | Python | 48 | -8 | 7 | 47 |
| [scripts/discovery/consolidate\_jurisdiction\_youtube\_channels.py](/scripts/discovery/consolidate_jurisdiction_youtube_channels.py) | Python | 211 | 291 | 21 | 523 |
| [scripts/discovery/contact\_extract\_crawl4ai.py](/scripts/discovery/contact_extract_crawl4ai.py) | Python | 148 | 8 | 23 | 179 |
| [scripts/discovery/contact\_extract\_from\_html.py](/scripts/discovery/contact_extract_from_html.py) | Python | 2,118 | 80 | 270 | 2,468 |
| [scripts/discovery/contact\_profile\_images.py](/scripts/discovery/contact_profile_images.py) | Python | 203 | 2 | 25 | 230 |
| [scripts/discovery/contacts\_bundle.py](/scripts/discovery/contacts_bundle.py) | Python | 122 | 6 | 13 | 141 |
| [scripts/discovery/download\_champds\_meetings.py](/scripts/discovery/download_champds_meetings.py) | Python | 455 | 24 | 55 | 534 |
| [scripts/discovery/election\_extract\_from\_html.py](/scripts/discovery/election_extract_from_html.py) | Python | 303 | 14 | 41 | 358 |
| [scripts/discovery/fold\_organization\_location\_into\_c1.py](/scripts/discovery/fold_organization_location_into_c1.py) | Python | 180 | 76 | 44 | 300 |
| [scripts/discovery/gomeet\_mp4\_to\_opus.py](/scripts/discovery/gomeet_mp4_to_opus.py) | Python | -1 | 1 | 0 | 0 |
| [scripts/discovery/int\_events\_channels\_persist.py](/scripts/discovery/int_events_channels_persist.py) | Python | 236 | 102 | 24 | 362 |
| [scripts/discovery/int\_youtube\_channel\_metadata.py](/scripts/discovery/int_youtube_channel_metadata.py) | Python | 285 | 179 | 27 | 491 |
| [scripts/discovery/jurisdiction\_contact\_seed\_urls.py](/scripts/discovery/jurisdiction_contact_seed_urls.py) | Python | 42 | 0 | 1 | 43 |
| [scripts/discovery/jurisdiction\_discovery\_pipeline.py](/scripts/discovery/jurisdiction_discovery_pipeline.py) | Python | 217 | -111 | 13 | 119 |
| [scripts/discovery/jurisdiction\_meeting\_seed\_urls.py](/scripts/discovery/jurisdiction_meeting_seed_urls.py) | Python | 19 | 6 | 1 | 26 |
| [scripts/discovery/load\_scraped\_meetings\_manifests\_to\_bronze.py](/scripts/discovery/load_scraped_meetings_manifests_to_bronze.py) | Python | 2 | 0 | 0 | 2 |
| [scripts/discovery/meetings\_platform\_heuristics.py](/scripts/discovery/meetings_platform_heuristics.py) | Python | 14 | 2 | 2 | 18 |
| [scripts/discovery/merge\_legacy\_scraped\_meeting\_dirs.py](/scripts/discovery/merge_legacy_scraped_meeting_dirs.py) | Python | 178 | 16 | 27 | 221 |
| [scripts/discovery/promote\_bronze\_meetings\_to\_c1\_event.py](/scripts/discovery/promote_bronze_meetings_to_c1_event.py) | Python | 262 | 193 | 24 | 479 |
| [scripts/discovery/refresh\_contacts\_from\_crawl\_html.py](/scripts/discovery/refresh_contacts_from_crawl_html.py) | Python | 94 | 2 | 7 | 103 |
| [scripts/discovery/refresh\_jurisdiction\_youtube\_metadata.py](/scripts/discovery/refresh_jurisdiction_youtube_metadata.py) | Python | 96 | 103 | 14 | 213 |
| [scripts/discovery/remap\_county\_city\_youtube\_channels.py](/scripts/discovery/remap_county_city_youtube_channels.py) | Python | 52 | 274 | 7 | 333 |
| [scripts/discovery/rescrape\_county\_geoids.py](/scripts/discovery/rescrape_county_geoids.py) | Python | 154 | 39 | 26 | 219 |
| [scripts/discovery/scrape\_http.py](/scripts/discovery/scrape_http.py) | Python | 154 | 23 | 26 | 203 |
| [scripts/discovery/sql/bronze\_jurisdictions\_scraped.sql](/scripts/discovery/sql/bronze_jurisdictions_scraped.sql) | MS SQL | 8 | 0 | 0 | 8 |
| [scripts/discovery/state\_youtube\_category\_classifier.py](/scripts/discovery/state_youtube_category_classifier.py) | Python | 145 | 11 | 24 | 180 |
| [scripts/discovery/sync\_bronze\_jurisdiction\_youtube\_from\_localview.py](/scripts/discovery/sync_bronze_jurisdiction_youtube_from_localview.py) | Python | 280 | 28 | 33 | 341 |
| [scripts/discovery/sync\_bronze\_jurisdiction\_youtube\_from\_meetings\_scrape.py](/scripts/discovery/sync_bronze_jurisdiction_youtube_from_meetings_scrape.py) | Python | 311 | 22 | 38 | 371 |
| [scripts/discovery/sync\_int\_youtube\_channel\_metadata.py](/scripts/discovery/sync_int_youtube_channel_metadata.py) | Python | 53 | 175 | 10 | 238 |
| [scripts/discovery/sync\_youtube\_primary\_from\_jurisdiction\_youtube.py](/scripts/discovery/sync_youtube_primary_from_jurisdiction_youtube.py) | Python | 67 | 126 | 10 | 203 |
| [scripts/discovery/youtube\_channel\_purpose.py](/scripts/discovery/youtube_channel_purpose.py) | Python | 360 | 29 | 60 | 449 |
| [scripts/discovery/youtube\_channel\_verification.py](/scripts/discovery/youtube_channel_verification.py) | Python | 394 | 32 | 80 | 506 |
| [scripts/discovery/youtube\_city\_channel\_remap.py](/scripts/discovery/youtube_city_channel_remap.py) | Python | 195 | 34 | 38 | 267 |
| [scripts/discovery/youtube\_primary\_channel.py](/scripts/discovery/youtube_primary_channel.py) | Python | 87 | 12 | 16 | 115 |
| [scripts/enrichment/enrich\_jurisdiction\_websites\_search.py](/scripts/enrichment/enrich_jurisdiction_websites_search.py) | Python | 2 | 0 | 0 | 2 |
| [scripts/frontend/sync\_wikimedia\_silhouettes\_public.sh](/scripts/frontend/sync_wikimedia_silhouettes_public.sh) | Shell Script | 115 | 5 | 11 | 131 |
| [scripts/gemini/browser\_policy\_analysis.py](/scripts/gemini/browser_policy_analysis.py) | Python | 1 | 0 | 0 | 1 |
| [scripts/gemini/cleanup\_policy\_transcript\_cache.py](/scripts/gemini/cleanup_policy_transcript_cache.py) | Python | 50 | 17 | 13 | 80 |
| [scripts/gemini/migrate\_policy\_cache\_numeric\_folders.py](/scripts/gemini/migrate_policy_cache_numeric_folders.py) | Python | 62 | 15 | 18 | 95 |
| [scripts/gemini/policy\_processing\_status\_report.py](/scripts/gemini/policy_processing_status_report.py) | Python | 12 | 0 | 1 | 13 |
| [scripts/gemini/transcript\_cache\_paths.py](/scripts/gemini/transcript_cache_paths.py) | Python | 625 | 72 | 78 | 775 |
| [scripts/gemini/transcript\_fetch.py](/scripts/gemini/transcript_fetch.py) | Python | -24 | 3 | -3 | -24 |
| [scripts/jurisdictions/\_\_init\_\_.py](/scripts/jurisdictions/__init__.py) | Python | 20 | 1 | 3 | 24 |
| [scripts/jurisdictions/jurisdiction\_id.py](/scripts/jurisdictions/jurisdiction_id.py) | Python | 248 | 39 | 41 | 328 |
| [scripts/localview/scrape\_youtube\_channels.py](/scripts/localview/scrape_youtube_channels.py) | Python | 9 | 0 | 0 | 9 |
| [scripts/wikimedia/download\_state\_silhouettes.py](/scripts/wikimedia/download_state_silhouettes.py) | Python | 409 | 23 | 54 | 486 |
| [tests/fixtures/contact\_extract/abbeville\_elected\_officials\_snippet.html](/tests/fixtures/contact_extract/abbeville_elected_officials_snippet.html) | HTML | 24 | 0 | 1 | 25 |
| [tests/test\_api\_batch\_jobs.py](/tests/test_api_batch_jobs.py) | Python | 28 | 1 | 11 | 40 |
| [tests/test\_backfill\_transcript\_order.py](/tests/test_backfill_transcript_order.py) | Python | 25 | 1 | 7 | 33 |
| [tests/test\_baker\_wix\_minutes\_agendas.py](/tests/test_baker_wix_minutes_agendas.py) | Python | 39 | 1 | 12 | 52 |
| [tests/test\_barrow\_vimeo\_meeting\_streams.py](/tests/test_barrow_vimeo_meeting_streams.py) | Python | 20 | 1 | 8 | 29 |
| [tests/test\_batch\_job\_dashboard\_slim.py](/tests/test_batch_job_dashboard_slim.py) | Python | 86 | 1 | 13 | 100 |
| [tests/test\_batch\_job\_db.py](/tests/test_batch_job_db.py) | Python | 44 | 1 | 17 | 62 |
| [tests/test\_batch\_job\_plan.py](/tests/test_batch_job_plan.py) | Python | 167 | 1 | 28 | 196 |
| [tests/test\_batch\_job\_status.py](/tests/test_batch_job_status.py) | Python | 204 | 1 | 25 | 230 |
| [tests/test\_bronze\_jurisdiction\_youtube\_persist\_sql.py](/tests/test_bronze_jurisdiction_youtube_persist_sql.py) | Python | 17 | 1 | 7 | 25 |
| [tests/test\_bronze\_transcript\_tracking.py](/tests/test_bronze_transcript_tracking.py) | Python | 47 | 2 | 13 | 62 |
| [tests/test\_builtin\_seed\_urls\_by\_geoid.py](/tests/test_builtin_seed_urls_by_geoid.py) | Python | 11 | 1 | 4 | 16 |
| [tests/test\_caboose\_aliceville\_flex\_grid.py](/tests/test_caboose_aliceville_flex_grid.py) | Python | 31 | 1 | 7 | 39 |
| [tests/test\_centreville\_big\_box\_contact\_extract.py](/tests/test_centreville_big_box_contact_extract.py) | Python | 35 | 1 | 5 | 41 |
| [tests/test\_champds\_client.py](/tests/test_champds_client.py) | Python | 27 | 1 | 12 | 40 |
| [tests/test\_civicplus\_alabaster\_council\_table\_extract.py](/tests/test_civicplus_alabaster_council_table_extract.py) | Python | 44 | 1 | 10 | 55 |
| [tests/test\_civicplus\_gulf\_shores\_contact\_extract.py](/tests/test_civicplus_gulf_shores_contact_extract.py) | Python | 51 | 1 | 10 | 62 |
| [tests/test\_consolidate\_jurisdiction\_youtube\_channels.py](/tests/test_consolidate_jurisdiction_youtube_channels.py) | Python | 33 | 1 | 7 | 41 |
| [tests/test\_county\_municipality\_websites.py](/tests/test_county_municipality_websites.py) | Python | 48 | 1 | 11 | 60 |
| [tests/test\_fusion\_boc\_heading\_contacts.py](/tests/test_fusion_boc_heading_contacts.py) | Python | 39 | 1 | 7 | 47 |
| [tests/test\_hostinger\_abbeville\_contact\_extract.py](/tests/test_hostinger_abbeville_contact_extract.py) | Python | 29 | 1 | 7 | 37 |
| [tests/test\_infomedia\_contact\_extract.py](/tests/test_infomedia_contact_extract.py) | Python | 40 | 1 | 10 | 51 |
| [tests/test\_int\_youtube\_channel\_metadata.py](/tests/test_int_youtube_channel_metadata.py) | Python | 47 | 1 | 8 | 56 |
| [tests/test\_jurisdiction\_id\_format.py](/tests/test_jurisdiction_id_format.py) | Python | 70 | 1 | 26 | 97 |
| [tests/test\_jurisdiction\_mapping\_youtube\_queries.py](/tests/test_jurisdiction_mapping_youtube_queries.py) | Python | 20 | 1 | 6 | 27 |
| [tests/test\_jurisdiction\_pilot\_county\_no\_mayor.py](/tests/test_jurisdiction_pilot_county_no_mayor.py) | Python | 63 | 1 | 10 | 74 |
| [tests/test\_meeting\_date\_from\_title.py](/tests/test_meeting_date_from_title.py) | Python | 58 | 0 | 18 | 76 |
| [tests/test\_pattern\_match\_gate.py](/tests/test_pattern_match_gate.py) | Python | 52 | 1 | 10 | 63 |
| [tests/test\_policy\_transcript\_cache.py](/tests/test_policy_transcript_cache.py) | Python | 76 | 1 | 13 | 90 |
| [tests/test\_profile\_image\_chrome\_filters.py](/tests/test_profile_image_chrome_filters.py) | Python | 19 | 1 | 6 | 26 |
| [tests/test\_scrape\_http.py](/tests/test_scrape_http.py) | Python | 12 | 1 | 9 | 22 |
| [tests/test\_shelby\_civicplus\_commission.py](/tests/test_shelby_civicplus_commission.py) | Python | 69 | 2 | 19 | 90 |
| [tests/test\_state\_youtube\_category\_classifier.py](/tests/test_state_youtube_category_classifier.py) | Python | 59 | 1 | 10 | 70 |
| [tests/test\_sync\_bronze\_jurisdiction\_youtube\_from\_localview.py](/tests/test_sync_bronze_jurisdiction_youtube_from_localview.py) | Python | 45 | 1 | 6 | 52 |
| [tests/test\_sync\_elections\_c1\_ids.py](/tests/test_sync_elections_c1_ids.py) | Python | 193 | 3 | 18 | 214 |
| [tests/test\_sync\_meetings\_scrape\_youtube.py](/tests/test_sync_meetings_scrape_youtube.py) | Python | 23 | 1 | 4 | 28 |
| [tests/test\_transcript\_api\_client.py](/tests/test_transcript_api_client.py) | Python | 213 | 1 | 38 | 252 |
| [tests/test\_transcript\_cache\_geography.py](/tests/test_transcript_cache_geography.py) | Python | 170 | 3 | 18 | 191 |
| [tests/test\_website\_youtube\_search.py](/tests/test_website_youtube_search.py) | Python | 25 | 1 | 8 | 34 |
| [tests/test\_wikimedia\_state\_silhouettes.py](/tests/test_wikimedia_state_silhouettes.py) | Python | 21 | 1 | 5 | 27 |
| [tests/test\_wp\_caption\_contact\_extract.py](/tests/test_wp_caption_contact_extract.py) | Python | 41 | 1 | 7 | 49 |
| [tests/test\_youtube\_channel\_diagnostics.py](/tests/test_youtube_channel_diagnostics.py) | Python | 39 | 0 | 15 | 54 |
| [tests/test\_youtube\_channel\_discovery\_scrape.py](/tests/test_youtube_channel_discovery_scrape.py) | Python | 46 | 1 | 13 | 60 |
| [tests/test\_youtube\_channel\_enrich.py](/tests/test_youtube_channel_enrich.py) | Python | 62 | 2 | 16 | 80 |
| [tests/test\_youtube\_channel\_page.py](/tests/test_youtube_channel_page.py) | Python | 21 | 1 | 9 | 31 |
| [tests/test\_youtube\_channel\_purpose.py](/tests/test_youtube_channel_purpose.py) | Python | 126 | 1 | 20 | 147 |
| [tests/test\_youtube\_channel\_verification.py](/tests/test_youtube_channel_verification.py) | Python | 361 | 4 | 36 | 401 |
| [tests/test\_youtube\_city\_channel\_remap.py](/tests/test_youtube_city_channel_remap.py) | Python | 81 | 2 | 22 | 105 |
| [tests/test\_youtube\_loader\_rate\_limit\_detail.py](/tests/test_youtube_loader_rate_limit_detail.py) | Python | 9 | 1 | 4 | 14 |
| [tests/test\_youtube\_primary\_channel.py](/tests/test_youtube_primary_channel.py) | Python | 78 | 2 | 12 | 92 |
| [website/docs/data-sources/citations.md](/website/docs/data-sources/citations.md) | Markdown | 27 | 0 | 11 | 38 |
| [website/docs/guides/hackathon-video-submission-ideas.md](/website/docs/guides/hackathon-video-submission-ideas.md) | Markdown | 127 | 0 | 93 | 220 |

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details