#!/usr/bin/env python3
"""
Download U.S. Conference of Mayors « Meet the Mayors » directory into JSON.

Source: https://www.usmayors.org/mayors/meet-the-mayors/

The page uses POST ``searchTerm`` with **full state names** (e.g. ``Alabama``), not USPS codes.
Results are HTML blocks per mayor under ``<ul>`` with photo URLs on ``secure.usmayors.org/mayorphotos``.

Caches JSON under ``data/cache/uscm/``. Load with ``load_uscm_mayors_to_bronze.py``.

Usage:
    ./.venv/bin/python packages/scrapers/src/scrapers/uscm/download_uscm_mayors.py
    ./.venv/bin/python packages/scrapers/src/scrapers/uscm/download_uscm_mayors.py --states MA,TX
    ./.venv/bin/python packages/scrapers/src/scrapers/uscm/download_uscm_mayors.py --delay 2.0
"""
from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_VENV_REEXEC = "_OPEN_NAVIGATOR_USCM_VENV_REEXEC"


def _in_project_venv() -> bool:
    px = Path(sys.prefix).resolve()
    return px in {(_ROOT / ".venv").resolve(), (_ROOT / ".venv-dbt").resolve()}


def _maybe_reexec_with_project_venv() -> None:
    if os.environ.get(_VENV_REEXEC) == "1":
        return
    if _in_project_venv():
        return
    for name in (".venv", ".venv-dbt"):
        vpy = _ROOT / name / "bin" / "python"
        if vpy.is_file():
            os.environ[_VENV_REEXEC] = "1"
            os.execv(str(vpy), [str(vpy)] + sys.argv)


try:
    import httpx
    from bs4 import BeautifulSoup
    from loguru import logger
except ImportError:
    _maybe_reexec_with_project_venv()
    print(
        "Need httpx, beautifulsoup4, loguru. cd repo root && ./.venv/bin/pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

sys.path.insert(0, str(_ROOT))

from scrapers.uscm.state_names import ALL_STATE_CODES, STATE_FULL_NAME

MEET_THE_MAYORS_URL = "https://www.usmayors.org/mayors/meet-the-mayors/"
CACHE_DIR = Path("data/cache/uscm")

HEADERS = {
    "User-Agent": "OpenNavigator/1.0 (Civic Research; https://github.com/getcommunityone/open-navigator)",
    "Accept": "text/html,application/xhtml+xml",
}


class _TermWidthHelpFormatter(argparse.HelpFormatter):
    """Match terminal width so long lines wrap instead of getting cut off."""

    def __init__(self, prog: str) -> None:
        try:
            cols = shutil.get_terminal_size(fallback=(96, 24)).columns
        except Exception:
            cols = 96
        cols = max(cols, 40)
        width = max(72, min(cols - 2, 120))
        super().__init__(prog, max_help_position=24, width=width)


def decode_cf_email(hex_enc: str) -> str:
    """Decode Cloudflare ``data-cfemail`` hex payload."""
    hex_enc = hex_enc.strip()
    if len(hex_enc) < 2:
        return ""
    key = int(hex_enc[0:2], 16)
    chars: list[str] = []
    i = 2
    while i + 2 <= len(hex_enc):
        chars.append(chr(int(hex_enc[i : i + 2], 16) ^ key))
        i += 2
    return "".join(chars)


def _parse_mayor_ul_fragment(fragment: str) -> dict[str, Any] | None:
    """Parse inner HTML of one ``<ul>`` mayor card."""
    m_img = re.search(
        r'<img[^>]+src=["\']([^"\']*mayorphotos[^"\']*)["\']',
        fragment,
        re.I,
    )
    if not m_img:
        return None
    photo_raw = html.unescape(unquote(m_img.group(1).replace("&#038;", "&")))
    m_name = re.search(r"<[Bb]>\s*([^<]+?)\s*</[Bb]>", fragment)
    if not m_name:
        return None
    mayor_name = html.unescape(m_name.group(1).strip())
    m_city = re.search(
        r"</[Bb]>\s*<br\s*/?>\s*([^,<]+),\s*([A-Z]{2})\s*<br",
        fragment,
        re.I,
    )
    if not m_city:
        return None
    municipality_name = html.unescape(m_city.group(1).strip())
    state_code = m_city.group(2).strip().upper()

    m_pop = re.search(r"Population:\s*([^<]+)", fragment, re.I)
    population = None
    if m_pop:
        digits = re.sub(r"[^\d]", "", m_pop.group(1))
        if digits:
            try:
                population = int(digits)
            except ValueError:
                pass

    web_m = re.search(
        r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>\s*Web\s+Site\s*</a>",
        fragment,
        re.I,
    )
    city_website = html.unescape(web_m.group(1)) if web_m else None

    elec_m = re.search(r"Next\s+Election\s+Date:\s*([^<\n]+)", fragment, re.I)
    next_election_raw = elec_m.group(1).strip() if elec_m else None

    bio_m = re.search(
        r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>\s*Bio\s*</a>",
        fragment,
        re.I,
    )
    bio_url = html.unescape(bio_m.group(1)) if bio_m else None

    phone = None
    tel_m = re.search(r"Phone:\s*<a\s+href=['\"]tel:([^'\"]+)['\"]", fragment, re.I)
    if tel_m:
        phone = html.unescape(tel_m.group(1).strip())

    email = None
    cf_m = re.search(
        r'data-cfemail=["\']([0-9a-f]+)["\']',
        fragment,
        re.I,
    )
    if cf_m:
        email = decode_cf_email(cf_m.group(1))

    return {
        "mayor_name": mayor_name,
        "municipality_name": municipality_name,
        "state_code": state_code,
        "population": population,
        "mayor_photo_url": photo_raw,
        "city_website": city_website,
        "bio_url": bio_url,
        "next_election_raw": next_election_raw,
        "phone": phone,
        "email": email,
        "raw_card_html": fragment[:8000],
    }


def extract_mayors_from_results_html(html_text: str, search_term_used: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    fusion_text = soup.select_one("div.fusion-text.fusion-text-1") or soup.select_one(
        "div.post-content div.fusion-text"
    )
    if not fusion_text:
        logger.warning("Could not find fusion-text container for mayor list")
        return []

    out: list[dict[str, Any]] = []
    for ul in fusion_text.find_all("ul"):
        imgs = ul.find_all("img", src=lambda u: u and "mayorphotos" in u)
        if not imgs:
            continue
        frag = ul.decode()
        row = _parse_mayor_ul_fragment(frag)
        if row:
            row["search_term_used"] = search_term_used
            out.append(row)
    return out


async def fetch_state_mayors(
    client: httpx.AsyncClient,
    state_code: str,
    *,
    delay_after_sec: float,
) -> list[dict[str, Any]]:
    st = state_code.strip().upper()
    full = STATE_FULL_NAME.get(st)
    if not full:
        logger.error(f"Unknown state code: {state_code}")
        return []

    logger.info(f"[{st}] POST searchTerm={full!r}")
    r = await client.post(
        MEET_THE_MAYORS_URL,
        data={"searchTerm": full, "submit": "Search"},
        headers={**HEADERS, "Referer": MEET_THE_MAYORS_URL},
        follow_redirects=True,
    )
    r.raise_for_status()
    mayors = extract_mayors_from_results_html(r.text, full)
    logger.success(f"[{st}] Parsed {len(mayors)} mayor record(s)")
    if delay_after_sec > 0:
        await asyncio.sleep(delay_after_sec)
    return mayors


async def main_async(
    states: list[str] | None,
    delay_sec: float,
    outfile: Path | None,
) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    codes = (
        [s.strip().upper() for s in states]
        if states
        else list(ALL_STATE_CODES)
    )

    date_str = datetime.now().strftime("%Y%m%d")
    out_path = outfile or (CACHE_DIR / f"meet_the_mayors_us_{date_str}.json")

    all_rows: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=60.0, headers=HEADERS) as client:
        for code in codes:
            try:
                rows = await fetch_state_mayors(client, code, delay_after_sec=delay_sec)
                all_rows.extend(rows)
            except Exception as exc:
                logger.error(f"[{code}] Failed: {exc}")

    payload = {
        "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_url": MEET_THE_MAYORS_URL,
        "state_codes_requested": codes,
        "mayor_count": len(all_rows),
        "mayors": all_rows,
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    logger.success(f"Wrote {len(all_rows):,} mayor rows → {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download USCM Meet the Mayors directory to JSON",
        formatter_class=_TermWidthHelpFormatter,
    )
    parser.add_argument(
        "--states",
        type=str,
        metavar="CODES",
        help="Comma-separated USPS codes (omit for all states + DC).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds to sleep after each state POST (default: 1.5).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help=(
            "JSON output path.\n"
            "Default if omitted: data/cache/uscm/meet_the_mayors_us_<YYYYMMDD>.json."
        ),
    )
    args = parser.parse_args()

    state_list = (
        [s.strip().upper() for s in args.states.split(",")] if args.states else None
    )

    logger.info("USCM Meet the Mayors → {}".format(CACHE_DIR))
    asyncio.run(
        main_async(
            states=state_list,
            delay_sec=max(0.0, args.delay),
            outfile=args.output,
        )
    )


if __name__ == "__main__":
    main()
