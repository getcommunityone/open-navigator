"""A minimal draw.io (mxGraph) writer: vertices, edges and the file wrapper. Ported from
healthtransformationlab/health-transformation-lab-nlp (diagrams/_build/gold_erd.py)."""

from __future__ import annotations

from xml.sax.saxutils import escape

INK, MUTED = "#1B3139", "#5B6B73"
FONT = "fontFamily=Helvetica;html=1;whiteSpace=wrap;"
# Mermaid-style cardinality ends -> draw.io ER arrow names
CARD = {"||": "ERmandOne", "|o": "ERzeroToOne", "o|": "ERzeroToOne", "o{": "ERzeroToMany", "}o": "ERzeroToMany",
        "|{": "ERoneToMany", "}|": "ERoneToMany"}


class Diagram:
    """Collects mxCell XML; `xml()` wraps it as a .drawio file."""

    def __init__(self) -> None:
        self.cells: list[str] = []
        self.n = 0

    def v(self, value: str, x: float, y: float, w: float, h: float, style: str, parent: str = "1",
          extra: str = "") -> str:
        """Adds a vertex; returns its id."""
        self.n += 1
        cid = f"c{self.n}"
        self.cells.append(f'<mxCell id="{cid}" value="{escape(value, {chr(34): "&quot;"})}" style="{FONT}{style}" '
                          f'vertex="1" parent="{parent}"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" '
                          f'as="geometry">{extra}</mxGeometry></mxCell>')
        return cid

    def xml(self, name: str) -> str:
        return (f'<mxfile host="drawio"><diagram name="{name}" id="{name}"><mxGraphModel grid="0" page="0" '
                'background="#FFFFFF"><root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(self.cells)
                + "</root></mxGraphModel></diagram></mxfile>")
