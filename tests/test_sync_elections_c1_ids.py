"""c1 election sync id/dedupe_key length guards."""

from pipeline.openstates.sync_elections_to_c1 import (
    BronzeElectionRow,
    _C1_LIMITS,
    _ON_CONFLICT_DEDUPE_KEY,
    _contest_id,
    _dedupe_key,
    _election_group_key,
    _election_id,
    _election_rows_for_upsert,
    fit_c1_id,
    make_ocd_id,
)


def test_on_conflict_matches_partial_dedupe_index():
    assert "WHERE dedupe_key IS NOT NULL" in _ON_CONFLICT_DEDUPE_KEY


def test_make_ocd_id_fits_varchar_50():
    for prefix in ("election", "candidatecontest", "candidacy", "ballotmeasure"):
        oid = make_ocd_id(prefix, "test-key")
        assert len(oid) <= _C1_LIMITS["id"]
        assert oid.startswith("ocd-")


def test_fit_c1_id_hashes_legacy_long_ocd_id():
    legacy = make_ocd_id("candidatecontest", "x")  # would be 57 chars with old prefix
    # Simulate old-format id stored in bronze
    old_style = f"ocd-candidatecontest/{legacy.split('/')[-1]}"
    assert len(old_style) > _C1_LIMITS["id"]
    short = fit_c1_id(old_style, prefix="candidatecontest", fallback_key="fb")
    assert len(short) <= _C1_LIMITS["id"]


def test_dedupe_key_truncated_to_500():
    long_name = "x" * 2000
    dk = _dedupe_key("jurisdiction", "2026-01-01", long_name, "general")
    assert dk is not None
    assert len(dk) == _C1_LIMITS["dedupe_key"]


def test_candidacy_uses_parent_election_id_from_raw_row():
    parent = make_ocd_id("election", "parent-key")
    row = BronzeElectionRow(
        id=2,
        scrape_batch_id="00000000-0000-0000-0000-000000000001",
        record_type="candidacy",
        ocd_id=make_ocd_id("candidacy", "cand-1"),
        election_name=None,
        election_date=None,
        election_type=None,
        election_status=None,
        ocd_jurisdiction_id="county_13047",
        state_code="GA",
        jurisdiction_id="county_13047",
        candidate_name="Jane",
        candidate_party=None,
        candidate_post="Mayor",
        candidate_status="candidate",
        candidate_vote_count=None,
        candidate_vote_percent=None,
        measure_title=None,
        measure_summary=None,
        measure_classification=None,
        measure_yes_count=None,
        measure_no_count=None,
        measure_outcome=None,
        source_url=None,
        source_name=None,
        raw_row={"election_id": parent},
    )
    election_id, dedupe = _election_id(row)
    assert election_id == fit_c1_id(parent, prefix="election", fallback_key=parent)
    assert dedupe == _dedupe_key("election", election_id)


def test_election_rows_for_upsert_one_row_per_c1_election_id():
    """Candidacy fallback dedupe_key must not create a second upsert for the same election id."""
    parent = make_ocd_id("election", "lee-voting")
    election_row = BronzeElectionRow(
        id=1,
        scrape_batch_id="00000000-0000-0000-0000-000000000001",
        record_type="election",
        ocd_id=parent,
        election_name="Voting Locations",
        election_date=None,
        election_type="unknown",
        election_status="scraped",
        ocd_jurisdiction_id="county_13177",
        state_code="GA",
        jurisdiction_id="county_13177",
        candidate_name=None,
        candidate_party=None,
        candidate_post=None,
        candidate_status=None,
        candidate_vote_count=None,
        candidate_vote_percent=None,
        measure_title=None,
        measure_summary=None,
        measure_classification=None,
        measure_yes_count=None,
        measure_no_count=None,
        measure_outcome=None,
        source_url=None,
        source_name=None,
        raw_row={},
    )
    eid = fit_c1_id(parent, prefix="election", fallback_key="1")
    candidacy_row = BronzeElectionRow(
        id=2,
        scrape_batch_id="00000000-0000-0000-0000-000000000001",
        record_type="candidacy",
        ocd_id=make_ocd_id("candidacy", "c1"),
        election_name=None,
        election_date=None,
        election_type=None,
        election_status=None,
        ocd_jurisdiction_id="county_13177",
        state_code="GA",
        jurisdiction_id="county_13177",
        candidate_name="Jane",
        candidate_party=None,
        candidate_post="Clerk",
        candidate_status="candidate",
        candidate_vote_count=None,
        candidate_vote_percent=None,
        measure_title=None,
        measure_summary=None,
        measure_classification=None,
        measure_yes_count=None,
        measure_no_count=None,
        measure_outcome=None,
        source_url=None,
        source_name=None,
        raw_row={"election_id": parent},
    )
    ups = _election_rows_for_upsert([election_row, candidacy_row])
    assert len(ups) == 1
    assert _election_group_key(candidacy_row) == eid


def test_election_rows_for_upsert_dedupes_same_dedupe_key():
    base = dict(
        scrape_batch_id="00000000-0000-0000-0000-000000000001",
        record_type="election",
        ocd_id=make_ocd_id("election", "a"),
        election_name="Voting Precincts",
        election_date=None,
        election_type="unknown",
        election_status="scraped",
        ocd_jurisdiction_id="ocd-division/country:us/state:ga/place:ringgold",
        state_code="GA",
        jurisdiction_id="county_13047",
        candidate_name=None,
        candidate_party=None,
        candidate_post=None,
        candidate_status=None,
        candidate_vote_count=None,
        candidate_vote_percent=None,
        measure_title=None,
        measure_summary=None,
        measure_classification=None,
        measure_yes_count=None,
        measure_no_count=None,
        measure_outcome=None,
        source_url=None,
        source_name=None,
        raw_row={},
    )
    rows = [
        BronzeElectionRow(id=1, **base),
        BronzeElectionRow(id=2, ocd_id=make_ocd_id("election", "b"), **{k: v for k, v in base.items() if k != "ocd_id"}),
    ]
    assert len(_election_rows_for_upsert(rows)) == 1


def test_election_id_and_contest_id_within_limits():
    row = BronzeElectionRow(
        id=1,
        scrape_batch_id="00000000-0000-0000-0000-000000000001",
        record_type="candidacy",
        ocd_id="ocd-candidatecontest/" + "a" * 36,
        election_name="A" * 3000,
        election_date=None,
        election_type="general",
        election_status=None,
        ocd_jurisdiction_id="county_13029",
        state_code="GA",
        jurisdiction_id="county_13029",
        candidate_name="Jane Doe",
        candidate_party=None,
        candidate_post="Commissioner " * 200,
        candidate_status="candidate",
        candidate_vote_count=None,
        candidate_vote_percent=None,
        measure_title=None,
        measure_summary=None,
        measure_classification=None,
        measure_yes_count=None,
        measure_no_count=None,
        measure_outcome=None,
        source_url="https://example.gov/elections",
        source_name="bronze_election_website_scrape",
        raw_row={},
    )
    election_id, dedupe = _election_id(row)
    assert len(election_id) <= _C1_LIMITS["id"]
    assert len(dedupe) <= _C1_LIMITS["dedupe_key"]
    contest_id, contest_key = _contest_id(row, election_id)
    assert len(contest_id) <= _C1_LIMITS["id"]
    assert len(contest_key) <= _C1_LIMITS["dedupe_key"]
