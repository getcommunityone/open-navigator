"""scrapers.youtube.rescan_homepage_channels: merging found links and choosing the primary."""

from __future__ import annotations

from scrapers.youtube import rescan_homepage_channels as r

NOW = "2026-11-16T00:00:00+00:00"


def test_merge_adds_new_links_and_relabels_known_ones():
    payload = {
        "youtube_channels": [
            {
                "channel_url": "https://www.youtube.com/@ElkinsCityHall",
                "discovery_method": "pattern_match",
                "confidence": 0.7,
            }
        ],
        "social_media": {"youtube": [], "vimeo": []},
        "other": 1,
    }
    out, added = r.merge_channels(
        payload,
        [
            "https://www.youtube.com/@elkinscityhall/",
            "https://www.youtube.com/channel/UC-j6MHOHpxlWYpNPTEt15-Q",
        ],
        now=NOW,
    )
    assert added == 1
    assert out["other"] == 1
    known, new = out["youtube_channels"]
    assert known["discovery_method"] == "website_scrape" and known["confidence"] == 0.9
    assert (
        new["channel_id"] == "UC-j6MHOHpxlWYpNPTEt15-Q" and new["discovered_at"] == NOW
    )
    assert len(out["social_media"]["youtube"]) == 2
    assert out["social_media"]["vimeo"] == []
    # The input is not mutated.
    assert payload["youtube_channels"][0]["discovery_method"] == "pattern_match"


def test_merge_with_nothing_found_keeps_payload():
    out, added = r.merge_channels(None, [], now=NOW)
    assert (
        added == 0
        and out["youtube_channels"] == []
        and out["social_media"]["youtube"] == []
    )


def test_primary_replaces_only_guesses_or_blanks():
    found = ["https://www.youtube.com/@real"]
    assert r.choose_primary(None, None, found) == found[0]
    assert (
        r.choose_primary("https://www.youtube.com/@guess", "pattern_match", found)
        == found[0]
    )
    assert (
        r.choose_primary("https://www.youtube.com/@site", "website_scrape", found)
        is None
    )
    assert (
        r.choose_primary("https://www.youtube.com/@guess", "pattern_match", []) is None
    )


def test_channel_id_only_from_channel_urls():
    assert r._channel_id("https://www.youtube.com/channel/UCabc/videos") == "UCabc"
    assert r._channel_id("https://www.youtube.com/@handle") is None


def test_select_sql():
    sql, params = r.select_sql(["al"], include_rescanned=False)
    assert (
        params == ["municipality", ["AL"]]
        and "homepage_rescan_at" in sql
        and sql.endswith("LIMIT %s")
    )
    assert "j.name AS jurisdiction_name" in sql
    sql, params = r.select_sql([], include_rescanned=True)
    assert params == ["municipality"] and "homepage_rescan_at" not in sql


def test_primary_replaces_search_picks():
    found = ["https://www.youtube.com/@real"]
    assert (
        r.choose_primary(
            "https://www.youtube.com/channel/UCnews", "domain_search", found
        )
        == found[0]
    )


def test_websites_source_joins_the_website_table_for_any_type():
    sql, params = r.select_sql(
        ["al"], include_rescanned=False, jtype="county", source="websites"
    )
    assert (
        "bronze_jurisdictions_counties_scraped" in sql
        and "int_jurisdiction_websites" in sql
    )
    assert params == ["county", ["AL"]]
    assert "s.youtube_channel_url" in sql


def test_school_districts_have_no_channel_columns():
    sql, _ = r.select_sql(
        [], include_rescanned=True, jtype="school_district", source="websites"
    )
    assert "NULL::text AS youtube_channel_url" in sql
    assert r.TABLES["school_district"] not in r.CHANNEL_COLUMN_TABLES


def test_normalize_homepage_adds_a_scheme():
    assert r.normalize_homepage("cityofx.gov") == "https://cityofx.gov"
    assert r.normalize_homepage("http://a.gov") == "http://a.gov"
    assert r.normalize_homepage("  ") is None


# --- #535: re-verifying pattern_match guesses -------------------------------------

GUESS = "https://www.youtube.com/@SeligmanAL"


def test_select_sql_filters_on_methods():
    sql, params = r.select_sql(
        [], include_rescanned=True, source="websites", methods=["pattern_match"]
    )
    assert "youtube_channel_selection_method, '') = ANY(%s)" in sql
    assert params == ["municipality", ["pattern_match"]]


def test_guess_linked_by_site_is_confirmed():
    v = r.verify_guess(
        GUESS,
        None,
        ["https://www.youtube.com/@seligmanal"],
        jurisdiction_name="Seligman",
        state_code="AL",
    )
    assert v.status == r.CONFIRMED and v.primary_url == GUESS


def test_guess_confirmed_by_channel_id():
    v = r.verify_guess(
        GUESS, "UCabc123", ["https://www.youtube.com/channel/UCabc123"]
    )
    assert v.status == r.CONFIRMED


def test_other_site_link_replaces_the_guess():
    v = r.verify_guess(
        GUESS, None, ["https://www.youtube.com/channel/UCreal"], jurisdiction_name="Seligman"
    )
    assert v.status == r.REPLACED
    assert v.primary_url == "https://www.youtube.com/channel/UCreal"


def test_site_without_links_marks_unverified():
    v = r.verify_guess(GUESS, None, [], homepage_error="")
    assert v.status == r.UNVERIFIED and v.reason == "no_site_link"


def test_unreadable_site_changes_nothing():
    v = r.verify_guess(GUESS, None, [], homepage_error="blocked:403")
    assert v.status == r.UNREADABLE and v.reason == "blocked:403"


def test_mismatch_guard_rejects_link_naming_another_government():
    """#527/#526: a city site linking the county commission's channel is not the city's."""
    v = r.verify_guess(
        GUESS,
        None,
        ["https://www.youtube.com/@MarionCountyCommission"],
        jurisdiction_name="Marion",
        jurisdiction_type="municipality",
        state_code="AL",
    )
    assert v.status == r.UNVERIFIED
    assert v.reason.startswith("site_links_other_government:names_county_government")
    # The guard skips a rejected link and takes the next acceptable one.
    v = r.verify_guess(
        GUESS,
        None,
        ["https://www.youtube.com/@CityOfBartow", "https://www.youtube.com/@CityOfMarion"],
        jurisdiction_name="Marion",
        state_code="AL",
    )
    assert v.status == r.REPLACED and v.primary_url.endswith("@CityOfMarion")


class _Cur:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params):
        self.log.append((sql, params))


class _Conn:
    def __init__(self):
        self.log: list = []

    def cursor(self):
        return _Cur(self.log)

    def commit(self):
        pass


def _row(method="pattern_match", url=GUESS):
    return {
        "key": "municipality|0169000",
        "geoid": "0169000",
        "usps": "AL",
        "table": r.TABLE,
        "homepage_url": "https://seligman.gov",
        "fill_homepage": False,
        "payload": {},
        "jurisdiction_name": "Seligman",
        "youtube_channel_url": url,
        "youtube_channel_selection_method": method,
        "youtube_channel_id": None,
    }


def _write(row, res):
    conn = _Conn()
    counts = r.write_results(conn, {row["key"]: row}, [res])
    (sql, params), = conn.log
    return counts, sql, params


def test_write_marks_unverified_and_keeps_url():
    res = r.RescanResult(key="municipality|0169000", homepage_url="https://seligman.gov")
    counts, sql, params = _write(_row(), res)
    assert counts[r.UNVERIFIED] == 1
    assert "youtube_channel_selection_method = %s" in sql
    assert r.PATTERN_MATCH_UNVERIFIED_METHOD in params
    assert "youtube_channel_url = %s" not in sql
    assert '"status": "unverified"' in params[0]


def test_write_confirms_guess_as_website_scrape():
    res = r.RescanResult(
        key="municipality|0169000",
        homepage_url="https://seligman.gov",
        channels=["https://www.youtube.com/@SeligmanAL"],
    )
    counts, sql, params = _write(_row(), res)
    assert counts[r.CONFIRMED] == 1 and "website_scrape" in params
    assert "youtube_channel_url = %s" not in sql


def test_write_unreadable_leaves_channel_columns_alone():
    res = r.RescanResult(
        key="municipality|0169000",
        homepage_url="https://seligman.gov",
        homepage_error="fetch_failed",
    )
    counts, sql, _ = _write(_row(), res)
    assert counts[r.UNREADABLE] == 1 and "youtube_channel" not in sql


def test_mark_no_website_sql():
    sql, params = r.mark_no_website_sql(r.TABLE, "municipality", ["al"], apply=False)
    assert sql.startswith("SELECT COUNT(*)") and params == ["municipality", ["AL"]]
    sql, params = r.mark_no_website_sql(r.TABLE, "municipality", [], apply=True)
    assert sql.startswith("UPDATE") and "no_website" in sql
    assert params[0] == r.PATTERN_MATCH_UNVERIFIED_METHOD and params[-1] == "municipality"


def test_unverified_guess_is_never_crawled():
    """The scraped-table catalog sources skip pattern_match_unverified (#535)."""
    import inspect

    from scrapers.youtube.load_youtube_events_to_postgres import YouTubeEventsLoader

    for fn in (
        YouTubeEventsLoader.get_jurisdictions_from_counties_scraped,
        YouTubeEventsLoader.get_jurisdictions_from_municipalities_scraped,
    ):
        src = inspect.getsource(fn)
        assert "youtube_channel_selection_method, '') <> %s" in src
        assert "[PATTERN_MATCH_UNVERIFIED_METHOD]" in src
