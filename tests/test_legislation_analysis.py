from scripts.gemini.legislation_analysis import (
    build_agenda_label_to_leg_id,
    enrich_part1_legislation,
    extract_agenda_labels_from_text,
    fuzzy_match_leg_id,
    ingest_agenda_legislation,
    validate_and_fix_legislation_refs,
)


def test_validate_fixes_orphan_ref_via_official_number():
    analysis = {
        "legislation": [
            {
                "leg_id": "z0726_2026_municipality_0177256",
                "official_number": "Z0726",
                "title": "Rezoning at 2842 18th Street",
            }
        ],
        "decisions": [
            {
                "decision_id": "D001",
                "legislation_refs": ["z0726_2026_typo"],
            }
        ],
        "uncontested_items": [],
        "subjects": [],
    }
    out, report = validate_and_fix_legislation_refs(analysis, fix=True)
    assert out["decisions"][0]["legislation_refs"] == ["z0726_2026_municipality_0177256"]
    assert report["fixed_refs"]
    assert report["orphan_refs"] == []


def test_validate_drops_unknown_orphan():
    analysis = {
        "legislation": [],
        "decisions": [{"decision_id": "D001", "legislation_refs": ["nonexistent_leg"]}],
        "uncontested_items": [],
        "subjects": [],
    }
    out, report = validate_and_fix_legislation_refs(analysis, fix=True)
    assert out["decisions"][0]["legislation_refs"] == []
    assert len(report["orphan_refs"]) == 1


def test_extract_agenda_labels():
    labels = extract_agenda_labels_from_text("public hearing for agenda item 10 C1 and case Z0726")
    assert "10C1" in labels or "10" in labels
    assert "Z0726" in labels


def test_ingest_maps_case_id_to_legislation_refs():
    analysis = {
        "legislation": [
            {
                "leg_id": "z0726_2026_municipality_0177256",
                "official_number": "Z0726",
                "title": "Rezoning",
            }
        ],
        "uncontested_items": [
            {
                "item_id": "U001",
                "headline": "Rezoning Z0726 at 2842 18th Street approved",
                "legislation_refs": [],
            }
        ],
        "decisions": [],
        "subjects": [],
    }
    out, report = ingest_agenda_legislation(analysis, fix_refs=True)
    assert "z0726_2026_municipality_0177256" in out["uncontested_items"][0]["legislation_refs"]
    assert report["refs_added"] >= 1
    assert out.get("agenda_legislation_map")


def test_build_agenda_label_to_leg_id():
    analysis = {
        "legislation": [
            {"leg_id": "resolution_2025_municipality_0177256", "official_number": "2025-4"}
        ]
    }
    m = build_agenda_label_to_leg_id(analysis)
    assert m.get("20254") == "resolution_2025_municipality_0177256" or "2025-4" in m


def test_enrich_part1_runs_end_to_end():
    analysis = {
        "legislation": [{"leg_id": "ord_1_municipality_01", "official_number": "42"}],
        "uncontested_items": [
            {"item_id": "U001", "headline": "Ordinance 42 adopted", "legislation_refs": []}
        ],
        "decisions": [],
        "subjects": [{"subject_id": "s1", "canonical_leg_id": "ord_1_municipality_01"}],
    }
    out = enrich_part1_legislation(analysis)
    assert out["_legislation_validation"]["ok"] is True
    assert out["uncontested_items"][0]["legislation_refs"]
