"""#885: vectors from a different encoder are never written next to the stored ones."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "llm" / "policy_questions" / "embed_instances.py"


def _load():
    """The guard alone, without importing the encoder stack (torch, sklearn) the module pulls in."""
    tree = ast.parse(SRC.read_text())
    keep = [n for n in tree.body if getattr(n, "name", "") in ("IncompatibleEmbeddingError", "check_embedding_compatible")]
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *keep], type_ignores=[])
    ns: dict = {}
    exec(compile(ast.fix_missing_locations(module), str(SRC), "exec"), ns)  # noqa: S102 - our own source file
    return ns["check_embedding_compatible"], ns["IncompatibleEmbeddingError"]


check, Incompatible = _load()

MINILM = ("all-MiniLM-L6-v2+transformer", 384)
TFIDF = ("all-MiniLM-L6-v2+tfidf", 256)


def test_an_empty_table_accepts_anything():
    check(*TFIDF, [])
    check(*MINILM, [])


def test_the_same_encoder_and_dimension_is_fine():
    check(*MINILM, [(*MINILM, 3054)])


def test_the_tfidf_fallback_is_refused_next_to_transformer_vectors():
    with pytest.raises(Incompatible) as err:
        check(*TFIDF, [(*MINILM, 3054)])
    text = str(err.value)
    assert "Nothing was written" in text and "3,054" in text and "384" in text and "256" in text
    assert "install torch and transformers" in text


def test_a_different_dimension_of_the_same_model_name_is_refused():
    with pytest.raises(Incompatible):
        check("all-MiniLM-L6-v2+transformer", 768, [(*MINILM, 10)])


def test_a_mixed_table_is_refused_even_when_some_rows_match():
    # The state the owner's table was left in: both kinds present.
    with pytest.raises(Incompatible):
        check(*MINILM, [(*MINILM, 3054), (*TFIDF, 8542)])


def test_a_deliberate_switch_is_allowed_with_the_flag():
    check(*TFIDF, [(*MINILM, 3054)], allow_model_change=True)
    check(*MINILM, [(*MINILM, 3054), (*TFIDF, 8542)], allow_model_change=True)


def test_the_guard_runs_before_the_upsert():
    text = SRC.read_text()
    assert text.index("check_embedding_compatible(name, dim, stored") < text.index('conn, "bronze.bronze_pq_embedding"')
