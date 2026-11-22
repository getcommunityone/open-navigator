"""YouTube API architecture — medallion layout (same pattern as HTL d0 / milliman).

Run:  python3 build_drawio.py
PNG:  see render.md / render_drawio.py (draw.io export engine)
"""
from _helpers import (
    ANALYTICS,
    APP_INT,
    COMPUTE,
    DB,
    DBX,
    GOOGLE,
    MGMT,
    NETWORK,
    SECURITY,
    STORAGE,
    TEAL,
    box,
    dbx_icon,
    edge,
    group,
    icon,
    lane,
    note,
    reset,
    save,
    title,
)

GREY, GREY_F = "#7D8998", "#F5F5F5"
BRONZE_C, BRONZE_F = "#A0522D", "#F6E7DA"
SILVER_C, SILVER_F = "#6B7280", "#EEF0F2"
GOLD_C, GOLD_F = "#B8860B", "#FFF6D6"
GREEN, GREEN_F = "#15803D", "#DCFCE7"
RED, RED_F = "#B91C1C", "#FEE2E2"
BLUE, BLUE_F = "#1E3A5F", "#DBEAFE"


def build_architecture():
    reset()
    title(
        "Architecture: public YouTube → API ingest → bronze / silver / gold → meeting pages (read + embed only)"
    )
    note(
        "API key only (no user OAuth). YouTube Data API v3 reads public metadata. "
        "Playback stays on YouTube (iframe + Open on YouTube). CommunityOne does not upload, edit, or delete videos.",
        40,
        48,
        1780,
        36,
    )

    # Lanes — same rhythm as HTL d0_medallion_architecture
    for label, x, w in [
        ("Source", 40, 260),
        ("Ingest", 320, 300),
        ("Bronze · Silver · Gold", 640, 620),
        ("Serve", 1280, 260),
        ("Consumer", 1560, 220),
    ]:
        lane(label, x, 95, w)

    # ---- Source ----
    group("g_yt", "YouTube (public content)", "ext", 40, 145, 260, 520)
    icon("yt_ch", "Public meeting\nchannels", "users", NETWORK, 118, 200, 48)
    icon("yt_vid", "Public videos\nmetadata + stream", "video", MGMT, 118, 330, 48)
    box(
        "yt_no",
        "Out of scope\nno upload / update / delete\nno Authorized Data / OAuth",
        60,
        470,
        220,
        70,
        RED,
        RED_F,
    )

    # ---- Ingest ----
    group("g_gcp", "Google Cloud · YouTube Data API v3", "google", 320, 145, 300, 250)
    icon("api_key", "API key pool\nYOUTUBE_API_KEY_*", "permissions", SECURITY, 360, 200, 44)
    icon("api_v3", "search · channels\nvideos · playlistItems", "api_gateway", APP_INT, 480, 200, 44)
    box("quota", "Read-only quota\npublic metadata JSON", 350, 310, 240, 50, GOOGLE, "#E8F0FE")

    group("g_scrape", "Open Navigator scrapers", "app", 320, 415, 300, 250)
    icon("disc", "Channel / video\ndiscovery + enrich", "search_document", ANALYTICS, 360, 470, 44)
    box(
        "vpn",
        "youtube.com page fetches\nvia VPN guard (#488)\nAPI host: googleapis.com",
        350,
        560,
        240,
        70,
        TEAL,
        "#E8F0F1",
    )

    # ---- Medallion warehouse ----
    group(
        "g_lake",
        "CommunityOne warehouse (Postgres) · medallion path for YouTube meeting metadata",
        "dbxlake",
        640,
        145,
        620,
        520,
    )
    box(
        "gov",
        "Governance: public metadata only · no private YouTube user data · Privacy §9 + Terms disclosures",
        660,
        185,
        580,
        44,
        SECURITY,
        "#FBE9EB",
    )
    box(
        "jobs",
        "Orchestration: scrapers + loaders → bronze; dbt bronze → staging → intermediate → marts",
        660,
        245,
        580,
        44,
        GREY,
        GREY_F,
    )

    box(
        "bronze",
        "BRONZE\nraw YouTube / event\npayloads (public JSON)\nvideo_id · channel_id",
        670,
        320,
        170,
        110,
        BRONZE_C,
        BRONZE_F,
    )
    box(
        "silver",
        "SILVER / staging\ncleaned metadata\njoined to jurisdictions\n& meeting keys",
        870,
        320,
        170,
        110,
        SILVER_C,
        SILVER_F,
    )
    box(
        "gold",
        "GOLD / marts\npublic meeting rows\nembed URL + title\nserved to the API",
        1070,
        320,
        170,
        110,
        GOLD_C,
        GOLD_F,
    )
    note(
        "bronze → silver: normalize public fields · silver → gold: meeting join, browse/search surfaces",
        670,
        445,
        560,
        36,
    )
    icon("db", "Postgres\nlocalhost / Neon", "database", DB, 760, 510, 48)
    icon("dbt", "dbt Core\nmedallion models", "gear", COMPUTE, 960, 510, 48)
    box(
        "api_svc",
        "FastAPI public schema\nmeeting + video metadata\nno YouTube write calls",
        870,
        590,
        280,
        50,
        TEAL,
        "#E8F0F1",
    )

    # ---- Serve ----
    group("g_web", "communityone.com", "app", 1280, 145, 260, 520)
    icon("meet", "Meeting page\nYouTube iframe", "client", TEAL, 1368, 210, 48)
    box(
        "embed",
        "Watch on YouTube\nOpen on YouTube →\n(stream stays on YT)",
        1310,
        320,
        200,
        70,
        TEAL,
        "#E8F0F1",
    )
    box(
        "legal",
        "Docs: Privacy §9\nTerms → YouTube ToS\nfooter Privacy / Terms",
        1310,
        430,
        200,
        80,
        GREEN,
        GREEN_F,
    )
    box(
        "no_ads",
        "No ads / tracking\nvia YouTube API",
        1310,
        550,
        200,
        55,
        RED,
        RED_F,
    )

    # ---- Consumer ----
    icon("citizen", "Citizen /\nresident", "user", TEAL, 1620, 230, 56)
    icon("advocate", "Advocate /\njournalist", "users", TEAL, 1620, 380, 56)
    icon("ops", "Operator\n(API keys / quota)", "business_people", GREY, 1620, 530, 56)

    # Edges
    edge("yt_ch", "api_v3", "public")
    edge("yt_vid", "api_v3", "")
    edge("api_key", "api_v3", "auth")
    edge("api_v3", "disc", "JSON")
    edge("disc", "bronze", "load", exit=(1, 0.5), entry=(0, 0.35), via=[(630, 494), (630, 358)])
    edge("bronze", "silver", "")
    edge("silver", "gold", "")
    edge("gold", "api_svc", "", exit=(0.5, 1), entry=(0.5, 0))
    edge("api_svc", "meet", "HTTPS", exit=(1, 0.5), entry=(0, 0.5), via=[(1260, 615), (1260, 234)])
    edge("meet", "citizen", "")
    edge("embed", "advocate", "", exit=(1, 0.5), entry=(0, 0.5), via=[(1540, 355), (1540, 408)])
    edge("meet", "yt_vid", "embed / watch", dashed=True, exit=(0.5, 0), entry=(1, 0.4), via=[(1410, 160), (300, 160), (300, 354)])
    edge("legal", "citizen", "disclosures", dashed=True, exit=(1, 0.2), entry=(0, 0.8), via=[(1540, 446), (1540, 290)])

    return save("yt1_architecture", 1820, 720)


if __name__ == "__main__":
    build_architecture()
