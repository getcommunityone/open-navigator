"""The data-dictionary ERD: subject areas, each table's header (name, row count, grain) and its columns, with
right-angled lines routed between tables. Two views of one model:

- full: every column's name, type and meaning, plus a profile (nulls, distinct and top values) when stats are given;
- entity: the full view's arrangement (the same subject areas in the same page columns, the tables in the same
  order), each table cut to its header and key columns, each area shrunk to fit.

Ported from healthtransformationlab/health-transformation-lab-nlp (diagrams/_build/dictionary_erd.py, #379, #403,
#601). A model is any object with TABLES ({name: table with .description and .columns}), RELATIONSHIPS (.parent,
.child, .parent_cols, .child_cols, .cardinality, .derived), GROUPS ([(title, page column, [tables])]), KINDS
({table: kind}), and optionally PHI, QUESTIONS, PROFILE (False: no profile column) and KIND_LABELS.

Each table is as wide as its own content. Rows are grey-banded with vertical column lines. Lines run right-angled from
the side of the foreign-key row to the side of the key row it points at, with crow's feet (dashed: matched, not a key).
The Router keeps lines out of tables, in the gaps between tables and subject areas, spread into separate lanes.
"""
from __future__ import annotations

import math
from itertools import pairwise
from pathlib import Path

from .drawio import CARD, INK, MUTED, Diagram

LIMITS = ((90, 170), (80, 220), (110, 210))     # min, max width of: name, type and meaning, profile
CHAR, LINE, PAD, GAP, HEAD_LINE = 5.6, 13, 56, 120, 14
FACT, DIM, SUMMARY, AREA, BAND = "#E3F8DF", "#FFD9A8", "#DCE9F7", "#FDF8C8", "#E6E6E6"
# header colour and legend label per kind; a model may relabel kinds with KIND_LABELS (open-navigator names tables by
# entity, not fact/dimension, so its kinds are "event", "entity" and "summary")
HEADER = {"fact": FACT, "event": FACT, "dimension": DIM, "entity": DIM, "summary": SUMMARY}
KIND_LABELS = {"fact": "FACT table (one row per event)", "event": "EVENT table (one row per event or record)",
               "dimension": "DIMENSION table (one row per thing)", "entity": "ENTITY table (one row per thing)",
               "summary": "SUMMARY table (one row per measure or group)"}
PK, FK, PHI_RED, PLAIN, QUESTION = "#1F5FBF", "#6A3FB5", "#C62828", "#4B5563", "#C62828"
NOT_YET = "not profiled yet"


def _lines(text, width):
    """Lines a wrapped cell needs: about CHAR px per character at 10 px Helvetica, newlines kept."""
    per = max(1, int((width - 8) / CHAR))
    return sum(max(1, math.ceil(len(part) / per)) for part in text.split("\n"))


def _esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")


def _cells(m, table, col, tstats):
    """name, meaning (type, then what it means, one per line), question or None, profile."""
    meaning = f"{col.type};\n{col.description}"
    profile = (tstats or {}).get("columns", {}).get(col.name, NOT_YET)
    return col.name, meaning, getattr(m, 'QUESTIONS', {}).get((table, col.name)), profile


def _fit(texts, lo, hi):
    longest = max((len(line) for t in texts for line in t.split("\n")), default=0)
    return int(min(hi, max(lo, longest * CHAR + 12)))


def table_widths(m, stats):
    """{table: (name, meaning, profile) widths}: each column sized to its own longest line, within LIMITS. A model
    with PROFILE = False (gold: its rows live in Databricks, not here) has no profile column: width 0."""
    out = {}
    profiled = getattr(m, "PROFILE", True)
    for name, t in m.TABLES.items():
        rows = [_cells(m, name, c, stats.get(name)) for c in t.columns]
        out[name] = (_fit([r[0] for r in rows], *LIMITS[0]),
                     _fit([r[1] for r in rows] + [r[2] or "" for r in rows], *LIMITS[1]),
                     _fit([r[3] for r in rows], *LIMITS[2]) if profiled else 0)
    return out


def _head_text(m, name, stats):
    rows = (stats.get(name) or {}).get("rows")
    return name, (f"{rows:,}" if rows is not None else "rows not measured yet"), m.TABLES[name].description


def _head_height(m, name, stats, width):
    desc = _head_text(m, name, stats)[2]
    return (2 + _lines(desc, width)) * HEAD_LINE + 10


def _row_height(cells, widths):
    name, meaning, question, profile = cells
    lines = max(_lines(name, widths[0]), _lines(meaning + ("\n" + question if question else ""), widths[1]),
                _lines(profile, widths[2]) if widths[2] else 1)
    return lines * LINE + 6


def _size(m, name, stats, widths):
    w = sum(widths)
    rows = [_cells(m, name, c, stats.get(name)) for c in m.TABLES[name].columns]
    return w, _head_height(m, name, stats, w) + sum(_row_height(r, widths) for r in rows)


def _key_colour(m, table, col):
    if (table, col.name) in getattr(m, 'PHI', set()):
        return PHI_RED, True
    if "PK" in col.key:
        return PK, True
    if "FK" in col.key:
        return FK, True
    return PLAIN, False


def _draw_table(d, m, name, x, y, stats, widths, anchors):
    tstats = stats.get(name)
    w, h = _size(m, name, stats, widths)
    head_h = _head_height(m, name, stats, w)
    fill = HEADER[m.KINDS[name]]
    title, count, desc = _head_text(m, name, stats)
    # the outline: rounded, white body, the header filled
    d.v("", x, y, w, h, f"rounded=1;arcSize=2;absoluteArcSize=1;fillColor=#FFFFFF;strokeColor={INK};strokeWidth=1.5;")
    hid = d.v(f"<b>{_esc(title)}</b><br>{_esc(count)}<br>{_esc(desc)}", x + 1, y + 1, w - 2, head_h - 1,
              f"rounded=1;arcSize=2;absoluteArcSize=1;fillColor={fill};strokeColor=none;fontSize=10;fontColor={INK};"
              "align=center;verticalAlign=top;spacingTop=2;")
    anchors[(name, None)] = (hid, x, y, w, head_h)
    d.v("", x, y + head_h, w, 1.5, f"rounded=0;fillColor={INK};strokeColor=none;")
    cy = y + head_h
    for i, col in enumerate(m.TABLES[name].columns):
        cells = _cells(m, name, col, tstats)
        rh = _row_height(cells, widths)
        band = f"fillColor={BAND};" if i % 2 else "fillColor=none;"
        colour, bold = _key_colour(m, name, col)
        cell = f"rounded=0;strokeColor=none;fontSize=10;align=left;verticalAlign=middle;spacingLeft=3;{band}"
        cx = x + 1
        name_text = f"<b>{_esc(col.name)}</b>" if bold else _esc(col.name)
        meaning = _esc(cells[1]) + (f"<br><span style='color:{QUESTION}'>{_esc(cells[2])}</span>" if cells[2] else "")
        for (text, colour_), cw in zip(((name_text, colour), (meaning, INK),
                                        (_esc(cells[3]), MUTED if cells[3] == NOT_YET else INK)), widths):
            if cw:
                d.v(text, cx, cy, cw - (2 if cx + cw >= x + w - 1 else 0), rh, cell + f"fontColor={colour_};")
            cx += cw
        # an invisible box the width of the table, so lines meet the side of this row
        anchors[(name, col.name)] = (d.v("", x, cy, w, rh, "fillColor=none;strokeColor=none;"), x, cy, w, rh)
        cy += rh
    vx = x
    for cw, nxt in pairwise(widths):                 # the vertical column lines, between drawn columns
        vx += cw
        if nxt:
            d.v("", vx, y + head_h, 1.5, h - head_h, f"rounded=0;fillColor={INK};strokeColor=none;")
    return w, h


def entity_columns(m, name):
    """The columns an entity view keeps: keys, and every column a relationship joins on (so each line has a row)."""
    joined = {c for r in m.RELATIONSHIPS if r.parent == name for c in r.parent_cols}
    joined |= {c for r in m.RELATIONSHIPS if r.child == name for c in r.child_cols}
    return [c for c in m.TABLES[name].columns if "PK" in c.key or "FK" in c.key or c.name in joined]


ENTITY_WIDTH = (180, 300)        # min, max width of an entity-view table


def _entity_row(col):
    return col.name + (f" {col.key}" if col.key else "")


def entity_size(m, name, stats):
    """An entity-view table's (width, height): as wide as its longest key row (within ENTITY_WIDTH), its header
    wrapped to that width, one row per key column."""
    cols = entity_columns(m, name)
    w = _fit([_entity_row(c) for c in cols] + [name], *ENTITY_WIDTH)
    return w, _head_height(m, name, stats, w) + (LINE + 6) * len(cols) + (4 if not cols else 0)


def _draw_entity_table(d, m, name, x, y, stats, w, anchors):
    """The entity view's table: its header (name, row count, grain) and one row per key column, coloured as in the
    full view, with no types, meanings or profiles (#601)."""
    head_h = _head_height(m, name, stats, w)
    cols = entity_columns(m, name)
    rh = LINE + 6
    h = entity_size(m, name, stats)[1]
    title, count, desc = _head_text(m, name, stats)
    d.v("", x, y, w, h, f"rounded=1;arcSize=2;absoluteArcSize=1;fillColor=#FFFFFF;strokeColor={INK};strokeWidth=1.5;")
    hid = d.v(f"<b>{_esc(title)}</b><br>{_esc(count)}<br>{_esc(desc)}", x + 1, y + 1, w - 2, head_h - 1,
              f"rounded=1;arcSize=2;absoluteArcSize=1;fillColor={HEADER[m.KINDS[name]]};strokeColor=none;fontSize=10;"
              f"fontColor={INK};align=center;verticalAlign=top;spacingTop=2;")
    anchors[(name, None)] = (hid, x, y, w, head_h)
    if cols:
        d.v("", x, y + head_h, w, 1.5, f"rounded=0;fillColor={INK};strokeColor=none;")
    cy = y + head_h
    for i, col in enumerate(cols):
        colour, bold = _key_colour(m, name, col)
        band = f"fillColor={BAND};" if i % 2 else "fillColor=none;"
        text = f"<b>{_esc(col.name)}</b>" if bold else _esc(col.name)
        tag = f" <span style='color:{MUTED}'>{_esc(col.key)}</span>" if col.key else ""
        d.v(text + tag, x + 1, cy, w - 2, rh, f"rounded=0;strokeColor=none;fontSize=10;align=left;verticalAlign=middle;"
            f"spacingLeft=3;{band}fontColor={colour};")
        anchors[(name, col.name)] = (d.v("", x, cy, w, rh, "fillColor=none;strokeColor=none;"), x, cy, w, rh)
        cy += rh
    return w, h, [c.name for c in cols]


def _legend_items(entity=False, kinds=("fact", "dimension"), profiled=True, labels=None, phi=True, questions=True):
    labels = {**KIND_LABELS, **(labels or {})}
    colour = {FACT: "green", DIM: "orange", SUMMARY: "blue"}
    return [*((HEADER[k], INK, f"{colour[HEADER[k]]} header = {labels[k]}") for k in kinds),
             ("#FFFFFF", PK, "blue name = primary key"),
             ("#FFFFFF", FK, "purple name = foreign key"),
             *([("#FFFFFF", PHI_RED, "red name = would hold PHI in a real extract: de-identify")] if phi else []),
             ("#FFFFFF", PLAIN, "grey name = not linked"),
             *([] if entity else [
                 *([("#FFFFFF", QUESTION, "red text in the meaning = an open question or issue")] if questions else []),
                 *([("#FFFFFF", INK, "profile: null=n (p%); n_distinct=k; values or top results, from the data")]
                   if profiled else [])]),
             *([("#FFFFFF", INK, "entity view: the full view's areas and order, each table's header and key columns only")]
               if entity else []),
             ("#FFFFFF", INK, "lines: crow's foot = many, bar = one; dashed = matched, not a key")]


def _legend(d, x, y, entity=False, kinds=("fact", "dimension"), profiled=True, labels=None, phi=True, questions=True):
    """Draws the legend; returns the height the full view's legend takes."""
    items = _legend_items(entity, kinds, profiled, labels, phi, questions)
    h = 34 + 22 * len(items)
    d.v("<b>Legend</b>", x, y, 500, h, f"rounded=1;fillColor=#EEF0FA;strokeColor={INK};fontSize=13;verticalAlign=top;")
    for i, (fill, colour, text) in enumerate(items):
        d.v(text, x + 12, y + 30 + 22 * i, 476, 18, f"rounded=0;fillColor={fill};strokeColor={INK};fontSize=10;fontColor={colour};align=left;spacingLeft=4;")
    return 34 + 22 * len(_legend_items(False, kinds, profiled, labels, phi, questions))


def _layout(tables, sizes):
    """Two tables a row: the rows, and the subject area's width and height."""
    rows = [tables[i:i + 2] for i in range(0, len(tables), 2)]
    gw = max(sum(sizes[n][0] for n in row) + PAD * (len(row) + 1) for row in rows)
    gh = 46 + sum(max(sizes[n][1] for n in row) + PAD for row in rows)
    return rows, gw, gh


def group_tops(m, stats, top=0, sizes=None):
    """{subject area: y}: stacked down each column, the column then placed by COLUMN_ALIGN (top, middle or bottom)
    against the tallest column. sizes: each table's (width, height); the full view's by default."""
    if sizes is None:
        widths = table_widths(m, stats)
        sizes = {n: _size(m, n, stats, widths[n]) for n in m.TABLES}
    heights = {}
    for title, c, tables in m.GROUPS:
        heights.setdefault(c, []).append((title, _layout(tables, sizes)[2]))
    tallest = max(sum(h for _, h in col) + GAP * (len(col) - 1) for col in heights.values())
    tops = {}
    for c, col in heights.items():
        span = sum(h for _, h in col) + GAP * (len(col) - 1)
        align = getattr(m, "COLUMN_ALIGN", {}).get(c, "top")
        y = top + {"top": 0, "middle": (tallest - span) / 2, "bottom": tallest - span}[align]
        for title, h in col:
            tops[title] = y
            y += h + GAP
    return tops


class Router:
    """Right-angled lines that never cross a table: a cheapest path on a STEP-px grid whose nodes inside a table (or
    within CLEAR px of one) are blocked. A turn costs BEND; running along a stretch another line already uses costs
    SHARE per px, so lines spread into neighbouring lanes instead of bundling (lines to the same key row share freely,
    merging into one trunk); crossing another line costs CROSS.
    Inside a subject area each px costs INSIDE, so lines between areas travel in the gaps between them; an area's
    title band is blocked, and running along an area's border (within 9 px of it) costs EDGE per px, so lines don't
    trace the borders. Above or below every area costs OUTER per px, so no line loops round the whole diagram."""
    STEP, CLEAR, STUB, BEND, SHARE, CROSS, INSIDE, TITLE, EDGE, OUTER = 8, 9, 16, 40, 6, 25, 1.6, 40, 6, 4

    def __init__(self, rects, areas=(), rows=()):
        import numpy as np
        self.rects = rects
        s = self.STEP
        x0 = min(x for x, _, _, _ in rects) - 12 * s
        y0 = min(y for _, y, _, _ in rects) - 4 * s
        x1 = max(x + w for x, _, w, _ in rects) + 12 * s
        y1 = max(y + h for _, y, _, h in rects) + 4 * s
        xs = set(np.arange(x0, x1, s).round(1))
        ys = set(np.arange(y0, y1, s).round(1))
        for x, y, w, h in rects:                       # the stub ends beside each table, on the grid exactly
            xs |= {round(x - self.STUB, 1), round(x + w + self.STUB, 1)}
        ys |= {round(y + h / 2, 1) for _, y, _, h in rows}   # and each row's centre line
        self.xs, self.ys = sorted(xs), sorted(ys)
        self.blocked = np.zeros((len(self.xs), len(self.ys)), bool)
        ax, ay = np.array(self.xs), np.array(self.ys)
        c = self.CLEAR
        for x, y, w, h in rects:
            ix = (ax > x - c) & (ax < x + w + c)
            iy = (ay > y - c) & (ay < y + h + c)
            self.blocked[np.ix_(ix, iy)] = True
        self.weight = np.ones((len(self.xs), len(self.ys)))
        self.areas = list(areas)
        for x, y, w, h in self.areas:
            ix = (ax > x) & (ax < x + w)
            self.weight[np.ix_(ix, (ay > y) & (ay < y + h))] = self.INSIDE
            self.blocked[np.ix_(ix, (ay > y) & (ay < y + self.TITLE))] = True
        if self.areas:
            outer = (ay < min(y for _, y, _, _ in self.areas)) | (ay > max(y + h for _, y, _, h in self.areas))
            self.weight[:, outer] = self.OUTER
        for x, y, w, h in self.areas:
            near_x, near_y = (ax > x - 9) & (ax < x + w + 9), (ay > y - 9) & (ay < y + h + 9)
            self.weight[np.ix_((abs(ax - x) < 9) | (abs(ax - x - w) < 9), near_y)] = self.EDGE
            self.weight[np.ix_(near_x, (abs(ay - y) < 9) | (abs(ay - y - h) < 9))] = self.EDGE
        self.used = {}                                   # (node, node) -> the key rows of the lines through it
        self.dirs = {}                                   # node -> set of 'h'/'v' already through it

    def _search(self, start, goals, key):
        """A* from start (ix, iy) to any goal; returns the node list."""
        import heapq
        xs, ys = self.xs, self.ys
        goal_set = set(goals)

        def h(i, j):
            return min(abs(xs[i] - xs[a]) + abs(ys[j] - ys[b]) for a, b in goals)
        best = {(start, None): 0}
        heap = [(h(*start), 0, start, None)]
        prev = {}
        while heap:
            _, g, node, d = heapq.heappop(heap)
            if g > best.get((node, d), 1e18):
                continue
            if node in goal_set:
                path, key = [node], (node, d)
                while key in prev:
                    key = prev[key]
                    path.append(key[0])
                return path[::-1]
            i, j = node
            for di, dj, nd in ((1, 0, "h"), (-1, 0, "h"), (0, 1, "v"), (0, -1, "v")):
                ni, nj = i + di, j + dj
                if not (0 <= ni < len(xs) and 0 <= nj < len(ys)) or self.blocked[ni, nj]:
                    continue
                a, b = (xs[i], ys[j]), (xs[ni], ys[nj])
                length = abs(a[0] - b[0]) + abs(a[1] - b[1])
                cost = length * (self.weight[i, j] + self.weight[ni, nj]) / 2 * (1 + self.SHARE * len(self.used.get((a, b) if a < b else (b, a), set()) - {key}))
                if d and d != nd:
                    cost += self.BEND
                if b in self.dirs and (("v" if nd == "h" else "h") in self.dirs[b]):
                    cost += self.CROSS
                ng = g + cost
                if ng < best.get(((ni, nj), nd), 1e18):
                    best[((ni, nj), nd)] = ng
                    prev[((ni, nj), nd)] = (node, d)
                    heapq.heappush(heap, (ng + h(ni, nj), ng, (ni, nj), nd))
        raise ValueError("no route")

    def route(self, src, tgt):
        """src, tgt: (x, y, w, h) of the two rows. Returns (bend points, exitX, entryX): the line leaves and enters
        each row's side horizontally, on whichever sides give the cheapest path."""
        sx, sy, sw, sh = src
        tx, ty, tw, th = tgt
        js, jt = self.ys.index(round(sy + sh / 2, 1)), self.ys.index(round(ty + th / 2, 1))
        best = None
        for ex, s_x in ((0, sx - self.STUB), (1, sx + sw + self.STUB)):
            i0 = self.xs.index(round(s_x, 1))
            if self.blocked[i0, js]:
                continue
            goals = {}
            for en, t_x in ((0, tx - self.STUB), (1, tx + tw + self.STUB)):
                it = self.xs.index(round(t_x, 1))
                if not self.blocked[it, jt]:
                    goals[(it, jt)] = en
            if not goals:
                continue
            path = self._search((i0, js), list(goals), tgt)
            pts = [(self.xs[i], self.ys[j]) for i, j in path]
            cost = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in pairwise(pts)) + self.BEND * len(_corners(pts))
            if best is None or cost < best[0]:
                best = (cost, pts, ex, goals[path[-1]])
        _, pts, ex, en = best
        for a, b in pairwise(pts):
            key = (a, b) if a < b else (b, a)
            self.used.setdefault(key, set()).add(tgt)
            nd = "h" if a[1] == b[1] else "v"
            self.dirs.setdefault(a, set()).add(nd)
            self.dirs.setdefault(b, set()).add(nd)
        return _corners(pts, keep_ends=True), ex, en


def _corners(pts, keep_ends=False):
    """The points where a right-angled path turns (and its two ends, if asked)."""
    out = [p for k, p in enumerate(pts[1:-1], 1)
           if (pts[k - 1][0] == p[0]) != (p[0] == pts[k + 1][0])]
    return [pts[0], *out, pts[-1]] if keep_ends else out


def build(m, stats=None, entity=False):
    """m: a model with TABLES, RELATIONSHIPS, GROUPS, KINDS, PHI, QUESTIONS. stats: table_profile.profile() output;
    a table missing from it says its rows aren't measured yet. entity: the entity view, laid out as the full view is
    (the same subject areas in the same page columns, the tables in the same order) with each table cut to its header
    and key columns, and every area shrunk to fit them."""
    stats = stats or {}
    d = Diagram()
    kinds = [k for k in HEADER if k in set(m.KINDS.values())]
    legend_h = _legend(d, 10, 10, entity, kinds, getattr(m, "PROFILE", True), getattr(m, "KIND_LABELS", None),
                       bool(getattr(m, "PHI", None)), bool(getattr(m, "QUESTIONS", None)))
    widths = table_widths(m, stats)
    sizes = {n: entity_size(m, n, stats) if entity else _size(m, n, stats, widths[n]) for n in m.TABLES}

    def layout(tables):
        return _layout(tables, sizes)

    columns = sorted({c for _, c, _ in m.GROUPS})
    col_w = {c: max(layout(t)[1] for _, gc, t in m.GROUPS if gc == c) for c in columns}
    col_x, x = {}, GAP                      # a margin on the left for lines into column 0
    for c in columns:
        col_x[c] = x
        x += col_w[c] + GAP
    tops = group_tops(m, stats, 10 + legend_h + GAP, sizes)
    anchors, tables_drawn, areas = {}, [], []
    d.tables, d.columns = {}, {}
    for title, c, tables in m.GROUPS:
        rows, _, gh = layout(tables)
        gx, gy = col_x[c], tops[title]
        d.v(f"{_esc(title)}", gx, gy, col_w[c], gh,
            f"rounded=1;arcSize=1;absoluteArcSize=1;fillColor={AREA};strokeColor={INK};fontSize=20;fontColor={INK};verticalAlign=top;spacingTop=6;")
        areas.append((gx, gy, col_w[c], gh))
        ty = gy + 46
        for i, row in enumerate(rows):
            tx = gx + PAD
            for n in row:
                if entity:
                    w, h, d.columns[n] = _draw_entity_table(d, m, n, tx, ty, stats, sizes[n][0], anchors)
                else:
                    w, h = _draw_table(d, m, n, tx, ty, stats, widths[n], anchors)
                    d.columns[n] = [c.name for c in m.TABLES[n].columns]
                tables_drawn.append((tx, ty, w, h))
                d.tables[n] = (tx, ty, w, h)
                tx += w + PAD
            ty += max(sizes[n][1] for n in row) + PAD
    router = Router(tables_drawn + [(10, 10, 500, legend_h)], areas, [a[1:] for a in anchors.values()])
    for r in m.RELATIONSHIPS:
        src = anchors.get((r.child, r.child_cols[0] if r.child_cols else None)) or anchors[(r.child, None)]
        tgt = anchors.get((r.parent, r.parent_cols[0] if r.parent_cols else None)) or anchors[(r.parent, None)]
        sid, tid = src[0], tgt[0]
        pts, ex, en = router.route(src[1:], tgt[1:])
        a, b = r.cardinality[:2], r.cardinality[-2:]
        dash = f"dashed=1;dashPattern=6 4;strokeColor={MUTED};" if r.derived else ""
        style = (f"edgeStyle=none;rounded=0;strokeColor={INK};strokeWidth=1.3;endFill=0;startFill=0;endSize=10;"
                 f"startSize=10;exitX={ex};exitY=0.5;exitPerimeter=0;entryX={en};entryY=0.5;entryPerimeter=0;{dash}"
                 f"startArrow={CARD[b]};endArrow={CARD[a]};")
        d.n += 1
        points = "".join(f'<mxPoint x="{px:.0f}" y="{py:.0f}"/>' for px, py in pts)
        d.cells.append(f'<mxCell id="c{d.n}" value="" style="html=1;{style}" edge="1" parent="1" source="{sid}" '
                       f'target="{tid}"><mxGeometry relative="1" as="geometry"><Array as="points">{points}</Array>'
                       "</mxGeometry></mxCell>")
        d.routes = getattr(d, "routes", []) + [[(src[1] + (src[3] if ex else 0), src[2] + src[4] / 2), *pts,
                                                (tgt[1] + (tgt[3] if en else 0), tgt[2] + tgt[4] / 2)]]
    d.obstacles, d.areas = router.rects, areas
    return d


def write(prefix, m, stats=None, src: Path = Path(".")):
    """<prefix>_full.drawio (the data dictionary) and <prefix>_entity.drawio (its arrangement, keys only) in src."""
    src.mkdir(parents=True, exist_ok=True)
    out = []
    for view, entity in (("full", False), ("entity", True)):
        stem = f"{prefix}_{view}"
        (src / f"{stem}.drawio").write_text(build(m, stats, entity).xml(stem))
        out.append(src / f"{stem}.drawio")
    return out
