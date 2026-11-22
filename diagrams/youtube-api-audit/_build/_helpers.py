"""draw.io helpers (same pattern as health-transformation-lab-nlp / milliman-panel-notes)."""
from pathlib import Path
from xml.sax.saxutils import escape as _escape

TEAL = "#354F52"
TEAL_F = "#E8F0F1"
GREY = "#7D8998"
GREY_F = "#F5F5F5"
BLUE = "#1E3A5F"
BLUE_F = "#DBEAFE"
ORANGE = "#C2410C"
ORANGE_F = "#FFEDD5"
GREEN = "#15803D"
GREEN_F = "#DCFCE7"
RED = "#B91C1C"
RED_F = "#FEE2E2"


def escape(t):
    return _escape(t, {'"': "&quot;"})


cells = []
_n = [0]
# Parallel list for PNG/SVG export: ("box"|"text"|"group", ...)
layout = []
anchors = {}  # cid -> (cx, cy, x, y, w, h)


def nid():
    _n[0] += 1
    return f"c{_n[0]}"


def reset():
    cells.clear()
    layout.clear()
    anchors.clear()
    _n[0] = 0
    cells.append('<mxCell id="0"/><mxCell id="1" parent="0"/>')


def title(text, x=40, y=10, w=1500):
    cells.append(
        f'<mxCell id="{nid()}" value="{escape(text)}" '
        f'style="text;html=1;fontSize=20;fontStyle=1;align=left;verticalAlign=middle;" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="40" as="geometry"/></mxCell>'
    )
    layout.append(("title", text, x, y, w, 40))


def note(text, x, y, w=1500, h=40):
    cells.append(
        f'<mxCell id="{nid()}" value="{escape(text)}" '
        f'style="text;html=1;fontSize=12;align=left;verticalAlign=top;whiteSpace=wrap;fontColor=#545B64;" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )
    layout.append(("note", text, x, y, w, h))


def group(cid, label, kind, x, y, w, h):
    styles = {
        "ext": "strokeColor=#7D8998;fillColor=none;dashed=1;",
        "plain": "strokeColor=#7D8998;fillColor=none;dashed=1;",
        "app": "strokeColor=#354F52;fillColor=#F8FAFA;",
        "google": "strokeColor=#4285F4;fillColor=#E8F0FE;",
    }
    style = (
        "rounded=0;whiteSpace=wrap;html=1;verticalAlign=top;align=left;spacingLeft=8;"
        f"fontStyle=1;fontColor=#232F3E;fontSize=13;{styles.get(kind, styles['plain'])}"
    )
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label)}" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )
    layout.append(("group", label, x, y, w, h, kind))


def lane(label, x, y, w, h=34):
    cells.append(
        f'<mxCell id="{nid()}" value="{escape(label)}" '
        f'style="rounded=0;whiteSpace=wrap;html=1;fillColor=#EAEDED;strokeColor=none;'
        f'fontSize=15;fontStyle=1;fontColor=#232F3E;" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )
    layout.append(("lane", label, x, y, w, h))


def box(cid, label, x, y, w, h, color=TEAL, fill=TEAL_F):
    style = (
        f"rounded=1;whiteSpace=wrap;html=1;fontSize=11;fontColor=#232F3E;"
        f"strokeColor={color};strokeWidth=2;fillColor={fill};"
    )
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label).replace(chr(10), "&lt;br&gt;")}" '
        f'style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )
    anchors[cid] = (x + w / 2, y + h / 2, x, y, w, h)
    layout.append(("box", label, x, y, w, h, color, fill))


def edge(src, dst, label="", dashed=False, exit=None, entry=None, via=()):
    pts = ""
    if exit:
        pts += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
    if entry:
        pts += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
    style = (
        "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
        "endArrow=block;endFill=1;strokeColor=#545B64;strokeWidth=1.5;fontSize=10;"
        f"fontColor=#232F3E;labelBackgroundColor=#ffffff;{'dashed=1;' if dashed else ''}{pts}"
    )
    geo = '<mxGeometry relative="1" as="geometry">'
    if via:
        geo += '<Array as="points">' + "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in via) + "</Array>"
    geo += "</mxGeometry>"
    cells.append(
        f'<mxCell id="{nid()}" value="{escape(label)}" style="{style}" edge="1" '
        f'parent="1" source="{src}" target="{dst}">{geo}</mxCell>'
    )
    layout.append(("edge", src, dst, label, dashed, list(via)))


def save(name, page_w=1600, page_h=900):
    xml = (
        f'<mxfile host="app.diagrams.net" agent="open-navigator youtube-api-audit build_drawio.py">'
        f'<diagram name="{name}"><mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" '
        f'guides="1" page="1" pageScale="1" pageWidth="{page_w}" pageHeight="{page_h}" '
        f'background="#ffffff"><root>' + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>"
    )
    out = Path(__file__).parent.parent / f"{name}.drawio"
    out.write_text(xml)
    print(name)
    return out, page_w, page_h
