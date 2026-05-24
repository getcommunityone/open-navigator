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
from urllib.parse import parse_qs, unquote, urljoin, urlparse

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

    existing_keys = {_structured_contact_row_key(r) for r in rows}
    emails_seen = {str(r.get("email") or "").lower() for r in rows if r.get("email")}

    for cpr in extract_civicplus_staff_directory_hcard_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        k = _structured_contact_row_key(cpr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        em = str(cpr.get("email") or "").lower()
        if em:
            emails_seen.add(em)
        rows.append(cpr)
        if len(rows) >= max_rows:
            break

    for swr in extract_cityofwp_staff_cards_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        em = str(swr.get("email") or "").lower()
        if em and em in emails_seen:
            continue
        if em:
            emails_seen.add(em)
        k = _structured_contact_row_key(swr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        rows.append(swr)
        if len(rows) >= max_rows:
            break

    for dgr in extract_duda_gallery_staff_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        em = str(dgr.get("email") or "").lower()
        if em and em in emails_seen:
            continue
        if em:
            emails_seen.add(em)
        k = _structured_contact_row_key(dgr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        rows.append(dgr)
        if len(rows) >= max_rows:
            break

    for bcr in extract_brochure_card_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        em = str(bcr.get("email") or "").lower()
        if em and em in emails_seen:
            continue
        if em:
            emails_seen.add(em)
        k = _structured_contact_row_key(bcr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        rows.append(bcr)
        if len(rows) >= max_rows:
            break

    for bsr in extract_brochure_staff_section_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        em = str(bsr.get("email") or "").lower()
        k = _structured_contact_row_key(bsr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        rows.append(bsr)
        if em:
            emails_seen.add(em)
        if len(rows) >= max_rows:
            break

    for er in extract_elementor_directory_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        em = str(er.get("email") or "").lower()
        if em and em in emails_seen:
            continue
        if em:
            emails_seen.add(em)
        k = _structured_contact_row_key(er)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        rows.append(er)
        if len(rows) >= max_rows:
            break

    for ibr in extract_elementor_image_box_directory_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        k = _structured_contact_row_key(ibr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        rows.append(ibr)
        if len(rows) >= max_rows:
            break

    for wr in extract_wix_commissioner_lines_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        k = _structured_contact_row_key(wr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        rows.append(wr)
        if len(rows) >= max_rows:
            break

    for rr in extract_commissioner_roster_list_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        em = str(rr.get("email") or "").lower()
        if em and em in emails_seen:
            continue
        if em:
            emails_seen.add(em)
        k = _structured_contact_row_key(rr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        rows.append(rr)
        if len(rows) >= max_rows:
            break

    for a in soup.select('a[href^="mailto:"]'):
        if len(rows) >= max_rows:
            break
        if _tag_inside_wp_caption(a):
            continue
        href = (a.get("href") or "").strip()
        m = _MAILTO_RE.search(href)
        if not m:
            continue
        email = _clean_mailto(m.group(1))
        if not email or "@" not in email:
            continue
        if email in emails_seen:
            continue
        label = a.get_text(" ", strip=True)
        if "@" in label:
            label = ""
        if label and (
            _SEND_EMAIL_LABEL_RE.match(label)
            or _EMAIL_BUTTON_LABEL_RE.match(label)
        ):
            continue
        name_guess = label[:512] if label and len(label) >= 3 else ""
        key = (email.lower(), name_guess.lower())
        if key in seen:
            continue
        seen.add(key)
        emails_seen.add(email)
        row = {
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
        rk = _structured_contact_row_key(row)
        if rk in existing_keys:
            continue
        existing_keys.add(rk)
        rows.append(row)

    for hr in extract_heading_section_contacts_from_html(html, page_url, max_rows=max(0, max_rows - len(rows))):
        k = _structured_contact_row_key(hr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        rows.append(hr)
        if len(rows) >= max_rows:
            break

    for cr in extract_caboose_directory_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        k = _structured_contact_row_key(cr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        em = str(cr.get("email") or "").lower()
        if em:
            emails_seen.add(em)
        rows.append(cr)
        if len(rows) >= max_rows:
            break

    for cbr in extract_centreville_big_box_profile_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        k = _structured_contact_row_key(cbr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        em = str(cbr.get("email") or "").lower()
        if em:
            emails_seen.add(em)
        rows.append(cbr)
        if len(rows) >= max_rows:
            break

    for dtr in extract_divi_team_member_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        k = _structured_contact_row_key(dtr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        em = str(dtr.get("email") or "").lower()
        if em:
            emails_seen.add(em)
        rows.append(dtr)
        if len(rows) >= max_rows:
            break

    for wcr in extract_wp_caption_figure_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        k = _structured_contact_row_key(wcr)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        em = str(wcr.get("email") or "").lower()
        if em:
            emails_seen.add(em)
        rows.append(wcr)
        if len(rows) >= max_rows:
            break

    rows.extend(
        extract_directory_cards_contacts_from_html(
            html, page_url, max_rows=max(0, max_rows - len(rows))
        )
    )

    dept_keys: Set[Tuple[str, str, str]] = set()
    for dr in extract_department_office_contacts_from_html(
        html, page_url, max_rows=max(0, max_rows - len(rows))
    ):
        k = (
            str(dr.get("department") or ""),
            str(dr.get("phone") or ""),
            str(dr.get("mailing_address") or ""),
        )
        if k in dept_keys:
            continue
        dept_keys.add(k)
        rows.append(dr)
        if len(rows) >= max_rows:
            break

    for row in rows:
        normalize_structured_contact_row(row)
    rows = dedupe_structured_contact_rows(rows)
    return rows[:max_rows]


_BG_IMAGE_URL_RE = re.compile(
    r"background-image\s*:\s*url\(\s*['\"]?([^'\")]+)['\"]?\s*\)",
    re.I,
)
_COUNCILOR_PREFIX_RE = re.compile(r"^councilor\s+", re.I)
_DISTRICT_LABEL_RE = re.compile(r"^district\s*\d+\s*$", re.I)
_SEND_EMAIL_LABEL_RE = re.compile(r"^send\s+an\s+email$", re.I)
_EMAIL_BUTTON_LABEL_RE = re.compile(r"^email\s+\w[\w'.-]*$", re.I)
_CONTACT_COMMISSIONER_SUBJECT_RE = re.compile(
    r"^contact\s+commissioner\s+(.+)$",
    re.I,
)
_MENU_OR_CHROME_ALT_RE = re.compile(r"^(menu|logo|city of tuscaloosa)$", re.I)
_OFFICE_HONORIFIC_LINE_RE = re.compile(
    r"^(councilor|mayor|vice\s*mayor|commissioner|commission\s+chair(?:man)?|"
    r"trustee|alderman|supervisor|senator|representative|director)\s+(.+)$",
    re.I,
)
_MORE_INFO_BUTTON_RE = re.compile(r"more\s+info", re.I)
_WIX_COMMISSIONER_LINE_RE = re.compile(
    r"^([A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){1,3})\s*,\s*([A-Za-z][A-Za-z\s'`.-]+District)\s*$"
)
_WIX_HEADSHOT_ALT_NAME_RE = re.compile(
    r"headshot[_-]?([A-Za-z]+(?:[A-Z][a-z]+)+)",
    re.I,
)


def _abs_background_image_url(raw: str, page_url: str) -> str:
    u = (raw or "").strip()
    if not u or u.lower().startswith("data:"):
        return ""
    if u.startswith("//"):
        u = "https:" + u
    return urljoin(page_url, u)


def profile_image_url_from_style(style: str, page_url: str) -> str:
    """Parse ``background-image:url(...)`` from an inline style attribute."""
    m = _BG_IMAGE_URL_RE.search(style or "")
    if not m:
        return ""
    return _abs_background_image_url(m.group(1), page_url)


def is_decorative_profile_image_url(url: str) -> bool:
    """Site chrome (menu arrows, seals, logos) — not official headshots."""
    if not url:
        return True
    low = url.lower()
    if any(
        tok in low
        for tok in (
            "white_arrows",
            "dark_logo",
            "/images/seal",
            "seal.png",
            "favicon",
            "apple-touch-icon",
            "facebook.com/tr",
            "pixel.gif",
            "1x1",
            "accessibility-plugin",
            "onetap-pro",
            "icon-drop-down-menu",
            "weatherforyou.net",
        )
    ):
        return True
    if re.search(
        r"/wp-content/plugins/(?:accessibility|onetap)[^/]*/assets/images/(?:english|german|spanish|)",
        low,
    ):
        return True
    if re.search(r"/assets/[^/]+/images/(white_|dark_|logo)", low):
        return True
    return False


def is_generic_district_label(text: Optional[str]) -> bool:
    return bool(_DISTRICT_LABEL_RE.match((text or "").strip()))


_GENERIC_MAILBOX_LOCAL_PARTS = frozenset(
    {
        "cityclerk",
        "clerk",
        "info",
        "contact",
        "contacts",
        "admin",
        "webmaster",
        "noreply",
        "no-reply",
        "support",
        "help",
        "meetings",
        "council",
        "office",
        "staff",
        "hr",
        "media",
        "press",
    }
)
_EMAIL_NAME_SUFFIX_DISPLAY = {
    "jr": "Jr.",
    "sr": "Sr.",
    "ii": "II",
    "iii": "III",
    "iv": "IV",
}
_DEPARTMENT_OFFICE_HEADING_RE = re.compile(
    r"(?:contact\s+the\s+.+?\s+office|city\s+council\s+office)",
    re.I,
)
_CITY_COUNCIL_CONTEXT_RE = re.compile(r"city\s*council|councilor", re.I)


def is_generic_mailbox_email(email: Optional[str]) -> bool:
    em = (email or "").strip().lower()
    if "@" not in em:
        return False
    local = em.split("@", 1)[0].strip()
    return local in _GENERIC_MAILBOX_LOCAL_PARTS or any(
        x in local for x in ("noreply", "no-reply", "donotreply")
    )


def derive_person_name_from_email(email: Optional[str]) -> Optional[str]:
    """
    Best-effort name from ``first.last@domain`` (e.g. ``joseph.eatmon@tuscaloosa.com`` → Joseph Eatmon).

    Skips generic mailboxes (``cityclerk``, ``info``, …) and locals without at least two name parts.
    """
    em = (email or "").strip().lower()
    if "@" not in em:
        return None
    local, _domain = em.split("@", 1)
    local = local.strip()
    if not local or local in _GENERIC_MAILBOX_LOCAL_PARTS:
        return None
    if any(tok in local for tok in ("noreply", "no-reply", "donotreply")):
        return None

    parts = [p for p in re.split(r"[._\-+]+", local) if p and p.isalpha()]
    if len(parts) < 2:
        return None

    suffixes: List[str] = []
    while parts and parts[-1].lower() in _EMAIL_NAME_SUFFIX_DISPLAY:
        suffixes.insert(0, _EMAIL_NAME_SUFFIX_DISPLAY[parts.pop().lower()])

    if len(parts) < 2:
        return None

    name = " ".join(p[:1].upper() + p[1:].lower() for p in parts if len(p) >= 2)
    if not name:
        return None
    if suffixes:
        name = f"{name}, {' '.join(suffixes)}"
    return name[:512]


def _normalize_department_office_label(heading: str) -> str:
    """Map page heading to a stable department label."""
    h = re.sub(r"\s+", " ", (heading or "").strip())
    if not h:
        return "Department Office"
    if _CITY_COUNCIL_CONTEXT_RE.search(h):
        return "City Council Office"
    m = re.search(r"contact\s+the\s+(.+?)\s+office", h, re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip().title()) + " Office"
    return h[:512]


def extract_department_office_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 8,
) -> List[Dict[str, Any]]:
    """
    Caboose ``div.contact-block`` sections under headings like ``Contact the City Council Office``.

    Emits ``contact_scope=department`` rows (no ``person_name``) with shared mailing address / phone.
    """
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen: Set[str] = set()

    for h in soup.find_all(["h2", "h3", "h4"]):
        if len(out) >= max_rows:
            break
        heading = re.sub(r"\s+", " ", h.get_text(" ", strip=True) or "").strip()
        if not heading or not _DEPARTMENT_OFFICE_HEADING_RE.search(heading):
            continue
        block = h.find_next("div", class_=lambda c: c and "contact-block" in str(c))
        if block is None:
            continue

        phone: Optional[str] = None
        mailing_address: Optional[str] = None
        email_pri: Optional[str] = None

        for unit in block.select("div.c-unit"):
            h4 = unit.select_one("h4")
            label = re.sub(r"\s+", " ", (h4.get_text(" ", strip=True) if h4 else "")).strip().lower()
            if "mailing" in label:
                rich = unit.select_one(".richtext, .text-holder .richtext")
                if rich:
                    for br in rich.find_all("br"):
                        br.replace_with(", ")
                    mailing_address = re.sub(
                        r"\s*,\s*",
                        ", ",
                        re.sub(r"\s+", " ", rich.get_text(" ", strip=True) or ""),
                    ).strip()[:500] or None
            elif "phone" in label:
                tel_a = unit.select_one('a[href^="tel:"]')
                if tel_a:
                    m = _TEL_RE.search(tel_a.get("href") or "")
                    if m:
                        phone = _normalize_phone_display(m.group(1))
                if not phone:
                    raw = unit.get_text(" ", strip=True)
                    for pm in _PHONE_RE.finditer(raw):
                        digits = re.sub(r"\D", "", pm.group(0))
                        if len(digits) >= 10:
                            phone = _normalize_phone_display(pm.group(0))
                            break
            elif "email" in label:
                for a in unit.select('a[href^="mailto:"]'):
                    email_pri = _clean_mailto((a.get("href") or "").replace("mailto:", "", 1))
                    if email_pri:
                        break

        dept_label = _normalize_department_office_label(heading)
        dedupe_key = f"{dept_label}|{phone or ''}|{mailing_address or ''}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        if not phone and not mailing_address and not email_pri:
            continue

        out.append(
            {
                "person_name": None,
                "title_or_role": None,
                "department": dept_label,
                "office_heading": heading[:512],
                "contact_scope": "department",
                "email": email_pri,
                "phone": phone,
                "mailing_address": mailing_address,
                "profile_url": _strip_fragment_for_url(page_url) if _CITY_COUNCIL_CONTEXT_RE.search(
                    page_url
                ) or _CITY_COUNCIL_CONTEXT_RE.search(heading)
                else None,
                "profile_image_url": None,
                "extraction_method": "caboose_department_contact_block",
                "raw_row": {"page_url": page_url, "heading": heading[:200]},
            }
        )

    return out


def is_city_council_person_row(row: Dict[str, Any]) -> bool:
    """True when row looks like an individual council member (not the shared office)."""
    if str(row.get("contact_scope") or "").strip().lower() == "department":
        return False
    blob = " ".join(
        str(row.get(k) or "")
        for k in ("title_or_role", "department", "page_classification", "source_page_url", "profile_url")
    )
    if _CITY_COUNCIL_CONTEXT_RE.search(blob):
        return True
    if row.get("title_or_role") and str(row.get("title_or_role")).lower() == "councilor":
        return True
    if is_generic_district_label(str(row.get("department") or "")):
        return True
    return False


def _normalize_honorific_token(token: str) -> str:
    t = (token or "").strip().lower()
    if t == "vice mayor":
        return "Vice Mayor"
    if t.startswith("commission chair"):
        return "Commission Chair" if "chairman" not in t else "Commission Chairman"
    return (token or "").strip().title()


def split_office_holder_fields(
    combined_line: Optional[str],
    district_or_subtitle: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Split a combined heading like ``Councilor Joseph Eatmon, Sr.`` into:

    - ``person_name`` — bare name (``Joseph Eatmon, Sr.``)
    - ``title_or_role`` — honorific (``Councilor``)
    - ``department`` — district label (``District 1``) when provided separately
    """
    line = (combined_line or "").strip()
    sub = (district_or_subtitle or "").strip()

    if line and _SEND_EMAIL_LABEL_RE.match(line):
        line = ""

    district: Optional[str] = None
    if sub and is_generic_district_label(sub):
        district = sub
    elif line and is_generic_district_label(line) and not sub:
        return None, None, line

    if not line:
        return None, None, district

    m = _OFFICE_HONORIFIC_LINE_RE.match(line)
    if m:
        honor = _normalize_honorific_token(m.group(1))
        person = (m.group(2) or "").strip() or None
        return person, honor, district

    if is_generic_district_label(line):
        return None, None, line

    extra_dept = district
    if sub and is_generic_district_label(sub):
        extra_dept = sub
    elif sub and not extra_dept:
        return line, sub, None
    return line, None, extra_dept


def normalize_structured_contact_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Caboose / council layouts: honorific → ``title_or_role``, district → ``department``,
    bare name → ``person_name``. Fixes legacy swaps and button labels.
    """
    raw_name = (row.get("person_name") or "").strip()
    raw_title = (row.get("title_or_role") or "").strip()
    raw_dept = (row.get("department") or "").strip()

    if raw_name and _SEND_EMAIL_LABEL_RE.match(raw_name):
        raw_name = ""

    title_looks_like_honorific_person = False
    title_match = _OFFICE_HONORIFIC_LINE_RE.match(raw_title)
    title_tail = (title_match.group(2) or "").strip() if title_match else ""
    if (
        title_match
        and title_tail
        and not title_tail.lower().startswith("of ")
        and _looks_like_person_name_line(title_tail)
    ):
        title_looks_like_honorific_person = True

    if (
        raw_name
        and _looks_like_person_name_line(raw_name)
        and raw_title
        and raw_dept
        and not is_generic_district_label(raw_title)
        and not is_generic_district_label(raw_dept)
        and not title_looks_like_honorific_person
    ):
        row["person_name"] = raw_name
        row["title_or_role"] = raw_title
        row["department"] = raw_dept
        return row

    if (
        raw_name
        and _looks_like_person_name_line(raw_name)
        and raw_title
        and not raw_dept
        and not is_generic_district_label(raw_title)
        and not title_looks_like_honorific_person
    ):
        row["person_name"] = raw_name
        row["title_or_role"] = raw_title
        row["department"] = None
        return row

    combined = raw_name
    district_hint = raw_dept or None

    # Legacy: person_name was District N, title_or_role was Councilor Name
    if is_generic_district_label(raw_name) and raw_title and _OFFICE_HONORIFIC_LINE_RE.match(raw_title):
        combined = raw_title
        district_hint = raw_name
    elif raw_title and is_generic_district_label(raw_title) and not district_hint:
        district_hint = raw_title
        if raw_title == raw_name:
            raw_title = ""
    elif raw_dept and is_generic_district_label(raw_dept):
        district_hint = raw_dept

    person, honor, dept = split_office_holder_fields(combined or None, district_hint)

    if person:
        row["person_name"] = person
    elif combined and not is_generic_district_label(combined):
        row["person_name"] = combined
    else:
        row["person_name"] = None

    if honor:
        row["title_or_role"] = honor
    elif raw_title and not is_generic_district_label(raw_title) and not _OFFICE_HONORIFIC_LINE_RE.match(
        raw_title
    ):
        row["title_or_role"] = raw_title
    else:
        row["title_or_role"] = None

    if dept:
        row["department"] = dept
    elif raw_dept and not is_generic_district_label(raw_dept):
        row["department"] = raw_dept
    elif raw_title and is_generic_district_label(raw_title):
        row["department"] = raw_title
    else:
        row["department"] = None

    if not (row.get("person_name") or "").strip():
        em = (row.get("email") or "").strip()
        if em and str(row.get("contact_scope") or "") != "department":
            derived = derive_person_name_from_email(em)
            if derived:
                row["person_name"] = derived
                raw = row.get("raw_row")
                if isinstance(raw, dict):
                    raw["person_name_derived_from_email"] = True

    return row


def _merge_supplemental_contact_fields(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    """Keep the higher-quality row but fill gaps (e.g. index ``profile_url`` + detail email)."""
    for field in (
        "title_or_role",
        "department",
        "profile_url",
        "profile_image_url",
        "phone",
        "mailing_address",
    ):
        if not (dst.get(field) or "").strip() and (src.get(field) or "").strip():
            dst[field] = src[field]


def infer_profile_url_from_source_page(row: Dict[str, Any]) -> None:
    """When detail crawl set ``source_page_url`` but not ``profile_url``, use that page."""
    if (row.get("profile_url") or "").strip():
        return
    sp = (row.get("source_page_url") or row.get("raw_row", {}).get("page_url") or "").strip()
    if not sp:
        return
    if re.search(r"/district-\d|/citycouncil/district|/commissioner|/official/", sp, re.I):
        row["profile_url"] = _strip_fragment_for_url(sp)


def dedupe_structured_contact_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prefer rows with a real person name over mailto / heading noise for the same email."""
    department_rows: List[Dict[str, Any]] = []
    person_rows: List[Dict[str, Any]] = []
    for row in rows:
        if str(row.get("contact_scope") or "").strip().lower() == "department":
            department_rows.append(row)
        else:
            person_rows.append(row)

    by_email: Dict[str, Dict[str, Any]] = {}
    no_email: List[Dict[str, Any]] = []

    def _name_quality(r: Dict[str, Any]) -> int:
        n = str(r.get("person_name") or "").strip()
        if not n or _SEND_EMAIL_LABEL_RE.match(n):
            return 0
        if is_generic_district_label(n):
            return 1
        if _OFFICE_HONORIFIC_LINE_RE.match(n):
            return 2
        score = 4
        if r.get("department"):
            score += 1
        if r.get("email"):
            score += 2
        if r.get("profile_url"):
            score += 1
        if str(r.get("extraction_method") or "").startswith("caboose_staff_block"):
            score += 1
        if str(r.get("extraction_method") or "").startswith("civicplus_staff_directory"):
            score += 3
        if str(r.get("extraction_method") or "") in (
            "wp_caption_figure",
            "centreville_big_box_profile",
            "divi_team_member",
        ):
            score += 4
        if str(r.get("extraction_method") or "") == "mailto_anchor":
            score -= 2
        return score

    for row in person_rows:
        normalize_structured_contact_row(row)
        em = str(row.get("email") or "").strip().lower()
        if not em:
            no_email.append(row)
            continue
        person_key = str(row.get("person_name") or "").strip().lower()
        dedupe_key = em
        if person_key and not is_generic_district_label(person_key):
            dedupe_key = f"{em}\0{person_key}"
        prev = by_email.get(dedupe_key)
        if prev is None:
            by_email[dedupe_key] = row
        elif _name_quality(row) > _name_quality(prev):
            _merge_supplemental_contact_fields(row, prev)
            by_email[dedupe_key] = row
        else:
            _merge_supplemental_contact_fields(prev, row)
        if person_key and not is_generic_district_label(person_key):
            stale = by_email.get(em)
            if stale is not None and stale is not by_email.get(dedupe_key):
                if not str(stale.get("person_name") or "").strip():
                    del by_email[em]

    out = list(by_email.values()) + no_email
    seen: Set[Tuple[str, str, str, str]] = set()
    deduped: List[Dict[str, Any]] = []
    for row in out:
        infer_profile_url_from_source_page(row)
        k = _structured_contact_row_key(row)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(row)

    dept_seen: Set[Tuple[str, str, str]] = set()
    for row in department_rows:
        normalize_structured_contact_row(row)
        infer_profile_url_from_source_page(row)
        dk = (
            str(row.get("department") or "").lower(),
            str(row.get("phone") or ""),
            str(row.get("mailing_address") or ""),
        )
        if dk in dept_seen:
            continue
        dept_seen.add(dk)
        deduped.append(row)

    return deduped


def _caboose_person_detail_url(container: Any, page_url: str) -> str:
    """``More Info`` / district detail link on a Caboose councilor card (consistent ``a.btn`` placement)."""
    from bs4 import Tag

    if not isinstance(container, Tag):
        return ""
    for a in container.select("a.btn, a.transparent, a[href]"):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("mailto:"):
            continue
        label = re.sub(r"\s+", " ", a.get_text(" ", strip=True) or "").strip()
        if _MORE_INFO_BUTTON_RE.search(label) or re.search(
            r"/district-\d", href, re.I
        ):
            abs_u = urljoin(page_url, href)
            if abs_u.lower().startswith(("http://", "https://")):
                return abs_u
    return ""


def _caboose_headshot_url(container: Any, page_url: str, *, photo_sel: str) -> str:
    from bs4 import Tag

    if not isinstance(container, Tag):
        return ""
    photo = container.select_one(photo_sel)
    if not photo:
        return ""
    bg = profile_image_url_from_style(photo.get("style") or "", page_url)
    if bg and is_decorative_profile_image_url(bg):
        return ""
    return bg


def _parse_caboose_official_block(
    container: Any,
    page_url: str,
    *,
    name_sel: str,
    district_sel: str,
    photo_sel: str,
    extraction_method: str,
) -> Optional[Dict[str, Any]]:
    """Parse one Caboose councilor card or staff-block (photo + name + district + optional mailto)."""
    from bs4 import Tag

    if not isinstance(container, Tag):
        return None
    name_el = container.select_one(name_sel)
    district_el = container.select_one(district_sel)
    raw_name = re.sub(r"\s+", " ", (name_el.get_text(" ", strip=True) if name_el else "")).strip()
    raw_district = re.sub(r"\s+", " ", (district_el.get_text(" ", strip=True) if district_el else "")).strip()
    person, honor, dept = split_office_holder_fields(raw_name or None, raw_district or None)
    if not person and not honor:
        return None
    email_pri = None
    for a in container.select('a[href^="mailto:"]'):
        email_pri = _clean_mailto((a.get("href") or "").replace("mailto:", "", 1))
        if email_pri:
            break
    bg_url = _caboose_headshot_url(container, page_url, photo_sel=photo_sel)
    profile_url = _caboose_person_detail_url(container, page_url)
    # Index cards: More Info → district URL. Detail ``staff-block`` pages: this page is the profile.
    if not profile_url and extraction_method == "caboose_staff_block":
        profile_url = _strip_fragment_for_url(page_url)
    return {
        "person_name": person,
        "title_or_role": honor,
        "department": dept,
        "email": email_pri,
        "phone": None,
        "mailing_address": None,
        "profile_url": profile_url or None,
        "profile_image_url": bg_url or None,
        "extraction_method": extraction_method,
        "raw_row": {"page_url": page_url},
    }


def extract_caboose_person_detail_urls_from_html(
    html: str,
    page_url: str,
    *,
    max_urls: int = 40,
) -> List[str]:
    """
    Enqueue targets from council index cards: ``a.btn`` / ``More Info`` → district detail pages.
    """
    from bs4 import BeautifulSoup

    out: List[str] = []
    seen: Set[str] = set()
    if not html:
        return out
    soup = BeautifulSoup(html, "html.parser")
    for card in soup.select("div.city-council-index div.councilor"):
        if len(out) >= max_urls:
            break
        abs_u = _caboose_person_detail_url(card, page_url)
        if not abs_u:
            continue
        key = _strip_fragment_for_url(abs_u)
        if key in seen:
            continue
        seen.add(key)
        out.append(abs_u)
    return out


def _strip_fragment_for_url(url: str) -> str:
    u = (url or "").strip()
    if "#" in u:
        u = u.split("#", 1)[0]
    return u


_DISTRICT_IN_TITLE_RE = re.compile(r"district\s*(\d+)\b", re.I)


def _split_civicplus_job_title(job: str) -> Tuple[Optional[str], Optional[str]]:
    """``Council Member - District 1`` → role + department label."""
    raw = re.sub(r"\s+", " ", (job or "").strip())
    if not raw:
        return None, None
    m = _DISTRICT_IN_TITLE_RE.search(raw)
    if m:
        dept = f"District {m.group(1)}"
        role = _DISTRICT_IN_TITLE_RE.sub("", raw).strip(" -/|")
        role = re.sub(r"\s+", " ", role).strip() or None
        return role[:500] if role else None, dept
    return raw[:500], None


def extract_civicplus_staff_directory_hcard_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 120,
) -> List[Dict[str, Any]]:
    """
    CivicPlus ``widgetStaffDirectory`` cards (microformats ``h-card`` on Northport and similar).

    Parses ``p-name``, ``p-job-title``, ``u-email``, ``p-tel``, and ``p-link`` detail URLs.
    """
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen_emails: Set[str] = set()
    seen_no_email: Set[Tuple[str, str]] = set()

    for card in soup.select("li.widgetItem.h-card, li.h-card"):
        if len(out) >= max_rows:
            break
        name_el = card.select_one("h4.widgetTitle.p-name, h4.p-name, .p-name")
        name = re.sub(r"\s+", " ", (name_el.get_text(" ", strip=True) if name_el else "")).strip()
        if not name:
            img = card.select_one("img.u-photo, img[alt]")
            name = (img.get("alt") or img.get("title") or "").strip() if img else ""
        job_el = card.select_one(".p-job-title, .field.p-job-title")
        job_raw = re.sub(r"\s+", " ", (job_el.get_text(" ", strip=True) if job_el else "")).strip()
        title_or_role, department = _split_civicplus_job_title(job_raw)

        email = None
        for a in card.select('a[href^="mailto:"]'):
            email = _clean_mailto((a.get("href") or "").replace("mailto:", "", 1))
            if email:
                break

        phone = None
        tel_a = card.select_one(".p-tel a[href^='tel:'], a[href^='tel:']")
        if tel_a:
            phone = _normalize_phone_display(
                re.sub(r"^tel:", "", (tel_a.get("href") or ""), flags=re.I)
            )

        profile_url = None
        plink = card.select_one(".p-link a[href], a[href*='directory.aspx']")
        if plink and plink.get("href"):
            profile_url = urljoin(page_url, str(plink.get("href")).strip())

        profile_image_url = None
        photo = card.select_one("img.u-photo, img.field")
        if photo and photo.get("src"):
            profile_image_url = urljoin(page_url, str(photo.get("src")).strip())

        if not name and not email:
            continue
        if email:
            if email in seen_emails:
                continue
            seen_emails.add(email)
        else:
            nk = (name.lower(), (profile_url or "").lower())
            if nk in seen_no_email:
                continue
            seen_no_email.add(nk)

        out.append(
            {
                "person_name": name[:512] or None,
                "title_or_role": title_or_role,
                "department": department,
                "email": email[:512] if email else None,
                "phone": phone,
                "mailing_address": None,
                "profile_url": profile_url,
                "profile_image_url": profile_image_url,
                "extraction_method": "civicplus_staff_directory_hcard",
                "raw_row": {"page_url": page_url, "job_title": job_raw[:300]},
            }
        )

    for row in out:
        normalize_structured_contact_row(row)
    return out


def extract_civicplus_directory_detail_urls_from_html(
    html: str,
    page_url: str,
    *,
    max_urls: int = 40,
) -> List[str]:
    """``More Information`` links on CivicPlus staff directory index cards."""
    from bs4 import BeautifulSoup

    out: List[str] = []
    seen: Set[str] = set()
    soup = BeautifulSoup(html or "", "html.parser")
    for a in soup.select("li.h-card .p-link a[href], li.widgetItem.h-card a[href*='directory']"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        label = a.get_text(" ", strip=True) or ""
        if "directory.aspx" not in href.lower() and not _MORE_INFO_BUTTON_RE.search(label):
            continue
        abs_u = urljoin(page_url, href)
        if abs_u in seen:
            continue
        seen.add(abs_u)
        out.append(abs_u)
        if len(out) >= max_urls:
            break
    return out


def extract_caboose_directory_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 40,
) -> List[Dict[str, Any]]:
    """
    Caboose CMS council / staff layouts (City of Tuscaloosa and similar).

    - ``div.staff-block`` district bios (detail pages with email + bio)
    - ``div.city-council-index div.councilor`` listing cards (photo + More Info link)
    """
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen_emails: Set[str] = set()
    seen_no_email: Set[Tuple[str, str]] = set()

    def _append_parsed(row: Optional[Dict[str, Any]]) -> None:
        if not row or len(out) >= max_rows:
            return
        normalize_structured_contact_row(row)
        em = str(row.get("email") or "").strip().lower()
        if em:
            if em in seen_emails:
                return
            seen_emails.add(em)
        else:
            nk = (
                str(row.get("person_name") or "").lower(),
                str(row.get("profile_url") or "").lower(),
            )
            if nk in seen_no_email:
                return
            seen_no_email.add(nk)
        if not row.get("person_name") and not em:
            return
        out.append(row)

    for block in soup.select("div.staff-block"):
        if len(out) >= max_rows:
            break
        _append_parsed(
            _parse_caboose_official_block(
                block,
                page_url,
                name_sel="h2.name, h2.rtedit.name",
                district_sel="h4.title, h4.rtedit.title",
                photo_sel=".image-holder .img, div.img[style*='background-image']",
                extraction_method="caboose_staff_block",
            )
        )

    for card in soup.select("div.city-council-index div.councilor"):
        if len(out) >= max_rows:
            break
        _append_parsed(
            _parse_caboose_official_block(
                card,
                page_url,
                name_sel="h5.name",
                district_sel="p.title",
                photo_sel="div.photo[style*='background-image']",
                extraction_method="caboose_council_index_card",
            )
        )

    return out


def extract_caboose_background_profile_jobs(
    html: str,
    page_url: str,
    *,
    max_jobs: int = 40,
) -> List[Dict[str, Any]]:
    """Download jobs for Caboose ``background-image`` headshots (not ``<img>`` tags)."""
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    soup = BeautifulSoup(html or "", "html.parser")

    def _job_from_block(
        container: Any,
        *,
        name_sel: str,
        district_sel: str,
        photo_sel: str,
        match_method: str,
    ) -> None:
        if len(out) >= max_jobs:
            return
        parsed = _parse_caboose_official_block(
            container,
            page_url,
            name_sel=name_sel,
            district_sel=district_sel,
            photo_sel=photo_sel,
            extraction_method=match_method,
        )
        if not parsed or not parsed.get("profile_image_url"):
            return
        person = parsed.get("person_name")
        if not person or _SEND_EMAIL_LABEL_RE.match(str(person)):
            return
        bg = str(parsed["profile_image_url"])
        if bg in seen:
            return
        seen.add(bg)
        out.append(
            {
                "person_name": person,
                "title_or_role": parsed.get("title_or_role"),
                "department": parsed.get("department"),
                "email": parsed.get("email"),
                "image_url": bg,
                "match_method": match_method,
            }
        )

    for block in soup.select("div.staff-block"):
        _job_from_block(
            block,
            name_sel="h2.name, h2.rtedit.name",
            district_sel="h4.title, h4.rtedit.title",
            photo_sel=".image-holder .img, div.img[style*='background-image']",
            match_method="caboose_staff_block_bg",
        )

    for card in soup.select("div.city-council-index div.councilor"):
        _job_from_block(
            card,
            name_sel="h5.name",
            district_sel="p.title",
            photo_sel="div.photo[style*='background-image']",
            match_method="caboose_council_index_bg",
        )

    return out[:max_jobs]


def _centreville_big_box_mailto_fields(anchor: Any) -> Tuple[str, Optional[str]]:
    """Shared inbox + optional commissioner name from ``mailto:`` on Bibb-style cards."""
    href = (anchor.get("href") or "").strip() if anchor is not None else ""
    m = _MAILTO_RE.search(href)
    if not m:
        return "", None
    email = _clean_mailto(m.group(1))
    if not email or "@" not in email:
        return "", None
    person: Optional[str] = None
    try:
        parsed = urlparse(href)
        for subj in parse_qs(parsed.query).get("subject") or []:
            sm = _CONTACT_COMMISSIONER_SUBJECT_RE.match(unquote(subj).strip())
            if sm:
                person = (sm.group(1) or "").strip() or None
                break
    except (ValueError, TypeError):
        pass
    return email, person


def extract_centreville_big_box_profile_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 40,
) -> List[Dict[str, Any]]:
    """
    Centreville Tech ``div.big-box-profiles`` roster (Bibb County ``bibbal.com`` and similar).

    Headshots are CSS ``background-image`` on ``div.profile-picture``; names in ``div.upper``,
    district in ``div.lower``; shared ``mailto:`` buttons with ``subject=Contact Commissioner …``.
    """
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen: Set[Tuple[str, str]] = set()

    for box in soup.select("div.big-box-profiles"):
        if len(out) >= max_rows:
            break
        upper = box.select_one("div.upper")
        lower = box.select_one("div.lower")
        name_line = (upper.get_text(" ", strip=True) if upper else "").strip()
        district_line = (lower.get_text(" ", strip=True) if lower else "").strip()
        if not name_line:
            continue
        person, title, dept = split_office_holder_fields(name_line, district_line)
        if not person:
            continue

        email = ""
        mailto_person: Optional[str] = None
        for a in box.select('a[href^="mailto:"]'):
            email, mailto_person = _centreville_big_box_mailto_fields(a)
            if email:
                break
        if mailto_person and not person:
            person = mailto_person

        photo = box.select_one("div.profile-picture")
        bg_url = profile_image_url_from_style(
            (photo.get("style") or "") if photo else "",
            page_url,
        )

        key = (person.lower(), (email or "").lower())
        if key in seen:
            continue
        seen.add(key)

        row: Dict[str, Any] = {
            "person_name": person,
            "title_or_role": title,
            "department": dept,
            "email": email or None,
            "phone": None,
            "mailing_address": None,
            "profile_url": None,
            "extraction_method": "centreville_big_box_profile",
            "raw_row": {
                "page_url": page_url,
                "district_line": district_line[:200] if district_line else None,
            },
        }
        if bg_url:
            row["profile_image_url"] = bg_url
        normalize_structured_contact_row(row)
        out.append(row)

    return out


def extract_centreville_big_box_profile_background_profile_jobs(
    html: str,
    page_url: str,
    *,
    max_jobs: int = 40,
) -> List[Dict[str, Any]]:
    """Download jobs for Centreville Tech ``big-box-profiles`` background headshots."""
    jobs: List[Dict[str, Any]] = []
    for row in extract_centreville_big_box_profile_contacts_from_html(
        html, page_url, max_rows=max_jobs
    ):
        bg = str(row.get("profile_image_url") or "")
        person = row.get("person_name")
        if not bg or not person:
            continue
        jobs.append(
            {
                "person_name": person,
                "title_or_role": row.get("title_or_role"),
                "department": row.get("department"),
                "email": row.get("email"),
                "image_url": bg,
                "match_method": "centreville_big_box_profile_bg",
            }
        )
    return jobs


def _figure_is_wp_caption(figure: Any) -> bool:
    classes = " ".join(figure.get("class") or [])
    return "wp-caption" in classes.lower()


def _tag_inside_wp_caption(tag: Any) -> bool:
    for parent in getattr(tag, "parents", []):
        if getattr(parent, "name", None) == "figure" and _figure_is_wp_caption(parent):
            return True
    return False


def _parse_wp_caption_figure(figure: Any, page_url: str) -> Optional[Dict[str, Any]]:
    """
    WordPress ``figure.wp-caption`` roster (Choctaw County commissioners and similar).

    ``<figcaption class="wp-caption-text">`` holds name (often ``<strong>``), district, mailto.
    """
    img = figure.find("img")
    if img is None:
        return None
    cap = figure.find("figcaption")
    if cap is None:
        return None

    strong = cap.find("strong")
    name = (strong.get_text(" ", strip=True) if strong else "").strip()
    if not name:
        name = (img.get("alt") or "").strip()
    if not name or not _looks_like_person_name_line(name):
        return None

    email: Optional[str] = None
    for a in cap.select('a[href^="mailto:"]'):
        email = _mailto_from_anchor(a)
        if email:
            break

    phone: Optional[str] = None
    district: Optional[str] = None
    for line in re.split(r"[\n\r]+", cap.get_text("\n", strip=True) or ""):
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line.lower() == name.lower():
            continue
        if _DISTRICT_LINE_RE.match(line):
            district = line
            continue
        pm = _PHONE_RE.search(line)
        if pm and not phone:
            phone = pm.group(0).strip()
            continue
        if "@" in line and not email:
            em_m = _EMAIL_RE.search(line)
            if em_m:
                email = em_m.group(0).strip().lower()

    src = (img.get("src") or "").strip()
    if not src:
        srcset = (img.get("srcset") or "").split(",")[0].strip().split()[0:1]
        src = srcset[0] if srcset else ""
    image_url = _abs_background_image_url(src, page_url) if src else ""

    person, title, dept = split_office_holder_fields(name, district)
    if not person:
        return None

    row: Dict[str, Any] = {
        "person_name": person,
        "title_or_role": title,
        "department": dept,
        "email": email,
        "phone": phone,
        "mailing_address": None,
        "profile_url": None,
        "extraction_method": "wp_caption_figure",
        "raw_row": {"page_url": page_url, "figure_id": figure.get("id")},
    }
    if image_url:
        row["profile_image_url"] = image_url
    normalize_structured_contact_row(row)
    return row


def extract_divi_team_member_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 40,
) -> List[Dict[str, Any]]:
    """
    Divi Builder ``et_pb_team_member`` cards (Dale County and similar Elegant Themes sites).

    Structure: ``.et_pb_team_member_image img`` + ``h4.et_pb_module_header`` + ``p.et_pb_member_position``.
    """
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen: Set[str] = set()

    for mod in soup.select("div.et_pb_team_member"):
        if len(out) >= max_rows:
            break
        img = mod.select_one(".et_pb_team_member_image img, div.et_pb_team_member_image img")
        header = mod.select_one("h4.et_pb_module_header, .et_pb_module_header")
        position = mod.select_one("p.et_pb_member_position, .et_pb_member_position")
        name = (header.get_text(" ", strip=True) if header else "").strip()
        if not name and img is not None:
            name = (img.get("alt") or "").strip()
        if not name or not _looks_like_person_name_line(name):
            continue
        role_line = (position.get_text(" ", strip=True) if position else "").strip() or None
        person, title, dept = split_office_holder_fields(name, role_line)
        if not person:
            continue
        nk = person.lower()
        if nk in seen:
            continue
        seen.add(nk)

        image_url = ""
        if img is not None:
            src = (img.get("src") or "").strip()
            if src:
                image_url = _abs_background_image_url(src, page_url)

        row: Dict[str, Any] = {
            "person_name": person,
            "title_or_role": title,
            "department": dept,
            "email": None,
            "phone": None,
            "mailing_address": None,
            "profile_url": None,
            "extraction_method": "divi_team_member",
            "raw_row": {"page_url": page_url, "role_line": role_line},
        }
        if image_url:
            row["profile_image_url"] = image_url
        normalize_structured_contact_row(row)
        out.append(row)

    return out


def extract_divi_team_member_profile_jobs(
    html: str,
    page_url: str,
    *,
    max_jobs: int = 40,
) -> List[Dict[str, Any]]:
    """Profile download jobs from Divi ``et_pb_team_member`` portrait cards."""
    jobs: List[Dict[str, Any]] = []
    for row in extract_divi_team_member_contacts_from_html(html, page_url, max_rows=max_jobs):
        img_u = str(row.get("profile_image_url") or "")
        person = row.get("person_name")
        if not img_u or not person:
            continue
        jobs.append(
            {
                "person_name": person,
                "title_or_role": row.get("title_or_role"),
                "department": row.get("department"),
                "email": row.get("email"),
                "image_url": img_u,
                "match_method": "divi_team_member",
            }
        )
    return jobs


def extract_wp_caption_figure_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 40,
) -> List[Dict[str, Any]]:
    """Official portraits in WordPress ``figure.wp-caption`` blocks with ``figcaption`` bios."""
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen: Set[Tuple[str, str]] = set()

    for figure in soup.find_all("figure"):
        if len(out) >= max_rows:
            break
        if not _figure_is_wp_caption(figure):
            continue
        row = _parse_wp_caption_figure(figure, page_url)
        if not row:
            continue
        key = (
            str(row.get("person_name") or "").lower(),
            str(row.get("email") or "").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)

    return out


def extract_divi_team_member_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 40,
) -> List[Dict[str, Any]]:
    """
    Divi ``et_pb_team_member`` cards (Dale County and other Elegant Themes sites).

    Structure: ``.et_pb_team_member_image img`` + ``h4.et_pb_module_header`` + ``p.et_pb_member_position``.
    """
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen: Set[Tuple[str, str]] = set()

    for mod in soup.select("div.et_pb_team_member"):
        if len(out) >= max_rows:
            break
        img = mod.select_one(".et_pb_team_member_image img, div.et_pb_team_member_image img")
        header = mod.select_one("h4.et_pb_module_header, .et_pb_module_header")
        position = mod.select_one("p.et_pb_member_position, .et_pb_member_position")
        name = (header.get_text(" ", strip=True) if header else "").strip()
        if not name:
            name = (img.get("alt") or "").strip() if img else ""
        if not name or not _looks_like_person_name_line(name):
            continue
        role_line = (position.get_text(" ", strip=True) if position else "").strip() or None
        person, title, dept = split_office_holder_fields(name, role_line)
        if not person:
            continue

        email = None
        phone = None
        for a in mod.select('a[href^="mailto:"]'):
            email = _mailto_from_anchor(a) or email
        blob = mod.get_text("\n", strip=True) or ""
        if not phone:
            pm = _PHONE_RE.search(blob)
            if pm:
                phone = pm.group(0).strip()

        image_url = ""
        if img:
            src = (img.get("src") or "").strip()
            if src:
                image_url = _abs_background_image_url(src, page_url)

        key = (person.lower(), (email or "").lower())
        if key in seen:
            continue
        seen.add(key)

        row: Dict[str, Any] = {
            "person_name": person,
            "title_or_role": title,
            "department": dept,
            "email": email,
            "phone": phone,
            "mailing_address": None,
            "profile_url": None,
            "extraction_method": "divi_team_member",
            "raw_row": {"page_url": page_url},
        }
        if image_url:
            row["profile_image_url"] = image_url
        normalize_structured_contact_row(row)
        out.append(row)

    return out


def extract_divi_team_member_profile_jobs(
    html: str,
    page_url: str,
    *,
    max_jobs: int = 40,
) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    for row in extract_divi_team_member_contacts_from_html(html, page_url, max_rows=max_jobs):
        img_u = str(row.get("profile_image_url") or "")
        person = row.get("person_name")
        if not img_u or not person:
            continue
        jobs.append(
            {
                "person_name": person,
                "title_or_role": row.get("title_or_role"),
                "department": row.get("department"),
                "email": row.get("email"),
                "image_url": img_u,
                "match_method": "divi_team_member",
            }
        )
    return jobs


def extract_wp_caption_figure_profile_jobs(
    html: str,
    page_url: str,
    *,
    max_jobs: int = 40,
) -> List[Dict[str, Any]]:
    """Profile download jobs from ``figure.wp-caption`` portrait + figcaption name."""
    jobs: List[Dict[str, Any]] = []
    for row in extract_wp_caption_figure_contacts_from_html(html, page_url, max_rows=max_jobs):
        img_u = str(row.get("profile_image_url") or "")
        person = row.get("person_name")
        if not img_u or not person:
            continue
        jobs.append(
            {
                "person_name": person,
                "title_or_role": row.get("title_or_role"),
                "department": row.get("department"),
                "email": row.get("email"),
                "image_url": img_u,
                "match_method": "wp_caption_figure",
            }
        )
    return jobs


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

_SCRIPTY_OR_UI_LINE_RE = re.compile(
    r"(?is)(\$\(document\)|document\.ready\(|loadgooglemapsscript\(|"
    r"function\s*\(|\{\s*var\s+\w+\s*=|more\s+information\b|"
    r"commissioners:\s*$)"
)

_COMMISSIONER_SECTION_RE = re.compile(
    r"\b(board\s+of\s+commissioners|commissioners?)\b",
    re.I,
)
_NAME_DASH_ROLE_RE = re.compile(
    r"^([A-Za-z][A-Za-z'`.\-\s]{1,90}?)\s*[\u2013\u2014\-]\s*(.+)$",
    re.I,
)
_DASH_ONLY_ROLE_RE = re.compile(r"^[\u2013\u2014\-]\s*(.+)$", re.I)
_DISTRICT_LINE_RE = re.compile(r"^district\s*\d+\b", re.I)
_NON_PERSON_ROSTER_LINE_RE = re.compile(
    r"\b(board\s+of\s+commissioners|to\s+contact\s+all\s+commissioners|"
    r"for\s+general\s+inquiries|administrator\s+of\s+.+|copyright|all\s+rights\s+reserved)\b",
    re.I,
)
_NON_PERSON_NAME_TOKEN_RE = re.compile(
    r"\b(county|code|physical|address|view|map|directions|suite|agenda|minutes|contact\s+us)\b",
    re.I,
)


def _tag_heading_level(tag: Any) -> int:
    from bs4 import Tag

    if not isinstance(tag, Tag):
        return 99
    return _HEADING_ORDER.get(tag.name, 99)


def _looks_like_person_name_line(s: str) -> bool:
    s = (s or "").strip()
    if len(s) < 3 or len(s) > 140:
        return False
    if _SCRIPTY_OR_UI_LINE_RE.search(s):
        return False
    if _line_is_contact_label(s):
        return False
    if re.search(r"\d{3}\s*[-.)]\s*\d{3}", s):
        return False
    if "@" in s:
        return False
    letters = re.sub(r"[^A-Za-z]", "", s)
    if len(letters) < 4:
        return False
    return bool(re.search(r"[A-Za-z][A-Za-z][A-Za-z].*[A-Za-z]", s))


def _line_is_contact_label(line: str) -> bool:
    s = (line or "").strip()
    if len(s) < 2:
        return True
    return bool(re.match(r"^(mailing\s+address|phone|email|fax|office|cell)\b", s, re.I))


# Live pages wrap rows in <motion>; crawled HTML often drops that tag — never scope on ``motion``.
_ELEMENTOR_OFFICIAL_ROW_SEL = "div.elementor-element.e-flex.e-con.e-child"


def _mailto_from_anchor(a: Any) -> str | None:
    """Prefer visible link text when ``href`` mailto does not match (common Elementor bug)."""
    visible = re.sub(r"\s+", " ", (a.get_text(" ", strip=True) or "")).strip()
    if visible and "@" in visible:
        vm = _EMAIL_RE.search(visible)
        if vm:
            em = vm.group(0).strip().lower()
            if not _BOGUS_EMAIL_SUFFIX.search(em):
                return em
    m = _MAILTO_RE.search(a.get("href") or "")
    if not m:
        return None
    em = _clean_mailto(m.group(1))
    return em if "@" in em and not _BOGUS_EMAIL_SUFFIX.search(em) else None


def extract_cityofwp_staff_cards_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 120,
) -> List[Dict[str, Any]]:
    """Extract contacts from CityOfWP-style staff cards (e.g. ``li.mc-staff``)."""
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out

    soup = BeautifulSoup(html, "html.parser")
    seen: Set[Tuple[str, str]] = set()

    for card in soup.select("li.mc-staff, li[class*='mc-staff']"):
        if len(out) >= max_rows:
            break

        name = ""
        role = ""
        email = ""
        phone = ""
        profile_url = ""
        profile_image_url = ""

        h3 = card.find("h3")
        if h3 is not None:
            name = re.sub(r"\s+", " ", h3.get_text(" ", strip=True) or "").strip()
        if name.lower().startswith("honorable "):
            name = name[len("Honorable ") :].strip()

        for p in card.find_all("p"):
            t = re.sub(r"\s+", " ", p.get_text(" ", strip=True) or "").strip()
            if not t:
                continue
            if _ROLE_HEADING_LINE.search(t):
                role = t[:512]
                break

        for a in card.find_all("a"):
            href = (a.get("href") or "").strip()
            em = _mailto_from_anchor(a)
            if em:
                email = em
            if href and href.startswith(("http://", "https://")):
                profile_url = href

        img = card.find("img")
        if img is not None:
            src = (
                (img.get("src") or "").strip()
                or (img.get("data-src") or "").strip()
                or (img.get("data-lazy-src") or "").strip()
            )
            if src:
                profile_image_url = urljoin(page_url, src)

        phone_text = card.get_text(" ", strip=True)
        pm = _PHONE_RE.search(phone_text)
        if pm:
            phone = _normalize_phone_display(pm.group(0))

        if not email:
            continue

        key = (email.lower(), name.lower())
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                "person_name": name[:512] if name else None,
                "title_or_role": role[:512] if role else None,
                "department": None,
                "email": email[:512],
                "phone": phone or None,
                "mailing_address": None,
                "profile_url": profile_url or None,
                "profile_image_url": profile_image_url or None,
                "extraction_method": "cityofwp_staff_card",
                "raw_row": {"page_url": page_url, "source": "li.mc-staff"},
            }
        )

    return out


def extract_duda_gallery_staff_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 120,
) -> List[Dict[str, Any]]:
    """Extract staff rows from Duda photo gallery cards with caption blocks."""
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out

    soup = BeautifulSoup(html, "html.parser")
    seen: Set[Tuple[str, str]] = set()

    for card in soup.select("div.photoGalleryThumbs"):
        if len(out) >= max_rows:
            break

        title_el = card.select_one(".caption-title")
        text_el = card.select_one(".caption-text")
        link_el = card.select_one(".image-container a[href]")
        img_el = card.select_one(".image-container img")

        name = re.sub(r"\s+", " ", title_el.get_text(" ", strip=True) or "").strip() if title_el else ""
        if not name:
            continue
        if not _looks_like_person_name_line(name):
            continue

        role = None
        department = None
        if text_el is not None:
            parts = [
                re.sub(r"\s+", " ", p.get_text(" ", strip=True) or "").strip().replace("/ ", "/ ")
                for p in text_el.find_all(["p", "div"])
            ]
            parts = [p for p in parts if p]
            if parts:
                role = parts[0][:512]
            if len(parts) > 1:
                department = parts[1][:512]

        profile_url = None
        if link_el is not None:
            href = (link_el.get("href") or "").strip()
            if href and not href.startswith("#"):
                profile_url = urljoin(page_url, href)

        profile_image_url = None
        if link_el is not None:
            bg = (link_el.get("data-image-url") or "").strip()
            if bg:
                profile_image_url = urljoin(page_url, bg)
        if not profile_image_url and img_el is not None:
            src = (
                (img_el.get("data-src") or "").strip()
                or (img_el.get("src") or "").strip()
            )
            if src:
                profile_image_url = urljoin(page_url, src)

        key = (name.lower(), (profile_url or "").lower())
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                "person_name": name[:512],
                "title_or_role": role,
                "department": department,
                "email": None,
                "phone": None,
                "mailing_address": None,
                "profile_url": profile_url,
                "profile_image_url": profile_image_url,
                "extraction_method": "duda_photo_gallery_staff_card",
                "raw_row": {"page_url": page_url, "source": "div.photoGalleryThumbs"},
            }
        )

    return out


_BROCHURE_PLACEHOLDER_ALT_RE = re.compile(r"^(?:photo\s+coming\s+soon|placeholder)$", re.I)
_BROCHURE_STREET_RE = re.compile(
    r"\b(?:street|st\.?|road|rd\.?|avenue|ave\.?|highway|hwy\.?|route|suite|county\s+road|court|ct\.?)\b",
    re.I,
)
_BROCHURE_CITY_STATE_RE = re.compile(r"\b[A-Za-z .'-]+,\s*[A-Z][a-z]?\.?\s+\d{5}(?:-\d{4})?\b")


def _is_brochure_addressish_line(line: str) -> bool:
    s = re.sub(r"\s+", " ", (line or "")).strip()
    if not s:
        return False
    if _BROCHURE_CITY_STATE_RE.search(s):
        return True
    if re.search(r"\b(?:po\s+box|box)\b", s, re.I):
        return True
    if re.search(r"\d", s) and _BROCHURE_STREET_RE.search(s):
        return True
    return False


def extract_brochure_card_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 120,
) -> List[Dict[str, Any]]:
    """Extract single-person brochure cards from compact ``div`` blocks with one image and one email."""
    from bs4 import BeautifulSoup, Tag

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out

    soup = BeautifulSoup(html, "html.parser")
    seen: Set[Tuple[str, str]] = set()
    candidates: List[Tag] = []

    for div in soup.find_all("div"):
        if not isinstance(div, Tag):
            continue
        imgs = div.find_all("img")
        if len(imgs) != 1:
            continue
        text = re.sub(r"\s+", " ", div.get_text(" ", strip=True) or "").strip()
        if not text or len(text) < 12 or len(text) > 800:
            continue

        emails: Set[str] = set()
        for a in div.select('a[href^="mailto:"]'):
            hm = _MAILTO_RE.search((a.get("href") or "").strip())
            if hm:
                em = _clean_mailto(hm.group(1))
                if em and "@" in em and not _BOGUS_EMAIL_SUFFIX.search(em):
                    emails.add(em)
        if not emails:
            for m in _EMAIL_RE.finditer(text):
                em = m.group(0).strip().lower()
                if em and not _BOGUS_EMAIL_SUFFIX.search(em):
                    emails.add(em)
        if len(emails) != 1:
            continue
        candidates.append(div)

    candidates.sort(key=lambda d: len(re.sub(r"\s+", " ", d.get_text(" ", strip=True) or "")))

    for div in candidates:
        if len(out) >= max_rows:
            break

        text = div.get_text("\n", strip=True) or ""
        lines_raw = [re.sub(r"\s+", " ", x).strip() for x in text.split("\n") if x.strip()]
        lines: List[str] = []
        seen_lines: Set[str] = set()
        for line in lines_raw:
            key = line.lower()
            if key in seen_lines:
                continue
            seen_lines.add(key)
            lines.append(line)
        if not lines:
            continue

        emails: List[str] = []
        for a in div.select('a[href^="mailto:"]'):
            hm = _MAILTO_RE.search((a.get("href") or "").strip())
            if hm:
                em = _clean_mailto(hm.group(1))
                if em and "@" in em and not _BOGUS_EMAIL_SUFFIX.search(em):
                    emails.append(em)
        if not emails:
            for m in _EMAIL_RE.finditer(" ".join(lines)):
                em = m.group(0).strip().lower()
                if em and not _BOGUS_EMAIL_SUFFIX.search(em):
                    emails.append(em)
        emails = sorted(set(emails))
        if len(emails) != 1:
            continue
        email = emails[0]

        img = div.find("img")
        img_alt = re.sub(r"\s+", " ", (img.get("alt") or "")).strip() if img else ""
        name = ""
        title = None
        department = None

        if img_alt and not _BROCHURE_PLACEHOLDER_ALT_RE.match(img_alt) and _looks_like_person_name_line(img_alt):
            name = img_alt

        filtered_lines: List[str] = []
        for line in lines:
            low = line.lower()
            if any(em in low for em in emails):
                continue
            if low == "commission office staff":
                continue
            filtered_lines.append(line)

        if filtered_lines and is_generic_district_label(filtered_lines[0]):
            department = filtered_lines[0][:512]
            filtered_lines = filtered_lines[1:]

        if filtered_lines:
            first = filtered_lines[0]
            if not name and _looks_like_person_name_line(first):
                name = first
                filtered_lines = filtered_lines[1:]
            elif not name and len(filtered_lines) > 1 and _looks_like_person_name_line(filtered_lines[1]):
                title = first[:512]
                name = filtered_lines[1]
                filtered_lines = filtered_lines[2:]

        if name and filtered_lines:
            for index, line in enumerate(filtered_lines):
                if line.lower() == name.lower():
                    if index > 0:
                        prev = filtered_lines[index - 1]
                        if not _is_brochure_addressish_line(prev) and not _PHONE_RE.search(prev):
                            title = prev[:512]
                    filtered_lines = filtered_lines[index + 1 :]
                    break

        if name and " - " in name:
            maybe_name, maybe_role = [x.strip() for x in name.split(" - ", 1)]
            if _looks_like_person_name_line(maybe_name) and maybe_role:
                name = maybe_name
                title = maybe_role[:512]

        if not name:
            derived = derive_person_name_from_email(email)
            if derived:
                name = derived

        if not name or not _looks_like_person_name_line(name) or _is_brochure_addressish_line(name):
            continue

        phone = None
        joined = " \n ".join(lines)
        pm = _PHONE_RE.search(joined)
        if pm:
            phone = _normalize_phone_display(pm.group(0))

        address_lines: List[str] = []
        for line in filtered_lines:
            if _PHONE_RE.search(line):
                break
            if _is_brochure_addressish_line(line):
                address_lines.append(line)
        mailing_address = ", ".join(address_lines)[:500] if address_lines else None

        profile_image_url = None
        if img is not None:
            src = (img.get("src") or "").strip()
            if src and not _BROCHURE_PLACEHOLDER_ALT_RE.match(img_alt or ""):
                abs_img = urljoin(page_url, src)
                if not is_decorative_profile_image_url(abs_img):
                    profile_image_url = abs_img

        key = (name.lower(), email.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "person_name": name[:512],
                "title_or_role": title,
                "department": department,
                "email": email[:512],
                "phone": phone,
                "mailing_address": mailing_address,
                "profile_url": None,
                "profile_image_url": profile_image_url,
                "extraction_method": "brochure_contact_card",
                "raw_row": {"page_url": page_url, "source": "div_brochure_card"},
            }
        )

    return out


def extract_brochure_staff_section_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 120,
) -> List[Dict[str, Any]]:
    """Extract role/name/email sequences from grouped brochure office staff sections."""
    from bs4 import BeautifulSoup, NavigableString, Tag

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out

    soup = BeautifulSoup(html, "html.parser")
    seen: Set[Tuple[str, str]] = set()

    for marker in soup.find_all(string=re.compile(r"commission\s+office\s+staff", re.I)):
        if len(out) >= max_rows:
            break
        if not isinstance(marker, NavigableString):
            continue

        chosen: Optional[Tag] = None
        node = marker.parent
        while isinstance(node, Tag):
            mailtos = node.select('a[href^="mailto:"]')
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True) or "").strip()
            if len(mailtos) >= 3 and len(text) <= 2500:
                chosen = node
                break
            node = node.parent
        if chosen is None:
            continue

        lines_all = [re.sub(r"\s+", " ", x).strip() for x in chosen.get_text("\n", strip=True).split("\n") if x.strip()]
        if not lines_all:
            continue

        start = 0
        for i, line in enumerate(lines_all):
            if re.search(r"commission\s+office\s+staff", line, re.I):
                start = i
                break
        end = len(lines_all)
        for i in range(start + 1, len(lines_all)):
            if re.search(r"county\s+commissioner'?s\s+contact\s+information", lines_all[i], re.I):
                end = i
                break
        lines = lines_all[start:end]
        if len(lines) < 5:
            continue

        emails: List[str] = []
        for a in chosen.select('a[href^="mailto:"]'):
            hm = _MAILTO_RE.search((a.get("href") or "").strip())
            if not hm:
                continue
            em = _clean_mailto(hm.group(1))
            if em and "@" in em and not _BOGUS_EMAIL_SUFFIX.search(em):
                emails.append(em)
        if not emails:
            continue

        email_index = 0
        i = 1
        while i + 1 < len(lines) and len(out) < max_rows and email_index < len(emails):
            role = lines[i]
            name = lines[i + 1]
            if re.search(r"^\d{3}[-.\s/]?\d{3}[-.\s/]?\d{4}$", role) or _is_brochure_addressish_line(role):
                i += 1
                continue
            if not _looks_like_person_name_line(name):
                i += 1
                continue

            phone = None
            j = i + 2
            if j < len(lines) and _PHONE_RE.search(lines[j]):
                phone = _normalize_phone_display(_PHONE_RE.search(lines[j]).group(0))
                j += 1

            email = emails[email_index]
            email_index += 1
            key = (name.lower(), email.lower())
            if key not in seen:
                seen.add(key)
                out.append(
                    {
                        "person_name": name[:512],
                        "title_or_role": role[:512],
                        "department": None,
                        "email": email[:512],
                        "phone": phone,
                        "mailing_address": None,
                        "profile_url": None,
                        "profile_image_url": None,
                        "extraction_method": "brochure_staff_section",
                        "raw_row": {"page_url": page_url, "source": "commission_office_staff_section"},
                    }
                )
                i = j + 1

    return out


def _iter_elementor_official_bands(soup: Any):
    """
    Elementor county-official rows: flex ``e-child`` containers with headings and mailto.

    Do not scope with the custom ``<motion>`` tag — crawled HTML often omits it and
    BeautifulSoup's CSS engine does not match ``motion`` descendants reliably.
    """
    from bs4 import Tag

    for band in soup.select(_ELEMENTOR_OFFICIAL_ROW_SEL):
        if not isinstance(band, Tag):
            continue
        if not band.select(".elementor-widget-heading"):
            continue
        if not band.select('a[href^="mailto:"]') and not band.select(".elementor-widget-text-editor"):
            continue
        yield band


def _parse_elementor_official_band(band: Any) -> Optional[Dict[str, Any]]:
    """
    Elementor row: portrait column + ``h2`` role + ``h3`` name + text-editor (mailto / phones).

    Headings are nested inside widget containers, so :func:`_heading_section_blob` on raw ``h2``
    tags does not see the contact block.
    """
    from bs4 import Tag

    if not isinstance(band, Tag):
        return None
    blob = band.get_text("\n", strip=True)
    if len(blob) < 20:
        return None
    if not band.select('a[href^="mailto:"]') and not _EMAIL_RE.search(blob):
        return None

    role = ""
    name = ""
    for h in band.select(".elementor-widget-heading h2, .elementor-widget-heading h3"):
        t = re.sub(r"\s+", " ", h.get_text(" ", strip=True) or "").strip()
        if not t:
            continue
        if h.name == "h2" and _ROLE_HEADING_LINE.search(t):
            role = t[:512]
        elif h.name == "h3" and _looks_like_person_name_line(t):
            name = t[:512]
        elif h.name == "h2" and _looks_like_person_name_line(t) and not role:
            name = t[:512]

    email_pri = None
    mailto_roots = band.select(".elementor-widget-text-editor") or [band]
    for root in mailto_roots:
        for a in root.select('a[href^="mailto:"]'):
            email_pri = _mailto_from_anchor(a)
            if email_pri:
                break
        if email_pri:
            break
    if not email_pri:
        for m in _EMAIL_RE.finditer(blob):
            em = m.group(0).strip().lower()
            if "@" in em and not _BOGUS_EMAIL_SUFFIX.search(em):
                email_pri = em
                break

    phones: List[str] = []
    for a in band.select('a[href^="tel:"]'):
        m = _TEL_RE.search(a.get("href") or "")
        if m:
            phones.append(_normalize_phone_display(m.group(1)))
    if not phones:
        for pm in _PHONE_RE.finditer(blob):
            digits = re.sub(r"\D", "", pm.group(0))
            if len(digits) >= 10:
                phones.append(_normalize_phone_display(pm.group(0)))
    phone = phones[0] if phones else None

    if not email_pri and not phone:
        return None
    if not name and not role:
        return None

    maddr = None
    mm = re.search(
        r"Mailing\s+Address:\s*(.+?)(?=\n\s*(Phone|Cell|Email|Fax)\s*:|$)",
        blob,
        re.I | re.S,
    )
    if mm:
        maddr = re.sub(r"\s+", " ", mm.group(1).strip())[:500] or None

    return {
        "person_name": name or None,
        "title_or_role": role or None,
        "department": None,
        "email": email_pri[:512] if email_pri else None,
        "phone": phone,
        "mailing_address": maddr,
        "profile_url": None,
        "extraction_method": "elementor_official_row",
        "raw_row": {"page_url": "", "role": role[:120], "name": (name or "")[:120]},
    }


def extract_elementor_directory_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 80,
) -> List[Dict[str, Any]]:
    """Official cards on Elementor flex rows (e.g. Tuscaloosa County Commission districts)."""
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out
    soup = BeautifulSoup(html or "", "html.parser")
    seen_emails: Set[str] = set()

    for band in _iter_elementor_official_bands(soup):
        if len(out) >= max_rows:
            break
        row = _parse_elementor_official_band(band)
        if not row:
            continue
        em = str(row.get("email") or "").lower()
        if em and em in seen_emails:
            continue
        if em:
            seen_emails.add(em)
        row["raw_row"] = {**row.get("raw_row", {}), "page_url": page_url}
        out.append(row)

    return out


_ELEMENTOR_IMAGE_BOX_HONORIFIC_RE = re.compile(
    r"^(commissioner|mayor|vice\s*mayor|chair(?:man|woman|person)?|trustee|"
    r"alderman|alderwoman|supervisor|senator|representative|director|councilor|"
    r"council\s*member)\s+",
    re.I,
)


def _strip_image_box_honorific(name: str) -> str:
    """``Commissioner Kylon Fort`` → ``Kylon Fort``; honorific belongs in title, not name."""
    return _ELEMENTOR_IMAGE_BOX_HONORIFIC_RE.sub("", (name or "").strip(), count=1).strip()


def extract_elementor_image_box_directory_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 40,
) -> List[Dict[str, Any]]:
    """
    Elementor ``image-box`` widgets used for commissioner / staff rosters.

    Pattern (Berrien County GA and similar WordPress + Elementor sites)::

        <div class="elementor-image-box-wrapper">
          <figure class="elementor-image-box-img">
            <img alt="..." src="...headshot.jpg" srcset="..."/>
          </figure>
          <div class="elementor-image-box-content">
            <h3 class="elementor-image-box-title">John Nugent</h3>
            <p class="elementor-image-box-description">District 1</p>
          </div>
        </div>

    Emits one row per box pairing the title (name) with the description (district /
    role / sub-title) and the headshot URL. Skips boxes whose title is not a
    plausible person name (chrome like "COUNTY COMMISSIONERS", "TAX ASSESSOR").
    """
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen: Set[Tuple[str, str]] = set()

    for box in soup.select("div.elementor-image-box-wrapper"):
        if len(out) >= max_rows:
            break
        title_el = box.select_one(
            "h1.elementor-image-box-title, h2.elementor-image-box-title, "
            "h3.elementor-image-box-title, h4.elementor-image-box-title, "
            "h5.elementor-image-box-title, h6.elementor-image-box-title, "
            ".elementor-image-box-title"
        )
        desc_el = box.select_one("p.elementor-image-box-description, .elementor-image-box-description")

        raw_name = re.sub(
            r"\s+", " ", (title_el.get_text(" ", strip=True) if title_el else "")
        ).strip()
        description = re.sub(
            r"\s+", " ", (desc_el.get_text(" ", strip=True) if desc_el else "")
        ).strip()

        name = _strip_image_box_honorific(raw_name)
        if not name or not _looks_like_person_name_line(name):
            continue
        if name.isupper() and len(name.split()) < 2:
            continue

        profile_image_url = None
        img_el = box.select_one("figure.elementor-image-box-img img[src], img[src]")
        if img_el is not None:
            src = str(img_el.get("src") or "").strip()
            if src and not src.lower().startswith("data:"):
                candidate = urljoin(page_url, src)
                if not is_decorative_profile_image_url(candidate):
                    profile_image_url = candidate

        key = (name.lower(), description.lower())
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                "person_name": name[:512],
                "title_or_role": description[:512] or None,
                "department": None,
                "email": None,
                "phone": None,
                "mailing_address": None,
                "profile_url": None,
                "profile_image_url": profile_image_url,
                "extraction_method": "elementor_image_box",
                "raw_row": {
                    "page_url": page_url,
                    "raw_title": raw_name[:200],
                    "description": description[:200],
                },
            }
        )

    return out


def extract_wix_commissioner_lines_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 80,
) -> List[Dict[str, Any]]:
    """Extract commissioner rows from Wix plain text lines and headshot image alts."""
    from bs4 import BeautifulSoup

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out

    soup = BeautifulSoup(html, "html.parser")
    lines = [
        re.sub(r"\s+", " ", x).strip()
        for x in soup.get_text("\n").split("\n")
        if x and x.strip()
    ]

    headshots: Dict[str, str] = {}
    for img in soup.find_all("img"):
        alt = str(img.get("alt") or "").strip()
        src = str(img.get("src") or "").strip()
        srcset = str(img.get("srcset") or "").strip()
        if "headshot" not in alt.lower() and "headshot" not in src.lower() and "headshot" not in srcset.lower():
            continue
        m = _WIX_HEADSHOT_ALT_NAME_RE.search(alt)
        if not m:
            continue
        camel = m.group(1)
        display_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", camel).strip()
        image_url = src
        if not image_url and srcset:
            image_url = srcset.split(",", 1)[0].strip().split(" ")[0]
        if not image_url:
            continue
        headshots[display_name.lower()] = image_url

    seen: Set[Tuple[str, str]] = set()
    for ln in lines:
        if len(out) >= max_rows:
            break
        m = _WIX_COMMISSIONER_LINE_RE.match(ln)
        if not m:
            continue
        name = m.group(1).strip()
        district = m.group(2).strip()
        if not _looks_like_person_name_line(name):
            continue
        key = (name.lower(), district.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "person_name": name[:512],
                "title_or_role": district[:512],
                "department": None,
                "email": None,
                "phone": None,
                "mailing_address": None,
                "profile_url": None,
                "profile_image_url": headshots.get(name.lower()),
                "extraction_method": "wix_commissioner_lines",
                "raw_row": {"page_url": page_url, "line": ln[:200]},
            }
        )

    return out


def _heading_section_blob(h: Any) -> str:
    from bs4 import NavigableString, Tag

    if not isinstance(h, Tag):
        return ""
    widget = h.find_parent(class_=lambda c: c and "elementor-widget" in str(c))
    if widget is not None:
        head = re.sub(r"\s+", " ", h.get_text(" ", strip=True) or "").strip()
        if not head:
            return ""
        lvl = _tag_heading_level(h)
        chunks: List[str] = [head]
        for sib in widget.find_next_siblings():
            if not hasattr(sib, "get") or not hasattr(sib, "name"):
                continue
            if "elementor-widget-heading" in " ".join(sib.get("class") or []):
                inner = sib.find(["h1", "h2", "h3", "h4", "h5", "h6"])
                if inner is not None and _tag_heading_level(inner) <= lvl:
                    break
            if "elementor-widget" in " ".join(sib.get("class") or []):
                body = sib.get_text("\n", strip=True)
                body = re.sub(r"\s+", " ", body).strip()
                if body:
                    chunks.append(body)
        return "\n".join(chunks)

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
    roster_seen: Set[Tuple[str, str]] = set()
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

        section_is_commissioners = any(_COMMISSIONER_SECTION_RE.search(ln) for ln in lines_raw[:8])
        if section_is_commissioners:
            i = 0
            while i < len(lines_raw) and len(out) < max_rows:
                ln = lines_raw[i]
                if not ln or len(ln) > 170 or _NON_PERSON_ROSTER_LINE_RE.search(ln):
                    i += 1
                    continue

                name = ""
                role = ""
                m_inline = _NAME_DASH_ROLE_RE.match(ln)
                if m_inline:
                    name = re.sub(r"\s+", " ", m_inline.group(1)).strip()
                    role = re.sub(r"\s+", " ", m_inline.group(2)).strip()
                elif _looks_like_person_name_line(ln):
                    name = ln.strip()
                    if i + 1 < len(lines_raw):
                        n1 = lines_raw[i + 1].strip()
                        m_role = _DASH_ONLY_ROLE_RE.match(n1)
                        if m_role:
                            role = re.sub(r"\s+", " ", m_role.group(1)).strip()
                            i += 1
                            if i + 1 < len(lines_raw):
                                n2 = lines_raw[i + 1].strip()
                                if _DISTRICT_LINE_RE.match(n2):
                                    role = f"{role} {n2}".strip()
                                    i += 1

                if name and _looks_like_person_name_line(name) and not _NON_PERSON_ROSTER_LINE_RE.search(name):
                    if _NON_PERSON_NAME_TOKEN_RE.search(name):
                        i += 1
                        continue
                    if not role:
                        i += 1
                        continue
                    role_norm = role[:512] or "Commissioner"
                    rk = (name.lower(), role_norm.lower())
                    if rk not in roster_seen:
                        roster_seen.add(rk)
                        out.append(
                            {
                                "person_name": name[:512],
                                "title_or_role": role_norm,
                                "department": None,
                                "email": email_pri,
                                "phone": phone,
                                "mailing_address": None,
                                "profile_url": None,
                                "extraction_method": "heading_section_commissioner_roster",
                                "raw_row": {"page_url": page_url, "heading": (title_guess or "")[:200]},
                            }
                        )
                i += 1

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

        if name_guess and _SCRIPTY_OR_UI_LINE_RE.search(name_guess):
            name_guess = ""

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


def extract_commissioner_roster_list_contacts_from_html(
    html: str,
    page_url: str,
    *,
    max_rows: int = 80,
) -> List[Dict[str, Any]]:
    """Extract commissioners from nested list rosters (CivicPlus-style HTML blocks).

    Pattern example:
      - <h3>Commissioners:</h3>
      - <ul>
          <li><strong>Danny Maxwell, Vice Chairman District 1</strong>
              <ul><li>phone: ...</li><li>email: ...</li></ul>
          </li>
        </ul>
    """
    from bs4 import BeautifulSoup, Tag

    out: List[Dict[str, Any]] = []
    if not html or max_rows <= 0:
        return out

    soup = BeautifulSoup(html, "html.parser")
    seen: Set[Tuple[str, str, str]] = set()

    for h in soup.find_all(["h2", "h3", "h4", "h5", "h6"]):
        htxt = re.sub(r"\s+", " ", h.get_text(" ", strip=True) or "").strip()
        if not _COMMISSIONER_SECTION_RE.search(htxt):
            continue
        ul = h.find_next("ul")
        if not isinstance(ul, Tag):
            continue

        for li in ul.find_all("li", recursive=False):
            if len(out) >= max_rows:
                break

            name_role = ""
            strong = li.find(["strong", "b"])
            if strong is None:
                continue
            name_role = re.sub(r"\s+", " ", strong.get_text(" ", strip=True) or "").strip()
            if not name_role:
                continue

            name = ""
            title = ""
            if "," in name_role:
                p1, p2 = name_role.split(",", 1)
                name = p1.strip()
                title = p2.strip()
            else:
                name = name_role.strip()

            if not _looks_like_person_name_line(name):
                continue
            if _NON_PERSON_ROSTER_LINE_RE.search(name):
                continue
            if _NON_PERSON_NAME_TOKEN_RE.search(name):
                continue

            li_blob = re.sub(r"\s+", " ", li.get_text(" ", strip=True) or "")
            phone = None
            pm = _PHONE_RE.search(li_blob)
            if pm:
                digits = re.sub(r"\D", "", pm.group(0))
                if len(digits) >= 10:
                    phone = _normalize_phone_display(pm.group(0))

            email = None
            best_email = ""
            for a in li.select('a[href^="mailto:"]'):
                vis = re.sub(r"\s+", " ", a.get_text(" ", strip=True) or "").strip().lower()
                hm = _MAILTO_RE.search((a.get("href") or "").strip())
                href_email = _clean_mailto(hm.group(1)) if hm else ""
                if vis and "@" in vis:
                    vm = _EMAIL_RE.search(vis)
                    if vm:
                        best_email = vm.group(0).strip().lower()
                        break
                if href_email and "@" in href_email:
                    best_email = href_email
            if not best_email:
                em = _EMAIL_RE.search(li_blob)
                if em:
                    best_email = em.group(0).strip().lower()
            if best_email and not _BOGUS_EMAIL_SUFFIX.search(best_email):
                email = best_email

            key = (name.lower(), (email or "").lower(), re.sub(r"\D", "", phone or "")[:15])
            if key in seen:
                continue
            seen.add(key)

            out.append(
                {
                    "person_name": name[:512],
                    "title_or_role": title[:512] or None,
                    "department": None,
                    "email": email,
                    "phone": phone,
                    "mailing_address": None,
                    "profile_url": None,
                    "extraction_method": "commissioner_roster_list",
                    "raw_row": {"page_url": page_url, "heading": htxt[:200]},
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
