import json
from pathlib import Path

from llm.gemini.transcript_cache_paths import (
    cache_type_segment,
    canonical_jurisdiction_root,
    find_jurisdiction_root,
    geoid_variants_for_numeric,
    is_legacy_policy_jurisdiction_dir,
    jurisdiction_cache_folder_aliases,
    jurisdiction_cache_folder_name,
    jurisdiction_root_candidates,
    list_legacy_policy_jurisdiction_dirs,
    list_numeric_policy_geo_dirs,
    lookup_jurisdiction_place_name,
    migrate_policy_cache_channels,
    migrate_policy_cache_folder_names,
    migrate_policy_cache_geography,
    migrate_policy_cache_numeric_folders,
    normalize_channel_segment,
    resolve_canonical_jurisdiction_id,
    resolve_numeric_folder_canonical_id,
)


def test_lookup_does_not_call_resolve_canonical(monkeypatch):
    """Regression: lookup and resolve must not call each other (RecursionError)."""
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.resolve_canonical_jurisdiction_id",
        lambda *_: (_ for _ in ()).throw(AssertionError("lookup must not resolve")),
    )
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths._fetch_place_name_from_db",
        lambda jid: "Anniston city" if "0101852" in jid else None,
    )
    lookup_jurisdiction_place_name.cache_clear()
    assert lookup_jurisdiction_place_name("municipality_0101852") == "Anniston city"


def test_resolve_canonical_uses_fetch_not_lookup(monkeypatch):
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths._fetch_place_name_from_db",
        lambda jid: "Anniston city" if jid == "municipality_0101852" else None,
    )
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.lookup_canonical_jurisdiction_id_from_bronze",
        lambda *a, **k: "",
    )
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.lookup_jurisdiction_place_name",
        lambda *_: (_ for _ in ()).throw(AssertionError("resolve must not lookup")),
    )
    assert resolve_canonical_jurisdiction_id("municipality_0101852") == "anniston_0101852"


def test_cache_type_segment_from_typed_id(monkeypatch):
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.resolve_canonical_jurisdiction_id",
        lambda jid: jid,
    )
    assert cache_type_segment("municipality_0177256") == "municipality"
    assert cache_type_segment("tuscaloosa_0177256") == "municipality"
    assert cache_type_segment("school_district_0100005") == "school"
    assert cache_type_segment("5583", jurisdiction_type="city") == "municipality"


def test_jurisdiction_cache_folder_name_strips_nbsp_city_suffix(monkeypatch):
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.resolve_canonical_jurisdiction_id",
        lambda jid: jid,
    )
    # Census / DB names sometimes use a non-breaking space before ``city``.
    assert jurisdiction_cache_folder_name("abbeville_0100124") == "abbeville_0100124"
    assert (
        jurisdiction_cache_folder_name(
            "municipality_0100124",
            place_name="Abbeville\u00a0city",
        )
        == "abbeville_0100124"
    )


def test_jurisdiction_cache_folder_aliases_include_legacy_city_slug(monkeypatch):
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.resolve_canonical_jurisdiction_id",
        lambda jid: jid,
    )
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.lookup_jurisdiction_place_name",
        lambda jid: None,
    )
    aliases = jurisdiction_cache_folder_aliases(
        "municipality_0100124",
        place_name="Abbeville city",
    )
    assert "abbeville_0100124" in aliases
    assert "abbeville_city_0100124" in aliases


def test_jurisdiction_cache_folder_name_county_seat_not_used(monkeypatch):
    """County folders use the county slug from bronze, not the seat city ``place_name``."""
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.lookup_canonical_jurisdiction_id_from_bronze",
        lambda geoid, jtype, database_url=None: (
            "henry_01067" if geoid == "01067" and jtype == "county" else ""
        ),
    )
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.resolve_canonical_jurisdiction_id",
        lambda jid: jid,
    )
    assert (
        jurisdiction_cache_folder_name("abbeville_01067", place_name="Abbeville city")
        == "henry_01067"
    )
    assert (
        jurisdiction_cache_folder_name("county_01067", place_name="Abbeville city")
        == "henry_01067"
    )


def test_jurisdiction_cache_folder_name(monkeypatch):
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.lookup_jurisdiction_place_name",
        lambda jid: "Anniston city" if "0101852" in jid else "Dublin city",
    )
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.resolve_canonical_jurisdiction_id",
        lambda jid: jid if jid.startswith("municipality_") else f"municipality_{jid}",
    )
    assert jurisdiction_cache_folder_name("municipality_0101852") == "anniston_0101852"
    assert jurisdiction_cache_folder_name("municipality_1324376") == "dublin_1324376"


def test_canonical_jurisdiction_root_with_state_and_channel(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.lookup_jurisdiction_place_name",
        lambda jid: "Dublin city",
    )
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.resolve_canonical_jurisdiction_id",
        lambda jid: "municipality_1324376",
    )
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.lookup_channel_id_from_db",
        lambda *a, **k: "UCxxc9YlL425MrKGFzaGW27Q",
    )
    root = canonical_jurisdiction_root(
        tmp_path,
        "municipality_1324376",
        state_code="GA",
        jurisdiction_type="city",
        channel_id="UCxxc9YlL425MrKGFzaGW27Q",
    )
    assert root == (
        tmp_path
        / "GA"
        / "municipality"
        / "dublin_1324376"
        / "UCxxc9YlL425MrKGFzaGW27Q"
    )


def test_normalize_channel_segment():
    assert normalize_channel_segment("UCxxc9YlL425MrKGFzaGW27Q") == "UCxxc9YlL425MrKGFzaGW27Q"
    assert normalize_channel_segment("") == "_unknown"


def test_find_jurisdiction_root_legacy_then_geographic(tmp_path: Path):
    legacy = tmp_path / "5583" / "01_transcripts"
    legacy.mkdir(parents=True)
    found = find_jurisdiction_root(tmp_path, "5583", state_code="GA")
    assert found == tmp_path / "5583"

    geo = tmp_path / "GA" / "municipality" / "5583" / "UCchan" / "01_transcripts"
    geo.mkdir(parents=True)
    found2 = find_jurisdiction_root(
        tmp_path, "5583", state_code="GA", channel_id="UCchan"
    )
    assert found2 == tmp_path / "GA" / "municipality" / "5583" / "UCchan"


def test_migrate_policy_cache_geography(tmp_path: Path, monkeypatch):
    src = tmp_path / "5583"
    (src / "01_transcripts").mkdir(parents=True)
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.resolve_jurisdiction_geo",
        lambda jid, **kw: ("GA", "municipality"),
    )
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.jurisdiction_cache_folder_name",
        lambda jid: jid,
    )
    stats = migrate_policy_cache_geography(tmp_path, dry_run=False)
    assert stats["moved"] == 1
    assert (tmp_path / "GA" / "municipality" / "5583").is_dir()
    assert not src.exists()


def test_migrate_policy_cache_channels(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.jurisdiction_cache_folder_name",
        lambda jid: jid,
    )
    geo = tmp_path / "GA" / "municipality" / "5583"
    tx = geo / "01_transcripts" / "2026-05-20_Foo.json"
    tx.parent.mkdir(parents=True)
    tx.write_text(
        '{"video_id":"abc12345678","title":"Foo","event_date":"2026-05-20"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.lookup_channel_id_from_db",
        lambda jid, vid="": "UCtestchannel1",
    )
    stats = migrate_policy_cache_channels(tmp_path, dry_run=False)
    assert stats["moved"] == 1
    assert (
        tmp_path / "GA" / "municipality" / "5583" / "UCtestchannel1" / "01_transcripts" / tx.name
    ).is_file()


def test_list_legacy_dirs(tmp_path: Path):
    (tmp_path / "5583").mkdir()
    (tmp_path / "AL" / "municipality" / "x").mkdir(parents=True)
    (tmp_path / "logs").mkdir()
    legacy = list_legacy_policy_jurisdiction_dirs(tmp_path)
    assert [p.name for p in legacy] == ["5583"]
    assert is_legacy_policy_jurisdiction_dir(tmp_path / "5583", tmp_path)
    assert not is_legacy_policy_jurisdiction_dir(tmp_path / "AL", tmp_path)


def test_migrate_policy_cache_folder_names(tmp_path: Path, monkeypatch):
    old = tmp_path / "AL" / "municipality" / "municipality_0101852"
    (old / "UCchan" / "01_transcripts").mkdir(parents=True)
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.lookup_jurisdiction_place_name",
        lambda jid: "Anniston city",
    )
    stats = migrate_policy_cache_folder_names(tmp_path, dry_run=False)
    assert stats["renamed"] == 1
    assert (tmp_path / "AL" / "municipality" / "anniston_0101852" / "UCchan").is_dir()
    assert not old.exists()


def test_jurisdiction_root_candidates_order(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "llm.gemini.transcript_cache_paths.lookup_jurisdiction_place_name",
        lambda jid: "Northport city",
    )
    cands = jurisdiction_root_candidates(
        tmp_path, "municipality_0155200", state_code="AL"
    )
    assert cands[0].parent == tmp_path / "AL" / "municipality" / "northport_0155200"


def test_geoid_variants_for_numeric():
    assert "0159472" in geoid_variants_for_numeric("159472")
    assert "2581005" in geoid_variants_for_numeric("2581005")


def test_resolve_numeric_folder_canonical_id():
    rows = [
        {
            "jurisdiction_id": "phenix_city_0159472",
            "geoid": "0159472",
            "name": "Phenix City city",
            "jurisdiction_type": "municipality",
            "state_code": "AL",
        },
        {
            "jurisdiction_id": "winthrop_town_2581005",
            "geoid": "2581005",
            "name": "Winthrop Town city",
            "jurisdiction_type": "municipality",
            "state_code": "MA",
        },
    ]
    assert (
        resolve_numeric_folder_canonical_id(
            "159472",
            state_code="AL",
            cache_type_segment="municipality",
            jurisdictions=rows,
        )
        == "phenix_city_0159472"
    )
    assert (
        resolve_numeric_folder_canonical_id(
            "2581005",
            state_code="MA",
            cache_type_segment="municipality",
            jurisdictions=rows,
        )
        == "winthrop_town_2581005"
    )


def test_migrate_policy_cache_numeric_folders(tmp_path: Path):
    rows = [
        {
            "jurisdiction_id": "phenix_city_0159472",
            "geoid": "0159472",
            "name": "Phenix City city",
            "jurisdiction_type": "municipality",
            "state_code": "AL",
        },
        {
            "jurisdiction_id": "winthrop_town_2581005",
            "geoid": "2581005",
            "name": "Winthrop Town city",
            "jurisdiction_type": "municipality",
            "state_code": "MA",
        },
    ]
    orphan = tmp_path / "AL" / "municipality" / "159472" / "UCchan" / "README.md"
    orphan.parent.mkdir(parents=True)
    orphan.write_text("legacy", encoding="utf-8")

    winthrop_src = tmp_path / "MA" / "municipality" / "2581005" / "UCw" / "01_transcripts"
    tx = winthrop_src / "2026-05-19_Foo.json"
    tx.parent.mkdir(parents=True)
    tx.write_text(
        '{"video_id":"abc12345678","title":"Foo","jurisdiction_id":"2581005"}',
        encoding="utf-8",
    )

    stats = migrate_policy_cache_numeric_folders(
        tmp_path,
        jurisdictions=rows,
        dry_run=False,
    )
    assert stats["renamed"] == 2
    assert not (tmp_path / "AL" / "municipality" / "159472").exists()
    assert (tmp_path / "MA" / "municipality" / "winthrop_town_2581005" / "UCw").is_dir()
    merged = json.loads(
        (
            tmp_path
            / "MA"
            / "municipality"
            / "winthrop_town_2581005"
            / "UCw"
            / "01_transcripts"
            / "2026-05-19_Foo.json"
        ).read_text(encoding="utf-8")
    )
    assert merged["jurisdiction_id"] == "winthrop_town_2581005"
