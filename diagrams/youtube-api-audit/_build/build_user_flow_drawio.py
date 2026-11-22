"""Standard flowchart shapes for the citizen YouTube watch journey (oval / rect / diamond)."""
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
        f'<mxCell id="{nid()}" value="{escape(text)}" style="text;html=1;fontSize=18;fontStyle=1;'
        f'align=left;" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="30" as="geometry"/></mxCell>'
    )


def note(text, x, y, w, h=40):
    cells.append(
        f'<mxCell id="{nid()}" value="{escape(text)}" style="text;html=1;fontSize=12;align=left;'
        f'fontColor=#545B64;whiteSpace=wrap;" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def terminal(cid, label, x, y, w=140, h=48):
    """Oval start/end."""
    style = (
        "ellipse;whiteSpace=wrap;html=1;aspect=fixed;fontSize=13;fontColor=#111827;"
        "strokeColor=#111827;strokeWidth=1.5;fillColor=#ffffff;"
    )
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label)}" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def process(cid, label, x, y, w=220, h=70):
    """Rectangle process / page."""
    style = (
        "rounded=0;whiteSpace=wrap;html=1;fontSize=12;fontColor=#111827;"
        "strokeColor=#111827;strokeWidth=1.5;fillColor=#ffffff;align=center;verticalAlign=middle;"
    )
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label).replace(chr(10), "&lt;br&gt;")}" style="{style}" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def decision(cid, label, x, y, w=200, h=100):
    """Diamond decision."""
    style = (
        "rhombus;whiteSpace=wrap;html=1;fontSize=12;fontColor=#111827;"
        "strokeColor=#111827;strokeWidth=1.5;fillColor=#ffffff;"
    )
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label).replace(chr(10), "&lt;br&gt;")}" style="{style}" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def subprocess(cid, label, x, y, w=200, h=70):
    """Predefined process (double vertical bars)."""
    style = (
        "shape=process;whiteSpace=wrap;html=1;fontSize=12;fontColor=#111827;"
        "strokeColor=#111827;strokeWidth=1.5;fillColor=#ffffff;size=0.12;"
    )
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label).replace(chr(10), "&lt;br&gt;")}" style="{style}" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def edge(src, dst, label="", exit=None, entry=None, via=(), dashed=False):
    pts = ""
    if exit:
        pts += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
    if entry:
        pts += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
    style = (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;html=1;endArrow=block;endFill=1;"
        f"strokeColor=#111827;strokeWidth=1.2;fontSize=11;fontColor=#111827;"
        f"labelBackgroundColor=#ffffff;{'dashed=1;' if dashed else ''}{pts}"
    )
    geo = '<mxGeometry relative="1" as="geometry">'
    if via:
        geo += '<Array as="points">' + "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in via) + "</Array>"
    geo += "</mxGeometry>"
    cells.append(
        f'<mxCell id="{nid()}" value="{escape(label)}" style="{style}" edge="1" parent="1" '
        f'source="{src}" target="{dst}">{geo}</mxCell>'
    )


def save(name, page_w=1400, page_h=1100):
    xml = (
        f'<mxfile host="app.diagrams.net" agent="open-navigator youtube-api-audit">'
        f'<diagram name="{name}"><mxGraphModel dx="1400" dy="1100" grid="1" gridSize="10" guides="1" '
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
        1200,
        28,
    )

    # Main column (center) — happy path down
    terminal("start", "Start", 520, 80, 120, 48)
    process("home", "Homepage\ncommunityone.com\nSearch place / topic / meeting", 460, 160, 240, 80)
    process("results", "Browse / search results\nPick a meeting", 460, 270, 240, 70)
    process("meeting", "Meeting page\ntitle · date · board\nmoney discussed", 460, 370, 240, 80)
    decision("has_rec", "YouTube\nrecording\nlinked?", 490, 480, 180, 110)

    # No branch (left)
    process("no_player", "Continue without player\nagenda / minutes / money", 120, 500, 240, 70)
    terminal("end_no", "End", 170, 620, 120, 48)

    # Yes → player
    process("player", "Meeting recording card\nYouTube iframe on page", 460, 640, 240, 70)
    decision("watch_how", "Watch how?", 490, 750, 180, 100)

    process("embed", "Play in-page embed\nstream hosted by YouTube", 160, 900, 240, 70)
    process("external", "Open / Watch on YouTube\nyoutube.com", 760, 900, 240, 70)

    decision("legal", "Read Privacy / Terms\nYouTube API notices?", 490, 1020, 180, 110)
    process("privacy", "Privacy Policy §9\nand/or Terms of Service\nYouTube API disclosures", 760, 1040, 260, 80)
    terminal("end_yes", "End", 520, 1180, 120, 48)

    # Out of journey (right)
    note("Not in this journey", 1080, 160, 220, 24)
    subprocess("never_up", "Upload video to\nYouTube via app", 1080, 200, 220, 70)
    subprocess("never_oauth", "YouTube OAuth login\nthrough CommunityOne", 1080, 300, 220, 70)

    # Edges
    edge("start", "home")
    edge("home", "results")
    edge("results", "meeting")
    edge("meeting", "has_rec")
    edge("has_rec", "no_player", "No", exit=(0, 0.5), entry=(1, 0.5))
    edge("no_player", "end_no")
    edge("has_rec", "player", "Yes", exit=(0.5, 1), entry=(0.5, 0))
    edge("player", "watch_how")
    edge("watch_how", "embed", "In page", exit=(0, 0.5), entry=(0.5, 0), via=[(250, 800)])
    edge("watch_how", "external", "Open on YT", exit=(1, 0.5), entry=(0.5, 0), via=[(880, 800)])
    edge("embed", "legal", "", exit=(0.5, 1), entry=(0, 0.5), via=[(280, 1075)])
    edge("external", "legal", "", exit=(0.5, 1), entry=(1, 0.5), via=[(880, 1075)])
    edge("legal", "privacy", "Yes", exit=(1, 0.5), entry=(0, 0.5))
    edge("legal", "end_yes", "No", exit=(0.5, 1), entry=(0.5, 0))
    edge("privacy", "end_yes", "", exit=(0.5, 1), entry=(1, 0.5), via=[(890, 1204)])
    edge("never_up", "end_yes", "never", dashed=True, exit=(0.5, 1), entry=(1, 0.5), via=[(1190, 1204)])
    edge("never_oauth", "never_up", "", dashed=True)

    return save("yt2_user_flow", 1400, 1280)


if __name__ == "__main__":
    build()
