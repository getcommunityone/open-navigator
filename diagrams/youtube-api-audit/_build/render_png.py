"""Render the last-built diagram layout to PNG (≥1280×720) for the audit form."""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import build_drawio
from _helpers import anchors, layout

ROOT = Path(__file__).resolve().parent.parent
FORM = Path(__file__).resolve().parents[3] / "data/cache/youtube-api-audit-screenshots/form-ready"


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    lines = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = words[0]
        for w in words[1:]:
            trial = f"{cur} {w}"
            if draw.textlength(trial, font=font) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def render(name: str, page_w: int, page_h: int, form_name: str):
    scale = 1.0
    img = Image.new("RGB", (int(page_w * scale), int(page_h * scale)), "#ffffff")
    draw = ImageDraw.Draw(img)
    title_font = _font(22, bold=True)
    note_font = _font(13)
    lane_font = _font(15, bold=True)
    box_font = _font(13)
    group_font = _font(13, bold=True)
    edge_font = _font(11)

    # groups / lanes first
    for item in layout:
        kind = item[0]
        if kind == "group":
            _, label, x, y, w, h, gkind = item
            stroke = "#4285F4" if gkind == "google" else ("#354F52" if gkind == "app" else "#7D8998")
            fill = "#E8F0FE" if gkind == "google" else ("#F8FAFA" if gkind == "app" else "#ffffff")
            draw.rectangle([x, y, x + w, y + h], outline=stroke, width=2, fill=fill)
            draw.text((x + 10, y + 6), label, fill="#232F3E", font=group_font)
        elif kind == "lane":
            _, label, x, y, w, h = item
            draw.rectangle([x, y, x + w, y + h], fill="#EAEDED", outline=None)
            draw.text((x + 10, y + 6), label, fill="#232F3E", font=lane_font)

    # boxes
    for item in layout:
        if item[0] != "box":
            continue
        _, label, x, y, w, h, color, fill = item
        draw.rounded_rectangle([x, y, x + w, y + h], radius=10, outline=color, width=2, fill=fill)
        lines = _wrap(draw, label, box_font, w - 16)
        ty = y + 10
        for line in lines:
            draw.text((x + 8, ty), line, fill="#232F3E", font=box_font)
            ty += 16

    # titles / notes
    for item in layout:
        if item[0] == "title":
            _, text, x, y, w, h = item
            draw.text((x, y + 4), text, fill="#111827", font=title_font)
        elif item[0] == "note":
            _, text, x, y, w, h = item
            lines = _wrap(draw, text, note_font, w - 8)
            ty = y
            for line in lines:
                draw.text((x, ty), line, fill="#545B64", font=note_font)
                ty += 16

    # edges (simple center-to-center)
    for item in layout:
        if item[0] != "edge":
            continue
        _, src, dst, label, dashed, via = item
        if src not in anchors or dst not in anchors:
            continue
        sx, sy, *_ = anchors[src]
        dx, dy, *_ = anchors[dst]
        pts = [(sx, sy)] + list(via) + [(dx, dy)]
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill="#545B64", width=2)
        # arrow head
        draw.polygon([(dx, dy), (dx - 8, dy - 5), (dx - 8, dy + 5)], fill="#545B64")
        if label:
            mx = (sx + dx) / 2
            my = (sy + dy) / 2 - 8
            draw.text((mx, my), label, fill="#545B64", font=edge_font)

    # Ensure ≥1280×720
    if img.width < 1280 or img.height < 720:
        canvas = Image.new("RGB", (max(1280, img.width), max(720, img.height)), "#ffffff")
        canvas.paste(img, (0, 0))
        img = canvas

    out = ROOT / f"{name}.png"
    img.save(out, "PNG", optimize=True)
    FORM.mkdir(parents=True, exist_ok=True)
    form_path = FORM / form_name
    shutil.copy2(out, form_path)
    print(f"{out.name} → {form_path} ({img.size[0]}x{img.size[1]}, {form_path.stat().st_size/1024:.0f}KB)")


def main():
    build_drawio.build_architecture()
    render("yt1_architecture", 1640, 620, "architecture-diagram.png")
    build_drawio.build_user_flow()
    render("yt2_user_flow", 1600, 640, "user-flow-diagram.png")


if __name__ == "__main__":
    main()
