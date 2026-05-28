# Diff Details

Date : 2026-05-28 16:52:44

Directory /home/developer/projects/open-navigator

Total : 639 files,  107686 codes, 5438 comments, 24033 blanks, all 137157 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [.github/workflows/ci-build-test.yml](/.github/workflows/ci-build-test.yml) | YAML | 40 | 10 | 8 | 58 |
| [Dockerfile](/Dockerfile) | Docker | 1 | 2 | 1 | 4 |
| [agents/\_\_init\_\_.py](/agents/__init__.py) | Python | -14 | -1 | -2 | -17 |
| [agents/advocacy.py](/agents/advocacy.py) | Python | -298 | -58 | -53 | -409 |
| [agents/base.py](/agents/base.py) | Python | -96 | -47 | -24 | -167 |
| [agents/classifier.py](/agents/classifier.py) | Python | -189 | -67 | -40 | -296 |
| [agents/debate\_grader.py](/agents/debate_grader.py) | Python | -305 | -64 | -56 | -425 |
| [agents/mlflow\_base.py](/agents/mlflow_base.py) | Python | -162 | -108 | -38 | -308 |
| [agents/mlflow\_classifier.py](/agents/mlflow_classifier.py) | Python | -140 | -147 | -22 | -309 |
| [agents/orchestrator.py](/agents/orchestrator.py) | Python | -154 | -81 | -35 | -270 |
| [agents/parser.py](/agents/parser.py) | Python | -123 | -47 | -30 | -200 |
| [agents/policy\_reasoning\_analyzer.py](/agents/policy_reasoning_analyzer.py) | Python | -370 | -91 | -42 | -503 |
| [agents/scraper.py](/agents/scraper.py) | Python | -34 | -7 | -10 | -51 |
| [agents/scraper\_undetected.py](/agents/scraper_undetected.py) | Python | -173 | -46 | -43 | -262 |
| [agents/sentiment.py](/agents/sentiment.py) | Python | -248 | -73 | -61 | -382 |
| [agents/test\_policy\_analyzer.py](/agents/test_policy_analyzer.py) | Python | -72 | -14 | -27 | -113 |
| [api/main.py](/api/main.py) | Python | 6 | 0 | 0 | 6 |
| [api/routes/addresses.py](/api/routes/addresses.py) | Python | 168 | 233 | 31 | 432 |
| [api/routes/cpi.py](/api/routes/cpi.py) | Python | 57 | 18 | 11 | 86 |
| [api/routes/geocode.py](/api/routes/geocode.py) | Python | 97 | 38 | 21 | 156 |
| [api/routes/jurisdiction\_mapping.py](/api/routes/jurisdiction_mapping.py) | Python | 11 | 78 | 1 | 90 |
| [api/routes/stats\_neon.py](/api/routes/stats_neon.py) | Python | -12 | -40 | 0 | -52 |
| [api/routes/trending.py](/api/routes/trending.py) | Python | -24 | 60 | -23 | 13 |
| [api/static/assets/index-7vzWAgiE.css](/api/static/assets/index-7vzWAgiE.css) | PostCSS | -1 | 0 | -1 | -2 |
| [api/static/assets/index-CuLxv8We.js](/api/static/assets/index-CuLxv8We.js) | JavaScript | -223 | 0 | -21 | -244 |
| [api/static/assets/index-DUP2inG1.js](/api/static/assets/index-DUP2inG1.js) | JavaScript | 226 | 0 | 24 | 250 |
| [api/static/assets/index-jc6LK3Mm.css](/api/static/assets/index-jc6LK3Mm.css) | PostCSS | 1 | 0 | 1 | 2 |
| [api/static/index.html](/api/static/index.html) | HTML | 2 | 0 | 0 | 2 |
| [api/static/wikimedia/AK\_silhouette.svg](/api/static/wikimedia/AK_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/AK\_silhouette\_locator.svg](/api/static/wikimedia/AK_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/AL\_silhouette.svg](/api/static/wikimedia/AL_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/AL\_silhouette\_locator.svg](/api/static/wikimedia/AL_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/AR\_silhouette.svg](/api/static/wikimedia/AR_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/AR\_silhouette\_locator.svg](/api/static/wikimedia/AR_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/AZ\_silhouette.svg](/api/static/wikimedia/AZ_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/AZ\_silhouette\_locator.svg](/api/static/wikimedia/AZ_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/CA\_silhouette.svg](/api/static/wikimedia/CA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/CA\_silhouette\_locator.svg](/api/static/wikimedia/CA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/CO\_silhouette.svg](/api/static/wikimedia/CO_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/CO\_silhouette\_locator.svg](/api/static/wikimedia/CO_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/CT\_silhouette.svg](/api/static/wikimedia/CT_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/CT\_silhouette\_locator.svg](/api/static/wikimedia/CT_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/DE\_silhouette.svg](/api/static/wikimedia/DE_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/DE\_silhouette\_locator.svg](/api/static/wikimedia/DE_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/FL\_silhouette.svg](/api/static/wikimedia/FL_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/FL\_silhouette\_locator.svg](/api/static/wikimedia/FL_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/GA\_silhouette.svg](/api/static/wikimedia/GA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/GA\_silhouette\_locator.svg](/api/static/wikimedia/GA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/GA\_silhouette\_state.svg](/api/static/wikimedia/GA_silhouette_state.svg) | XML | 76 | 0 | 1 | 77 |
| [api/static/wikimedia/HI\_silhouette.svg](/api/static/wikimedia/HI_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/HI\_silhouette\_locator.svg](/api/static/wikimedia/HI_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/IA\_silhouette.svg](/api/static/wikimedia/IA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/IA\_silhouette\_locator.svg](/api/static/wikimedia/IA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/ID\_silhouette.svg](/api/static/wikimedia/ID_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/ID\_silhouette\_locator.svg](/api/static/wikimedia/ID_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/IL\_silhouette.svg](/api/static/wikimedia/IL_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/IL\_silhouette\_locator.svg](/api/static/wikimedia/IL_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/IN\_silhouette.svg](/api/static/wikimedia/IN_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/IN\_silhouette\_locator.svg](/api/static/wikimedia/IN_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/KS\_silhouette.svg](/api/static/wikimedia/KS_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/KS\_silhouette\_locator.svg](/api/static/wikimedia/KS_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/KY\_silhouette.svg](/api/static/wikimedia/KY_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/KY\_silhouette\_locator.svg](/api/static/wikimedia/KY_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/LA\_silhouette.svg](/api/static/wikimedia/LA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/LA\_silhouette\_locator.svg](/api/static/wikimedia/LA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MA\_silhouette.svg](/api/static/wikimedia/MA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MA\_silhouette\_locator.svg](/api/static/wikimedia/MA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MD\_silhouette.svg](/api/static/wikimedia/MD_silhouette.svg) | XML | 882 | 1 | 209 | 1,092 |
| [api/static/wikimedia/MD\_silhouette\_locator.svg](/api/static/wikimedia/MD_silhouette_locator.svg) | XML | 882 | 1 | 209 | 1,092 |
| [api/static/wikimedia/ME\_silhouette.svg](/api/static/wikimedia/ME_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/ME\_silhouette\_locator.svg](/api/static/wikimedia/ME_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MI\_silhouette.svg](/api/static/wikimedia/MI_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MI\_silhouette\_locator.svg](/api/static/wikimedia/MI_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MN\_silhouette.svg](/api/static/wikimedia/MN_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MN\_silhouette\_locator.svg](/api/static/wikimedia/MN_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MO\_silhouette.svg](/api/static/wikimedia/MO_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MO\_silhouette\_locator.svg](/api/static/wikimedia/MO_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MS\_silhouette.svg](/api/static/wikimedia/MS_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MS\_silhouette\_locator.svg](/api/static/wikimedia/MS_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MT\_silhouette.svg](/api/static/wikimedia/MT_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/MT\_silhouette\_locator.svg](/api/static/wikimedia/MT_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NC\_silhouette.svg](/api/static/wikimedia/NC_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NC\_silhouette\_locator.svg](/api/static/wikimedia/NC_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/ND\_silhouette.svg](/api/static/wikimedia/ND_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/ND\_silhouette\_locator.svg](/api/static/wikimedia/ND_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NE\_silhouette.svg](/api/static/wikimedia/NE_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NE\_silhouette\_locator.svg](/api/static/wikimedia/NE_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NH\_silhouette.svg](/api/static/wikimedia/NH_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NH\_silhouette\_locator.svg](/api/static/wikimedia/NH_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NJ\_silhouette.svg](/api/static/wikimedia/NJ_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NJ\_silhouette\_locator.svg](/api/static/wikimedia/NJ_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NM\_silhouette.svg](/api/static/wikimedia/NM_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NM\_silhouette\_locator.svg](/api/static/wikimedia/NM_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NV\_silhouette.svg](/api/static/wikimedia/NV_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NV\_silhouette\_locator.svg](/api/static/wikimedia/NV_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NY\_silhouette.svg](/api/static/wikimedia/NY_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/NY\_silhouette\_locator.svg](/api/static/wikimedia/NY_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/OH\_silhouette.svg](/api/static/wikimedia/OH_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/OH\_silhouette\_locator.svg](/api/static/wikimedia/OH_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/OK\_silhouette.svg](/api/static/wikimedia/OK_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/OK\_silhouette\_locator.svg](/api/static/wikimedia/OK_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/OR\_silhouette.svg](/api/static/wikimedia/OR_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/OR\_silhouette\_locator.svg](/api/static/wikimedia/OR_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/PA\_silhouette.svg](/api/static/wikimedia/PA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/PA\_silhouette\_locator.svg](/api/static/wikimedia/PA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/RI\_silhouette.svg](/api/static/wikimedia/RI_silhouette.svg) | XML | 948 | 1 | 208 | 1,157 |
| [api/static/wikimedia/RI\_silhouette\_locator.svg](/api/static/wikimedia/RI_silhouette_locator.svg) | XML | 948 | 1 | 208 | 1,157 |
| [api/static/wikimedia/SC\_silhouette.svg](/api/static/wikimedia/SC_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/SC\_silhouette\_locator.svg](/api/static/wikimedia/SC_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/SD\_silhouette.svg](/api/static/wikimedia/SD_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/SD\_silhouette\_locator.svg](/api/static/wikimedia/SD_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/TN\_silhouette.svg](/api/static/wikimedia/TN_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/TN\_silhouette\_locator.svg](/api/static/wikimedia/TN_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/TX\_silhouette.svg](/api/static/wikimedia/TX_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/TX\_silhouette\_locator.svg](/api/static/wikimedia/TX_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/USA\_silhouette.svg](/api/static/wikimedia/USA_silhouette.svg) | XML | 78 | 1 | 0 | 79 |
| [api/static/wikimedia/UT\_silhouette.svg](/api/static/wikimedia/UT_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/UT\_silhouette\_locator.svg](/api/static/wikimedia/UT_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/VA\_silhouette.svg](/api/static/wikimedia/VA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/VA\_silhouette\_locator.svg](/api/static/wikimedia/VA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/VT\_silhouette.svg](/api/static/wikimedia/VT_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/VT\_silhouette\_locator.svg](/api/static/wikimedia/VT_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/WA\_silhouette.svg](/api/static/wikimedia/WA_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/WA\_silhouette\_locator.svg](/api/static/wikimedia/WA_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/WI\_silhouette.svg](/api/static/wikimedia/WI_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/WI\_silhouette\_locator.svg](/api/static/wikimedia/WI_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/WV\_silhouette.svg](/api/static/wikimedia/WV_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/WV\_silhouette\_locator.svg](/api/static/wikimedia/WV_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/WY\_silhouette.svg](/api/static/wikimedia/WY_silhouette.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/WY\_silhouette\_locator.svg](/api/static/wikimedia/WY_silhouette_locator.svg) | XML | 845 | 1 | 209 | 1,055 |
| [api/static/wikimedia/outlines/AK\_outline.svg](/api/static/wikimedia/outlines/AK_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/AL\_outline.svg](/api/static/wikimedia/outlines/AL_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/AR\_outline.svg](/api/static/wikimedia/outlines/AR_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/AS\_outline.svg](/api/static/wikimedia/outlines/AS_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/AZ\_outline.svg](/api/static/wikimedia/outlines/AZ_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/CA\_outline.svg](/api/static/wikimedia/outlines/CA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/CO\_outline.svg](/api/static/wikimedia/outlines/CO_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/CT\_outline.svg](/api/static/wikimedia/outlines/CT_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/DE\_outline.svg](/api/static/wikimedia/outlines/DE_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/FL\_outline.svg](/api/static/wikimedia/outlines/FL_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/GA\_outline.svg](/api/static/wikimedia/outlines/GA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/GU\_outline.svg](/api/static/wikimedia/outlines/GU_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/HI\_outline.svg](/api/static/wikimedia/outlines/HI_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/IA\_outline.svg](/api/static/wikimedia/outlines/IA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/ID\_outline.svg](/api/static/wikimedia/outlines/ID_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/IL\_outline.svg](/api/static/wikimedia/outlines/IL_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/IN\_outline.svg](/api/static/wikimedia/outlines/IN_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/KS\_outline.svg](/api/static/wikimedia/outlines/KS_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/KY\_outline.svg](/api/static/wikimedia/outlines/KY_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/LA\_outline.svg](/api/static/wikimedia/outlines/LA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/MA\_outline.svg](/api/static/wikimedia/outlines/MA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/MD\_outline.svg](/api/static/wikimedia/outlines/MD_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/ME\_outline.svg](/api/static/wikimedia/outlines/ME_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/MI\_outline.svg](/api/static/wikimedia/outlines/MI_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/MN\_outline.svg](/api/static/wikimedia/outlines/MN_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/MO\_outline.svg](/api/static/wikimedia/outlines/MO_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/MP\_outline.svg](/api/static/wikimedia/outlines/MP_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/MS\_outline.svg](/api/static/wikimedia/outlines/MS_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/MT\_outline.svg](/api/static/wikimedia/outlines/MT_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/NC\_outline.svg](/api/static/wikimedia/outlines/NC_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/ND\_outline.svg](/api/static/wikimedia/outlines/ND_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/NE\_outline.svg](/api/static/wikimedia/outlines/NE_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/NH\_outline.svg](/api/static/wikimedia/outlines/NH_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/NJ\_outline.svg](/api/static/wikimedia/outlines/NJ_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/NM\_outline.svg](/api/static/wikimedia/outlines/NM_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/NV\_outline.svg](/api/static/wikimedia/outlines/NV_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/NY\_outline.svg](/api/static/wikimedia/outlines/NY_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/OH\_outline.svg](/api/static/wikimedia/outlines/OH_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/OK\_outline.svg](/api/static/wikimedia/outlines/OK_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/OR\_outline.svg](/api/static/wikimedia/outlines/OR_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/PA\_outline.svg](/api/static/wikimedia/outlines/PA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/PR\_outline.svg](/api/static/wikimedia/outlines/PR_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/RI\_outline.svg](/api/static/wikimedia/outlines/RI_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/SC\_outline.svg](/api/static/wikimedia/outlines/SC_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/SD\_outline.svg](/api/static/wikimedia/outlines/SD_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/TN\_outline.svg](/api/static/wikimedia/outlines/TN_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/TX\_outline.svg](/api/static/wikimedia/outlines/TX_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/UT\_outline.svg](/api/static/wikimedia/outlines/UT_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/VA\_outline.svg](/api/static/wikimedia/outlines/VA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/VI\_outline.svg](/api/static/wikimedia/outlines/VI_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/VT\_outline.svg](/api/static/wikimedia/outlines/VT_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/WA\_outline.svg](/api/static/wikimedia/outlines/WA_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/WI\_outline.svg](/api/static/wikimedia/outlines/WI_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/WV\_outline.svg](/api/static/wikimedia/outlines/WV_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [api/static/wikimedia/outlines/WY\_outline.svg](/api/static/wikimedia/outlines/WY_outline.svg) | XML | 4 | 0 | 1 | 5 |
| [archive/datasources/cdp/example\_fetch.py](/archive/datasources/cdp/example_fetch.py) | Python | 56 | 21 | 15 | 92 |
| [archive/datasources/census/fix\_geoid\_format.py](/archive/datasources/census/fix_geoid_format.py) | Python | 45 | 63 | 8 | 116 |
| [archive/datasources/fec/demo\_fec\_integration.py](/archive/datasources/fec/demo_fec_integration.py) | Python | 180 | 54 | 55 | 289 |
| [archive/datasources/fec/demo\_political\_influence.py](/archive/datasources/fec/demo_political_influence.py) | Python | 260 | 32 | 60 | 352 |
| [archive/datasources/gemini/migrations/README.md](/archive/datasources/gemini/migrations/README.md) | Markdown | 65 | 0 | 28 | 93 |
| [archive/datasources/gemini/migrations/backfill\_ntee\_from\_arguments.py](/archive/datasources/gemini/migrations/backfill_ntee_from_arguments.py) | Python | 139 | 16 | 23 | 178 |
| [archive/datasources/gemini/migrations/backfill\_ntee\_to\_topics.py](/archive/datasources/gemini/migrations/backfill_ntee_to_topics.py) | Python | 108 | 15 | 20 | 143 |
| [archive/datasources/gemini/migrations/cleanup\_null\_records.py](/archive/datasources/gemini/migrations/cleanup_null_records.py) | Python | 88 | 20 | 35 | 143 |
| [archive/datasources/gemini/migrations/infer\_ntee\_from\_topics.py](/archive/datasources/gemini/migrations/infer_ntee_from_topics.py) | Python | 144 | 16 | 30 | 190 |
| [archive/datasources/gemini/migrations/migrate\_add\_ntee\_to\_topics.py](/archive/datasources/gemini/migrations/migrate_add_ntee_to_topics.py) | Python | 109 | 17 | 22 | 148 |
| [archive/datasources/gemini/migrations/migrate\_add\_secondary\_ntee.py](/archive/datasources/gemini/migrations/migrate_add_secondary_ntee.py) | Python | 102 | 8 | 20 | 130 |
| [archive/datasources/gemini/migrations/migrate\_multimodel\_support.py](/archive/datasources/gemini/migrations/migrate_multimodel_support.py) | Python | 154 | 158 | 31 | 343 |
| [archive/datasources/gemini/migrations/repopulate\_ntee\_codes.py](/archive/datasources/gemini/migrations/repopulate_ntee_codes.py) | Python | 293 | 40 | 53 | 386 |
| [archive/datasources/google\_civic/prune\_legacy\_flat\_source\_cache.py](/archive/datasources/google_civic/prune_legacy_flat_source_cache.py) | Python | 20 | 2 | 9 | 31 |
| [archive/datasources/grants\_gov/demo\_grants\_gov.py](/archive/datasources/grants_gov/demo_grants_gov.py) | Python | 204 | 35 | 52 | 291 |
| [archive/datasources/jurisdictions/migrate\_parquet\_state\_naming.py](/archive/datasources/jurisdictions/migrate_parquet_state_naming.py) | Python | 60 | 22 | 17 | 99 |
| [archive/datasources/master\_data/create\_jurisdiction\_master.py](/archive/datasources/master_data/create_jurisdiction_master.py) | Python | 1,005 | 182 | 144 | 1,331 |
| [archive/datasources/nccs/README.md](/archive/datasources/nccs/README.md) | Markdown | 165 | 0 | 53 | 218 |
| [archive/datasources/nces/fix\_and\_enrich\_school\_districts.py](/archive/datasources/nces/fix_and_enrich_school_districts.py) | Python | 144 | 166 | 22 | 332 |
| [archive/datasources/nces/migrate\_schools\_to\_orgloc.py](/archive/datasources/nces/migrate_schools_to_orgloc.py) | Python | 123 | 18 | 28 | 169 |
| [archive/datasources/ntee/README.md](/archive/datasources/ntee/README.md) | Markdown | 163 | 0 | 49 | 212 |
| [archive/datasources/wikidata/cleanup\_bad\_counties.py](/archive/datasources/wikidata/cleanup_bad_counties.py) | Python | 111 | 21 | 18 | 150 |
| [archive/datasources/wikidata/fix\_fips\_codes.py](/archive/datasources/wikidata/fix_fips_codes.py) | Python | 111 | 21 | 25 | 157 |
| [archive/datasources/wikidata/load\_jurisdictions\_wikidata.py](/archive/datasources/wikidata/load_jurisdictions_wikidata.py) | Python | 2,484 | 1,524 | 152 | 4,160 |
| [config/\_\_init\_\_.py](/config/__init__.py) | Python | -2 | -1 | -2 | -5 |
| [config/settings.py](/config/settings.py) | Python | -80 | -24 | -23 | -127 |
| [databricks/README.md](/databricks/README.md) | Markdown | -279 | 0 | -71 | -350 |
| [databricks/communityone\_schema.sql](/databricks/communityone_schema.sql) | MS SQL | -501 | -88 | -53 | -642 |
| [databricks/deployment.py](/databricks/deployment.py) | Python | -193 | -108 | -44 | -345 |
| [databricks/evaluation.py](/databricks/evaluation.py) | Python | -162 | -146 | -36 | -344 |
| [databricks/notebooks/01\_agent\_bricks\_quickstart.py](/databricks/notebooks/01_agent_bricks_quickstart.py) | Python | -52 | -262 | -16 | -330 |
| [dbt\_project/CONVENTIONS.md](/dbt_project/CONVENTIONS.md) | Markdown | 240 | 0 | 86 | 326 |
| [dbt\_project/macros/c1\_election\_ids.sql](/dbt_project/macros/c1_election_ids.sql) | MS SQL | 85 | 0 | 10 | 95 |
| [dbt\_project/macros/latest\_per\_natural\_key.sql](/dbt_project/macros/latest_per_natural_key.sql) | MS SQL | 18 | 0 | 1 | 19 |
| [dbt\_project/macros/state\_code\_to\_name.sql](/dbt_project/macros/state_code_to_name.sql) | MS SQL | 57 | 10 | 1 | 68 |
| [dbt\_project/models/bronze/bronze\_bls\_cpi.sql](/dbt_project/models/bronze/bronze_bls_cpi.sql) | MS SQL | 20 | 10 | 4 | 34 |
| [dbt\_project/models/bronze/bronze\_census\_finance\_variables.sql](/dbt_project/models/bronze/bronze_census_finance_variables.sql) | MS SQL | 26 | 10 | 4 | 40 |
| [dbt\_project/models/bronze/bronze\_jurisdiction\_tpc.sql](/dbt_project/models/bronze/bronze_jurisdiction_tpc.sql) | MS SQL | 23 | 10 | 4 | 37 |
| [dbt\_project/models/intermediate/\_intermediate.yml](/dbt_project/models/intermediate/_intermediate.yml) | YAML | 59 | 0 | 3 | 62 |
| [dbt\_project/models/intermediate/\_schema\_int\_ballotpedia.yml](/dbt_project/models/intermediate/_schema_int_ballotpedia.yml) | YAML | 92 | 1 | 3 | 96 |
| [dbt\_project/models/intermediate/\_schema\_int\_google\_civic.yml](/dbt_project/models/intermediate/_schema_int_google_civic.yml) | YAML | 108 | 0 | 2 | 110 |
| [dbt\_project/models/intermediate/\_schema\_int\_master.yml](/dbt_project/models/intermediate/_schema_int_master.yml) | YAML | 128 | 0 | 5 | 133 |
| [dbt\_project/models/intermediate/\_schema\_int\_nccs.yml](/dbt_project/models/intermediate/_schema_int_nccs.yml) | YAML | 51 | 2 | 2 | 55 |
| [dbt\_project/models/intermediate/\_schema\_int\_ntee.yml](/dbt_project/models/intermediate/_schema_int_ntee.yml) | YAML | 47 | 2 | 2 | 51 |
| [dbt\_project/models/intermediate/\_schema\_int\_powerbi.yml](/dbt_project/models/intermediate/_schema_int_powerbi.yml) | YAML | 77 | 2 | 2 | 81 |
| [dbt\_project/models/intermediate/int\_ballotpedia\_\_measure\_resolved.sql](/dbt_project/models/intermediate/int_ballotpedia__measure_resolved.sql) | MS SQL | 123 | 50 | 9 | 182 |
| [dbt\_project/models/intermediate/int\_events\_channels\_registry.sql](/dbt_project/models/intermediate/int_events_channels_registry.sql) | MS SQL | 26 | 9 | 1 | 36 |
| [dbt\_project/models/intermediate/int\_google\_civic\_\_election\_ids.sql](/dbt_project/models/intermediate/int_google_civic__election_ids.sql) | MS SQL | 80 | 36 | 9 | 125 |
| [dbt\_project/models/intermediate/int\_jurisdictions.sql](/dbt_project/models/intermediate/int_jurisdictions.sql) | MS SQL | 0 | 9 | 0 | 9 |
| [dbt\_project/models/intermediate/int\_master\_\_crosswalk.sql](/dbt_project/models/intermediate/int_master__crosswalk.sql) | MS SQL | 359 | 65 | 22 | 446 |
| [dbt\_project/models/intermediate/int\_master\_\_crosswalk\_enriched.sql](/dbt_project/models/intermediate/int_master__crosswalk_enriched.sql) | MS SQL | 20 | 10 | 7 | 37 |
| [dbt\_project/models/intermediate/int\_master\_\_domain\_registry.sql](/dbt_project/models/intermediate/int_master__domain_registry.sql) | MS SQL | 76 | 16 | 10 | 102 |
| [dbt\_project/models/intermediate/int\_nccs\_\_current\_orgs.sql](/dbt_project/models/intermediate/int_nccs__current_orgs.sql) | MS SQL | 25 | 8 | 6 | 39 |
| [dbt\_project/models/intermediate/int\_ntee\_\_breadcrumb.sql](/dbt_project/models/intermediate/int_ntee__breadcrumb.sql) | MS SQL | 46 | 25 | 9 | 80 |
| [dbt\_project/models/intermediate/int\_powerbi\_\_measure\_with\_jurisdiction.sql](/dbt_project/models/intermediate/int_powerbi__measure_with_jurisdiction.sql) | MS SQL | 78 | 38 | 10 | 126 |
| [dbt\_project/models/intermediate/int\_wikidata\_\_jurisdictions\_enriched.sql](/dbt_project/models/intermediate/int_wikidata__jurisdictions_enriched.sql) | MS SQL | 193 | 35 | 17 | 245 |
| [dbt\_project/models/intermediate/int\_youtube\_\_events.sql](/dbt_project/models/intermediate/int_youtube__events.sql) | MS SQL | 81 | 21 | 9 | 111 |
| [dbt\_project/models/marts/\_schema\_dim\_jurisdictions\_master.yml](/dbt_project/models/marts/_schema_dim_jurisdictions_master.yml) | YAML | 74 | 0 | 4 | 78 |
| [dbt\_project/models/marts/\_schema\_elections.yml](/dbt_project/models/marts/_schema_elections.yml) | YAML | 281 | 15 | 6 | 302 |
| [dbt\_project/models/marts/dim\_candidate\_contests.sql](/dbt_project/models/marts/dim_candidate_contests.sql) | MS SQL | 50 | 35 | 10 | 95 |
| [dbt\_project/models/marts/dim\_election\_divisions.sql](/dbt_project/models/marts/dim_election_divisions.sql) | MS SQL | 38 | 21 | 8 | 67 |
| [dbt\_project/models/marts/dim\_jurisdictions\_master.sql](/dbt_project/models/marts/dim_jurisdictions_master.sql) | MS SQL | 58 | 26 | 8 | 92 |
| [dbt\_project/models/marts/fct\_ballot\_measures\_civic.sql](/dbt_project/models/marts/fct_ballot_measures_civic.sql) | MS SQL | 51 | 41 | 9 | 101 |
| [dbt\_project/models/marts/fct\_candidacies.sql](/dbt_project/models/marts/fct_candidacies.sql) | MS SQL | 62 | 43 | 11 | 116 |
| [dbt\_project/models/marts/fct\_elections.sql](/dbt_project/models/marts/fct_elections.sql) | MS SQL | 42 | 37 | 8 | 87 |
| [dbt\_project/models/staging/\_schema\_stg\_ballotpedia.yml](/dbt_project/models/staging/_schema_stg_ballotpedia.yml) | YAML | 85 | 2 | 2 | 89 |
| [dbt\_project/models/staging/\_schema\_stg\_bls.yml](/dbt_project/models/staging/_schema_stg_bls.yml) | YAML | 30 | 0 | 2 | 32 |
| [dbt\_project/models/staging/\_schema\_stg\_everyorg.yml](/dbt_project/models/staging/_schema_stg_everyorg.yml) | YAML | 47 | 2 | 2 | 51 |
| [dbt\_project/models/staging/\_schema\_stg\_google\_civic.yml](/dbt_project/models/staging/_schema_stg_google_civic.yml) | YAML | 98 | 0 | 2 | 100 |
| [dbt\_project/models/staging/\_schema\_stg\_gsa.yml](/dbt_project/models/staging/_schema_stg_gsa.yml) | YAML | 53 | 1 | 13 | 67 |
| [dbt\_project/models/staging/\_schema\_stg\_hifld.yml](/dbt_project/models/staging/_schema_stg_hifld.yml) | YAML | 76 | 2 | 4 | 82 |
| [dbt\_project/models/staging/\_schema\_stg\_mdm.yml](/dbt_project/models/staging/_schema_stg_mdm.yml) | YAML | 138 | 0 | 4 | 142 |
| [dbt\_project/models/staging/\_schema\_stg\_naco.yml](/dbt_project/models/staging/_schema_stg_naco.yml) | YAML | 58 | 2 | 2 | 62 |
| [dbt\_project/models/staging/\_schema\_stg\_nccs.yml](/dbt_project/models/staging/_schema_stg_nccs.yml) | YAML | 53 | 2 | 2 | 57 |
| [dbt\_project/models/staging/\_schema\_stg\_ntee.yml](/dbt_project/models/staging/_schema_stg_ntee.yml) | YAML | 49 | 2 | 2 | 53 |
| [dbt\_project/models/staging/\_schema\_stg\_powerbi.yml](/dbt_project/models/staging/_schema_stg_powerbi.yml) | YAML | 73 | 2 | 2 | 77 |
| [dbt\_project/models/staging/\_schema\_stg\_wikidata.yml](/dbt_project/models/staging/_schema_stg_wikidata.yml) | YAML | 199 | 13 | 7 | 219 |
| [dbt\_project/models/staging/\_schema\_stg\_youtube.yml](/dbt_project/models/staging/_schema_stg_youtube.yml) | YAML | 112 | 1 | 31 | 144 |
| [dbt\_project/models/staging/\_staging.yml](/dbt_project/models/staging/_staging.yml) | YAML | 389 | 13 | 10 | 412 |
| [dbt\_project/models/staging/stg\_ballotpedia\_\_measure.sql](/dbt_project/models/staging/stg_ballotpedia__measure.sql) | MS SQL | 133 | 49 | 22 | 204 |
| [dbt\_project/models/staging/stg\_bls\_\_cpi\_annual.sql](/dbt_project/models/staging/stg_bls__cpi_annual.sql) | MS SQL | 44 | 15 | 8 | 67 |
| [dbt\_project/models/staging/stg\_everyorg\_\_cause.sql](/dbt_project/models/staging/stg_everyorg__cause.sql) | MS SQL | 36 | 8 | 8 | 52 |
| [dbt\_project/models/staging/stg\_google\_civic\_\_election\_record.sql](/dbt_project/models/staging/stg_google_civic__election_record.sql) | MS SQL | 76 | 18 | 8 | 102 |
| [dbt\_project/models/staging/stg\_gsa\_\_domains.sql](/dbt_project/models/staging/stg_gsa__domains.sql) | MS SQL | 38 | 10 | 8 | 56 |
| [dbt\_project/models/staging/stg\_hifld\_\_location.sql](/dbt_project/models/staging/stg_hifld__location.sql) | MS SQL | 116 | 30 | 20 | 166 |
| [dbt\_project/models/staging/stg\_mdm\_\_jurisdiction.sql](/dbt_project/models/staging/stg_mdm__jurisdiction.sql) | MS SQL | 47 | 13 | 7 | 67 |
| [dbt\_project/models/staging/stg\_mdm\_\_jurisdictions\_wikidata.sql](/dbt_project/models/staging/stg_mdm__jurisdictions_wikidata.sql) | MS SQL | 47 | 7 | 7 | 61 |
| [dbt\_project/models/staging/stg\_mdm\_\_organization\_location.sql](/dbt_project/models/staging/stg_mdm__organization_location.sql) | MS SQL | 52 | 15 | 7 | 74 |
| [dbt\_project/models/staging/stg\_naco\_\_county.sql](/dbt_project/models/staging/stg_naco__county.sql) | MS SQL | 119 | 32 | 19 | 170 |
| [dbt\_project/models/staging/stg\_nccs\_\_organization.sql](/dbt_project/models/staging/stg_nccs__organization.sql) | MS SQL | 49 | 9 | 8 | 66 |
| [dbt\_project/models/staging/stg\_ntee\_\_code.sql](/dbt_project/models/staging/stg_ntee__code.sql) | MS SQL | 38 | 11 | 8 | 57 |
| [dbt\_project/models/staging/stg\_powerbi\_\_ballot\_measure.sql](/dbt_project/models/staging/stg_powerbi__ballot_measure.sql) | MS SQL | 191 | 41 | 32 | 264 |
| [dbt\_project/models/staging/stg\_wikidata\_\_enrichment.sql](/dbt_project/models/staging/stg_wikidata__enrichment.sql) | MS SQL | 84 | 22 | 8 | 114 |
| [dbt\_project/models/staging/stg\_wikidata\_\_jurisdiction\_counties.sql](/dbt_project/models/staging/stg_wikidata__jurisdiction_counties.sql) | MS SQL | 41 | 15 | 8 | 64 |
| [dbt\_project/models/staging/stg\_wikidata\_\_jurisdiction\_municipalities.sql](/dbt_project/models/staging/stg_wikidata__jurisdiction_municipalities.sql) | MS SQL | 45 | 12 | 8 | 65 |
| [dbt\_project/models/staging/stg\_wikidata\_\_jurisdiction\_school\_districts.sql](/dbt_project/models/staging/stg_wikidata__jurisdiction_school_districts.sql) | MS SQL | 43 | 13 | 8 | 64 |
| [dbt\_project/models/staging/stg\_youtube\_\_event.sql](/dbt_project/models/staging/stg_youtube__event.sql) | MS SQL | 126 | 37 | 10 | 173 |
| [dbt\_project/scripts/STATS\_PIPELINE\_README.md](/dbt_project/scripts/STATS_PIPELINE_README.md) | Markdown | 265 | 0 | 83 | 348 |
| [dbt\_project/scripts/export\_stats\_to\_open\_navigator.py](/dbt_project/scripts/export_stats_to_open_navigator.py) | Python | 108 | 21 | 29 | 158 |
| [dbt\_project/scripts/rebuild\_stats\_aggregates\_fixed.py](/dbt_project/scripts/rebuild_stats_aggregates_fixed.py) | Python | 201 | 12 | 22 | 235 |
| [dbt\_project/scripts/rebuild\_stats\_fixed.py](/dbt_project/scripts/rebuild_stats_fixed.py) | Python | 214 | 12 | 24 | 250 |
| [frontend/package-lock.json](/frontend/package-lock.json) | JSON | 317 | 0 | 0 | 317 |
| [frontend/package.json](/frontend/package.json) | JSON | 9 | 0 | 0 | 9 |
| [frontend/src/App.tsx](/frontend/src/App.tsx) | TypeScript JSX | 17 | 6 | 2 | 25 |
| [frontend/src/api/batchJobs.ts](/frontend/src/api/batchJobs.ts) | TypeScript | 8 | 0 | 0 | 8 |
| [frontend/src/api/jurisdictionMappingYoutubeDiagnostics.ts](/frontend/src/api/jurisdictionMappingYoutubeDiagnostics.ts) | TypeScript | 30 | 1 | 3 | 34 |
| [frontend/src/components/AddressLookup.tsx](/frontend/src/components/AddressLookup.tsx) | TypeScript JSX | -29 | 3 | 0 | -26 |
| [frontend/src/components/CensusDrilldownLocalView.tsx](/frontend/src/components/CensusDrilldownLocalView.tsx) | TypeScript JSX | 262 | 30 | 17 | 309 |
| [frontend/src/components/CensusDrilldownStage.tsx](/frontend/src/components/CensusDrilldownStage.tsx) | TypeScript JSX | 898 | 151 | 38 | 1,087 |
| [frontend/src/components/CensusMapDisplayPopover.tsx](/frontend/src/components/CensusMapDisplayPopover.tsx) | TypeScript JSX | 189 | 10 | 12 | 211 |
| [frontend/src/components/CensusMapLeftRail.tsx](/frontend/src/components/CensusMapLeftRail.tsx) | TypeScript JSX | 114 | 13 | 6 | 133 |
| [frontend/src/components/CensusMapLegends.tsx](/frontend/src/components/CensusMapLegends.tsx) | TypeScript JSX | 239 | 0 | 5 | 244 |
| [frontend/src/components/CensusMetricBrowserPanel.tsx](/frontend/src/components/CensusMetricBrowserPanel.tsx) | TypeScript JSX | 89 | 13 | 5 | 107 |
| [frontend/src/components/InflationToggle.tsx](/frontend/src/components/InflationToggle.tsx) | TypeScript JSX | 49 | 12 | 3 | 64 |
| [frontend/src/components/MapAddressSearch.tsx](/frontend/src/components/MapAddressSearch.tsx) | TypeScript JSX | 245 | 23 | 15 | 283 |
| [frontend/src/data/causes.ts](/frontend/src/data/causes.ts) | TypeScript | 61 | 2 | 3 | 66 |
| [frontend/src/data/exploreActionPhases.ts](/frontend/src/data/exploreActionPhases.ts) | TypeScript | 510 | 6 | 36 | 552 |
| [frontend/src/data/homeQuickNavFlyouts.tsx](/frontend/src/data/homeQuickNavFlyouts.tsx) | TypeScript JSX | 349 | 1 | 11 | 361 |
| [frontend/src/data/wikicommonsPlatesLatest.json](/frontend/src/data/wikicommonsPlatesLatest.json) | JSON | 26 | 0 | 1 | 27 |
| [frontend/src/data/wikimediaStateSilhouettes.json](/frontend/src/data/wikimediaStateSilhouettes.json) | JSON | 116 | 0 | 1 | 117 |
| [frontend/src/hooks/useCpiAnnual.ts](/frontend/src/hooks/useCpiAnnual.ts) | TypeScript | 23 | 12 | 5 | 40 |
| [frontend/src/hooks/useInflationToggle.ts](/frontend/src/hooks/useInflationToggle.ts) | TypeScript | 40 | 13 | 9 | 62 |
| [frontend/src/index.css](/frontend/src/index.css) | PostCSS | 14 | 2 | 1 | 17 |
| [frontend/src/lib/api.types.ts](/frontend/src/lib/api.types.ts) | TypeScript | 1,149 | 408 | 2 | 1,559 |
| [frontend/src/lib/apiClient.ts](/frontend/src/lib/apiClient.ts) | TypeScript | 3 | 11 | 2 | 16 |
| [frontend/src/pages/BatchJobStatusPage.tsx](/frontend/src/pages/BatchJobStatusPage.tsx) | TypeScript JSX | -1 | 0 | -1 | -2 |
| [frontend/src/pages/CensusDrilldownMapPage.tsx](/frontend/src/pages/CensusDrilldownMapPage.tsx) | TypeScript JSX | 1,708 | 172 | 72 | 1,952 |
| [frontend/src/pages/CensusMapPage.tsx](/frontend/src/pages/CensusMapPage.tsx) | TypeScript JSX | 195 | 10 | 1 | 206 |
| [frontend/src/pages/DataExplorerScorecardPage.tsx](/frontend/src/pages/DataExplorerScorecardPage.tsx) | TypeScript JSX | -30 | 2 | 0 | -28 |
| [frontend/src/pages/jurisdiction-quality/CountyYoutubeDiagnosticsSection.tsx](/frontend/src/pages/jurisdiction-quality/CountyYoutubeDiagnosticsSection.tsx) | TypeScript JSX | 58 | 9 | 6 | 73 |
| [frontend/src/pages/jurisdiction-quality/EntityQualityDashboard.tsx](/frontend/src/pages/jurisdiction-quality/EntityQualityDashboard.tsx) | TypeScript JSX | 12 | 6 | 1 | 19 |
| [frontend/src/utils/censusMapTransforms.ts](/frontend/src/utils/censusMapTransforms.ts) | TypeScript | 0 | 4 | 0 | 4 |
| [frontend/src/utils/censusMetricGroups.ts](/frontend/src/utils/censusMetricGroups.ts) | TypeScript | 80 | 17 | 10 | 107 |
| [frontend/src/utils/inflation.ts](/frontend/src/utils/inflation.ts) | TypeScript | 50 | 24 | 6 | 80 |
| [frontend/src/utils/ringOverlap.ts](/frontend/src/utils/ringOverlap.ts) | TypeScript | 53 | 23 | 7 | 83 |
| [models/meeting\_event.py](/models/meeting_event.py) | Python | -220 | -71 | -51 | -342 |
| [packages/accessibility/src/accessibility/README.md](/packages/accessibility/src/accessibility/README.md) | Markdown | 193 | 0 | 70 | 263 |
| [packages/accessibility/src/accessibility/\_\_init\_\_.py](/packages/accessibility/src/accessibility/__init__.py) | Python | 0 | 1 | 1 | 2 |
| [packages/accessibility/src/accessibility/\_int\_websites.py](/packages/accessibility/src/accessibility/_int_websites.py) | Python | 11 | 2 | 6 | 19 |
| [packages/accessibility/src/accessibility/docker\_entrypoint.py](/packages/accessibility/src/accessibility/docker_entrypoint.py) | Python | 54 | 2 | 12 | 68 |
| [packages/accessibility/src/accessibility/export\_pdf\_urls.py](/packages/accessibility/src/accessibility/export_pdf_urls.py) | Python | 182 | 11 | 25 | 218 |
| [packages/accessibility/src/accessibility/export\_urls.py](/packages/accessibility/src/accessibility/export_urls.py) | Python | 86 | 99 | 14 | 199 |
| [packages/accessibility/src/accessibility/lambda\_handler.py](/packages/accessibility/src/accessibility/lambda_handler.py) | Python | 134 | 20 | 12 | 166 |
| [packages/accessibility/src/accessibility/pa11yci.config.cjs](/packages/accessibility/src/accessibility/pa11yci.config.cjs) | JavaScript | 21 | 4 | 2 | 27 |
| [packages/accessibility/src/accessibility/package-lock.json](/packages/accessibility/src/accessibility/package-lock.json) | JSON | 3,853 | 0 | 1 | 3,854 |
| [packages/accessibility/src/accessibility/package.json](/packages/accessibility/src/accessibility/package.json) | JSON | 21 | 0 | 1 | 22 |
| [packages/accessibility/src/accessibility/persist\_lighthouse\_results.py](/packages/accessibility/src/accessibility/persist_lighthouse_results.py) | Python | 100 | 160 | 6 | 266 |
| [packages/accessibility/src/accessibility/persist\_results.py](/packages/accessibility/src/accessibility/persist_results.py) | Python | 254 | 47 | 31 | 332 |
| [packages/accessibility/src/accessibility/persist\_verapdf\_results.py](/packages/accessibility/src/accessibility/persist_verapdf_results.py) | Python | 49 | 118 | 6 | 173 |
| [packages/accessibility/src/accessibility/run\_accessibility\_scan.sh](/packages/accessibility/src/accessibility/run_accessibility_scan.sh) | Shell Script | 103 | 8 | 12 | 123 |
| [packages/accessibility/src/accessibility/run\_axe\_scan.mjs](/packages/accessibility/src/accessibility/run_axe_scan.mjs) | JavaScript | 150 | 8 | 17 | 175 |
| [packages/accessibility/src/accessibility/run\_lighthouse\_scan.mjs](/packages/accessibility/src/accessibility/run_lighthouse_scan.mjs) | JavaScript | 209 | 19 | 27 | 255 |
| [packages/accessibility/src/accessibility/run\_pa11y\_workers.mjs](/packages/accessibility/src/accessibility/run_pa11y_workers.mjs) | JavaScript | 173 | 15 | 21 | 209 |
| [packages/accessibility/src/accessibility/run\_verapdf\_scan.py](/packages/accessibility/src/accessibility/run_verapdf_scan.py) | Python | 172 | 12 | 30 | 214 |
| [packages/accessibility/src/accessibility/run\_verapdf\_scan.sh](/packages/accessibility/src/accessibility/run_verapdf_scan.sh) | Shell Script | 55 | 7 | 10 | 72 |
| [packages/accessibility/src/accessibility/sql/bronze\_jurisdiction\_pdf\_verapdf.sql](/packages/accessibility/src/accessibility/sql/bronze_jurisdiction_pdf_verapdf.sql) | MS SQL | 32 | 2 | 7 | 41 |
| [packages/accessibility/src/accessibility/sql/bronze\_jurisdiction\_website\_accessibility.sql](/packages/accessibility/src/accessibility/sql/bronze_jurisdiction_website_accessibility.sql) | MS SQL | 31 | 3 | 7 | 41 |
| [packages/accessibility/src/accessibility/sql/bronze\_jurisdiction\_website\_lighthouse.sql](/packages/accessibility/src/accessibility/sql/bronze_jurisdiction_website_lighthouse.sql) | MS SQL | 66 | 4 | 8 | 78 |
| [packages/accessibility/src/accessibility/verapdf\_cli.py](/packages/accessibility/src/accessibility/verapdf_cli.py) | Python | 154 | 4 | 24 | 182 |
| [packages/agents/agents/\_\_init\_\_.py](/packages/agents/agents/__init__.py) | Python | 14 | 1 | 2 | 17 |
| [packages/agents/agents/advocacy.py](/packages/agents/agents/advocacy.py) | Python | 298 | 58 | 53 | 409 |
| [packages/agents/agents/base.py](/packages/agents/agents/base.py) | Python | 96 | 47 | 24 | 167 |
| [packages/agents/agents/classifier.py](/packages/agents/agents/classifier.py) | Python | 189 | 67 | 40 | 296 |
| [packages/agents/agents/debate\_grader.py](/packages/agents/agents/debate_grader.py) | Python | 305 | 64 | 56 | 425 |
| [packages/agents/agents/mlflow\_base.py](/packages/agents/agents/mlflow_base.py) | Python | 162 | 108 | 38 | 308 |
| [packages/agents/agents/mlflow\_classifier.py](/packages/agents/agents/mlflow_classifier.py) | Python | 140 | 147 | 22 | 309 |
| [packages/agents/agents/orchestrator.py](/packages/agents/agents/orchestrator.py) | Python | 154 | 81 | 35 | 270 |
| [packages/agents/agents/parser.py](/packages/agents/agents/parser.py) | Python | 123 | 47 | 30 | 200 |
| [packages/agents/agents/policy\_reasoning\_analyzer.py](/packages/agents/agents/policy_reasoning_analyzer.py) | Python | 370 | 91 | 42 | 503 |
| [packages/agents/agents/scraper.py](/packages/agents/agents/scraper.py) | Python | 34 | 7 | 10 | 51 |
| [packages/agents/agents/scraper\_undetected.py](/packages/agents/agents/scraper_undetected.py) | Python | 173 | 46 | 43 | 262 |
| [packages/agents/agents/sentiment.py](/packages/agents/agents/sentiment.py) | Python | 248 | 73 | 61 | 382 |
| [packages/agents/agents/test\_policy\_analyzer.py](/packages/agents/agents/test_policy_analyzer.py) | Python | 72 | 14 | 27 | 113 |
| [packages/core-lib/src/core\_lib/\_\_init\_\_.py](/packages/core-lib/src/core_lib/__init__.py) | Python | 1 | 1 | 2 | 4 |
| [packages/core-lib/src/core\_lib/db/\_\_init\_\_.py](/packages/core-lib/src/core_lib/db/__init__.py) | Python | 9 | 1 | 2 | 12 |
| [packages/core-lib/src/core\_lib/db/engine.py](/packages/core-lib/src/core_lib/db/engine.py) | Python | 46 | 1 | 11 | 58 |
| [packages/core-lib/src/core\_lib/db/session.py](/packages/core-lib/src/core_lib/db/session.py) | Python | 46 | 4 | 15 | 65 |
| [packages/core-lib/src/core\_lib/http/\_\_init\_\_.py](/packages/core-lib/src/core_lib/http/__init__.py) | Python | 2 | 1 | 2 | 5 |
| [packages/core-lib/src/core\_lib/http/client.py](/packages/core-lib/src/core_lib/http/client.py) | Python | 109 | 15 | 18 | 142 |
| [packages/core-lib/src/core\_lib/logging.py](/packages/core-lib/src/core_lib/logging.py) | Python | 20 | 2 | 7 | 29 |
| [packages/core-lib/src/core\_lib/pipeline/\_\_init\_\_.py](/packages/core-lib/src/core_lib/pipeline/__init__.py) | Python | 4 | 1 | 2 | 7 |
| [packages/core-lib/src/core\_lib/pipeline/base.py](/packages/core-lib/src/core_lib/pipeline/base.py) | Python | 72 | 13 | 15 | 100 |
| [packages/core-lib/src/core\_lib/pipeline/metrics.py](/packages/core-lib/src/core_lib/pipeline/metrics.py) | Python | 17 | 1 | 5 | 23 |
| [packages/core-lib/src/core\_lib/pipeline/schemas.py](/packages/core-lib/src/core_lib/pipeline/schemas.py) | Python | 17 | 3 | 11 | 31 |
| [packages/core/config/\_\_init\_\_.py](/packages/core/config/__init__.py) | Python | 2 | 1 | 2 | 5 |
| [packages/core/config/settings.py](/packages/core/config/settings.py) | Python | 80 | 28 | 23 | 131 |
| [packages/datamodels/models/\_\_init\_\_.py](/packages/datamodels/models/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/datamodels/models/meeting\_event.py](/packages/datamodels/models/meeting_event.py) | Python | 220 | 71 | 51 | 342 |
| [packages/ingestion/src/ingestion/\_\_init\_\_.py](/packages/ingestion/src/ingestion/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/arcgis/\_\_init\_\_.py](/packages/ingestion/src/ingestion/arcgis/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/arcgis/addresses.py](/packages/ingestion/src/ingestion/arcgis/addresses.py) | Python | 268 | 222 | 39 | 529 |
| [packages/ingestion/src/ingestion/ballotpedia/\_\_init\_\_.py](/packages/ingestion/src/ingestion/ballotpedia/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/ballotpedia/measures.py](/packages/ingestion/src/ingestion/ballotpedia/measures.py) | Python | 196 | 86 | 47 | 329 |
| [packages/ingestion/src/ingestion/bls/\_\_init\_\_.py](/packages/ingestion/src/ingestion/bls/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/bls/cpi.py](/packages/ingestion/src/ingestion/bls/cpi.py) | Python | 282 | 95 | 50 | 427 |
| [packages/ingestion/src/ingestion/census/\_\_init\_\_.py](/packages/ingestion/src/ingestion/census/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/census/acs.py](/packages/ingestion/src/ingestion/census/acs.py) | Python | 413 | 205 | 110 | 728 |
| [packages/ingestion/src/ingestion/census/counties.py](/packages/ingestion/src/ingestion/census/counties.py) | Python | 155 | 104 | 48 | 307 |
| [packages/ingestion/src/ingestion/census/counties\_jurisdictions.py](/packages/ingestion/src/ingestion/census/counties_jurisdictions.py) | Python | 177 | 51 | 37 | 265 |
| [packages/ingestion/src/ingestion/census/county\_mappings.py](/packages/ingestion/src/ingestion/census/county_mappings.py) | Python | 146 | 71 | 43 | 260 |
| [packages/ingestion/src/ingestion/census/details.py](/packages/ingestion/src/ingestion/census/details.py) | Python | 168 | 71 | 36 | 275 |
| [packages/ingestion/src/ingestion/census/gazetteer.py](/packages/ingestion/src/ingestion/census/gazetteer.py) | Python | 312 | 285 | 7 | 604 |
| [packages/ingestion/src/ingestion/census/govsstatefin\_variables.py](/packages/ingestion/src/ingestion/census/govsstatefin_variables.py) | Python | 292 | 100 | 44 | 436 |
| [packages/ingestion/src/ingestion/census/municipalities.py](/packages/ingestion/src/ingestion/census/municipalities.py) | Python | 135 | 97 | 43 | 275 |
| [packages/ingestion/src/ingestion/census/place\_crosswalks.py](/packages/ingestion/src/ingestion/census/place_crosswalks.py) | Python | 270 | 164 | 71 | 505 |
| [packages/ingestion/src/ingestion/census/postal\_codes.py](/packages/ingestion/src/ingestion/census/postal_codes.py) | Python | 182 | 93 | 56 | 331 |
| [packages/ingestion/src/ingestion/census/relationships.py](/packages/ingestion/src/ingestion/census/relationships.py) | Python | 194 | 114 | 57 | 365 |
| [packages/ingestion/src/ingestion/census/shapefiles.py](/packages/ingestion/src/ingestion/census/shapefiles.py) | Python | 261 | 197 | 45 | 503 |
| [packages/ingestion/src/ingestion/census/states.py](/packages/ingestion/src/ingestion/census/states.py) | Python | 103 | 35 | 17 | 155 |
| [packages/ingestion/src/ingestion/dot/\_\_init\_\_.py](/packages/ingestion/src/ingestion/dot/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/dot/download.py](/packages/ingestion/src/ingestion/dot/download.py) | Python | 225 | 36 | 38 | 299 |
| [packages/ingestion/src/ingestion/dot/events.py](/packages/ingestion/src/ingestion/dot/events.py) | Python | 134 | 42 | 28 | 204 |
| [packages/ingestion/src/ingestion/everyorg/\_\_init\_\_.py](/packages/ingestion/src/ingestion/everyorg/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/everyorg/causes.py](/packages/ingestion/src/ingestion/everyorg/causes.py) | Python | 208 | 75 | 46 | 329 |
| [packages/ingestion/src/ingestion/everyorg/causes.yaml](/packages/ingestion/src/ingestion/everyorg/causes.yaml) | YAML | 120 | 15 | 18 | 153 |
| [packages/ingestion/src/ingestion/fec/\_\_init\_\_.py](/packages/ingestion/src/ingestion/fec/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/fec/bulk.py](/packages/ingestion/src/ingestion/fec/bulk.py) | Python | 316 | 171 | 40 | 527 |
| [packages/ingestion/src/ingestion/fec/contributions.py](/packages/ingestion/src/ingestion/fec/contributions.py) | Python | 195 | 192 | 27 | 414 |
| [packages/ingestion/src/ingestion/google\_civic/\_\_init\_\_.py](/packages/ingestion/src/ingestion/google_civic/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/google\_civic/ocd.py](/packages/ingestion/src/ingestion/google_civic/ocd.py) | Python | 197 | 60 | 48 | 305 |
| [packages/ingestion/src/ingestion/google\_civic/officials.py](/packages/ingestion/src/ingestion/google_civic/officials.py) | Python | 326 | 264 | 41 | 631 |
| [packages/ingestion/src/ingestion/gsa/\_\_init\_\_.py](/packages/ingestion/src/ingestion/gsa/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/gsa/domains.py](/packages/ingestion/src/ingestion/gsa/domains.py) | Python | 133 | 65 | 36 | 234 |
| [packages/ingestion/src/ingestion/gsa/download.py](/packages/ingestion/src/ingestion/gsa/download.py) | Python | 51 | 12 | 21 | 84 |
| [packages/ingestion/src/ingestion/hifld/\_\_init\_\_.py](/packages/ingestion/src/ingestion/hifld/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/hifld/download.py](/packages/ingestion/src/ingestion/hifld/download.py) | Python | 127 | 31 | 37 | 195 |
| [packages/ingestion/src/ingestion/hifld/locations.py](/packages/ingestion/src/ingestion/hifld/locations.py) | Python | 133 | 64 | 37 | 234 |
| [packages/ingestion/src/ingestion/hud/\_\_init\_\_.py](/packages/ingestion/src/ingestion/hud/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/hud/zip\_county.py](/packages/ingestion/src/ingestion/hud/zip_county.py) | Python | 157 | 52 | 41 | 250 |
| [packages/ingestion/src/ingestion/irs/\_\_init\_\_.py](/packages/ingestion/src/ingestion/irs/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/irs/bmf.py](/packages/ingestion/src/ingestion/irs/bmf.py) | Python | 230 | 97 | 38 | 365 |
| [packages/ingestion/src/ingestion/leagueofcities/\_\_init\_\_.py](/packages/ingestion/src/ingestion/leagueofcities/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/leagueofcities/directories.py](/packages/ingestion/src/ingestion/leagueofcities/directories.py) | Python | 519 | 359 | 61 | 939 |
| [packages/ingestion/src/ingestion/localview/\_\_init\_\_.py](/packages/ingestion/src/ingestion/localview/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/localview/events.py](/packages/ingestion/src/ingestion/localview/events.py) | Python | 333 | 184 | 56 | 573 |
| [packages/ingestion/src/ingestion/naco/\_\_init\_\_.py](/packages/ingestion/src/ingestion/naco/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/naco/counties.py](/packages/ingestion/src/ingestion/naco/counties.py) | Python | 127 | 206 | 35 | 368 |
| [packages/ingestion/src/ingestion/nccs/\_\_init\_\_.py](/packages/ingestion/src/ingestion/nccs/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/nccs/bulk.py](/packages/ingestion/src/ingestion/nccs/bulk.py) | Python | 168 | 202 | 31 | 401 |
| [packages/ingestion/src/ingestion/nccs/download.py](/packages/ingestion/src/ingestion/nccs/download.py) | Python | 243 | 65 | 60 | 368 |
| [packages/ingestion/src/ingestion/nces/\_\_init\_\_.py](/packages/ingestion/src/ingestion/nces/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/nces/school\_districts.py](/packages/ingestion/src/ingestion/nces/school_districts.py) | Python | 297 | 337 | 42 | 676 |
| [packages/ingestion/src/ingestion/ncls/\_\_init\_\_.py](/packages/ingestion/src/ingestion/ncls/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/ncls/ballot\_measures.py](/packages/ingestion/src/ingestion/ncls/ballot_measures.py) | Python | 133 | 66 | 41 | 240 |
| [packages/ingestion/src/ingestion/ntee/\_\_init\_\_.py](/packages/ingestion/src/ingestion/ntee/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/ntee/codes.py](/packages/ingestion/src/ingestion/ntee/codes.py) | Python | 220 | 138 | 49 | 407 |
| [packages/ingestion/src/ingestion/openstates/\_\_init\_\_.py](/packages/ingestion/src/ingestion/openstates/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/openstates/download.py](/packages/ingestion/src/ingestion/openstates/download.py) | Python | 160 | 51 | 49 | 260 |
| [packages/ingestion/src/ingestion/openstates/people.py](/packages/ingestion/src/ingestion/openstates/people.py) | Python | 143 | 172 | 26 | 341 |
| [packages/ingestion/src/ingestion/osf/\_\_init\_\_.py](/packages/ingestion/src/ingestion/osf/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/osf/download.py](/packages/ingestion/src/ingestion/osf/download.py) | Python | 301 | 68 | 79 | 448 |
| [packages/ingestion/src/ingestion/osf/files.py](/packages/ingestion/src/ingestion/osf/files.py) | Python | 133 | 56 | 38 | 227 |
| [packages/ingestion/src/ingestion/osf/rds.py](/packages/ingestion/src/ingestion/osf/rds.py) | Python | 246 | 69 | 59 | 374 |
| [packages/ingestion/src/ingestion/tpc/\_\_init\_\_.py](/packages/ingestion/src/ingestion/tpc/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/tpc/finance.py](/packages/ingestion/src/ingestion/tpc/finance.py) | Python | 380 | 163 | 59 | 602 |
| [packages/ingestion/src/ingestion/uscm/\_\_init\_\_.py](/packages/ingestion/src/ingestion/uscm/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/uscm/mayors.py](/packages/ingestion/src/ingestion/uscm/mayors.py) | Python | 97 | 143 | 16 | 256 |
| [packages/ingestion/src/ingestion/wikicommons/\_\_init\_\_.py](/packages/ingestion/src/ingestion/wikicommons/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/wikicommons/download.py](/packages/ingestion/src/ingestion/wikicommons/download.py) | Python | 503 | 49 | 65 | 617 |
| [packages/ingestion/src/ingestion/wikidata/\_\_init\_\_.py](/packages/ingestion/src/ingestion/wikidata/__init__.py) | Python | 10 | 23 | 3 | 36 |
| [packages/ingestion/src/ingestion/wikidata/download.py](/packages/ingestion/src/ingestion/wikidata/download.py) | Python | 297 | 206 | 40 | 543 |
| [packages/ingestion/src/ingestion/wikidata/enrichment.py](/packages/ingestion/src/ingestion/wikidata/enrichment.py) | Python | 81 | 138 | 19 | 238 |
| [packages/ingestion/src/ingestion/wikimedia/\_\_init\_\_.py](/packages/ingestion/src/ingestion/wikimedia/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/wikimedia/download.py](/packages/ingestion/src/ingestion/wikimedia/download.py) | Python | 421 | 52 | 68 | 541 |
| [packages/ingestion/src/ingestion/youtube/\_\_init\_\_.py](/packages/ingestion/src/ingestion/youtube/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [packages/ingestion/src/ingestion/youtube/events.py](/packages/ingestion/src/ingestion/youtube/events.py) | Python | 299 | 192 | 55 | 546 |
| [packages/ingestion/tests/test\_arcgis\_addresses\_pipeline.py](/packages/ingestion/tests/test_arcgis_addresses_pipeline.py) | Python | 159 | 4 | 39 | 202 |
| [packages/ingestion/tests/test\_ballotpedia\_measures\_pipeline.py](/packages/ingestion/tests/test_ballotpedia_measures_pipeline.py) | Python | 162 | 16 | 37 | 215 |
| [packages/ingestion/tests/test\_bls\_cpi\_pipeline.py](/packages/ingestion/tests/test_bls_cpi_pipeline.py) | Python | 211 | 34 | 47 | 292 |
| [packages/ingestion/tests/test\_census\_acs\_pipeline.py](/packages/ingestion/tests/test_census_acs_pipeline.py) | Python | 130 | 6 | 34 | 170 |
| [packages/ingestion/tests/test\_census\_counties\_jurisdictions\_pipeline.py](/packages/ingestion/tests/test_census_counties_jurisdictions_pipeline.py) | Python | 112 | 4 | 33 | 149 |
| [packages/ingestion/tests/test\_census\_counties\_pipeline.py](/packages/ingestion/tests/test_census_counties_pipeline.py) | Python | 131 | 5 | 36 | 172 |
| [packages/ingestion/tests/test\_census\_county\_mappings\_pipeline.py](/packages/ingestion/tests/test_census_county_mappings_pipeline.py) | Python | 136 | 9 | 32 | 177 |
| [packages/ingestion/tests/test\_census\_details\_pipeline.py](/packages/ingestion/tests/test_census_details_pipeline.py) | Python | 157 | 7 | 38 | 202 |
| [packages/ingestion/tests/test\_census\_gazetteer\_pipeline.py](/packages/ingestion/tests/test_census_gazetteer_pipeline.py) | Python | 134 | 3 | 37 | 174 |
| [packages/ingestion/tests/test\_census\_govsstatefin\_variables\_pipeline.py](/packages/ingestion/tests/test_census_govsstatefin_variables_pipeline.py) | Python | 202 | 23 | 53 | 278 |
| [packages/ingestion/tests/test\_census\_municipalities\_pipeline.py](/packages/ingestion/tests/test_census_municipalities_pipeline.py) | Python | 142 | 8 | 39 | 189 |
| [packages/ingestion/tests/test\_census\_place\_crosswalks\_pipeline.py](/packages/ingestion/tests/test_census_place_crosswalks_pipeline.py) | Python | 114 | 9 | 33 | 156 |
| [packages/ingestion/tests/test\_census\_postal\_codes\_pipeline.py](/packages/ingestion/tests/test_census_postal_codes_pipeline.py) | Python | 128 | 4 | 37 | 169 |
| [packages/ingestion/tests/test\_census\_relationships\_pipeline.py](/packages/ingestion/tests/test_census_relationships_pipeline.py) | Python | 132 | 2 | 36 | 170 |
| [packages/ingestion/tests/test\_census\_shapefiles\_pipeline.py](/packages/ingestion/tests/test_census_shapefiles_pipeline.py) | Python | 142 | 3 | 36 | 181 |
| [packages/ingestion/tests/test\_census\_states\_pipeline.py](/packages/ingestion/tests/test_census_states_pipeline.py) | Python | 56 | 2 | 18 | 76 |
| [packages/ingestion/tests/test\_dot\_download.py](/packages/ingestion/tests/test_dot_download.py) | Python | 70 | 9 | 20 | 99 |
| [packages/ingestion/tests/test\_dot\_events\_pipeline.py](/packages/ingestion/tests/test_dot_events_pipeline.py) | Python | 114 | 7 | 37 | 158 |
| [packages/ingestion/tests/test\_everyorg\_causes\_pipeline.py](/packages/ingestion/tests/test_everyorg_causes_pipeline.py) | Python | 199 | 8 | 55 | 262 |
| [packages/ingestion/tests/test\_fec\_bulk\_pipeline.py](/packages/ingestion/tests/test_fec_bulk_pipeline.py) | Python | 145 | 8 | 35 | 188 |
| [packages/ingestion/tests/test\_fec\_contributions\_pipeline.py](/packages/ingestion/tests/test_fec_contributions_pipeline.py) | Python | 125 | 7 | 33 | 165 |
| [packages/ingestion/tests/test\_google\_civic\_ocd\_pipeline.py](/packages/ingestion/tests/test_google_civic_ocd_pipeline.py) | Python | 150 | 16 | 38 | 204 |
| [packages/ingestion/tests/test\_google\_civic\_officials\_pipeline.py](/packages/ingestion/tests/test_google_civic_officials_pipeline.py) | Python | 180 | 10 | 35 | 225 |
| [packages/ingestion/tests/test\_gsa\_domains\_pipeline.py](/packages/ingestion/tests/test_gsa_domains_pipeline.py) | Python | 101 | 3 | 30 | 134 |
| [packages/ingestion/tests/test\_gsa\_download.py](/packages/ingestion/tests/test_gsa_download.py) | Python | 47 | 3 | 14 | 64 |
| [packages/ingestion/tests/test\_hifld\_download.py](/packages/ingestion/tests/test_hifld_download.py) | Python | 86 | 8 | 30 | 124 |
| [packages/ingestion/tests/test\_hifld\_locations\_pipeline.py](/packages/ingestion/tests/test_hifld_locations_pipeline.py) | Python | 92 | 14 | 28 | 134 |
| [packages/ingestion/tests/test\_hud\_zip\_county\_pipeline.py](/packages/ingestion/tests/test_hud_zip_county_pipeline.py) | Python | 127 | 2 | 32 | 161 |
| [packages/ingestion/tests/test\_irs\_bmf\_pipeline.py](/packages/ingestion/tests/test_irs_bmf_pipeline.py) | Python | 144 | 3 | 31 | 178 |
| [packages/ingestion/tests/test\_leagueofcities\_directories\_pipeline.py](/packages/ingestion/tests/test_leagueofcities_directories_pipeline.py) | Python | 167 | 12 | 47 | 226 |
| [packages/ingestion/tests/test\_localview\_events\_pipeline.py](/packages/ingestion/tests/test_localview_events_pipeline.py) | Python | 153 | 7 | 35 | 195 |
| [packages/ingestion/tests/test\_naco\_counties\_pipeline.py](/packages/ingestion/tests/test_naco_counties_pipeline.py) | Python | 150 | 14 | 33 | 197 |
| [packages/ingestion/tests/test\_nccs\_bulk\_pipeline.py](/packages/ingestion/tests/test_nccs_bulk_pipeline.py) | Python | 136 | 4 | 35 | 175 |
| [packages/ingestion/tests/test\_nccs\_download.py](/packages/ingestion/tests/test_nccs_download.py) | Python | 57 | 10 | 26 | 93 |
| [packages/ingestion/tests/test\_nces\_school\_districts\_pipeline.py](/packages/ingestion/tests/test_nces_school_districts_pipeline.py) | Python | 166 | 6 | 44 | 216 |
| [packages/ingestion/tests/test\_ncls\_ballot\_measures\_pipeline.py](/packages/ingestion/tests/test_ncls_ballot_measures_pipeline.py) | Python | 91 | 20 | 34 | 145 |
| [packages/ingestion/tests/test\_ntee\_codes\_pipeline.py](/packages/ingestion/tests/test_ntee_codes_pipeline.py) | Python | 191 | 10 | 58 | 259 |
| [packages/ingestion/tests/test\_openstates\_download.py](/packages/ingestion/tests/test_openstates_download.py) | Python | 51 | 3 | 13 | 67 |
| [packages/ingestion/tests/test\_openstates\_people\_pipeline.py](/packages/ingestion/tests/test_openstates_people_pipeline.py) | Python | 148 | 1 | 41 | 190 |
| [packages/ingestion/tests/test\_osf\_download.py](/packages/ingestion/tests/test_osf_download.py) | Python | 91 | 16 | 32 | 139 |
| [packages/ingestion/tests/test\_osf\_files\_pipeline.py](/packages/ingestion/tests/test_osf_files_pipeline.py) | Python | 123 | 5 | 38 | 166 |
| [packages/ingestion/tests/test\_osf\_rds\_pipeline.py](/packages/ingestion/tests/test_osf_rds_pipeline.py) | Python | 141 | 16 | 44 | 201 |
| [packages/ingestion/tests/test\_tpc\_finance\_pipeline.py](/packages/ingestion/tests/test_tpc_finance_pipeline.py) | Python | 226 | 44 | 50 | 320 |
| [packages/ingestion/tests/test\_uscm\_mayors\_pipeline.py](/packages/ingestion/tests/test_uscm_mayors_pipeline.py) | Python | 104 | 3 | 28 | 135 |
| [packages/ingestion/tests/test\_wikicommons\_download.py](/packages/ingestion/tests/test_wikicommons_download.py) | Python | 95 | 10 | 17 | 122 |
| [packages/ingestion/tests/test\_wikidata\_enrichment\_pipeline.py](/packages/ingestion/tests/test_wikidata_enrichment_pipeline.py) | Python | 90 | 2 | 26 | 118 |
| [packages/ingestion/tests/test\_wikimedia\_download.py](/packages/ingestion/tests/test_wikimedia_download.py) | Python | 76 | 7 | 15 | 98 |
| [packages/ingestion/tests/test\_youtube\_events\_pipeline.py](/packages/ingestion/tests/test_youtube_events_pipeline.py) | Python | 165 | 14 | 53 | 232 |
| [requirements.txt](/requirements.txt) | pip requirements | -25 | 27 | 0 | 2 |
| [scripts/accessibility/README.md](/scripts/accessibility/README.md) | Markdown | -193 | 0 | -70 | -263 |
| [scripts/accessibility/\_\_init\_\_.py](/scripts/accessibility/__init__.py) | Python | 0 | -1 | -1 | -2 |
| [scripts/accessibility/\_int\_websites.py](/scripts/accessibility/_int_websites.py) | Python | -11 | -2 | -6 | -19 |
| [scripts/accessibility/docker\_entrypoint.py](/scripts/accessibility/docker_entrypoint.py) | Python | -54 | -2 | -12 | -68 |
| [scripts/accessibility/export\_pdf\_urls.py](/scripts/accessibility/export_pdf_urls.py) | Python | -182 | -11 | -25 | -218 |
| [scripts/accessibility/export\_urls.py](/scripts/accessibility/export_urls.py) | Python | -86 | -99 | -14 | -199 |
| [scripts/accessibility/lambda\_handler.py](/scripts/accessibility/lambda_handler.py) | Python | -134 | -20 | -12 | -166 |
| [scripts/accessibility/pa11yci.config.cjs](/scripts/accessibility/pa11yci.config.cjs) | JavaScript | -21 | -4 | -2 | -27 |
| [scripts/accessibility/package-lock.json](/scripts/accessibility/package-lock.json) | JSON | -3,853 | 0 | -1 | -3,854 |
| [scripts/accessibility/package.json](/scripts/accessibility/package.json) | JSON | -21 | 0 | -1 | -22 |
| [scripts/accessibility/persist\_lighthouse\_results.py](/scripts/accessibility/persist_lighthouse_results.py) | Python | -100 | -160 | -6 | -266 |
| [scripts/accessibility/persist\_results.py](/scripts/accessibility/persist_results.py) | Python | -254 | -47 | -31 | -332 |
| [scripts/accessibility/persist\_verapdf\_results.py](/scripts/accessibility/persist_verapdf_results.py) | Python | -49 | -118 | -6 | -173 |
| [scripts/accessibility/run\_accessibility\_scan.sh](/scripts/accessibility/run_accessibility_scan.sh) | Shell Script | -103 | -8 | -12 | -123 |
| [scripts/accessibility/run\_axe\_scan.mjs](/scripts/accessibility/run_axe_scan.mjs) | JavaScript | -150 | -8 | -17 | -175 |
| [scripts/accessibility/run\_lighthouse\_scan.mjs](/scripts/accessibility/run_lighthouse_scan.mjs) | JavaScript | -209 | -19 | -27 | -255 |
| [scripts/accessibility/run\_pa11y\_workers.mjs](/scripts/accessibility/run_pa11y_workers.mjs) | JavaScript | -173 | -15 | -21 | -209 |
| [scripts/accessibility/run\_verapdf\_scan.py](/scripts/accessibility/run_verapdf_scan.py) | Python | -172 | -12 | -30 | -214 |
| [scripts/accessibility/run\_verapdf\_scan.sh](/scripts/accessibility/run_verapdf_scan.sh) | Shell Script | -55 | -7 | -10 | -72 |
| [scripts/accessibility/sql/bronze\_jurisdiction\_pdf\_verapdf.sql](/scripts/accessibility/sql/bronze_jurisdiction_pdf_verapdf.sql) | MS SQL | -32 | -2 | -7 | -41 |
| [scripts/accessibility/sql/bronze\_jurisdiction\_website\_accessibility.sql](/scripts/accessibility/sql/bronze_jurisdiction_website_accessibility.sql) | MS SQL | -31 | -3 | -7 | -41 |
| [scripts/accessibility/sql/bronze\_jurisdiction\_website\_lighthouse.sql](/scripts/accessibility/sql/bronze_jurisdiction_website_lighthouse.sql) | MS SQL | -66 | -4 | -8 | -78 |
| [scripts/accessibility/verapdf\_cli.py](/scripts/accessibility/verapdf_cli.py) | Python | -154 | -4 | -24 | -182 |
| [scripts/datasources/ballotpedia/load\_ballotpedia\_measures\_to\_bronze.py](/scripts/datasources/ballotpedia/load_ballotpedia_measures_to_bronze.py) | Python | -356 | -68 | -53 | -477 |
| [scripts/datasources/bls/\_\_init\_\_.py](/scripts/datasources/bls/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/bls/load\_bls\_cpi.py](/scripts/datasources/bls/load_bls_cpi.py) | Python | 4 | 16 | 3 | 23 |
| [scripts/datasources/cdp/example\_fetch.py](/scripts/datasources/cdp/example_fetch.py) | Python | -56 | -21 | -15 | -92 |
| [scripts/datasources/census/download\_census\_finance\_variables.py](/scripts/datasources/census/download_census_finance_variables.py) | Python | 4 | 19 | 3 | 26 |
| [scripts/datasources/census/export\_census\_map\_static.py](/scripts/datasources/census/export_census_map_static.py) | Python | 8 | 5 | 1 | 14 |
| [scripts/datasources/census/export\_zcta\_metrics.py](/scripts/datasources/census/export_zcta_metrics.py) | Python | 238 | 90 | 44 | 372 |
| [scripts/datasources/census/fix\_geoid\_format.py](/scripts/datasources/census/fix_geoid_format.py) | Python | -45 | -63 | -8 | -116 |
| [scripts/datasources/census/load\_acs.py](/scripts/datasources/census/load_acs.py) | Python | -259 | -145 | -82 | -486 |
| [scripts/datasources/census/load\_census\_counties.py](/scripts/datasources/census/load_census_counties.py) | Python | -183 | -69 | -52 | -304 |
| [scripts/datasources/census/load\_census\_gazetteer.py](/scripts/datasources/census/load_census_gazetteer.py) | Python | -418 | -77 | -40 | -535 |
| [scripts/datasources/census/load\_census\_municipalities.py](/scripts/datasources/census/load_census_municipalities.py) | Python | -151 | -43 | -36 | -230 |
| [scripts/datasources/census/load\_census\_postal\_codes.py](/scripts/datasources/census/load_census_postal_codes.py) | Python | -261 | -70 | -70 | -401 |
| [scripts/datasources/census/load\_census\_relationships.py](/scripts/datasources/census/load_census_relationships.py) | Python | -342 | -64 | -87 | -493 |
| [scripts/datasources/census/load\_census\_shapefiles.py](/scripts/datasources/census/load_census_shapefiles.py) | Python | -258 | -156 | -8 | -422 |
| [scripts/datasources/census/load\_census\_states.py](/scripts/datasources/census/load_census_states.py) | Python | -128 | -19 | -19 | -166 |
| [scripts/datasources/census/load\_county\_mappings.py](/scripts/datasources/census/load_county_mappings.py) | Python | -147 | -64 | -50 | -261 |
| [scripts/datasources/census/load\_place\_crosswalks.py](/scripts/datasources/census/load_place_crosswalks.py) | Python | -312 | -186 | -59 | -557 |
| [scripts/datasources/dot/download\_state\_dot\_public\_pages.py](/scripts/datasources/dot/download_state_dot_public_pages.py) | Python | -273 | -29 | -36 | -338 |
| [scripts/datasources/dot/load\_dot\_unified\_events\_to\_postgres.py](/scripts/datasources/dot/load_dot_unified_events_to_postgres.py) | Python | -121 | -12 | -19 | -152 |
| [scripts/datasources/fec/demo\_fec\_integration.py](/scripts/datasources/fec/demo_fec_integration.py) | Python | -180 | -54 | -55 | -289 |
| [scripts/datasources/fec/demo\_political\_influence.py](/scripts/datasources/fec/demo_political_influence.py) | Python | -260 | -32 | -60 | -352 |
| [scripts/datasources/fec/load\_fec\_bulk.py](/scripts/datasources/fec/load_fec_bulk.py) | Python | -304 | -141 | -72 | -517 |
| [scripts/datasources/fec/load\_fec\_individual\_contributions\_by\_date\_to\_bronze.py](/scripts/datasources/fec/load_fec_individual_contributions_by_date_to_bronze.py) | Python | -177 | -298 | -22 | -497 |
| [scripts/datasources/gemini/migrations/README.md](/scripts/datasources/gemini/migrations/README.md) | Markdown | -65 | 0 | -28 | -93 |
| [scripts/datasources/gemini/migrations/backfill\_ntee\_from\_arguments.py](/scripts/datasources/gemini/migrations/backfill_ntee_from_arguments.py) | Python | -139 | -16 | -23 | -178 |
| [scripts/datasources/gemini/migrations/backfill\_ntee\_to\_topics.py](/scripts/datasources/gemini/migrations/backfill_ntee_to_topics.py) | Python | -108 | -15 | -20 | -143 |
| [scripts/datasources/gemini/migrations/cleanup\_null\_records.py](/scripts/datasources/gemini/migrations/cleanup_null_records.py) | Python | -88 | -20 | -35 | -143 |
| [scripts/datasources/gemini/migrations/infer\_ntee\_from\_topics.py](/scripts/datasources/gemini/migrations/infer_ntee_from_topics.py) | Python | -144 | -16 | -30 | -190 |
| [scripts/datasources/gemini/migrations/migrate\_add\_ntee\_to\_topics.py](/scripts/datasources/gemini/migrations/migrate_add_ntee_to_topics.py) | Python | -109 | -17 | -22 | -148 |
| [scripts/datasources/gemini/migrations/migrate\_add\_secondary\_ntee.py](/scripts/datasources/gemini/migrations/migrate_add_secondary_ntee.py) | Python | -102 | -8 | -20 | -130 |
| [scripts/datasources/gemini/migrations/migrate\_multimodel\_support.py](/scripts/datasources/gemini/migrations/migrate_multimodel_support.py) | Python | -154 | -158 | -31 | -343 |
| [scripts/datasources/gemini/migrations/repopulate\_ntee\_codes.py](/scripts/datasources/gemini/migrations/repopulate_ntee_codes.py) | Python | -293 | -40 | -53 | -386 |
| [scripts/datasources/google\_civic/load\_google\_civic\_officials\_to\_c1.py](/scripts/datasources/google_civic/load_google_civic_officials_to_c1.py) | Python | -1,000 | -77 | -71 | -1,148 |
| [scripts/datasources/google\_civic/prune\_legacy\_flat\_source\_cache.py](/scripts/datasources/google_civic/prune_legacy_flat_source_cache.py) | Python | -20 | -2 | -9 | -31 |
| [scripts/datasources/grants\_gov/demo\_grants\_gov.py](/scripts/datasources/grants_gov/demo_grants_gov.py) | Python | -204 | -35 | -52 | -291 |
| [scripts/datasources/gsa/download\_gsa\_domains.py](/scripts/datasources/gsa/download_gsa_domains.py) | Python | -123 | -14 | -31 | -168 |
| [scripts/datasources/gsa/load\_gsa\_domains\_to\_postgres.py](/scripts/datasources/gsa/load_gsa_domains_to_postgres.py) | Python | -180 | -17 | -42 | -239 |
| [scripts/datasources/hifld/download\_hifld.py](/scripts/datasources/hifld/download_hifld.py) | Python | -86 | -11 | -25 | -122 |
| [scripts/datasources/hifld/load\_hifld\_to\_postgres.py](/scripts/datasources/hifld/load_hifld_to_postgres.py) | Python | -265 | -81 | -64 | -410 |
| [scripts/datasources/hud/load\_zip\_county.py](/scripts/datasources/hud/load_zip_county.py) | Python | -151 | -22 | -40 | -213 |
| [scripts/datasources/irs/load\_irs\_bmf.py](/scripts/datasources/irs/load_irs_bmf.py) | Python | -339 | -142 | -88 | -569 |
| [scripts/datasources/jurisdiction\_pilot/load\_ocd\_into\_postgres.py](/scripts/datasources/jurisdiction_pilot/load_ocd_into_postgres.py) | Python | -136 | -31 | -33 | -200 |
| [scripts/datasources/jurisdictions/load\_counties\_to\_postgres.py](/scripts/datasources/jurisdictions/load_counties_to_postgres.py) | Python | -160 | -26 | -35 | -221 |
| [scripts/datasources/jurisdictions/load\_details\_to\_postgres.py](/scripts/datasources/jurisdictions/load_details_to_postgres.py) | Python | -177 | -10 | -19 | -206 |
| [scripts/datasources/jurisdictions/migrate\_parquet\_state\_naming.py](/scripts/datasources/jurisdictions/migrate_parquet_state_naming.py) | Python | -60 | -22 | -17 | -99 |
| [scripts/datasources/jurisdictions/youtube\_channel\_diagnostics.py](/scripts/datasources/jurisdictions/youtube_channel_diagnostics.py) | Python | 14 | 6 | 0 | 20 |
| [scripts/datasources/leagueofcities/load\_league\_city\_directories\_to\_bronze.py](/scripts/datasources/leagueofcities/load_league_city_directories_to_bronze.py) | Python | -405 | -465 | -41 | -911 |
| [scripts/datasources/localview/README\_workflow.md](/scripts/datasources/localview/README_workflow.md) | Markdown | 121 | 0 | 52 | 173 |
| [scripts/datasources/localview/check\_meeting\_data.py](/scripts/datasources/localview/check_meeting_data.py) | Python | 205 | 24 | 60 | 289 |
| [scripts/datasources/localview/extract\_transcripts.py](/scripts/datasources/localview/extract_transcripts.py) | Python | 144 | 47 | 45 | 236 |
| [scripts/datasources/localview/load\_localview\_to\_postgres.py](/scripts/datasources/localview/load_localview_to_postgres.py) | Python | -381 | -20 | -50 | -451 |
| [scripts/datasources/localview/load\_priority\_states.sh](/scripts/datasources/localview/load_priority_states.sh) | Shell Script | 133 | 16 | 26 | 175 |
| [scripts/datasources/localview/scrape\_youtube\_channels.py](/scripts/datasources/localview/scrape_youtube_channels.py) | Python | 582 | 105 | 108 | 795 |
| [scripts/datasources/localview/update\_all.sh](/scripts/datasources/localview/update_all.sh) | Shell Script | 39 | 9 | 11 | 59 |
| [scripts/datasources/localview/update\_municipality\_list.py](/scripts/datasources/localview/update_municipality_list.py) | Python | 202 | 45 | 52 | 299 |
| [scripts/datasources/master\_data/create\_jurisdiction\_master.py](/scripts/datasources/master_data/create_jurisdiction_master.py) | Python | -1,005 | -182 | -144 | -1,331 |
| [scripts/datasources/naco/load\_naco\_to\_bronze.py](/scripts/datasources/naco/load_naco_to_bronze.py) | Python | -347 | -64 | -64 | -475 |
| [scripts/datasources/nccs/README.md](/scripts/datasources/nccs/README.md) | Markdown | -165 | 0 | -53 | -218 |
| [scripts/datasources/nccs/download\_nccs\_bulk.py](/scripts/datasources/nccs/download_nccs_bulk.py) | Python | -332 | -39 | -75 | -446 |
| [scripts/datasources/nccs/load\_nccs\_bulk.py](/scripts/datasources/nccs/load_nccs_bulk.py) | Python | -336 | -36 | -46 | -418 |
| [scripts/datasources/nces/fix\_and\_enrich\_school\_districts.py](/scripts/datasources/nces/fix_and_enrich_school_districts.py) | Python | -144 | -166 | -22 | -332 |
| [scripts/datasources/nces/load\_nces\_school\_districts\_to\_bronze.py](/scripts/datasources/nces/load_nces_school_districts_to_bronze.py) | Python | -393 | -108 | -15 | -516 |
| [scripts/datasources/nces/migrate\_schools\_to\_orgloc.py](/scripts/datasources/nces/migrate_schools_to_orgloc.py) | Python | -123 | -18 | -28 | -169 |
| [scripts/datasources/ntee/README.md](/scripts/datasources/ntee/README.md) | Markdown | -163 | 0 | -49 | -212 |
| [scripts/datasources/ntee/\_\_init\_\_.py](/scripts/datasources/ntee/__init__.py) | Python | 0 | -10 | -1 | -11 |
| [scripts/datasources/ntee/load\_to\_postgres.py](/scripts/datasources/ntee/load_to_postgres.py) | Python | -183 | -49 | -57 | -289 |
| [scripts/datasources/openstates/load\_openstates\_bulk.py](/scripts/datasources/openstates/load_openstates_bulk.py) | Python | -293 | -153 | -82 | -528 |
| [scripts/datasources/openstates/load\_openstates\_people.py](/scripts/datasources/openstates/load_openstates_people.py) | Python | -205 | -73 | -47 | -325 |
| [scripts/datasources/osf/download\_osf\_zip.py](/scripts/datasources/osf/download_osf_zip.py) | Python | -307 | -48 | -82 | -437 |
| [scripts/datasources/osf/load\_osf\_rds\_to\_bronze.py](/scripts/datasources/osf/load_osf_rds_to_bronze.py) | Python | -152 | -20 | -38 | -210 |
| [scripts/datasources/osf/load\_osf\_to\_bronze.py](/scripts/datasources/osf/load_osf_to_bronze.py) | Python | -133 | -25 | -38 | -196 |
| [scripts/datasources/parcels/load\_parcel\_addresses\_to\_bronze.py](/scripts/datasources/parcels/load_parcel_addresses_to_bronze.py) | Python | -87 | -241 | -8 | -336 |
| [scripts/datasources/powerbi\_ballot\_measures/load\_powerbi\_ballot\_measures\_to\_bronze.py](/scripts/datasources/powerbi_ballot_measures/load_powerbi_ballot_measures_to_bronze.py) | Python | -358 | -157 | -52 | -567 |
| [scripts/datasources/tpc/\_\_init\_\_.py](/scripts/datasources/tpc/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [scripts/datasources/tpc/load\_tpc\_finance.py](/scripts/datasources/tpc/load_tpc_finance.py) | Python | 4 | 19 | 3 | 26 |
| [scripts/datasources/uscm/load\_uscm\_mayors\_to\_bronze.py](/scripts/datasources/uscm/load_uscm_mayors_to_bronze.py) | Python | -218 | -59 | -17 | -294 |
| [scripts/datasources/wikidata/README.md](/scripts/datasources/wikidata/README.md) | Markdown | 36 | 0 | 1 | 37 |
| [scripts/datasources/wikidata/cleanup\_bad\_counties.py](/scripts/datasources/wikidata/cleanup_bad_counties.py) | Python | -111 | -21 | -18 | -150 |
| [scripts/datasources/wikidata/fix\_fips\_codes.py](/scripts/datasources/wikidata/fix_fips_codes.py) | Python | -111 | -21 | -25 | -157 |
| [scripts/datasources/wikidata/load\_jurisdictions\_wikidata.py](/scripts/datasources/wikidata/load_jurisdictions_wikidata.py) | Python | -2,435 | -1,486 | -145 | -4,066 |
| [scripts/datasources/youtube/download\_tuscaloosa\_city\_meeting\_audio.py](/scripts/datasources/youtube/download_tuscaloosa_city_meeting_audio.py) | Python | -3 | 0 | -1 | -4 |
| [scripts/datasources/youtube/load\_youtube\_events\_to\_postgres.py](/scripts/datasources/youtube/load_youtube_events_to_postgres.py) | Python | -1 | 21 | 0 | 20 |
| [scripts/datasources/youtube/run\_load\_youtube\_events\_terminal.sh](/scripts/datasources/youtube/run_load_youtube_events_terminal.sh) | Shell Script | 7 | 8 | 1 | 16 |
| [scripts/datasources/youtube/sync\_bronze\_youtube\_from\_localview.py](/scripts/datasources/youtube/sync_bronze_youtube_from_localview.py) | Python | 0 | 9 | 0 | 9 |
| [scripts/dbt/README.md](/scripts/dbt/README.md) | Markdown | -265 | 0 | -83 | -348 |
| [scripts/dbt/export\_stats\_to\_open\_navigator.py](/scripts/dbt/export_stats_to_open_navigator.py) | Python | -108 | -21 | -29 | -158 |
| [scripts/dbt/rebuild\_stats\_aggregates\_fixed.py](/scripts/dbt/rebuild_stats_aggregates_fixed.py) | Python | -201 | -12 | -22 | -235 |
| [scripts/dbt/rebuild\_stats\_fixed.py](/scripts/dbt/rebuild_stats_fixed.py) | Python | -214 | -12 | -24 | -250 |
| [scripts/deployment/neon/migrations/076\_widen\_bronze\_youtube\_video\_id.sql](/scripts/deployment/neon/migrations/076_widen_bronze_youtube_video_id.sql) | MS SQL | 48 | 20 | 8 | 76 |
| [scripts/deployment/neon/migrations/077\_create\_bronze\_bls\_cpi.sql](/scripts/deployment/neon/migrations/077_create_bronze_bls_cpi.sql) | MS SQL | 18 | 20 | 7 | 45 |
| [scripts/deployment/neon/migrations/078\_create\_bronze\_tpc\_government\_finance.sql](/scripts/deployment/neon/migrations/078_create_bronze_tpc_government_finance.sql) | MS SQL | 26 | 36 | 9 | 71 |
| [scripts/deployment/neon/migrations/079\_create\_bronze\_census\_finance\_variables.sql](/scripts/deployment/neon/migrations/079_create_bronze_census_finance_variables.sql) | MS SQL | 28 | 27 | 8 | 63 |
| [scripts/deployment/neon/migrations/080\_rename\_bronze\_tpc\_government\_finance.sql](/scripts/deployment/neon/migrations/080_rename_bronze_tpc_government_finance.sql) | MS SQL | 19 | 17 | 5 | 41 |
| [scripts/deployment/neon/migrations/081\_alter\_bronze\_bls\_cpi\_year\_varchar.sql](/scripts/deployment/neon/migrations/081_alter_bronze_bls_cpi_year_varchar.sql) | MS SQL | 15 | 15 | 4 | 34 |
| [scripts/frontend/export\_openapi.py](/scripts/frontend/export_openapi.py) | Python | 31 | 15 | 11 | 57 |
| [scripts/frontend/prep\_zcta\_tiles.sh](/scripts/frontend/prep_zcta_tiles.sh) | Shell Script | 59 | 35 | 10 | 104 |
| [scripts/localview/README.md](/scripts/localview/README.md) | Markdown | -121 | 0 | -52 | -173 |
| [scripts/localview/check\_meeting\_data.py](/scripts/localview/check_meeting_data.py) | Python | -205 | -24 | -60 | -289 |
| [scripts/localview/extract\_transcripts.py](/scripts/localview/extract_transcripts.py) | Python | -144 | -47 | -45 | -236 |
| [scripts/localview/load\_priority\_states.sh](/scripts/localview/load_priority_states.sh) | Shell Script | -133 | -16 | -26 | -175 |
| [scripts/localview/scrape\_youtube\_channels.py](/scripts/localview/scrape_youtube_channels.py) | Python | -582 | -105 | -108 | -795 |
| [scripts/localview/update\_all.sh](/scripts/localview/update_all.sh) | Shell Script | -39 | -9 | -11 | -59 |
| [scripts/localview/update\_municipality\_list.py](/scripts/localview/update_municipality_list.py) | Python | -202 | -45 | -52 | -299 |
| [scripts/wikicommons/README.md](/scripts/wikicommons/README.md) | Markdown | 2 | 0 | 0 | 2 |
| [scripts/wikicommons/download\_wikicommons\_assets.py](/scripts/wikicommons/download_wikicommons_assets.py) | Python | -490 | -24 | -55 | -569 |
| [scripts/wikicommons/download\_wikicommons\_assets.sh](/scripts/wikicommons/download_wikicommons_assets.sh) | Shell Script | 0 | 1 | 0 | 1 |
| [scripts/wikimedia/download\_state\_silhouettes.py](/scripts/wikimedia/download_state_silhouettes.py) | Python | -409 | -23 | -54 | -486 |
| [tests/test\_core\_lib\_db\_session.py](/tests/test_core_lib_db_session.py) | Python | 53 | 1 | 21 | 75 |
| [tests/test\_core\_lib\_http\_client.py](/tests/test_core_lib_http_client.py) | Python | 64 | 1 | 26 | 91 |
| [tests/test\_core\_lib\_pipeline.py](/tests/test_core_lib_pipeline.py) | Python | 83 | 4 | 28 | 115 |
| [uv.lock](/uv.lock) | toml | 3,474 | 0 | 137 | 3,611 |
| [website/docs/data-sources/\_TEMPLATE.md](/website/docs/data-sources/_TEMPLATE.md) | Markdown | 62 | 0 | 23 | 85 |
| [website/docs/data-sources/charity-navigator.md](/website/docs/data-sources/charity-navigator.md) | Markdown | 14 | 0 | 1 | 15 |
| [website/docusaurus.config.ts](/website/docusaurus.config.ts) | TypeScript | 12 | 0 | 0 | 12 |
| [website/sidebars.ts](/website/sidebars.ts) | TypeScript | 122 | 15 | 2 | 139 |

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details