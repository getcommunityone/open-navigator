"""Render .drawio → .png with draw.io's export page (same as HTL / milliman)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

EXPORT_URL = "http://127.0.0.1:8765/export3.html"


async def render_files(files: list[Path], scale: float = 2.0):
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--allow-file-access-from-files"])
        page = await browser.new_page(viewport={"width": 1800, "height": 1200}, device_scale_factor=1)
        for f in files:
            xml = f.read_text()
            await page.goto(EXPORT_URL)
            await page.wait_for_function("typeof render === 'function'", timeout=60000)
            await page.add_script_tag(url="http://127.0.0.1:8765/js/stencils.min.js")
            await page.add_script_tag(url="http://127.0.0.1:8765/js/shapes-14-6-5.min.js")
            await page.wait_for_function(
                "typeof mxStencilRegistry !== 'undefined' && typeof mxStencilRegistry.loadStencil === 'function'",
                timeout=60000,
            )
            await page.evaluate(
                "d => render(d)",
                {"xml": xml, "format": "png", "scale": scale, "border": 20, "bg": "#ffffff"},
            )
            await page.wait_for_selector("#LoadingComplete", state="attached", timeout=90000)
            bounds = json.loads(await page.evaluate("document.getElementById('LoadingComplete').getAttribute('bounds')"))
            w = int(bounds["width"] + 2 * 20 * scale) + 2
            h = int(bounds["height"] + 2 * 20 * scale) + 2
            await page.set_viewport_size({"width": max(w, 1280), "height": max(h, 720)})
            out = f.with_suffix(".png")
            await page.screenshot(path=str(out), full_page=True)
            print(out.name, bounds)
        await browser.close()


if __name__ == "__main__":
    paths = [Path(a).resolve() for a in sys.argv[1:]]
    asyncio.run(render_files(paths))
