"""Unit tests for the municipal council roster scraper (no network)."""

from scrapers.municipal import council_roster
from scrapers.municipal.council_roster import (
    CONFIGS,
    CURATED_ROSTERS,
    OFFICIAL_PROFILE_SOURCES,
    CouncilMember,
    get_council,
    parse_civicplus_member,
    parse_council_html,
    scrape_civicplus_directory,
    scrape_official_photos,
    scrape_official_profile,
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
        <img src="/sites/default/files/img/breadon-headshot.jpg?itok=abc" alt="Liz Breadon headshot"/>
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
    # Headshot src (alt="<Name> headshot") is captured and resolved to an absolute URL.
    assert breadon.photo_url == "https://www.boston.gov/sites/default/files/img/breadon-headshot.jpg?itok=abc"
    # A member whose img carries no src gets no photo (no crash).
    assert members[1].photo_url is None
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


def test_scrape_official_photos_handles_mayor_title_and_relative_src(monkeypatch):
    # The mayor's-office layout: alt="A headshot of Mayor <Name> smiling." with a
    # clean title="<Name>", and a relative src that must be made absolute.
    html = """
    <html><body>
      <img src="/sites/default/files/img/wu-headshot-square.png?itok=abc"
           alt="A headshot of Mayor Michelle Wu smiling." title="Michelle Wu" />
      <img src="/sites/default/files/img/burke-headshot.jpg" alt="Fire Commissioner Paul F. Burke" />
      <img src="/logo.svg" alt="city logo" />
    </body></html>
    """
    monkeypatch.setattr(council_roster, "fetch_html", lambda url, **kw: html)
    photos = scrape_official_photos("https://www.boston.gov/departments/mayors-office")
    # Mayor matched via title; src resolved to absolute. Non-headshot logo ignored.
    assert photos["michelle wu"] == (
        "https://www.boston.gov/sites/default/files/img/wu-headshot-square.png?itok=abc"
    )
    assert "city logo" not in photos
    assert "paul f. burke" not in photos  # no "headshot" in alt -> skipped


def test_atlanta_mayor_profile_pulls_photo_and_bio(monkeypatch):
    # Atlanta's "Meet the Mayor" page is a single-official profile: one headshot
    # plus a body-prose bio. scrape_official_profile should pull BOTH and attach
    # the bio to that one official.
    assert "atlanta" in OFFICIAL_PROFILE_SOURCES
    html = """
    <html><body>
      <nav>Home Government Departments</nav>
      <h1>Meet the Mayor</h1>
      <img src="/files/dickens-headshot.jpg?itok=xyz"
           alt="A headshot of Mayor Andre Dickens smiling." title="Andre Dickens" />
      <p>Andre Dickens is the 61st Mayor of the City of Atlanta, sworn into
         office in January 2022 after a career in business and public service.</p>
      <p>A lifelong Atlantan, he has focused his administration on public safety,
         affordable housing, and creating opportunity for every resident.</p>
      <a href="/contact">Contact</a>
    </body></html>
    """
    monkeypatch.setattr(council_roster, "fetch_html", lambda url, **kw: html)
    profiles = scrape_official_profile(OFFICIAL_PROFILE_SOURCES["atlanta"][0])
    assert "andre dickens" in profiles
    prof = profiles["andre dickens"]
    # Photo matched via the clean title attribute, relative src made absolute.
    assert prof.photo_url == "https://www.atlantaga.gov/files/dickens-headshot.jpg?itok=xyz"
    # Bio harvested from the body prose; short nav/labels excluded.
    assert prof.biography is not None
    assert "61st Mayor" in prof.biography
    assert "affordable housing" in prof.biography
    assert "Home Government Departments" not in prof.biography
    assert prof.source_url == OFFICIAL_PROFILE_SOURCES["atlanta"][0]


def test_scrape_official_profile_no_bio_on_multi_headshot_page(monkeypatch):
    # A department page with multiple headshots (mayor + cabinet) can't tie the
    # bio to one person, so profiles carry the photo only.
    html = """
    <html><body>
      <img src="/wu.png" alt="A headshot of Mayor Michelle Wu smiling." title="Michelle Wu" />
      <img src="/burke.png" alt="A headshot of Chief Paul Burke smiling." title="Paul Burke" />
      <p>The mayor's office leads the city across many departments and serves the
         residents of Boston every single day of the year.</p>
    </body></html>
    """
    monkeypatch.setattr(council_roster, "fetch_html", lambda url, **kw: html)
    profiles = scrape_official_profile("https://www.boston.gov/departments/mayors-office")
    assert set(profiles) == {"michelle wu", "paul burke"}
    assert all(p.biography is None for p in profiles.values())
    assert profiles["michelle wu"].photo_url == "https://www.boston.gov/wu.png"


# Cities whose mayor IS in OpenStates -> the curated roster is council-only to
# avoid duplicating that official. Kingsport is the exception: OpenStates carries
# no Kingsport officials at all, so its roster legitimately includes the mayor.
_MAYOR_IN_OPENSTATES = {"tuscaloosa", "boston", "atlanta"}


def test_curated_rosters_are_council_members():
    for slug, roster in CURATED_ROSTERS.items():
        assert roster, f"{slug} roster is empty"
        assert all(isinstance(m, CouncilMember) for m in roster)
        # Where the mayor is already in OpenStates, don't curate one here.
        if slug in _MAYOR_IN_OPENSTATES:
            assert all("mayor" not in m.title.lower() for m in roster)


def test_curated_northport_includes_mayor_and_five_districts():
    members = get_council("northport")
    assert len(members) == 6
    # No OpenStates officials for Northport, so the curated roster includes the mayor.
    mayor = next(m for m in members if m.title == "Mayor")
    assert mayor.full_name == "Dale Phillips"
    assert mayor.district is None
    districts = {m.district for m in members if m.district}
    assert districts == {f"District {i}" for i in range(1, 6)}
    assert all(m.jurisdiction == "Northport Government" for m in members)
    assert all(m.state_code == "AL" for m in members)
    # Every Northport member carries a scraped biography + headshot.
    assert all(m.biography for m in members)
    assert all(m.photo_url and m.photo_url.startswith("https://") for m in members)
    # The district-4 holder also presides over the body.
    president = next(m for m in members if m.title == "City Council President")
    assert president.full_name == "Jamie Dykes"
    assert president.district == "District 4"


# A CivicPlus directory.aspx detail page (Northport layout): breadcrumb, name,
# category, "Title:" line, sectioned bio, a footer with the CITY HALL phone that
# must NOT be mistaken for the member's, and a headshot whose alt drops the "III".
_CIVICPLUS_DETAIL_HTML = """
<html><body>
  <nav><a href="/">Home</a><a href="/directory.aspx">Staff Directory</a></nav>
  <h1>Woodrow Washington III</h1>
  <span>City Council</span>
  <p>Title: Pro Tempore / Council Member - District 2</p>
  <h2>Personal Profile</h2>
  <p>Retired Fire Captain from Tuscaloosa Fire Service</p>
  <h2>Education</h2>
  <p>Graduate of Stillman College</p>
  <img src="/ImageRepository/Document?documentID=1780" alt="Woodrow Washington" />
  <img src="/ImageRepository/Document?documentID=27" alt="Northport, AL" />
  <a href="/directory.aspx">Return to Staff Directory</a>
  <footer>Northport City Hall <span>Phone:</span> <span>205-339-7000</span></footer>
</body></html>
"""


def test_parse_civicplus_member_pulls_title_district_bio_and_headshot():
    cfg = CONFIGS["northport"]
    member = parse_civicplus_member(_CIVICPLUS_DETAIL_HTML, cfg)
    assert member is not None
    assert member.full_name == "Woodrow Washington III"
    # "Pro Tempore" maps to the council-pro-tem title; district parsed off the line.
    assert member.title == "City Councilor (Mayor Pro Tempore)"
    assert member.district == "District 2"
    assert member.jurisdiction == "Northport Government"
    # Bio keeps section structure and excludes the footer/return chrome.
    assert "Personal Profile" in member.biography
    assert "Retired Fire Captain" in member.biography
    assert "Education" in member.biography
    assert "Return to Staff Directory" not in member.biography
    # The CITY HALL footer phone must NOT be attached to the member.
    assert member.phone is None
    # Headshot matched despite the alt dropping the "III"; the site logo is ignored.
    assert member.photo_url == (
        "https://www.northportal.gov/ImageRepository/Document?documentID=1780"
    )


def test_scrape_civicplus_directory_discovers_eids_and_parses_each(monkeypatch):
    roster_html = """
    <html><body>
      <div><a href="/directory.aspx?eid=39">More Information</a></div>
      <div><a href="/directory.aspx?eid=37">More Information</a></div>
    </body></html>
    """
    mayor_html = """
    <html><body><nav>Staff Directory</nav><h1>Dale Phillips</h1><span>Mayor</span>
      <p>Title: Mayor</p><span>Phone:</span><span>205-394-1476</span>
      <h2>Overall Goals</h2><p>Sworn in as Mayor on November 3, 2025.</p>
      <img src="/ImageRepository/Document?documentID=1771" alt="Dale Phillips" />
      <a href="/directory.aspx">Return to Staff Directory</a></body></html>
    """
    pages = {
        "https://www.northportal.gov/220/City-Council": roster_html,
        "https://www.northportal.gov/directory.aspx?eid=39": _CIVICPLUS_DETAIL_HTML,
        "https://www.northportal.gov/directory.aspx?eid=37": mayor_html,
    }
    monkeypatch.setattr(council_roster, "fetch_html", lambda url, **kw: pages[url])
    members = scrape_civicplus_directory(CONFIGS["northport"])
    # Both detail pages parsed; sorted mayor-first then by district.
    assert [m.full_name for m in members] == ["Dale Phillips", "Woodrow Washington III"]
    assert members[0].title == "Mayor"
    assert members[0].phone == "205-394-1476"  # real contact-block phone IS captured
    # A lone bio section header is dropped, leaving just the prose.
    assert members[0].biography == "Sworn in as Mayor on November 3, 2025."
