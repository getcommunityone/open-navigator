"""YouTube API audit diagrams — same draw.io builder pattern as HTL / milliman.

Run from this directory:
  python3 build_drawio.py
  python3 render_png.py
"""
from __future__ import annotations

from _helpers import (
    BLUE,
    BLUE_F,
    GREEN,
    GREEN_F,
    GREY,
    GREY_F,
    ORANGE,
    ORANGE_F,
    RED,
    RED_F,
    TEAL,
    TEAL_F,
    box,
    edge,
    group,
    lane,
    note,
    reset,
    save,
    title,
)


def build_architecture():
    reset()
    title("CommunityOne — YouTube API Services architecture (read + embed only; no uploads)")
    note(
        "API key auth only (no user OAuth). Public metadata via YouTube Data API v3. "
        "Playback stays on YouTube (iframe embed + Open on YouTube). We do not upload, edit, or delete videos.",
        40,
        50,
        1520,
        36,
    )

    lane("Public YouTube", 40, 100, 280)
    lane("Google Cloud", 340, 100, 300)
    lane("CommunityOne ingest", 660, 100, 360)
    lane("Warehouse", 1040, 100, 260)
    lane("Product (communityone.com)", 1320, 100, 280)

    group("g_yt", "YouTube (public content)", "ext", 40, 150, 280, 420)
    box("yt_ch", "Public meeting channels\ncity councils · boards\nschool districts", 60, 200, 240, 70, GREY, GREY_F)
    box("yt_vid", "Public videos\ntitles · descriptions\nthumbnails · publish dates", 60, 300, 240, 70, GREY, GREY_F)
    box("yt_no", "NOT used\nupload / update / delete\nprivate or Authorized Data", 60, 420, 240, 80, RED, RED_F)

    group("g_gcp", "Google Cloud project", "google", 340, 150, 300, 420)
    box("api_key", "API key (server-side)\nYOUTUBE_API_KEY_* pool\nno end-user OAuth", 360, 200, 260, 70, BLUE, BLUE_F)
    box("api_v3", "YouTube Data API v3\nsearch.list · channels.list\nvideos.list · playlistItems", 360, 300, 260, 80, BLUE, BLUE_F)
    box("quota", "Quota / rate limits\nread-only discovery", 360, 420, 260, 60, BLUE, BLUE_F)

    group("g_on", "Open Navigator scrapers", "app", 660, 150, 360, 420)
    box("disc", "Channel / video discovery\njurisdiction websites +\nYouTube API enrichment", 680, 200, 320, 80, TEAL, TEAL_F)
    box("meta", "Store public metadata only\nvideo_id · channel_id\ntitle · url · published_at", 680, 310, 320, 80, TEAL, TEAL_F)
    box("vpn", "YouTube page fetches\nvia VPN guard (scrapers)\nAPI calls use Google APIs host", 680, 420, 320, 80, ORANGE, ORANGE_F)

    group("g_db", "Postgres warehouse", "plain", 1040, 150, 260, 420)
    box("bronze", "bronze YouTube / events\nraw public payloads", 1060, 220, 220, 70, GREY, GREY_F)
    box("marts", "public meeting marts\njoin video → meeting", 1060, 330, 220, 70, GREY, GREY_F)
    box("serve", "API serves metadata +\nembed URL to web app", 1060, 440, 220, 70, GREY, GREY_F)

    group("g_web", "Web app + docs", "app", 1320, 150, 280, 420)
    box("meet", "Meeting page\nYouTube iframe embed\nWatch / Open on YouTube", 1340, 210, 240, 90, TEAL, TEAL_F)
    box("legal", "Privacy §9 + Terms\nYouTube API disclosures\nGoogle Privacy Policy link", 1340, 330, 240, 90, GREEN, GREEN_F)
    box("footer", "Homepage / docs footer\nPrivacy · Terms links", 1340, 450, 240, 60, GREEN, GREEN_F)

    edge("yt_ch", "api_v3", "public metadata")
    edge("yt_vid", "api_v3", "")
    edge("api_key", "api_v3", "auth")
    edge("api_v3", "disc", "JSON")
    edge("disc", "meta", "")
    edge("meta", "bronze", "load")
    edge("bronze", "marts", "dbt")
    edge("marts", "serve", "")
    edge("serve", "meet", "HTTPS")
    edge("meet", "yt_vid", "embed / watch on YT", dashed=True, exit=(0.5, 0), entry=(1, 0.5), via=[(1460, 160), (320, 160), (320, 335)])

    return save("yt1_architecture", 1640, 620)


def build_user_flow():
    reset()
    title("CommunityOne — user flow for meeting recordings (YouTube embed; no upload)")
    note(
        "Citizens never grant YouTube OAuth to CommunityOne. They watch public meeting video on YouTube "
        "(embedded player or Open on YouTube). CommunityOne does not upload video to YouTube.",
        40,
        50,
        1520,
        36,
    )

    lane("Citizen", 40, 110, 300)
    lane("communityone.com", 360, 110, 420)
    lane("YouTube", 800, 110, 360)
    lane("Out of scope", 1180, 110, 380)

    box("u1", "1. Open Open Navigator\nSearch place / meeting / topic", 60, 180, 260, 70, TEAL, TEAL_F)
    box("u2", "2. Open a meeting page\nwith a linked recording", 60, 290, 260, 70, TEAL, TEAL_F)
    box("u3", "3. Watch in-page player\nor click Open on YouTube", 60, 400, 260, 70, TEAL, TEAL_F)
    box("u4", "4. Optionally read Privacy §9\n/ Terms (YouTube API notices)", 60, 510, 260, 70, GREEN, GREEN_F)

    box("a1", "Web app loads meeting\nfrom public API / warehouse", 390, 180, 360, 70, TEAL, TEAL_F)
    box("a2", "Shows title, date, board\n+ YouTube video_id metadata", 390, 290, 360, 70, TEAL, TEAL_F)
    box("a3", "Renders youtube.com embed\n+ Watch / Open on YouTube link", 390, 400, 360, 70, TEAL, TEAL_F)
    box("a4", "Docs site: Privacy Policy §9\nTerms → YouTube ToS acknowledgment", 390, 510, 360, 70, GREEN, GREEN_F)

    box("y1", "Public video / channel\nalready published by the city", 820, 200, 320, 80, GREY, GREY_F)
    box("y2", "YouTube player serves stream\n(user stays under YouTube ToS)", 820, 340, 320, 80, GREY, GREY_F)
    box("y3", "Google Privacy Policy applies\nto YouTube playback", 820, 470, 320, 70, BLUE, BLUE_F)

    box("x1", "CommunityOne does NOT\nupload videos to YouTube", 1200, 220, 340, 80, RED, RED_F)
    box("x2", "No YouTube write APIs\nNo Authorized Data access", 1200, 340, 340, 80, RED, RED_F)
    box("x3", "No ads / device tracking\nvia YouTube API Services", 1200, 460, 340, 80, RED, RED_F)

    edge("u1", "a1", "")
    edge("a1", "u2", "")
    edge("u2", "a2", "")
    edge("a2", "a3", "")
    edge("a3", "u3", "")
    edge("u3", "y2", "play / open")
    edge("y1", "y2", "")
    edge("u4", "a4", "read")
    edge("a3", "y1", "video_id", dashed=True)

    return save("yt2_user_flow", 1600, 640)


if __name__ == "__main__":
    build_architecture()
    build_user_flow()
