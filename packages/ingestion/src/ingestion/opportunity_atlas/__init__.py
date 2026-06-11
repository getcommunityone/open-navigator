"""Opportunity Atlas commuting-zone intergenerational-mobility ingestion.

Ingests the Opportunity Insights "Opportunity Atlas" commuting-zone (CZ) outcomes
file (Chetty, Hendren, Jones & Porter 2018, "Race and Economic Opportunity in the
United States") and lands the mobility measures we serve into
``bronze.bronze_opportunity_atlas_cz`` (long/tidy: one row per
cz x race x gender x parent_income_level).

The source CSV is ~58 MB / 741 CZ rows x ~10,825 columns; we read only the ~84
columns we need (63 ``kfr_<race>_<gender>_p<plevel>`` value columns + 21
``kfr_<race>_<gender>_n`` sample-count columns + ``cz`` + ``czname``) by streaming
with the stdlib ``csv`` module and selecting by column index — we never load the
full wide frame.

Modules:
  * ``download`` — stream the CSV to a local cache file (not committed).
  * ``load``     — parse + reshape long + UPSERT into bronze. Runnable as
                   ``python -m ingestion.opportunity_atlas.load``.
"""
