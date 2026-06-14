"""LocalBench ingestion — county-level LLM benchmark QA pairs.

LocalBench (MadCollab/LocalBench) is a third-party benchmark of 14,782 QA pairs
for evaluating LLMs on U.S. county-level local knowledge and reasoning. It ships
three released data files, each with its own raw layout but a shared *logical*
schema (see the repo's ``data/README.md``):

    census_QA.csv      6,120  U.S. Census + USDA + NRHP + IMLS (numeric / True-False)
    reddit_QA.parquet  4,000  Local subreddits (Jan 2024 – Mar 2025), top-50 comments
    news_QA.parquet    4,662  NELA-Local (Horne et al., 2022) county-tagged articles

``download`` fetches the three files into a local cache; ``bronze`` lands them
verbatim into three ``bronze.bronze_localbench_*`` tables. Unification to the
README's common schema happens downstream in dbt staging.

Source: https://github.com/MadCollab/LocalBench  (see CITATIONS.md)
"""
