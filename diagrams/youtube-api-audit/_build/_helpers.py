"""draw.io helpers — same module as health-transformation-lab-nlp / milliman-panel-notes."""
from pathlib import Path
from xml.sax.saxutils import escape as _escape
import base64


def escape(t):
    return _escape(t, {'"': "&quot;"})


STORAGE, APP_INT, SECURITY, NETWORK, COMPUTE, MGMT, ANALYTICS, DB, MIGRATION = (
    "#7AA116", "#E7157B", "#DD344C", "#8C4FFF", "#ED7100", "#E7157B", "#8C4FFF", "#C925D1", "#01A88D")
DBX = "#FF3621"
TEAL = "#354F52"
GOOGLE = "#4285F4"

cells = []
_n = [0]


def nid():
    _n[0] += 1
    return f"c{_n[0]}"


def reset():
    cells.clear()
    _n[0] = 0
    cells.append('<mxCell id="0"/><mxCell id="1" parent="0"/>')


def title(text, x=40, y=10, w=1500):
    cells.append(
        f'<mxCell id="{nid()}" value="{escape(text)}" style="text;html=1;fontSize=20;fontStyle=1;'
        f'align=left;verticalAlign=middle;" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="40" as="geometry"/></mxCell>'
    )


def note(text, x, y, w=1500, h=40):
    cells.append(
        f'<mxCell id="{nid()}" value="{escape(text)}" style="text;html=1;fontSize=12;align=left;'
        f'verticalAlign=top;whiteSpace=wrap;fontColor=#545B64;" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def group(cid, label, kind, x, y, w, h):
    styles = {
        "cloud": "grIcon=mxgraph.aws4.group_aws_cloud_alt;strokeColor=#232F3E;fillColor=none;",
        "vpc": "grIcon=mxgraph.aws4.group_vpc;strokeColor=#8C4FFF;fillColor=none;",
        "private": "grIcon=mxgraph.aws4.group_security_group;strokeColor=#00A4A6;fillColor=#E6F6F7;",
        "public": "grIcon=mxgraph.aws4.group_security_group;strokeColor=#7AA116;fillColor=#F2F6E8;",
        "dbx": "grIcon=mxgraph.aws4.group_corporate_data_center;strokeColor=#FF3621;fillColor=none;",
        "ext": "grIcon=mxgraph.aws4.group_corporate_data_center;strokeColor=#7D8998;fillColor=none;dashed=1;",
        "plain": "strokeColor=#7D8998;fillColor=none;dashed=1;",
        "onprem": "grIcon=mxgraph.aws4.group_corporate_data_center;strokeColor=#232F3E;fillColor=none;",
        "saas": "grIcon=mxgraph.aws4.group_corporate_data_center;strokeColor=#0073FF;fillColor=none;dashed=1;",
        "dbxlake": "strokeColor=#FF3621;fillColor=#FFF7F5;",
        "google": "grIcon=mxgraph.aws4.group_aws_cloud_alt;strokeColor=#4285F4;fillColor=#E8F0FE;",
        "app": "grIcon=mxgraph.aws4.group_corporate_data_center;strokeColor=#354F52;fillColor=#F8FAFA;",
    }
    style = (
        "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],[1,1],"
        "[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]];outlineConnect=0;"
        "gradientColor=none;dashed=0;verticalAlign=top;align=left;spacingLeft=30;fontStyle=1;"
        "fontColor=#232F3E;html=1;whiteSpace=wrap;shape=mxgraph.aws4.group;fontSize=13;"
        + styles[kind]
    )
    if kind in ("plain", "dbxlake"):
        style = (
            "rounded=0;whiteSpace=wrap;html=1;verticalAlign=top;align=left;spacingLeft=8;"
            f"fontStyle=1;fontColor=#232F3E;fontSize=13;{styles[kind]}"
        )
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label)}" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def icon(cid, label, res, color, x, y, size=64):
    style = (
        "sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;dashed=0;"
        "verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=11;"
        f"fontStyle=0;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};"
        f"fillColor={color};strokeColor=#ffffff;"
    )
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label).replace(chr(10), "&lt;br&gt;")}" style="{style}" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{size}" height="{size}" as="geometry"/></mxCell>'
    )


ICON_DIR = Path(__file__).parent / "dbx_icons"


def dbx_icon(cid, label, slug, x, y, size=56):
    svg = base64.b64encode((ICON_DIR / f"{slug}.svg").read_bytes()).decode()
    style = (
        f"shape=image;verticalLabelPosition=bottom;verticalAlign=top;imageAspect=0;aspect=fixed;"
        f"html=1;fontSize=11;fontColor=#232F3E;image=data:image/svg+xml,{svg};"
    )
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label).replace(chr(10), "&lt;br&gt;")}" style="{style}" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{size}" height="{size}" as="geometry"/></mxCell>'
    )


def lane(label, x, y, w, h=34):
    cells.append(
        f'<mxCell id="{nid()}" value="{escape(label)}" style="rounded=0;whiteSpace=wrap;html=1;'
        f'fillColor=#EAEDED;strokeColor=none;fontSize=15;fontStyle=1;fontColor=#232F3E;" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def box(cid, label, x, y, w, h, color=DBX, fill="#FFF3F0"):
    style = (
        f"rounded=1;whiteSpace=wrap;html=1;fontSize=11;fontColor=#232F3E;"
        f"strokeColor={color};strokeWidth=2;fillColor={fill};"
    )
    cells.append(
        f'<mxCell id="{cid}" value="{escape(label).replace(chr(10), "&lt;br&gt;")}" style="{style}" '
        f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


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
        f'<mxCell id="{nid()}" value="{escape(label)}" style="{style}" edge="1" parent="1" '
        f'source="{src}" target="{dst}">{geo}</mxCell>'
    )


def save(name, page_w=1600, page_h=900):
    xml = (
        f'<mxfile host="app.diagrams.net" agent="open-navigator youtube-api-audit build_drawio.py">'
        f'<diagram name="{name}"><mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" guides="1" '
        f'page="1" pageScale="1" pageWidth="{page_w}" pageHeight="{page_h}" background="#ffffff"><root>'
        + "".join(cells)
        + "</root></mxGraphModel></diagram></mxfile>"
    )
    out = Path(__file__).parent.parent / f"{name}.drawio"
    out.write_text(xml)
    print(name)
    return out
