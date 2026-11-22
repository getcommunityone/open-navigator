"""YouTube API architecture — Databricks-style visual language (teal + coral).

Reference: Data Intelligence Platform cards (dark teal headers, coral frame,
white cards, monochrome icons, medallion cylinders).
"""
from _helpers import (
    CORAL,
    TEAL_DK,
    coral_bar,
    cylinder,
    dashed_group,
    edge,
    header_panel,
    line_icon,
    note,
    platform_frame,
    reset,
    save,
    soft_card,
    teal_bar,
    title,
)


def build_architecture():
    reset()
    title("CommunityOne · YouTube API Services architecture", 40, 16, 1700)
    note(
        "Read + embed only · API key auth (no user OAuth) · public metadata via YouTube Data API v3 · "
        "playback stays on YouTube · CommunityOne does not upload, edit, or delete videos",
        40,
        52,
        1700,
        32,
    )

    # ========== LEFT: Sources ==========
    header_panel(
        "src_yt",
        "YouTube (public)",
        "",
        40,
        110,
        280,
        420,
    )
    line_icon("yt_ch", "Meeting channels\ncity · board · school", "users", 150, 170, 44)
    # mxgraph.aws4.video does not exist — use multimedia (renders as media tile)
    line_icon("yt_vid", "Public videos\ntitle · thumb · stream", "multimedia", 150, 280, 44)
    soft_card(
        "yt_out",
        "Out of scope\nno upload / update / delete\nno Authorized Data · no OAuth",
        60,
        400,
        240,
        90,
        CORAL,
    )

    # ========== CENTER: Platform (coral frame) ==========
    platform_frame(
        "plat",
        "Open Navigator data platform",
        360,
        100,
        980,
        560,
    )
    teal_bar("orch", "Orchestration · scrapers + loaders · dbt Core (bronze → staging → marts)", 380, 140, 940, 34)

    # Ingest column
    dashed_group("ing", "Data ingestion", 380, 190, 220, 340)
    soft_card("api_key", "1  API key pool\nYOUTUBE_API_KEY_*\nserver-side only", 395, 230, 190, 70)
    soft_card("api_v3", "2  YouTube Data API v3\nsearch · channels\nvideos · playlistItems", 395, 315, 190, 80)
    soft_card("disc", "3  Discovery + enrich\n+ VPN guard for\nyoutube.com pages", 395, 410, 190, 80)

    # Medallion / ETL
    dashed_group("etl", "Medallion warehouse (Postgres)", 620, 190, 400, 340)
    cylinder("bronze", "BRONZE\nraw public JSON", 645, 240, 100, 90, "#E35D4B", "#FFF5F3")
    cylinder("silver", "SILVER\nclean + join", 770, 240, 100, 90, "#5F6B6D", "#F4F5F5")
    cylinder("gold", "GOLD\nmeeting marts", 895, 240, 100, 90, "#C9A227", "#FFF9E6")
    soft_card(
        "norm",
        "bronze→silver: normalize public fields\nsilver→gold: meeting join · browse/search",
        645,
        360,
        350,
        55,
    )
    soft_card("store", "Postgres / Neon  ·  public schema API  ·  no YouTube write calls", 645, 430, 350, 55)

    # Serving inside platform
    dashed_group("serve", "Serving", 1040, 190, 280, 340)
    header_panel("svc_meet", "Meeting pages", "YouTube iframe embed\nWatch / Open on YouTube", 1055, 230, 250, 100)
    header_panel("svc_legal", "Legal disclosures", "Privacy Policy §9\nTerms → YouTube ToS\nSite footer links", 1055, 350, 250, 110)
    soft_card("svc_no", "No ads / device tracking\nvia YouTube API Services", 1055, 480, 250, 40, CORAL)

    # Foundation bar
    coral_bar(
        "found",
        "Foundation · public metadata only · Privacy §9 + Terms · Google Privacy Policy for playback",
        380,
        600,
        940,
        36,
    )

    # ========== RIGHT: Downstream ==========
    line_icon("citizen", "Citizen /\nresident", "user", 1420, 160, 48)
    soft_card("out1", "Watch meeting recording\n(embed or youtube.com)", 1380, 240, 220, 55)
    line_icon("advocate", "Advocate /\njournalist", "users", 1420, 330, 48)
    soft_card("out2", "Cite public meeting video\n+ money / agenda context", 1380, 410, 220, 55)
    # business_people is not in aws4 — identity_and_access_management reads as ops/admin
    line_icon("ops", "Operator", "identity_and_access_management", 1420, 500, 48)
    soft_card("out3", "API keys · quota ·\ninventory health", 1380, 580, 220, 50)

    # Edges — clean left→right
    edge("yt_ch", "api_key", "", exit=(1, 0.5), entry=(0, 0.5), via=[(340, 192), (340, 265)])
    edge("yt_vid", "api_v3", "", exit=(1, 0.5), entry=(0, 0.5), via=[(340, 302), (340, 355)])
    edge("api_key", "api_v3", "")
    edge("api_v3", "disc", "")
    edge("disc", "bronze", "JSON", exit=(1, 0.5), entry=(0, 0.5), via=[(610, 450), (610, 285)])
    edge("bronze", "silver", "")
    edge("silver", "gold", "")
    edge("gold", "svc_meet", "", exit=(1, 0.3), entry=(0, 0.5), via=[(1030, 267), (1030, 280)])
    edge("store", "svc_meet", "API", exit=(1, 0.5), entry=(0, 0.8), via=[(1030, 457), (1030, 310)])
    edge("svc_meet", "out1", "")
    edge("svc_legal", "out2", "disclosures", dashed=True)
    edge("svc_meet", "yt_vid", "embed / watch", dashed=True, exit=(0.5, 0), entry=(1, 0.35), via=[(1180, 120), (300, 120), (300, 300)])

    return save("yt1_architecture", 1680, 720)


if __name__ == "__main__":
    build_architecture()
