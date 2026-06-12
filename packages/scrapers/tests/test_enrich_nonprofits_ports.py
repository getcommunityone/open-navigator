"""Smoke tests for the nonprofit-enrichment modules ported from scripts/.

These modules were moved out of ``scripts/enrichment/`` into the scrapers
package (``scrapers.irs``). The heavy/optional deps (boto3, google-cloud-bigquery,
xmltodict) are imported lazily inside the methods that use them, so the modules
must stay importable without those extras installed.
"""


def test_gt990_module_imports_without_boto3():
    import scrapers.irs.enrich_nonprofits_gt990 as gt990

    assert hasattr(gt990, "main")
    assert hasattr(gt990, "GivingTuesday990Enricher")


def test_bigquery_module_imports_without_gcloud():
    import scrapers.irs.enrich_nonprofits_bigquery as bq

    assert hasattr(bq, "main")
    assert hasattr(bq, "BigQueryNonprofitEnricher")


def test_gt990_lazy_imports_are_not_top_level():
    """boto3/xmltodict must not be imported at module top level."""
    import inspect

    import scrapers.irs.enrich_nonprofits_gt990 as gt990

    src = inspect.getsource(gt990)
    head = "\n".join(src.splitlines()[:60])
    assert "\nimport boto3" not in head
    assert "\nimport xmltodict" not in head
