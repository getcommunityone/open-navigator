"""Granicus / Legistar meeting readers (#536). No network: httpx.MockTransport + fixtures.

Fixtures in ``fixtures/platforms``: ``legistar_*.json`` were recorded from the public
Legistar Web API on 2026-11-17 and trimmed. ``granicus_*`` are hand-built in the
Granicus page structure: Granicus portals disallow all crawlers in robots.txt, so no
page was recorded from one.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Callable

import httpx
import pytest

from scrapers.platforms import granicus, legistar
from scrapers.platforms.discover import Candidate, candidate_slugs, legistar_client_from_url, probe_legistar, survey_targets
from scrapers.platforms.http import Blocked, PoliteClient, RobotsDisallowed
from scrapers.platforms.model import CaptionCue, MeetingCaption, PlatformMeeting, PortalResult
from scrapers.platforms.store import _upsert_sql, caption_row, meeting_row, portal_row
from scrapers.discovery.survey_meeting_sources import Government

FIX = Path(__file__).parent / "fixtures" / "platforms"


def fx(name: str) -> str:
    return (FIX / name).read_text()


def polite(handler: Callable[[httpx.Request], httpx.Response]) -> PoliteClient:
    return PoliteClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)), min_interval_s=0, use_vpn_bypass=False)


def run(coro):
    return asyncio.run(coro)


# ----------------------------------------------------------------------- http


def test_robots_disallow_all_blocks_every_page():
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.path)
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: Googlebot\nDisallow: /JSON.php\n\nUser-agent: *\nDisallow: /\n")
        return httpx.Response(200, text="<html>should not be fetched</html>")

    async def go():
        async with polite(handler) as http:
            with pytest.raises(RobotsDisallowed):
                await http.get("https://x.granicus.com/ViewPublisher.php?view_id=1")

    run(go())
    assert seen == ["/robots.txt"]


def test_robots_404_allows_and_user_agent_is_descriptive():
    agents: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        agents.append(req.headers["user-agent"])
        if req.url.path == "/robots.txt":
            return httpx.Response(404, text="nope")
        return httpx.Response(200, json=[])

    async def go():
        async with polite(handler) as http:
            return await http.get("https://webapi.legistar.com/v1/x/events")

    assert run(go()).status_code == 200
    assert all(a.startswith("OpenNavigatorMeetingReader/") and "@" not in a for a in agents)


def test_robots_5xx_means_disallow():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503) if req.url.path == "/robots.txt" else httpx.Response(200)

    async def go():
        async with polite(handler) as http:
            return await http.allowed("https://x.example/page")

    assert run(go()) is False


def test_403_is_reported_as_blocked_not_retried_around():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(403, text="Access denied", headers={"content-type": "text/html"})

    async def go():
        async with polite(handler) as http:
            with pytest.raises(Blocked):
                await http.get("https://x.example/page")

    run(go())
    assert calls.count("/page") == 1


# ----------------------------------------------------------------------- legistar


def test_rtf_to_text():
    rtf = r"{\rtf1\ansi{\fonttbl{\f0\fnil Arial;}}{\colortbl ;\red0\green0\blue0;}\pard\fs24 Called to order at 9:00 a.m.\par Motion \'93carried\'94 " + "\\" + r"u8212? 7-0.\par}"
    assert legistar.rtf_to_text(rtf) == "Called to order at 9:00 a.m.\nMotion “carried” — 7-0."
    assert legistar.rtf_to_text("  plain text ") == "plain text"
    assert legistar.rtf_to_text(None) is None


def test_classify_error():
    payload = json.loads(fx("legistar_not_configured.json"))
    assert legistar.classify_error(payload)[0] == "not_configured"
    assert legistar.classify_error([]) is None


def test_meeting_from_recorded_event_and_items():
    events = {e["EventId"]: e for e in json.loads(fx("legistar_dakota_events.json"))}
    items = json.loads(fx("legistar_dakota_1505_eventitems.json"))
    m = legistar.meeting_from_event(
        "dakota", events[1505], items, jurisdiction_id="dakota_27037", state_code="MN", granicus_host="dakota.granicus.com"
    )
    assert m.meeting_uid == "dakota:1505"
    assert m.meeting_date == date(2026, 10, 27)
    assert m.body_name == "Board of Commissioners"
    assert m.agenda_url.endswith("_Agenda.pdf") and m.minutes_url.endswith("_Minutes.pdf")
    assert m.video_clip_id == "1357"
    assert m.video_url == "https://dakota.granicus.com/MediaPlayer.php?clip_id=1357"
    assert m.video_url_source == "granicus_clip"
    assert m.transcription_status == "queued_whisper"
    assert m.minutes_text and "{\\rtf" not in m.minutes_text and "called to order" in m.minutes_text.lower()
    assert m.agenda_text and "Call to Order" in m.agenda_text
    assert m.source_modified_at is not None and m.source_modified_at.tzinfo is not None


def test_clip_without_known_host_is_not_queued():
    event = json.loads(fx("legistar_dakota_events.json"))[0]
    m = legistar.meeting_from_event("dakota", event, None)
    assert m.video_url is None
    assert m.transcription_status == "video_url_unknown"
    assert m.agenda_text is None and m.minutes_text is None


def test_minutes_text_needs_a_note_or_action_text():
    assert legistar.minutes_text([{"EventItemTitle": "Item", "EventItemPassedFlagName": "Pass"}]) is None


def test_minutes_text_includes_roll_call_votes():
    items = [
        {
            "EventItemId": 1,
            "EventItemTitle": "Approve agenda",
            "EventItemMinutesSequence": 1,
            "EventItemActionName": "Approved",
            "EventItemActionText": "Motion carried.",
            "EventItemPassedFlagName": "Pass",
        }
    ]
    votes = {
        1: [
            {"VoteId": 10, "VotePersonName": "Ada", "VoteValueName": "Ayes", "VoteSort": 1},
            {"VoteId": 11, "VotePersonName": "Bea", "VoteValueName": "Nays", "VoteSort": 2},
        ]
    }
    text = legistar.minutes_text(items, votes)
    assert text is not None
    assert "Action: Approved - Pass" in text
    assert "Roll call: Ada: Ayes; Bea: Nays" in text
    payload = legistar.votes_json_payload(items, votes)
    assert payload[0]["event_item_id"] == 1
    assert payload[0]["votes"][0]["person_name"] == "Ada"


def test_events_url_filters_dates():
    url = legistar.events_url("dakota", date(2025, 1, 1), until=date(2026, 1, 1))
    assert "datetime%272025-01-01%27" in url and "datetime%272026-01-01%27" in url and "%24top" not in url


def test_read_client_skips_unchanged_and_reports_not_configured():
    events = json.loads(fx("legistar_dakota_events.json"))
    items = fx("legistar_dakota_1505_eventitems.json")
    item_calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path.startswith("/v1/loudoun/"):
            return httpx.Response(500, text=fx("legistar_not_configured.json"))
        if req.url.path.endswith("/votes"):
            return httpx.Response(200, json=[])
        if req.url.path.endswith("/eventitems"):
            item_calls.append(req.url.path)
            return httpx.Response(200, text=items)
        return httpx.Response(200, json=events)

    known = {"dakota:1500": legistar._parse_utc(events[0]["EventLastModifiedUtc"])}

    async def go():
        async with polite(handler) as http:
            ok = await legistar.read_client(http, "dakota", since=date(2026, 1, 1), known_modified=known,
                                            today=date(2026, 11, 17))
            bad = await legistar.read_client(http, "loudoun", since=date(2026, 1, 1))
            return ok, bad

    ok, bad = run(go())
    assert ok.status == "ok"
    assert [m.meeting_uid for m in ok.meetings] == ["dakota:1505"]
    assert item_calls == ["/v1/dakota/events/1505/eventitems"]
    assert bad.status == "not_configured" and not bad.meetings


# ----------------------------------------------------------------------- granicus


def test_parse_view_publisher_rows():
    rows = granicus.parse_view_publisher(fx("granicus_view_publisher.html"), "example.granicus.com", 1)
    by = {(r["clip_id"], r["event_id"]): r for r in rows}
    council = by[("5501", None)]
    assert council["name"] == "City Council Regular Meeting"
    assert council["meeting_date"] == date(2026, 11, 4)
    assert council["minutes_url"] == "https://example.granicus.com/MinutesViewer.php?view_id=1&clip_id=5501"
    assert council["video_url"] == "https://example.granicus.com/MediaPlayer.php?view_id=1&clip_id=5501"
    assert by[("5490", None)]["agenda_url"] is None
    upcoming = by[(None, "901")]
    assert upcoming["meeting_date"] == date(2026, 12, 2) and upcoming["video_url"] is None
    m = granicus.meeting_from_row("example.granicus.com", upcoming)
    assert m.meeting_uid == "example.granicus.com:event901" and m.transcription_status == "no_video"


def test_parse_rss():
    (item,) = granicus.parse_rss(fx("granicus_rss.xml"))
    assert item["clip_id"] == "5501" and item["meeting_date"] == date(2026, 11, 4)


def test_captions_from_player_track():
    url = granicus.caption_track_url(fx("granicus_player.html"), "https://example.granicus.com/MediaPlayer.php?clip_id=5501")
    assert url == "https://example.granicus.com/videos/5501/captions.vtt"
    cues = granicus.parse_captions(fx("granicus_captions.vtt"))
    assert [c.start for c in cues] == [1.0, 4.5]
    assert cues[0].text == "Good evening, I call this meeting to order."
    assert cues[1].duration == 4.75


def test_read_portal_robots_disallowed_makes_no_page_request():
    paths = []

    def handler(req: httpx.Request) -> httpx.Response:
        paths.append(req.url.path)
        return httpx.Response(200, text="User-agent: *\nDisallow: /\n")

    async def go():
        async with polite(handler) as http:
            return await granicus.read_portal(http, "https://loudoun.granicus.com/")

    res = run(go())
    assert res.status == "robots_disallowed" and not res.meetings
    assert paths == ["/robots.txt"]


def test_read_portal_allowed_reads_rows_and_captions():
    pages = {
        "/robots.txt": (404, ""),
        "/ViewPublisher.php": (200, fx("granicus_view_publisher.html")),
        "/MediaPlayer.php": (200, fx("granicus_player.html")),
        "/videos/5501/captions.vtt": (200, fx("granicus_captions.vtt")),
    }

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/MediaPlayer.php" and req.url.params.get("clip_id") != "5501":
            return httpx.Response(200, text="<html>no captions</html>")
        status, body = pages.get(req.url.path, (404, ""))
        return httpx.Response(status, text=body)

    async def go():
        async with polite(handler) as http:
            return await granicus.read_portal(http, "example.granicus.com", jurisdiction_id="example_0100000")

    res = run(go())
    assert res.status == "ok"
    status = {m.meeting_uid: m.transcription_status for m in res.meetings}
    assert status == {
        "example.granicus.com:event901": "no_video",
        "example.granicus.com:clip5501": "captions",
        "example.granicus.com:clip5490": "queued_whisper",
    }
    cap = next(m.caption for m in res.meetings if m.caption)
    assert cap.caption_source == "granicus_vtt" and "data center rezoning" in cap.raw_text


# ----------------------------------------------------------------------- discover / store


def test_survey_targets_pair_legistar_with_granicus_host():
    rows = [
        {"jurisdiction_id": "dakota_27037", "state_code": "MN", "platform": "granicus", "url": "https://dakota.granicus.com/", "data_center_site_id": "s1"},
        {"jurisdiction_id": "dakota_27037", "state_code": "MN", "platform": "legistar", "url": "https://dakota.legistar.com/", "data_center_site_id": "s1"},
        {"jurisdiction_id": "dakota_27037", "state_code": "MN", "platform": "legistar", "url": "https://dakota.legistar.com/", "data_center_site_id": "s2"},
        {"jurisdiction_id": "x_1", "state_code": "TX", "platform": "youtube", "url": "https://youtube.com/@x", "data_center_site_id": None},
    ]
    targets = survey_targets(rows)
    assert [(t.platform, t.portal) for t in targets] == [("granicus", "dakota.granicus.com"), ("legistar", "dakota")]
    assert targets[1].granicus_host == "dakota.granicus.com" and targets[1].data_center
    assert legistar_client_from_url("https://webapi.legistar.com/v1/fulton/events") == "fulton"


def test_probe_needs_api_and_a_calendar_page_naming_the_government():
    gov = Government("fulton_13121", "13121", "Fulton County", "GA", "Georgia", "county")
    c = Candidate(government=gov, data_center=True, extra_slugs=["fulton"])
    assert candidate_slugs(c)[:2] == ["fulton", "fultoncountyga"]

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.host == "webapi.legistar.com":
            client = req.url.path.split("/")[2]
            return httpx.Response(200, json=[{"BodyId": 1}]) if client in ("fulton", "fultoncountyga") else httpx.Response(500, json={"Message": "x", "ExceptionMessage": "LegistarConnectionString setting is not set up in InSite"})
        if req.url.host == "fulton.legistar.com":
            return httpx.Response(200, text="<title>Some City of Elsewhere - Calendar</title>", headers={"content-type": "text/html"})
        return httpx.Response(200, text="<title>Fulton County, Georgia - Calendar</title>", headers={"content-type": "text/html"})

    async def go():
        async with polite(handler) as http:
            return await probe_legistar(http, [c], target=5, max_probes=5)

    found, probed = run(go())
    assert probed == 1
    assert [(t.portal, t.found_via) for t in found] == [("fultoncountyga", "url_pattern")]


def test_store_rows_and_upsert_sql():
    m = PlatformMeeting(platform="granicus", meeting_uid="h:clip1", portal="h", meeting_date=date(2026, 1, 2),
                        title="Council\x00", video_url="https://h/MediaPlayer.php?clip_id=1",
                        caption=MeetingCaption("granicus_vtt", None, "vtt", "hi there", [CaptionCue(1.0, 2.0, "hi there")]))
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    row = meeting_row(m, now)
    # title, votes_json, has_captions, transcription_status (#633 inserted votes_json)
    assert row[6] == "Council" and row[18] is None and row[19] is True and row[20] == "captions"
    cap = caption_row(m, now)
    assert json.loads(cap[7]) == [{"start": 1.0, "duration": 2.0, "text": "hi there"}] and cap[8] == 1
    assert caption_row(PlatformMeeting("legistar", "a:1", "a"), now) is None
    sql = _upsert_sql("t", ("platform", "meeting_uid", "title"), ("platform", "meeting_uid"))
    assert sql.endswith("ON CONFLICT (platform, meeting_uid) DO UPDATE SET title = EXCLUDED.title")
    p = PortalResult("legistar", "a", "u", None, status="not_configured")
    assert portal_row(p, now)[7] == "not_configured"


def test_official_site_link_carries_the_state():
    from scrapers.platforms.discover import official_site_names_state

    ga = Government("fulton_13121", "13121", "Fulton County", "GA", "Georgia", "county")
    oh = Government("fulton_39051", "39051", "Fulton County", "OH", "Ohio", "county")
    html = '<a href="https://www.fultoncountyga.gov/">Home</a><a href="https://granicus.com/">x</a>'
    assert official_site_names_state(html, ga) is True
    assert official_site_names_state(html, oh) is False
    mn = Government("dakota_27037", "27037", "Dakota County", "MN", "Minnesota", "county")
    assert official_site_names_state('<a href="https://www.co.dakota.mn.us/x">', mn) is True
