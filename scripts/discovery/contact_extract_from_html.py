"""
Extract contact hints from HTML fetched during meetings / jurisdiction crawls.

Collects ``mailto:`` and ``tel:`` links plus a conservative pass for visible email addresses
and US-style phone numbers in page text. Intended for manifest enrichment, not as verified CRM data.

:func:`extract_structured_contacts_from_html` adds best-effort **person-shaped** rows from
schema.org JSON-LD ``Person`` blocks and prominent ``mailto:`` anchors (for directory pages).
"""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Dict, List, Set, Tuple
from urllib.parse import unquote

_MAILTO_RE = re.compile(r"mailto:([^?#\"'>\s\\]+)", re.I)
_TEL_RE = re.compile(r"tel:([^?#\"'>\s\\]+)", re.I)
# Visible emails: avoid matching long hex-like strings
_EMAIL_RE = re.compile(
    r"(?<![a-z0-9._%+-])"
    r"[a-z0-9][a-z0-9._%+-]{0,63}"
    r"@[a-z0-9][a-z0-9.-]{0,253}\.[a-z]{2,63}"
    r"(?![a-z0-9._%+-])",
    re.I,
)
_PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]?)?(?:\(?[0-9]{3}\)?[-.\s/]?[0-9]{3}[-.\s/]?[0-9]{4})\b"
)
_BOGUS_EMAIL_SUFFIX = re.compile(
    r"\.(png|jpe?g|gif|webp|svg|ico|css|js|map|woff2?|ttf|eot)(\b|$)",
    re.I,
)


def _clean_mailto(raw: str) -> str:
    s = unescape(unquote((raw or "").strip()))
    if "," in s:
        s = s.split(",")[0].strip()
    return s.strip().lower()


def _normalize_phone_display(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return (raw or "").strip()[:24]


def extract_contacts_from_page(
    html: str,
    page_url: str,
    *,
    max_emails: int = 35,
    max_phones: int = 20,
) -> Dict[str, Any]:
    """
    Return ``{ "page_url", "emails": [...], "phones": [...] }`` for one HTML document.
    """
    emails: Set[str] = set()
    phones: Set[str] = set()
    text = html or ""

    for m in _MAILTO_RE.finditer(text):
        em = _clean_mailto(m.group(1))
        if "@" in em and not _BOGUS_EMAIL_SUFFIX.search(em):
            emails.add(em)

    for m in _TEL_RE.finditer(text):
        raw_tel = unquote(m.group(1).strip())
        if ";" in raw_tel:
            raw_tel = raw_tel.split(";", 1)[0].strip()
        digits = re.sub(r"\D", "", raw_tel)
        if len(digits) >= 10:
            phones.add(_normalize_phone_display(digits))

    # mailto already counted; skip those spans in a crude way — still OK if duplicate
    for m in _EMAIL_RE.finditer(text):
        em = m.group(0).strip().lower()
        if not _BOGUS_EMAIL_SUFFIX.search(em) and "@" in em:
            emails.add(em)

    for m in _PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) >= 10:
            phones.add(_normalize_phone_display(m.group(0)))

    return {
        "page_url": page_url,
        "emails": sorted(emails)[:max_emails],
        "phones": sorted(phones)[:max_phones],
    }


def merge_contact_manifest_rows(
    rows: List[Dict[str, Any]],
    *,
    max_distinct_emails: int = 80,
    max_distinct_phones: int = 50,
    max_pages_in_manifest: int = 28,
) -> Dict[str, Any]:
    """
    Merge per-page dicts from ``extract_contacts_from_page`` into one manifest object.
    """
    all_emails: Set[str] = set()
    all_phones: Set[str] = set()
    by_page: List[Dict[str, Any]] = []
    for row in rows:
        if not row:
            continue
        em = row.get("emails") or []
        ph = row.get("phones") or []
        if not em and not ph:
            continue
        by_page.append(row)
        all_emails.update(em)
        all_phones.update(ph)
    return {
        "emails": sorted(all_emails)[:max_distinct_emails],
        "phones": sorted(all_phones)[:max_distinct_phones],
        "by_page": by_page[:max_pages_in_manifest],
    }


def _norm_email(val: Any) -> str:
    if isinstance(val, list):
        val = val[0] if val else ""
    s = str(val or "").strip()
    if not s or "@" not in s:
        return ""
    return _clean_mailto(s)


def _json_ld_walk(obj: Any, out: List[Dict[str, Any]], *, page_url: str) -> None:
    if obj is None:
        return
    if isinstance(obj, dict):
        raw_type = obj.get("@type")
        types: Set[str] = set()
        if isinstance(raw_type, str):
            types.add(raw_type.strip().lower())
        elif isinstance(raw_type, list):
            types.update(str(x).strip().lower() for x in raw_type if x)
        if "person" in types:
            from scripts.discovery.contact_profile_images import collect_person_jsonld_image_urls

            name = obj.get("name") or obj.get("givenName")
            if isinstance(name, list):
                name = " ".join(str(x) for x in name if x).strip()
            else:
                name = str(name or "").strip()
            title = obj.get("jobTitle") or obj.get("worksFor")
            if isinstance(title, dict):
                title = title.get("name") or ""
            title_s = str(title or "").strip()
            email = _norm_email(obj.get("email"))
            phone = str(obj.get("telephone") or "").strip()[:64]
            prof = str(obj.get("url") or "").strip()[:4096]
            imgs = collect_person_jsonld_image_urls(obj, page_url)
            row: Dict[str, Any] = {
                "person_name": name[:512],
                "title_or_role": title_s[:512],
                "department": "",
                "email": email[:512] if email else None,
                "phone": phone or None,
                "mailing_address": "",
                "profile_url": prof or None,
                "extraction_method": "json_ld_person",
                "raw_row": {"@context": obj.get("@context"), "@type": raw_type, "source": page_url},
            }
            if imgs:
                row["profile_image_url"] = imgs[0]
            if name or email or phone or imgs:
                out.append(row)
        for v in obj.values():
            _json_ld_walk(v, out, page_url=page_url)
    elif isinstance(obj, list):
        for it in obj:
            _json_ld_walk(it, out, page_url=page_url)


def extract_structured_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 200,
) -> List[Dict[str, Any]]:
    """
    Return person-ish rows (name, title, email, phone, …) for directory-style pages.

    Sources: ``application/ld+json`` Person entities; ``mailto:`` anchors with link text
    that looks like a person's name.
    """
    from bs4 import BeautifulSoup

    rows: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str]] = set()
    soup = BeautifulSoup(html or "", "html.parser")

    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        _json_ld_walk(data, rows, page_url=page_url)

    for a in soup.select('a[href^="mailto:"]'):
        if len(rows) >= max_rows:
            break
        href = (a.get("href") or "").strip()
        m = _MAILTO_RE.search(href)
        if not m:
            continue
        email = _clean_mailto(m.group(1))
        if not email or "@" not in email:
            continue
        label = a.get_text(" ", strip=True)
        if "@" in label:
            label = ""
        name_guess = label[:512] if label and len(label) >= 3 else ""
        key = (email.lower(), name_guess.lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "person_name": name_guess or None,
                "title_or_role": None,
                "department": None,
                "email": email[:512],
                "phone": None,
                "mailing_address": None,
                "profile_url": None,
                "extraction_method": "mailto_anchor",
                "raw_row": {"page_url": page_url, "href": href[:500]},
            }
        )

    existing_keys = {_structured_contact_row_key(r) for r in rows}
    for hr in extract_heading_section_contacts_from_html(html, page_url, max_rows=max(0, max_rows - len(rows))):
        k = _structured_contact_row_key(hr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        rows.append(hr)
        if len(rows) >= max_rows:
            break

    rows.extend(extract_directory_cards_contacts_from_html(html, page_url, max_rows=max(0, max_rows - len(rows))))
    return rows[:max_rows]


def _structured_contact_row_key(r: Dict[str, Any]) -> Tuple[str, str, str, str]:
    ph = re.sub(r"\D", "", str(r.get("phone") or ""))[:15]
    return (
        str(r.get("email") or "").lower(),
        str(r.get("person_name") or "").lower()[:160],
        ph,
        str(r.get("title_or_role") or "").lower()[:160],
    )


_HEADING_ORDER = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

_ROLE_HEADING_LINE = re.compile(
    r"(?is)\b("
    r"commission(\s+chairman|\s+chair|\s+district\s*\d+|\s+member)?"
    r"|county\s+commission(\s+district\s*\d+)?"
    r"|probate\s+judge"
    r"|district\s*\d+"
    r"|mayor|vice\s*mayor"
    r"|council(\s*member|\s*president)?"
    r"|trustee|clerk|sheriff|superintendent|assessor|treasurer|tax\s+collector"
    r")\b",
)


def _tag_heading_level(tag: Any) -> int:
    from bs4 import Tag

    if not isinstance(tag, Tag):
        return 99
    return _HEADING_ORDER.get(tag.name, 99)


def _heading_section_blob(h: Any) -> str:
    from bs4 import NavigableString, Tag

    if not isinstance(h, Tag):
        return ""
    head = re.sub(r"\s+", " ", h.get_text(" ", strip=True) or "").strip()
    if not head:
        return ""
    lvl = _tag_heading_level(h)
    chunks: List[str] = [head]
    for sib in h.next_siblings:
        if isinstance(sib, NavigableString):
            t = str(sib).strip()
            if t:
                chunks.append(t)
            continue
        if not isinstance(sib, Tag):
            continue
        if sib.name in _HEADING_ORDER and _tag_heading_level(sib) <= lvl:
            break
        body = sib.get_text("\n", strip=True)
        body = re.sub(r"\s+", " ", body).strip()
        if body:
            chunks.append(body)
    return "\n".join(chunks)


def extract_heading_section_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 120,
) -> List[Dict[str, Any]]:
    """
    WordPress / brochure layouts: ``h2``–``h6`` section titles with plain-text ``Email:`` / phones
    (no ``mailto:``), e.g. Tuscaloosa County Commission district blocks.
    """
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out
    soup = BeautifulSoup(html, "html.parser")

    for h in soup.find_all(["h2", "h3", "h4", "h5", "h6"]):
        if len(out) >= max_rows:
            break
        blob = _heading_section_blob(h)
        if not blob or len(blob) < 24:
            continue
        title_guess = re.sub(r"\s+", " ", h.get_text(" ", strip=True) or "").strip()[:512] or None
        if not title_guess:
            continue
        if re.match(r"^about\s+", title_guess, re.I):
            continue

        lines_raw = [re.sub(r"\s+", " ", x).strip() for x in blob.split("\n") if x.strip()]
        preview = "\n".join(lines_raw[:5])[:900]

        emails: Set[str] = set()
        for m in _EMAIL_RE.finditer(blob):
            em = m.group(0).strip().lower()
            if "@" in em and not _BOGUS_EMAIL_SUFFIX.search(em):
                emails.add(em)
        email_list = sorted(emails)
        email_pri = email_list[0] if email_list else None

        phones: List[str] = []
        for pm in _PHONE_RE.finditer(blob):
            digits = re.sub(r"\D", "", pm.group(0))
            if len(digits) >= 10:
                phones.append(_normalize_phone_display(pm.group(0)))
        phone = phones[0] if phones else None

        if not email_pri and not phone:
            continue

        role_signal = bool(_ROLE_HEADING_LINE.search(title_guess) or _ROLE_HEADING_LINE.search(preview))

        name_guess = ""
        for ln in lines_raw[1:16]:
            if not ln or len(ln) > 160:
                continue
            if re.match(r"^(mailing\s+address|phone|email|fax|office|cell)\b", ln, re.I):
                continue
            if "@" in ln:
                continue
            digits = re.sub(r"\D", "", ln)
            if len(digits) >= 10:
                continue
            if re.search(r"\b\d{5}(?:-\d{4})?\b", ln) and len(ln) > 35:
                continue
            letters = re.sub(r"[^A-Za-z]", "", ln)
            if len(letters) < 4:
                continue
            name_guess = ln[:512]
            break

        if not role_signal and not name_guess:
            continue

        if not name_guess and title_guess and not _ROLE_HEADING_LINE.search(title_guess):
            if "@" not in title_guess and len(title_guess) <= 140:
                letters = re.sub(r"[^A-Za-z]", "", title_guess)
                if len(letters) >= 4:
                    name_guess = title_guess
                    title_guess = None

        maddr = None
        mm = re.search(
            r"Mailing\s+Address:\s*(.+?)(?=\n\s*(Phone|Cell|Email|Fax)\s*:|$)",
            blob,
            re.I | re.S,
        )
        if mm:
            maddr = re.sub(r"\s+", " ", mm.group(1).strip())[:500] or None

        out.append(
            {
                "person_name": name_guess or None,
                "title_or_role": title_guess,
                "department": None,
                "email": email_pri,
                "phone": phone,
                "mailing_address": maddr,
                "profile_url": None,
                "extraction_method": "heading_section_plaintext",
                "raw_row": {"page_url": page_url, "heading": (title_guess or "")[:200]},
            }
        )

    return out


def extract_directory_cards_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 120,
) -> List[Dict[str, Any]]:
    """
    Bootstrap-style ``div.card`` grids (Prime / Bootstrap) with an ``h1``–``h6`` title and body text.

    Captures mayor/council cards (name + role + phone) and committee assignment blurbs when phones
    are absent. Intended for pages already flagged as directory-like by the meetings crawl.
    """
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen: Set[Tuple[str, str, str]] = set()

    for card in soup.select("div.card"):
        if len(out) >= max_rows:
            break
        h = card.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        if not h:
            continue
        name = re.sub(r"\s+", " ", (h.get_text() or "")).strip()
        if not name or len(name) > 160:
            continue
        blob = card.get_text("\n", strip=True)
        phones: List[str] = []
        for pm in _PHONE_RE.finditer(blob):
            digits = re.sub(r"\D", "", pm.group(0))
            if len(digits) >= 10:
                phones.append(_normalize_phone_display(pm.group(0)))
        phone = phones[0] if phones else None

        role_chunks: List[str] = []
        for p in card.find_all("p"):
            t = re.sub(r"\s+", " ", p.get_text(" ", strip=True) or "").strip()
            if not t or len(t) > 800:
                continue
            digits_only = re.sub(r"\D", "", t)
            letters_only = re.sub(r"[^A-Za-z]", "", t)
            if len(digits_only) >= 10 and len(letters_only) < 4:
                continue
            p_raw = str(p)
            if "<a" in p_raw and "mailto:" in p_raw.lower() and len(t) < 8:
                continue
            role_chunks.append(t)
        title = " — ".join(role_chunks).strip()[:500] or None
        if phone and title:
            title = _PHONE_RE.sub("", title)
            title = re.sub(r"\s+", " ", title).strip()[:500] or None
        if not title and len(blob) > len(name) + 3:
            tail = blob.replace(name, "", 1).strip()
            tail = _PHONE_RE.sub("", tail)
            tail = re.sub(r"\s+", " ", tail).strip()[:500]
            title = tail or None

        key = (name.lower(), phone or "", (title or "")[:120])
        if key in seen:
            continue
        seen.add(key)

        tjoin = title or ""
        is_councillor_card = bool(phone) or bool(
            tjoin
            and len(tjoin) < 48
            and re.search(r"\bward\s*\d\b", tjoin, re.I)
        ) or bool(
            tjoin
            and len(tjoin) < 48
            and re.match(r"^\s*(mayor|vice\s+mayor)\s*$", tjoin.strip(), re.I | re.S)
        )
        is_committee_card = bool(not is_councillor_card and tjoin and ("," in tjoin or " and " in tjoin.lower()))
        method = "directory_card_committee" if is_committee_card else "directory_card_person"
        out.append(
            {
                "person_name": name[:512],
                "title_or_role": title,
                "department": None,
                "email": None,
                "phone": phone,
                "mailing_address": None,
                "profile_url": None,
                "extraction_method": method,
                "raw_row": {"page_url": page_url, "source": "bootstrap_card"},
            }
        )

    return out
