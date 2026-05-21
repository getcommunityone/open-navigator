"""
Human-readable PDF filenames for scraped meetings (date + title, snake_case).

Shared by :mod:`scripts.discovery.comprehensive_discovery_pipeline_jurisdiction` and
:mod:`scripts.discovery.load_scraped_meetings_manifests_to_bronze` so bronze date/title logic stays
aligned with on-disk names.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import List, Optional, Set, Tuple
from urllib.parse import parse_qs, unquote, unquote_plus, urlparse

_ANCHOR_DATE_US = re.compile(
    r"(?:agenda|minutes?|meeting|packet)\s+for\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
    re.I,
)

# "January 12, 2023" / "Jun 27 2019" / "July 15 2019 - Work Session"
_MONTH_WORD_TO_NUM = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_ANCHOR_MONTH_DAY_YEAR = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
    r"\s+([0-3]?\d)(?:st|nd|rd|th)?,?\s*((?:19|20)\d{2})\b",
    re.I,
)

_FILENAME_MMDDYYYY = re.compile(r"(?:^|[_\s-])(\d{2})(\d{2})(\d{4})(?:[_\s.-]|\.pdf)", re.I)

# Anchor like ``5-18-26 Regular City Council`` or filename ``5-18-26-AGENDA.docx`` (two-digit year).
_ANCHOR_MDY_SHORTY = re.compile(
    r"\b(?P<m>[0-1]?\d)[/-](?P<d>[0-3]?\d)[/-](?P<y>\d{2})\b(?!\d)",
    re.I,
)


def _two_digit_year_to_four(y2: int) -> int:
    if y2 >= 70:
        return 1900 + y2
    return 2000 + y2


def _date_from_mdy_short_year_blob(blob: str) -> Tuple[Optional[date], Optional[str]]:
    m = _ANCHOR_MDY_SHORTY.search(blob or "")
    if not m:
        return None, None
    try:
        mo, d, y2 = int(m.group("m")), int(m.group("d")), int(m.group("y"))
        y = _two_digit_year_to_four(y2)
        return date(y, mo, d), "mdy_short_year"
    except ValueError:
        return None, None


def _date_from_yymmdd_prefix_in_filename(name: str) -> Tuple[Optional[date], Optional[str]]:
    """
    Filenames like ``250616_181145_00.mp3`` (YYMMDD + time) used for Big Timber-style audio minutes.
    """
    stem = Path((name or "").strip()).stem
    m = re.match(r"^(\d{2})(\d{2})(\d{2})_", stem)
    if not m:
        return None, None
    try:
        yy, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            return None, None
        y = _two_digit_year_to_four(yy)
        return date(y, mo, d), "filename_yymmdd_prefix"
    except ValueError:
        return None, None


def _date_from_filename_short_mdy(name: str) -> Tuple[Optional[date], Optional[str]]:
    m = re.match(
        r"^(\d{1,2})-(\d{1,2})-(\d{2})(?=[-_.]|[.]pdf|[.]docx|[.]doc\b|[.]rtf|[.]ppt|[.]mp3|[.]m4a|[.]wav)",
        (name or "").strip(),
        re.I,
    )
    if not m:
        return None, None
    try:
        mo, d, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = _two_digit_year_to_four(y2)
        return date(y, mo, d), "filename_mdy_short_year"
    except ValueError:
        return None, None

_GENERIC_TITLE_SLUGS = frozenset(
    {
        "document",
        "meeting_document",
        "filedownload",
        "download",
        "view",
        "online",
        "click_here",
        "none",
        "agenda",
        "minutes",
        "packet",
        "pdf",
        "html",
        "index",
    }
)


def _parse_y_m_d(parts: List[str]) -> Optional[date]:
    if len(parts) != 3:
        return None
    try:
        y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
        return date(y, mo, d)
    except ValueError:
        return None


def _parse_m_d_y(parts: List[str]) -> Optional[date]:
    """Assume M-D-Y when first token is 1-2 digits and third is 4-digit year."""
    if len(parts) != 3:
        return None
    try:
        if len(parts[2]) == 4 and parts[2].isdigit():
            return date(int(parts[2]), int(parts[0]), int(parts[1]))
    except ValueError:
        return None
    return None


def filename_tokens_from_url(url: str) -> List[str]:
    """Decoded ``FileName=`` / ``filename=`` query values (school BoardDocs-style handlers)."""
    q = parse_qs(urlparse(url).query)
    out: List[str] = []
    for key in ("FileName", "filename"):
        for v in q.get(key) or []:
            s = unquote_plus((v or "").strip())
            if s:
                out.append(s)
    return out


def _date_from_month_day_year_text(blob: str) -> Tuple[Optional[date], Optional[str]]:
    m = _ANCHOR_MONTH_DAY_YEAR.search(blob or "")
    if not m:
        return None, None
    mo_word = m.group(1).lower()
    mo = _MONTH_WORD_TO_NUM.get(mo_word)
    if not mo:
        return None, None
    try:
        day = int(m.group(2))
        year = int(m.group(3))
        return date(year, mo, day), "month_day_year_text"
    except ValueError:
        return None, None


def date_from_url_query(url: str) -> Tuple[Optional[date], Optional[str]]:
    q = parse_qs(urlparse(url).query)
    for key in ("odate", "meeting_date", "meetingdate", "date", "dt", "mdate"):
        vals = q.get(key) or []
        for v in vals:
            raw = (v or "").strip()
            if not raw:
                continue
            for sep in ("-", "/"):
                if sep in raw:
                    parts = [p for p in raw.replace("/", "-").split("-") if p]
                    if len(parts) == 3 and parts[0].isdigit():
                        d = _parse_y_m_d(parts) if len(parts[0]) == 4 else _parse_m_d_y(parts)
                        if d:
                            return d, f"url_query:{key}"
    return None, None


def _date_from_anchor(anchor: str) -> Tuple[Optional[date], Optional[str]]:
    if not anchor:
        return None, None
    d, src = _date_from_mdy_short_year_blob(anchor)
    if d:
        return d, src
    m = _ANCHOR_DATE_US.search(anchor)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(1)), int(m.group(2))), "anchor_text"
        except ValueError:
            pass
    d, src = _date_from_month_day_year_text(anchor)
    if d:
        return d, src
    return None, None


def _date_from_url_filename_queries(url: str) -> Tuple[Optional[date], Optional[str]]:
    for blob in filename_tokens_from_url(url):
        d, src = _date_from_month_day_year_text(blob)
        if d:
            return d, f"url_FileName:{src}"
        d2, src2 = _date_from_filename(Path(blob).name)
        if d2:
            return d2, f"url_FileName:{src2}"
    return None, None


def _date_from_filename(name: str) -> Tuple[Optional[date], Optional[str]]:
    m = _FILENAME_MMDDYYYY.search(name or "")
    if not m:
        return None, None
    try:
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return date(y, mo, d), "filename"
    except ValueError:
        pass
    return None, None


_YEAR_HINT_ANYWHERE = re.compile(r"(20\d{2})")


def infer_year_hint_from_url(url: str, fallback: int) -> int:
    """
    Last-resort calendar year for storage folders: scan URL path stem, then any ``20xx`` in the
    decoded URL. Does **not** use anchor text (use :func:`pick_meeting_date` / :func:`infer_calendar_folder_year` first).
    """
    path = unquote(urlparse(url).path or "")
    stem = Path(path).stem
    found: List[Tuple[int, int]] = []
    for i in range(0, max(0, len(stem) - 3)):
        if stem[i : i + 2] != "20" or i + 4 > len(stem):
            continue
        if not stem[i + 2 : i + 4].isdigit():
            continue
        y = int(stem[i : i + 4])
        if 1990 <= y <= 2100:
            found.append((i, y))
    if found:
        return found[-1][1]
    decoded = unquote(url)
    years: List[int] = []
    for m in _YEAR_HINT_ANYWHERE.finditer(decoded):
        try:
            y = int(m.group(1))
            if 1990 <= y <= 2100:
                years.append(y)
        except ValueError:
            continue
    if years:
        return years[-1]
    return fallback


def infer_calendar_folder_year(
    url: str,
    anchor_text: str = "",
    doc_type: str = "",
    *,
    fallback_year: int,
) -> int:
    """Pick ``{root}/.../{year}/`` like scrapes should: meeting date first, then URL year hints."""
    d, _ = pick_meeting_date(url=url, anchor=anchor_text, doc_type=doc_type or None)
    if d:
        return d.year
    return infer_year_hint_from_url(url, fallback_year)


def pick_meeting_date(
    *,
    url: str,
    anchor: str,
    doc_type: Optional[str] = None,
) -> Tuple[Optional[date], Optional[str]]:
    """Best-effort calendar date from anchor text, ``FileName=`` query, URL params, path stem."""
    _ = doc_type  # reserved for future vendors
    d, src = _date_from_anchor(anchor)
    if d:
        return d, src
    d, src = _date_from_url_filename_queries(url)
    if d:
        return d, src
    d, src = date_from_url_query(url)
    if d:
        return d, src
    base = urlparse(url).path.split("/")[-1] or url
    d, src = _date_from_filename_short_mdy(base)
    if d:
        return d, src
    d, src = _date_from_yymmdd_prefix_in_filename(base)
    if d:
        return d, src
    d, src = _date_from_filename(base)
    if d:
        return d, src
    return None, None


def clean_anchor_text(anchor: str) -> str:
    """Strip noisy link phrases so titles slugify cleanly."""
    if not anchor:
        return ""
    a = str(anchor).strip()
    a = re.sub(r"\([^)]*opens\s+in\s+new[^)]*\)", "", a, flags=re.I)
    a = re.sub(r"\([^)]*\bpdf\b[^)]*\)", "", a, flags=re.I)
    a = re.sub(r"\s+", " ", a).strip()
    low = a.lower()
    if low in {"opens in new window", "opens in new tab", "click here", "(opens in new window)"}:
        return ""
    return a


def pdf_meeting_title(anchor: str, url: str) -> str:
    """Prefer ``FileName=`` query for handler URLs; then anchor; then URL path tail."""
    fnames = filename_tokens_from_url(url)
    path_tail = urlparse(url).path.split("/")[-1]
    handler_like = "filedownload" in (path_tail or "").lower() or "filedownload" in (url or "").lower()

    if fnames:
        stem = Path(fnames[0]).stem.strip()
        if stem:
            c = clean_anchor_text(anchor)
            # Avoid duplicating the whole anchor when FileName already encodes the doc title.
            if handler_like or not c:
                return stem[:500]
            if c.lower() not in stem.lower() and stem.lower() not in c.lower():
                return f"{stem} — {c}"[:500]
            return stem[:500]

    c = clean_anchor_text(anchor)
    if c:
        return c[:500]
    return unquote_plus(path_tail or url)[:500]


def strip_redundant_meeting_date_from_title(raw_title: str, d: date) -> str:
    """Remove the meeting date phrase once we're already encoding ``d`` in the filename prefix."""
    t = (raw_title or "").strip()
    if not t:
        return ""

    mo_long = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )[d.month - 1]
    mo_short = mo_long[:3]
    if d.month == 9:
        mo_short_alt = "sept"
    else:
        mo_short_alt = mo_short
    y = d.year
    day = d.day
    day2 = f"{day:02d}"

    def _subs(pat: str, flags: int = 0) -> str:
        nonlocal t
        t = re.sub(pat, " ", t, flags=flags).strip()
        return t

    # SuiteOne listing cells: ``Jan 06, 2026 | 03:00 PM`` (zero-padded day is common).
    month_words = "|".join(re.escape(x) for x in (mo_long, mo_short, mo_short_alt))
    for dd in (str(day), day2):
        _subs(
            rf"\b(?:{month_words})\s+{dd}(?:st|nd|rd|th)?,?\s+{y}\s*\|\s*\d{{1,2}}:\d{{2}}\s*[AP]M\b",
            flags=re.I,
        )
        _subs(rf"\b(?:{month_words})\s+{dd}(?:st|nd|rd|th)?,?\s+{y}\b", flags=re.I)

    patterns = [
        rf"{mo_long}\s+{day},?\s+{y}",
        rf"{mo_short}\s+{day},?\s+{y}",
        rf"{mo_short_alt}\s+{day},?\s+{y}",
        rf"{mo_long}\s+{day2},?\s+{y}",
        rf"{mo_short}\s+{day2},?\s+{y}",
        rf"{mo_short_alt}\s+{day2},?\s+{y}",
        rf"{mo_long}\s+{day}\s+{y}",
        rf"{mo_short}\s+{day}\s+{y}",
        rf"{mo_long}\s+{day2}\s+{y}",
        rf"{mo_short}\s+{day2}\s+{y}",
        rf"{y}-{d.month:02d}-{d.day:02d}",
        rf"{d.month:02d}/{d.day:02d}/{y}",
        rf"{d.month:02d}-{d.day:02d}-{y}",
    ]
    for pat in patterns:
        _subs(pat, flags=re.I)

    # Trailing pipe time when the committee name already includes a clock time.
    _subs(r"\s*\|\s*\d{1,2}:\d{2}\s*[AP]M\s*$", flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*[—\-]\s*$", "", t).strip()
    return t


def strip_redundant_date_slug_suffix(slug: str, d: date) -> str:
    """
    Drop a trailing ``_jan_06_2026`` (and optional ``_03_00_pm``) when the ISO date is already the prefix.
    """
    s = (slug or "").strip().strip("_")
    if not s or not d:
        return slug

    mo_long = (
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    )[d.month - 1]
    mo_short = mo_long[:3]
    mo_alt = "sept" if d.month == 9 else mo_short
    y = d.year
    day = d.day
    day2 = f"{day:02d}"
    time_tail = r"(?:_\d{1,2}_\d{2}_(?:am|pm))?"

    tails: List[str] = []
    for mon in (mo_short, mo_alt, mo_long):
        for dd in (str(day), day2):
            tails.append(rf"_{mon}_{dd}_{y}")
    tails.append(rf"_{d.month:02d}_{d.day:02d}_{y}")
    tails.append(rf"_{d.month}_{day}_{y}")
    tails.append(rf"_{d.month}_{day2}_{y}")

    out = s
    for pat in tails:
        nxt = re.sub(pat + time_tail + r"$", "", out, flags=re.I)
        if nxt != out:
            out = nxt.rstrip("_")
    return out or slug


_STORE_EXTS_LONGEST_FIRST: Tuple[str, ...] = (
    ".docx",
    ".pptx",
    ".xlsx",
    ".opus",
    ".m4a",
    ".mp3",
    ".wav",
    ".pdf",
    ".rtf",
    ".doc",
    ".ppt",
    ".xls",
)


def meeting_document_storage_suffix(url: str) -> str:
    """
    Lowercase file extension (including dot) for the path tail of ``url``.

    Defaults to ``.pdf`` when no known meeting-document extension is present (handler URLs).
    """
    path = unquote((urlparse(url).path or "").lower())
    for ext in _STORE_EXTS_LONGEST_FIRST:
        if path.endswith(ext):
            return ext
    return ".pdf"


def slugify_meeting_filename(text: str, *, max_len: int = 110) -> str:
    """ASCII snake_case safe for POSIX/Windows filenames."""
    raw = unicodedata.normalize("NFKD", text or "")
    raw = raw.encode("ascii", "ignore").decode("ascii")
    raw = raw.lower()
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    if len(raw) > max_len:
        raw = raw[:max_len].rstrip("_")
    return raw or "document"


def build_meeting_pdf_disk_filename(
    url: str,
    anchor_text: str = "",
    doc_type: str = "",
    *,
    year_fallback: Optional[str] = None,
    storage_suffix: Optional[str] = None,
) -> str:
    """
    Basename ``YYYY-MM-DD_title_snake.<ext>`` (or ``YYYY_…`` when only calendar year is known).

    Uses :func:`pick_meeting_date` then manifest/year folder hint, then ``undated``.
    ``storage_suffix`` defaults from :func:`meeting_document_storage_suffix` (``.pdf``, ``.docx``, …).
    """
    suf = (storage_suffix or meeting_document_storage_suffix(url) or ".pdf").lower()
    if not suf.startswith("."):
        suf = "." + suf
    d, _ = pick_meeting_date(url=url, anchor=anchor_text, doc_type=doc_type or None)
    if d:
        date_prefix = d.isoformat()
    else:
        ys = (year_fallback or "").strip()
        if ys.isdigit() and len(ys) == 4:
            yi = int(ys)
            if 1990 <= yi <= 2100:
                date_prefix = ys
            else:
                date_prefix = "undated"
        else:
            date_prefix = "undated"

    title_src = pdf_meeting_title(anchor_text, url)
    dt = (doc_type or "").strip().lower()
    parts: List[str] = []
    if dt and dt != "unknown":
        parts.append(dt)
    if title_src:
        parts.append(title_src)
    raw_title = " ".join(parts) if parts else "meeting_document"
    if d:
        raw_title = strip_redundant_meeting_date_from_title(raw_title, d)
        raw_title = raw_title or "meeting_document"
    slug = slugify_meeting_filename(raw_title)
    if d:
        slug = strip_redundant_date_slug_suffix(slug, d)
    if slug in _GENERIC_TITLE_SLUGS or len(slug) < 4:
        h = hashlib.sha256(url.encode("utf-8", errors="replace")).hexdigest()[:8]
        slug = f"{slug}_{h}"

    base = f"{date_prefix}_{slug}{suf}"
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    base = re.sub(r"_+", "_", base)
    if len(base) > 200:
        stem = Path(base).stem[:170].rstrip("._")
        base = f"{stem}{suf}"
    return base


def allocate_unique_pdf_path(
    dest_dir: Path,
    url: str,
    anchor_text: str,
    doc_type: str,
    *,
    year_fallback: Optional[str],
    reserved_basenames: Optional[Set[str]] = None,
    reserved_paths: Optional[Set[str]] = None,
    ignore_existing_path: Optional[Path] = None,
    storage_suffix: Optional[str] = None,
) -> Path:
    """Pick ``dest_dir / <name>.<ext>``; append a URL hash before the extension if the name is taken."""
    blocked = reserved_basenames or set()
    path_block = reserved_paths or set()

    def taken(p: Path) -> bool:
        if path_block:
            try:
                if str(p.resolve()) in path_block:
                    return True
            except OSError:
                if str(p) in path_block:
                    return True
        if p.name in blocked:
            return True
        try:
            exists = p.exists()
        except OSError:
            exists = False
        if not exists:
            return False
        if ignore_existing_path is not None:
            try:
                if p.resolve() == ignore_existing_path.resolve():
                    return False
            except OSError:
                pass
        return True

    suf = storage_suffix or meeting_document_storage_suffix(url)
    if not suf.startswith("."):
        suf = "." + suf
    name = build_meeting_pdf_disk_filename(
        url,
        anchor_text,
        doc_type,
        year_fallback=year_fallback,
        storage_suffix=suf,
    )
    dest = dest_dir / name
    if not taken(dest):
        return dest
    stem = Path(name).stem
    h = hashlib.sha256(url.encode("utf-8", errors="replace")).hexdigest()[:8]
    alt = dest_dir / f"{stem}_{h}{suf}"
    if not taken(alt):
        return alt
    for i in range(2, 50):
        cand = dest_dir / f"{stem}_{h}_{i}{suf}"
        if not taken(cand):
            return cand
    return alt


def legacy_sha14_pdf_candidate(dest_dir: Path, url: str) -> Optional[Path]:
    """
    Older scrapes stored handler downloads as ``filedownload_<sha256(url)[:14]>.pdf``.

    Used when ``pdfs[].path`` still points at a missing ``…/filedownload.ashx`` shared path.
    """
    path_tail = Path(urlparse(url).path).name or ""
    stem = Path(path_tail).stem if path_tail else "filedownload"
    if stem.lower() != "filedownload":
        stem = "filedownload"
    h14 = hashlib.sha256(url.encode("utf-8", errors="replace")).hexdigest()[:14]
    p = dest_dir / f"{stem}_{h14}.pdf"
    return p if p.is_file() else None
