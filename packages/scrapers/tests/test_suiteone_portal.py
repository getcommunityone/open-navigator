"""Tests for the SuiteOne portal parser (pure HTML → MeetingDoc / older-groups)."""
from __future__ import annotations

from scrapers.suiteone.portal import (
    _normalize_doc_url,
    parse_listing,
    parse_older_groups,
)

BASE = "https://tuscaloosaal.suiteonemedia.com/"

# One listing row carrying an event link, a date cell, and agenda + minutes docs.
# The minutes href deliberately bakes in the trailing-space bug the scraper fixes.
_ROW_HTML = """
<table><tbody>
<tr>
  <a href="/event/?id=11169" title="Navigate to 3:15 p.m. Finance Committee">3:15 p.m. Finance Committee</a>
  <td data-sort="1700000000">Jun 09, 2026 | 03:00 PM</td>
  <a href="/event/GetAgendaFile/Agenda?aid=5819">Agenda</a>
  <a href="/event/GetMinutesFile/Synopsis%20?mid=5048">Minutes</a>
</tr>
</tbody></table>
"""

_OLDER_HTML = """
<a href="#" class="older_meetings_click" id="older_meetings_Div_pmFinanceCommittee"
   data-yearFrom="2025" title="Load all events for Finance"
   data-groupId="4" data-uniqueId="pmFinanceCommittee" data-categoryId="30"
   data-groupName="3:15 p.m. Finance Committee"><small>Older Meetings..</small></a>
<a href="#" class="older_meetings_click"
   data-yearFrom="2025" data-groupId="9" data-uniqueId="pmPlanningZoning"
   data-categoryId="81" data-groupName="5:00 p.m. Planning &amp; Zoning Commission">x</a>
"""


def test_normalize_doc_url_strips_trailing_space_before_query():
    assert (
        _normalize_doc_url("https://x/event/GetMinutesFile/Synopsis%20?mid=5048")
        == "https://x/event/GetMinutesFile/Synopsis?mid=5048"
    )
    assert (
        _normalize_doc_url("https://x/event/GetMinutesFile/Synopsis ?mid=5048")
        == "https://x/event/GetMinutesFile/Synopsis?mid=5048"
    )


def test_normalize_doc_url_canonicalizes_date_polluted_label():
    # Older portal rows bake the meeting date into the decorative path label.
    # Embedded slashes create extra path segments that 404 the link; the file is
    # served purely by aid/mid, so collapse the label to its keyword.
    assert (
        _normalize_doc_url("https://x/event/GetAgendaFile/11/2/21%20Agenda?aid=4748")
        == "https://x/event/GetAgendaFile/Agenda?aid=4748"
    )
    assert (
        _normalize_doc_url("https://x/event/GetAgendaFile/Agenda%2006-15-2021?aid=1")
        == "https://x/event/GetAgendaFile/Agenda?aid=1"
    )
    # Minutes vs Synopsis label is preserved (no swap), only date noise is dropped.
    assert (
        _normalize_doc_url("https://x/event/GetMinutesFile/8-3-21%20Canvassing%20Synopsis?mid=2")
        == "https://x/event/GetMinutesFile/Synopsis?mid=2"
    )
    assert (
        _normalize_doc_url("https://x/event/GetMinutesFile/Minutes?mid=4155")
        == "https://x/event/GetMinutesFile/Minutes?mid=4155"
    )
    # Clean URLs are untouched.
    assert (
        _normalize_doc_url("https://x/event/GetAgendaFile/Agenda?aid=5520")
        == "https://x/event/GetAgendaFile/Agenda?aid=5520"
    )


def test_parse_listing_emits_agenda_and_minutes_with_clean_urls():
    docs = parse_listing(_ROW_HTML, BASE)
    by_type = {d.doc_type: d for d in docs}
    assert set(by_type) == {"agenda", "minutes"}
    assert by_type["agenda"].body_name == "Finance Committee"
    assert str(by_type["agenda"].meeting_date) == "2026-06-09"
    # the trailing-space bug must be normalized out at parse time
    assert "%20?" not in by_type["minutes"].url
    assert by_type["minutes"].url.endswith("/Synopsis?mid=5048")
    assert by_type["minutes"].ref_id == "5048"


def test_parse_older_groups_extracts_params_and_unescapes_names():
    groups = parse_older_groups(_OLDER_HTML)
    assert len(groups) == 2
    fin = next(g for g in groups if g.group_id == "4")
    assert fin.category_id == "30"
    assert fin.unique_id == "pmFinanceCommittee"
    assert fin.group_name == "3:15 p.m. Finance Committee"
    # HTML entity in the data attribute is decoded for the POST payload
    pz = next(g for g in groups if g.group_id == "9")
    assert pz.group_name == "5:00 p.m. Planning & Zoning Commission"
