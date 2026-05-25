"""c1 election sync id/dedupe_key length guards."""

from scripts.datasources.openstates.sync_elections_to_c1 import (
    BronzeElectionRow,
    _C1_LIMITS,
    _contest_id,
    _dedupe_key,
    _election_id,
    fit_c1_id,
    make_ocd_id,
)


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
    assert len(dk) == _C1_LIMITS["dedupe_key"]


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
