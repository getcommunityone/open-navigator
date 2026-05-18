"""Tests for notebook cell visibility helpers."""

from __future__ import annotations

from scripts.colab.colab_notebook_ui import infer_cell_label, parse_cell_label


def test_parse_cell_label_first_line() -> None:
    src = "# @cell §4 API keys\nimport os\n"
    assert parse_cell_label(src) == "§4 API keys"


def test_parse_cell_label_after_comment() -> None:
    src = "# §1 Bootstrap\n# @cell §1 Bootstrap\nx = 1\n"
    assert parse_cell_label(src) == "§1 Bootstrap"


def test_parse_cell_label_missing() -> None:
    assert parse_cell_label("import os\n") is None


def test_infer_cell_label_from_section_comment() -> None:
    src = "# §1 Bootstrap — repo\nimport os\n"
    assert infer_cell_label(src, run_index=1) == "§1 Bootstrap — repo"


def test_infer_cell_label_fallback_index() -> None:
    assert infer_cell_label("x = 1\n", run_index=3) == "code cell #3"
