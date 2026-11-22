"""Citizen YouTube watch journey — oval / rect / diamond flowchart.

Routing rule: vias only in empty corridors; Yes/No as opaque label cells.
"""
from pathlib import Path
from xml.sax.saxutils import escape as _escape

cells = []
_n = [0]


def nid():
    _n[0] += 1
    return f"c{_n[0]}"


def reset():
    cells.clear()
    _n[0] = 0
    cells.append('<mxCell id="0"/><mxCell id="1" parent="0"/>')


def escape(t):
    return _escape(t, {'"': "&quot;"})


def title(text, x=40, y=10, w=1400):
    cells.append(
        f'<mxCell id="{nid()}" value="{escape(text)}" style="text;html=1;fontSize=18;fontStyle=1;align=left;" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="30" as="geometry"/></mxCell>'
    )


def note(text, x, y, w, h=40):
    cells.append(
        f'<mxCell id="{nid()}" value="{escape(text)}" style="text;html=1;fontSize=12;align=left;'
        f'fontColor=#545B64;whiteSpace=wrap;" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def edge_label(text, x, y, w=70, h=22):
    cells.append(
        f'<mxCell id="{nid()}" value="{escape(text)}" style="rounded=0;whiteSpace=wrap;html=1;fontSize=11;'
        f'fontColor=#111827;fillColor=#ffffff;strokeColor=none;align=center;verticalAlign=middle;" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def terminal(cid, label, x, y, w=120, h=48):
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label)}" style="ellipse;whiteSpace=wrap;html=1;fontSize=13;'
        f'fontColor=#111827;strokeColor=#111827;strokeWidth=1.5;fillColor=#ffffff;" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def process(cid, label, x, y, w=280, h=72):
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label).replace(chr(10), "&lt;br&gt;")}" '
        f'style="rounded=0;whiteSpace=wrap;html=1;fontSize=12;fontColor=#111827;strokeColor=#111827;'
        f'strokeWidth=1.5;fillColor=#ffffff;align=center;verticalAlign=middle;spacing=8;" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def decision(cid, label, x, y, w=200, h=120):
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label).replace(chr(10), "&lt;br&gt;")}" '
        f'style="rhombus;whiteSpace=wrap;html=1;fontSize=12;fontColor=#111827;strokeColor=#111827;'
        f'strokeWidth=1.5;fillColor=#ffffff;spacing=10;" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def out_card(cid, label, x, y, w=340, h=96):
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label).replace(chr(10), "&lt;br&gt;")}" '
        f'style="rounded=1;whiteSpace=wrap;html=1;fontSize=12;fontColor=#111827;strokeColor=#111827;'
        f'strokeWidth=1.5;dashed=1;dashPattern=6 4;fillColor=#ffffff;align=center;verticalAlign=middle;'
        f'spacing=14;spacingTop=12;spacingBottom=12;spacingLeft=16;spacingRight=16;" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def edge(src, dst, exit=None, entry=None, via=()):
    pts = ""
    if exit:
        pts += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
    if entry:
        pts += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
    style = (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
        f"endArrow=block;endFill=1;strokeColor=#111827;strokeWidth=1.2;{pts}"
    )
    geo = '<mxGeometry relative="1" as="geometry">'
    if via:
        geo += '<Array as="points">' + "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in via) + "</Array>"
    geo += "</mxGeometry>"
    cells.append(
        f'<mxCell id="{nid()}" value="" style="{style}" edge="1" parent="1" '
        f'source="{src}" target="{dst}">{geo}</mxCell>'
    )


def save(name, page_w=1600, page_h=1500):
    xml = (
        f'<mxfile host="app.diagrams.net" agent="open-navigator youtube-api-audit">'
        f'<diagram name="{name}"><mxGraphModel dx="1600" dy="1500" grid="1" gridSize="10" guides="1" '
        f'page="1" pageScale="1" pageWidth="{page_w}" pageHeight="{page_h}" background="#ffffff"><root>'
        + "".join(cells)
        + "</root></mxGraphModel></diagram></mxfile>"
    )
    out = Path(__file__).parent.parent / f"{name}.drawio"
    out.write_text(xml)
    print(name)
    return out


def build():
    reset()
    title("User flow: citizen watches a meeting recording on CommunityOne (YouTube embed; no upload)")
    note(
        "Standard flowchart shapes. Journey never includes YouTube OAuth or CommunityOne uploading video.",
        40,
        42,
        1400,
        28,
    )

    # Main spine
    terminal("start", "Start", 590, 80, 120, 48)
    process("home", "Homepage · communityone.com\nSearch place / topic / meeting", 510, 160, 280, 72)
    process("results", "Browse / search results\nPick a meeting", 510, 270, 280, 64)
    process("meeting", "Meeting page\ntitle · date · board · money discussed", 510, 370, 280, 72)
    decision("has_rec", "YouTube recording\nlinked?", 530, 480, 240, 130)

    process("no_player", "Continue without player\nagenda / minutes / money", 100, 500, 280, 70)
    terminal("end_no", "End", 180, 640, 120, 48)

    process("player", "Meeting recording card\nYouTube iframe on page", 510, 650, 280, 70)
    decision("watch_how", "Watch how?", 540, 770, 220, 120)

    # Watch options — wide gap so corridors don't share x with privacy later
    process("embed", "Play in-page embed\nstream hosted by YouTube", 100, 960, 280, 70)
    process("external", "Open / Watch on YouTube\nyoutube.com", 960, 960, 280, 70)

    # Legal: inputs enter from the TOP (corridor y=1070 is empty)
    decision("legal", "Read Privacy / Terms\n(YouTube API notices)?", 520, 1120, 260, 140)

    # Privacy sits to the right of End path; End below legal
    terminal("end_yes", "End", 590, 1320, 120, 48)
    process(
        "privacy",
        "Privacy Policy §9\nand/or Terms of Service\nYouTube API disclosures",
        900,
        1260,
        300,
        100,
    )

    # Out of journey
    note("Not in this journey", 1180, 150, 340, 24)
    out_card("never_up", "Upload video to YouTube\nvia CommunityOne", 1180, 185, 340, 96)
    out_card("never_oauth", "YouTube OAuth login\nthrough CommunityOne", 1180, 305, 340, 96)
    note("(no path from the journey)", 1180, 420, 340, 24)

    # Spine
    edge("start", "home", exit=(0.5, 1), entry=(0.5, 0))
    edge("home", "results", exit=(0.5, 1), entry=(0.5, 0))
    edge("results", "meeting", exit=(0.5, 1), entry=(0.5, 0))
    edge("meeting", "has_rec", exit=(0.5, 1), entry=(0.5, 0))

    edge("has_rec", "no_player", exit=(0, 0.5), entry=(1, 0.5))
    edge_label("No", 420, 500, 36, 20)
    edge("no_player", "end_no", exit=(0.5, 1), entry=(0.5, 0))
    edge("has_rec", "player", exit=(0.5, 1), entry=(0.5, 0))
    edge_label("Yes", 670, 610, 36, 20)
    edge("player", "watch_how", exit=(0.5, 1), entry=(0.5, 0))

    # Watch branches — labels near diamond only
    edge("watch_how", "embed", exit=(0, 0.5), entry=(0.5, 0), via=[(240, 825), (240, 930)])
    edge_label("In page", 320, 790, 70, 20)
    edge("watch_how", "external", exit=(1, 0.5), entry=(0.5, 0), via=[(1100, 825), (1100, 930)])
    edge_label("Open on YT", 760, 790, 90, 20)

    # Converge into TOP of legal along y=1070 (below watch boxes, above legal)
    edge("embed", "legal", exit=(0.5, 1), entry=(0.25, 0), via=[(240, 1070), (600, 1070)])
    edge("external", "legal", exit=(0.5, 1), entry=(0.75, 0), via=[(1100, 1070), (700, 1070)])

    # No → End straight down
    edge("legal", "end_yes", exit=(0.5, 1), entry=(0.5, 0))
    edge_label("No", 670, 1265, 36, 20)

    # Yes → privacy (right), then down/left under End into End's right side
    edge("legal", "privacy", exit=(1, 0.5), entry=(0, 0.3), via=[(850, 1180), (850, 1267)])
    edge_label("Yes", 760, 1160, 36, 20)
    edge("privacy", "end_yes", exit=(0.5, 1), entry=(1, 0.5), via=[(1050, 1380), (730, 1380)])

    return save("yt2_user_flow", 1600, 1480)


if __name__ == "__main__":
    build()
