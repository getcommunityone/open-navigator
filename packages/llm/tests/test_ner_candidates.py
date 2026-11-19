"""NER candidate extraction without a spaCy model download."""

from __future__ import annotations

from types import SimpleNamespace

from llm.ner.candidates import extract_candidates


class _Ent:
    def __init__(self, text: str, label: str, start: int, end: int):
        self.text = text
        self.label_ = label
        self.start_char = start
        self.end_char = end


class _FakeNlp:
    def __call__(self, text: str):
        # Miriam Rolls … Ninstar Park
        return SimpleNamespace(
            ents=[
                _Ent("Miriam Rolls", "PERSON", 0, 12),
                _Ent("Miriam", "PERSON", 20, 26),  # bare first name → drop
                _Ent("Ninstar Park", "FAC", 40, 52),
                _Ent("UNKNOWN", "PERSON", 60, 67),  # bad → drop
                _Ent("Hancock County", "GPE", 70, 84),
            ]
        )


def test_extract_keeps_full_names_and_places():
    rows = extract_candidates("ignored", nlp=_FakeNlp())
    assert [r.text for r in rows if r.label == "PERSON"] == ["Miriam Rolls"]
    assert {r.text for r in rows if r.label == "PLACE"} == {
        "Ninstar Park",
        "Hancock County",
    }


def test_empty_text():
    assert extract_candidates("  ", nlp=_FakeNlp()) == []
