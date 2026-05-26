#!/usr/bin/env python3
"""
Download ChampDS (``play.champds.com``) archived meeting VODs and agendas for a jurisdiction.

Gwinnett County TV Gwinnett embeds the Board of Commissioners archive at
``play.champds.com/gwinnettcoga/archive/1``. This script lists events via ``playapi.champds.com``,
resolves HLS ``master.m3u8`` URLs, downloads with ``yt-dlp``, transcodes to **Opus** (same defaults
as GoMeet / SuiteOne), and saves agenda/minutes PDFs when the API exposes attachments.

Examples::

    .venv/bin/python -m scripts.discovery.download_champds_meetings \\
        --jurisdiction-dir data/cache/scraped_meetings/GA/county/gwinnett_13135 \\
        --limit 10

    .venv/bin/python -m scripts.discovery.download_champds_meetings \\
        --customer-access-id gwinnettcoga --archive-id 1 --archive-group-id 1 \\
        --out-dir data/cache/scraped_meetings/GA/county/gwinnett_13135/_champds_downloads \\
        --limit 3 --skip-opus
"""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence, Tuple

import requests
from loguru import logger

from scripts.discovery.champds_client import (
    ChampDsClient,
    ChampDsEvent,
    attachment_download_url,
    board_of_commissioners_group_id,
    parse_champds_archive_embed_url,
    recent_events_with_media,
    vod_stream_url,
)
from scripts.discovery.gomeet_mp4_to_opus import post_ytdlp_transcode_output
from scripts.discovery.meeting_document_naming import (
    build_meeting_pdf_disk_filename,
    clean_anchor_text,
    infer_calendar_folder_year,
    pdf_meeting_title,
    pick_meeting_date,
    slugify_meeting_filename,
    strip_redundant_meeting_date_from_title,
)

ROOT = Path(__file__).resolve().parents[2]

# Gwinnett County GA — TV Gwinnett commission meetings (ChampDS archive group 1 = BOC)
GWINNETT_COMMISSION_PAGE = (
    "https://www.gwinnettcounty.com/government/departments/communications/"
    "tv-gwinnett/videos/commission-meetings"
)
GWINNETT_CHAMPDS_EMBED = "https://play.champds.com/gwinnettcoga/archive/1"

_MEDIA_SUFFIXES = frozenset({".mp4", ".webm", ".mkv", ".m4a", ".opus"})

_GWINNETT_DEFAULTS = {
    "customer_access_id": "gwinnettcoga",
    "archive_id": 1,
    "archive_group_id": 1,
    "page_url": GWINNETT_COMMISSION_PAGE,
    "embed_url": GWINNETT_CHAMPDS_EMBED,
}


def _resolve_yt_dlp(spec: str) -> Tuple[str, List[str]]:
    """Return executable path and optional argv prefix (e.g. ``python -m yt_dlp``)."""
    raw = (spec or "yt-dlp").strip()
    if " -m " in raw or raw.endswith(" -m yt_dlp"):
        parts = raw.split()
        if len(parts) >= 3 and parts[-2] == "-m":
            py = shutil.which(parts[0]) or parts[0]
            return py, parts
    found = shutil.which(raw)
    if found:
        return found, [found]
    if Path(raw).is_file():
        return raw, [raw]
    for py in (sys.executable, shutil.which("python3"), shutil.which("python")):
        if not py:
            continue
        try:
            subprocess.run(
                [py, "-m", "yt_dlp", "--version"],
                capture_output=True,
                check=True,
                timeout=30,
            )
            return py, [py, "-m", "yt_dlp"]
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return "", []


def _load_repo_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(ROOT / ".env")


def _event_meeting_date(event: ChampDsEvent) -> date | None:
    for raw in (event.event_datetime_local, event.event_datetime_utc):
        s = (raw or "").strip()
        if not s:
            continue
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s[:19], fmt).date()
            except ValueError:
                continue
    return None


def build_champds_video_stem_and_year(
    event: ChampDsEvent,
    *,
    fallback_year: int,
) -> Tuple[str, str]:
    """Calendar-year folder + ``YYYY-MM-DD_title_snake`` stem for yt-dlp output."""
    anchor = clean_anchor_text(event.event_title) or f"champds_event_{event.customer_event_id}"
    pseudo_url = (
        f"https://play.champds.com/event/{event.customer_event_id}"
        f"?dt={event.event_datetime_utc or event.event_datetime_local}"
    )
    d = _event_meeting_date(event)
    if d is None:
        d, _ = pick_meeting_date(url=pseudo_url, anchor=anchor)
    cy = infer_calendar_folder_year(pseudo_url, anchor, "", fallback_year=fallback_year)
    year_folder = str(cy)

    raw_title = pdf_meeting_title(anchor, pseudo_url).strip() or "commission_meeting"
    if d:
        date_prefix = d.isoformat()
        raw_title = strip_redundant_meeting_date_from_title(raw_title, d) or "commission_meeting"
    else:
        ys = year_folder.strip()
        if ys.isdigit() and len(ys) == 4 and 1990 <= int(ys) <= 2100:
            date_prefix = ys
        else:
            date_prefix = "undated"

    slug = slugify_meeting_filename(raw_title)
    weak = frozenset({"document", "meeting_document", "commission_meeting", "video", "meeting"})
    if slug in weak or len(slug) < 4:
        h = hashlib.sha256(pseudo_url.encode("utf-8", errors="replace")).hexdigest()[:8]
        slug = f"{slug}_{h}"

    stem = f"{date_prefix}_{slug}"
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem)
    stem = re.sub(r"_+", "_", stem)
    if len(stem) > 200:
        stem = stem[:180].rstrip("._")
    return year_folder, stem


def _session_cookies_to_netscape(session: requests.Session, path: Path) -> None:
    jar = http.cookiejar.MozillaCookieJar(str(path))
    for c in session.cookies:
        jar.set_cookie(
            http.cookiejar.Cookie(
                version=0,
                name=c.name,
                value=c.value,
                port=None,
                port_specified=False,
                domain=c.domain,
                domain_specified=bool(c.domain),
                domain_initial_dot=c.domain.startswith(".") if c.domain else False,
                path=c.path or "/",
                path_specified=True,
                secure=bool(c.secure),
                expires=int(c.expires) if c.expires else None,
                discard=False,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
        )
    jar.save(ignore_discard=True, ignore_expires=True)


_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _download_stream_ytdlp(
    *,
    stream_url: str,
    out_tpl: str,
    yt_dlp_argv: List[str],
    referer: str,
    cookie_path: Path | None,
    log_prefix: str,
) -> Tuple[bool, str]:
    cmd: List[str] = [
        *yt_dlp_argv,
        "--no-playlist",
        "--referer",
        referer,
        "--add-header",
        f"User-Agent:{_BROWSER_UA}",
        "--add-header",
        f"Referer:{referer}",
        "-o",
        out_tpl,
        stream_url,
    ]
    if cookie_path and cookie_path.is_file():
        insert_at = len(yt_dlp_argv)
        cmd[insert_at:insert_at] = ["--cookies", str(cookie_path)]
    logger.info("{} yt_dlp_cmd stream={}", log_prefix, stream_url[:120])
    proc = subprocess.run(cmd, cwd=str(ROOT), timeout=7200)
    if proc.returncode != 0:
        return False, f"yt-dlp_exit_{proc.returncode}"
    return True, ""


def _download_attachment(
    session: requests.Session,
    url: str,
    dest: Path,
    *,
    log_prefix: str,
) -> bool:
    if dest.is_file() and dest.stat().st_size > 200:
        logger.info("{} skip_existing_agenda path={}", log_prefix, dest.name)
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = session.get(url, timeout=120, stream=True)
        r.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    fh.write(chunk)
    except Exception as exc:
        logger.warning("{} agenda_download_fail url={} err={!r}", log_prefix, url[:80], exc)
        return False
    if dest.stat().st_size < 200:
        try:
            dest.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    logger.info("{} agenda_saved path={}", log_prefix, dest.name)
    return True


def _attachment_dest_name(
    customer_access_id: str,
    event: ChampDsEvent,
    attachment: Mapping[str, Any],
    *,
    doc_type: str,
    year_folder: str,
) -> str:
    url = attachment_download_url(customer_access_id, attachment) or (
        f"https://play.champds.com/ATT/{customer_access_id}/"
        f"{attachment.get('MediaFileLocation')}/{attachment.get('MediaFileName')}"
    )
    anchor = clean_anchor_text(event.event_title)
    fname = str(attachment.get("MediaFileName") or "agenda.pdf")
    if not fname.lower().endswith(".pdf"):
        fname = f"{fname}.pdf" if "." not in fname else fname
    base = build_meeting_pdf_disk_filename(
        url,
        anchor,
        doc_type,
        year_fallback=year_folder,
        meeting_date=_event_meeting_date(event),
        storage_suffix=Path(fname).suffix or ".pdf",
    )
    return base


def download_event(
    client: ChampDsClient,
    event: ChampDsEvent,
    *,
    out_root: Path,
    yt_dlp_argv: List[str],
    referer: str,
    fallback_year: int,
    skip_opus: bool,
    skip_existing: bool,
    download_agendas: bool,
    log_prefix: str,
) -> Tuple[bool, str]:
    detail = client.enrich_event(event)
    svc = detail.raw.get("ServicesAndMachineInfo") or {}
    if not isinstance(svc, dict):
        svc = {}
    try:
        stream = vod_stream_url(svc, detail.media_info)
    except ValueError as exc:
        return False, f"no_stream_url:{exc}"

    year_folder, stem = build_champds_video_stem_and_year(detail, fallback_year=fallback_year)
    year_dir = out_root / year_folder
    year_dir.mkdir(parents=True, exist_ok=True)

    if skip_existing:
        existing = [
            p
            for p in year_dir.glob(f"{re.escape(stem)}.*")
            if p.suffix.lower() in _MEDIA_SUFFIXES
        ]
        if existing:
            logger.info("{} skip_existing_media path={}", log_prefix, existing[0])
            media_ok = True
        else:
            media_ok = False
    else:
        media_ok = False

    cookie_path: Path | None = None
    if not media_ok:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="champds_cookies_"
        ) as tf:
            cookie_path = Path(tf.name)
        _session_cookies_to_netscape(client.session, cookie_path)
        target_tpl = str(year_dir / f"{stem}.%(ext)s")
        play_referer = (
            f"{client.play_base}/{client.customer_access_id}/event/{detail.customer_event_id}"
        )
        ok, err = _download_stream_ytdlp(
            stream_url=stream,
            out_tpl=target_tpl,
            yt_dlp_argv=yt_dlp_argv,
            referer=play_referer,
            cookie_path=cookie_path,
            log_prefix=log_prefix,
        )
        try:
            cookie_path.unlink(missing_ok=True)
        except OSError:
            pass
        if not ok:
            return False, err
        if not skip_opus:
            post_ytdlp_transcode_output(year_dir, stem, respect_download_mp4_opus_env=True)

    if download_agendas:
        customer_id = client.customer_access_id
        for doc_type, attachments in (
            ("agenda", detail.agenda_attachments),
            ("minutes", detail.minutes_attachments),
        ):
            for att in attachments:
                if not isinstance(att, dict):
                    continue
                url = attachment_download_url(customer_id, att, play_host=client.play_host)
                if not url:
                    continue
                dest_name = _attachment_dest_name(
                    customer_id,
                    detail,
                    att,
                    doc_type=doc_type,
                    year_folder=year_folder,
                )
                # Prefix doc type when filename would collide
                dest = year_dir / dest_name
                if doc_type == "minutes" and dest_name.lower().startswith("agenda"):
                    dest = year_dir / dest_name.replace(".pdf", "_minutes.pdf", 1)
                elif doc_type == "minutes":
                    stem_pdf = Path(dest_name).stem
                    dest = year_dir / f"{stem_pdf}_minutes.pdf"
                _download_attachment(client.session, url, dest, log_prefix=log_prefix)

    return True, ""


def _resolve_archive_group_id(
    client: ChampDsClient,
    archive_id: int,
    archive_group_id: int | None,
) -> int:
    if archive_group_id and archive_group_id > 0:
        return int(archive_group_id)
    arch = client.fetch_archive(archive_id)
    gid = board_of_commissioners_group_id(arch)
    if gid is None:
        raise ValueError(
            f"Could not resolve archive group for archive_id={archive_id}; pass --archive-group-id"
        )
    logger.info("resolved archive_group_id={} archive_title={!r}", gid, arch.archive_title)
    return gid


def run_download(args: argparse.Namespace) -> int:
    customer = (args.customer_access_id or "").strip() or _GWINNETT_DEFAULTS["customer_access_id"]
    archive_id = int(args.archive_id or _GWINNETT_DEFAULTS["archive_id"])
    archive_group_id = int(args.archive_group_id) if args.archive_group_id else 0

    embed = (args.embed_url or "").strip() or _GWINNETT_DEFAULTS["embed_url"]
    parsed = parse_champds_archive_embed_url(embed)
    if parsed:
        customer, archive_id = parsed

    referer = (args.page_url or "").strip() or _GWINNETT_DEFAULTS["page_url"]

    jdir = Path(args.jurisdiction_dir).expanduser().resolve() if args.jurisdiction_dir else None
    out_root = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else (jdir / "_champds_downloads" if jdir else ROOT / "data/cache/_champds_downloads")
    )
    out_root.mkdir(parents=True, exist_ok=True)

    yt_dlp_exe, yt_dlp_argv = _resolve_yt_dlp(args.yt_dlp)
    if not yt_dlp_exe:
        logger.error("yt-dlp not found on PATH (install yt-dlp or pass --yt-dlp)")
        return 2

    fy = int(args.fallback_year or 0)
    fallback_year = fy if 1990 <= fy <= 2100 else datetime.now().year

    client = ChampDsClient(customer_access_id=customer)
    group_id = _resolve_archive_group_id(
        client,
        archive_id,
        archive_group_id if archive_group_id > 0 else None,
    )
    rows = client.list_events_with_media(group_id)
    events = recent_events_with_media(rows, limit=max(1, args.limit))
    if not events:
        logger.error("No ChampDS events with media in archive group {}", group_id)
        return 2

    logger.info(
        "champds_batch_start customer={} group={} n_events={} out_dir={}",
        customer,
        group_id,
        len(events),
        out_root,
    )

    ok_n = 0
    fail_n = 0
    manifest_rows: list[dict[str, Any]] = []

    for idx, ev in enumerate(events, start=1):
        prefix = f"champds[{idx}/{len(events)}] event_id={ev.customer_event_id}"
        logger.info("{} title={!r}", prefix, ev.event_title[:80])
        good, err = download_event(
            client,
            ev,
            out_root=out_root,
            yt_dlp_argv=yt_dlp_argv,
            referer=referer,
            fallback_year=fallback_year,
            skip_opus=args.skip_opus,
            skip_existing=args.skip_existing,
            download_agendas=not args.skip_agendas,
            log_prefix=prefix,
        )
        if good:
            ok_n += 1
            manifest_rows.append(
                {
                    "customer_event_id": ev.customer_event_id,
                    "event_title": ev.event_title,
                    "event_datetime_utc": ev.event_datetime_utc,
                }
            )
        else:
            fail_n += 1
            logger.warning("{} failed err={}", prefix, err)

    manifest_path = out_root / "_champds_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "customer_access_id": customer,
                "archive_id": archive_id,
                "archive_group_id": group_id,
                "page_url": referer,
                "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "events": manifest_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info("champds_batch_done ok={} fail={} manifest={}", ok_n, fail_n, manifest_path)
    return 0 if fail_n == 0 else 1


def main(argv: Sequence[str] | None = None) -> int:
    _load_repo_dotenv()
    p = argparse.ArgumentParser(description="Download ChampDS meeting VODs and agendas.")
    p.add_argument("--jurisdiction-dir", default="", help="Scraped meetings folder (sets default out dir)")
    p.add_argument("--out-dir", default="", help="Output root (default: {jurisdiction}/_champds_downloads)")
    p.add_argument("--customer-access-id", default="", help="ChampDS customer slug (default: gwinnettcoga)")
    p.add_argument("--archive-id", type=int, default=0, help="Archive id (default: 1 for Gwinnett)")
    p.add_argument("--archive-group-id", type=int, default=0, help="Archive group (default: BOC group 1)")
    p.add_argument("--embed-url", default="", help="play.champds.com/.../archive/N embed URL")
    p.add_argument("--page-url", default="", help="Referer / source page URL")
    p.add_argument("--limit", type=int, default=10, help="Most recent N meetings with VOD (default: 10)")
    p.add_argument("--fallback-year", type=int, default=0, help="Calendar year when date unknown")
    p.add_argument("--yt-dlp", default="yt-dlp", help="yt-dlp executable name or path")
    p.add_argument("--skip-opus", action="store_true", help="Keep downloaded container; no ffmpeg Opus step")
    p.add_argument("--skip-existing", action="store_true", help="Skip when media file already present")
    p.add_argument("--skip-agendas", action="store_true", help="Do not download agenda/minutes PDFs")
    args = p.parse_args(list(argv) if argv is not None else None)
    return run_download(args)


if __name__ == "__main__":
    sys.exit(main())
