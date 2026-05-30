"""Unit tests for the hosting.huggingface library (no network calls)."""

from __future__ import annotations

import pandas as pd
import pytest

from hosting.huggingface import HFConfig, HFConfigError, dataset_name_from_stem
from hosting.huggingface import datasets as ds
from hosting.huggingface import spaces
from hosting.huggingface.publisher import DatasetPublisher, UploadResult, summarize


# -- config ------------------------------------------------------------
def test_config_dataset_repo_id():
    cfg = HFConfig(token="t", organization="Org", dataset_prefix="one")
    assert cfg.dataset_repo_id("bills") == "Org/one-bills"
    assert cfg.dataset_prefix_repo("meetings") == "Org/one-meetings"


def test_require_token_raises_when_missing():
    with pytest.raises(HFConfigError):
        HFConfig(token=None).require_token()


# -- name simplification ----------------------------------------------
@pytest.mark.parametrize(
    "stem,expected",
    [
        ("bills_bills", "bills"),
        ("bills_bill_actions", "bill-actions"),
        ("nonprofits_organizations", "nonprofits-organizations"),
        ("events_documents", "event-documents"),
        ("some_other_table", "some-other-table"),
    ],
)
def test_dataset_name_from_stem(stem, expected):
    assert dataset_name_from_stem(stem) == expected


# -- split name derivation for state splits ---------------------------
def test_split_name_for_strips_state_and_family_prefix():
    assert ds._split_name_for("nonprofits_organizations_AL", "AL") == "organizations"
    assert ds._split_name_for("jurisdictions_directory_TX", "TX") == "directory"


# -- registries are well-formed ---------------------------------------
def test_registries_use_parquet_filenames():
    for table in (ds.MEETING_TABLES, ds.CONTACTS_TABLES, ds.NONPROFIT_TABLES):
        assert all(fname.endswith(".parquet") for fname in table.values())
    assert "AL" in ds.US_STATES and "DC" in ds.US_STATES


# -- summarize ---------------------------------------------------------
def test_summarize_counts_ok_and_failed():
    results = [
        UploadResult(repo_id="a", url="u", records=10),
        UploadResult(repo_id="b", url="u", error="boom"),
    ]
    ok, failed, total = summarize(results)
    assert (ok, failed, total) == (1, 1, 10)


# -- publisher wiring (mock HF, no network) ---------------------------
class _FakeDataset:
    def __init__(self, df):
        self.df = df

    @classmethod
    def from_pandas(cls, df):
        return cls(df)

    def push_to_hub(self, **kwargs):  # noqa: D401 - records the call
        _FakeDataset.last_call = kwargs


def _make_publisher(monkeypatch):
    pub = DatasetPublisher.__new__(DatasetPublisher)
    pub.config = HFConfig(token="t", organization="Org", dataset_prefix="one")
    pub.token = "t"
    pub.api = object()
    monkeypatch.setattr(pub, "ensure_repo", lambda *a, **k: None)
    return pub


def test_publish_dataframe_pushes_with_split(monkeypatch):
    import hosting.huggingface.publisher as pub_mod

    monkeypatch.setitem(__import__("sys").modules, "datasets", type("M", (), {"Dataset": _FakeDataset}))
    pub = _make_publisher(monkeypatch)
    df = pd.DataFrame({"x": [1, 2, 3]})
    result = pub.publish_dataframe(df, "Org/one-bills", split="train")
    assert result.ok
    assert result.records == 3
    assert _FakeDataset.last_call["repo_id"] == "Org/one-bills"
    assert _FakeDataset.last_call["split"] == "train"


def test_publish_parquet_missing_file_returns_error(monkeypatch, tmp_path):
    pub = _make_publisher(monkeypatch)
    result = pub.publish_parquet(tmp_path / "nope.parquet", "Org/one-x")
    assert not result.ok
    assert result.error == "File not found"


# -- spaces dry-run counting ------------------------------------------
def test_space_dry_run_counts_files(tmp_path):
    (tmp_path / "keep.txt").write_text("a")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("b")
    count = spaces.SpaceDeployer._count_uploadable(
        tmp_path, spaces.DEFAULT_IGNORE_PATTERNS
    )
    assert count == 1
