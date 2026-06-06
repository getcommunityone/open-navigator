"""Unit tests for the municipal council roster scraper (no network)."""

from scrapers.municipal.council_roster import (
    CONFIGS,
    CURATED_ROSTERS,
    CouncilMember,
    get_council,
    parse_council_html,
)


def test_curated_tuscaloosa_has_seven_districts():
    members = get_council("tuscaloosa")
    assert len(members) == 7
    districts = {m.district for m in members}
    assert districts == {f"District {i}" for i in range(1, 8)}
    # Every curated member matches the city's jurisdiction so the API city
    # filter (jurisdiction ILIKE '%Tuscaloosa%' AND NOT '%county%') returns them.
    assert all(m.jurisdiction == "Tuscaloosa Government" for m in members)
    assert all(m.state_code == "AL" for m in members)


def test_curated_boston_has_four_at_large_and_nine_districts():
    members = get_council("boston")
    assert len(members) == 13
    districts = {m.district for m in members}
    assert districts == {"At-Large"} | {f"District {i}" for i in range(1, 10)}
    assert len([m for m in members if m.district == "At-Large"]) == 4
    # Matches Mayor Wu's jurisdiction string so ?city=Boston returns the council too.
    assert all(m.jurisdiction == "Boston Government" for m in members)
    assert all(m.state_code == "MA" for m in members)
    # District 9's holder also presides over the body.
    president = next(m for m in members if m.title == "City Council President")
    assert president.full_name == "Liz Breadon"
    assert president.district == "District 9"


def test_parse_council_html_name_then_role_layout():
    """Boston-style page: a bare name line followed by a 'City Councilor, ...' role line."""
    cfg = CONFIGS["boston"]
    html = """
    <html><body>
      <h2>City Council president</h2>
      <div class="member">
        <img alt="Liz Breadon headshot"/>
        <h3>Liz Breadon</h3>
        <p>City Council President; City Councilor, District 9</p>
      </div>
      <h2>City Council members</h2>
      <div class="member">
        <img alt="Ruthzee Louijeune headshot"/>
        <h3>Ruthzee Louijeune</h3>
        <p>City Councilor, At-Large</p>
      </div>
      <div class="member">
        <img alt="Gabriela Coletta Zapata headshot"/>
        <h3>Gabriela Coletta Zapata</h3>
        <p>City Councilor, District 1</p>
      </div>
      <script>var x = "Fake Person City Councilor, District 9";</script>
    </body></html>
    """
    members = parse_council_html(html, cfg)
    assert len(members) == 3  # section headings + script content are not members
    breadon = members[0]
    assert breadon.full_name == "Liz Breadon"
    assert breadon.district == "District 9"
    assert breadon.title == "City Council President"
    assert members[1].full_name == "Ruthzee Louijeune"
    assert members[1].district == "At-Large"
    assert members[1].title == cfg.member_title
    assert members[2].full_name == "Gabriela Coletta Zapata"
    assert members[2].district == "District 1"
    assert all(m.jurisdiction == "Boston Government" for m in members)


def test_get_council_unknown_city_raises():
    try:
        get_council("atlantis")
    except ValueError as exc:
        assert "atlantis" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for unknown city")


def test_parse_council_html_pairs_name_and_district():
    cfg = CONFIGS["tuscaloosa"]
    html = """
    <html><body>
      <div class="member"><h3>Councilor Joseph Eatmon, Sr.</h3><p>District 1</p></div>
      <div class="member"><h3>Councilwoman Raevan Howard</h3><p>District 2</p></div>
      <script>var x = "Councilor Fake Person District 9";</script>
    </body></html>
    """
    members = parse_council_html(html, cfg)
    assert len(members) == 2  # script content is skipped
    assert members[0].full_name == "Joseph Eatmon, Sr."
    assert members[0].district == "District 1"
    assert members[1].full_name == "Raevan Howard"
    assert members[1].title == cfg.member_title
    assert members[1].jurisdiction == cfg.jurisdiction


def test_parse_council_html_empty_when_no_roster():
    cfg = CONFIGS["tuscaloosa"]
    assert parse_council_html("<html><body><p>No council here</p></body></html>", cfg) == []


def test_curated_rosters_are_council_members():
    for slug, roster in CURATED_ROSTERS.items():
        assert roster, f"{slug} roster is empty"
        assert all(isinstance(m, CouncilMember) for m in roster)
        # Mayors are sourced from OpenStates, not curated here (avoids duplicates).
        assert all("mayor" not in m.title.lower() for m in roster)
