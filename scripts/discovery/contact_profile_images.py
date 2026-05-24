"""
Detect people-style profile images in HTML, score “person + photo” pages, and download images.

Saved files use the contact’s name in lower snake_case. If the name is missing or not usable,
the first file is ``unknown``, then ``unknown_2``, ``unknown_3``, and so on. Job rows still carry
``title_or_role`` for context, but titles are not used in the filename.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

_IMG_EXT_RE = re.compile(r"\.(jpe?g|png|gif|webp)(\?|$)", re.I)
_PLACEHOLDER_IMG = re.compile(r"(spacer|blank\.|placeholder|pixel\.gif|1x1)", re.I)
_SKIP_IMG_HOST = re.compile(
    r"(gravatar|fbcdn\.net|fbsbx\.com|platform\.facebook\.com|connect\.facebook\.net|"
    r"facebook\.com/(tr/|plugins/|rsrc\.php)|"
    r"instagram\.com|cdninstagram\.com|pbs\.twimg\.com|twimg\.com/media|"
    r"doubleclick|googlesyndication|google-analytics|pixel\.|tracking)",
    re.I,
)
_IMG_CLASS_HINT = re.compile(
    r"(avatar|photo|headshot|portrait|profile|staff|member|team|bio|thumbnail|head\s*shot)",
    re.I,
)
_NAMEISH = re.compile(r"[A-Za-z][A-Za-z][A-Za-z].*[A-Za-z]")
_ROLE_HEADING_HINT = re.compile(
    r"(?is)\b("
    r"commission(\s+chairman|\s+chair|\s+district\s*\d+|\s+member)?"
    r"|district\s*\d+"
    r"|county\s+commission"
    r"|mayor|vice\s*mayor|council(\s*member)?"
    r"|trustee|judge|clerk|sheriff|superintendent|assessor|treasurer"
    r")\b",
)
# Headings / chrome that share a site logo or stock wp-block-image — not directory headshots.
_NON_PERSON_PHOTO_SUBJECT_RE = re.compile(
    r"(?is)\b("
    r"frequently\s+asked|faq\b|common\s+questions"
    r"|search[\s\w]{0,48}site\b"
    r"|privacy\s+policy|terms\s+of\s+(service|use)|cookie\s+policy"
    r"|subscribe|newsletter|sign\s+up"
    r"|welcome\s+to|thank\s+you\s+for\s+visiting"
    r"|facebook\s+posts|instagram\s+feed|twitter\s+feed|social\s+media\s+feed"
    r")\b",
)

_NON_PERSON_NAME_LINE_RE = re.compile(
    r"(?is)\b("
    r"welcome|promote|growth|progress|hub|industry|shopping|entertainment|"
    r"connectivity|major\s+thoroughfares|central\s+to|southeast\s+georgia|"
    r"click\s+here|learn\s+more|visit\s+our|discover|explore|community"
    r")\b"
)


def contact_profile_image_stem_from_name(person_name: Optional[str]) -> Optional[str]:
    """
    Lower snake_case stem from the contact’s **name** only (no extension).

    Returns ``None`` when there is no usable person name (caller saves as ``unknown``, ``unknown_2``, …).
    """
    raw = (person_name or "").strip()
    raw = re.sub(r"^councilor\s+", "", raw, flags=re.I).strip()
    if len(raw) < 2 or not _NAMEISH.search(raw):
        return None
    nfkd = unicodedata.normalize("NFKD", raw)
    ascii_fold = nfkd.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "_", ascii_fold)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        return None
    return s[:120]


def img_best_abs_url(img: Any, page_url: str) -> str:
    """
    Resolve a usable absolute image URL from lazy / responsive attributes (WordPress, etc.).

    Prefers ``data-src`` / ``data-lazy-src`` when ``src`` is empty or a placeholder.
    """
    from bs4 import Tag

    if not isinstance(img, Tag):
        return ""
    candidates: List[str] = []
    for attr in ("data-src", "data-lazy-src", "data-lazy-loaded", "data-original"):
        v = (img.get(attr) or "").strip()
        if v and not v.lower().startswith("data:"):
            candidates.append(v)
    srcset = (img.get("srcset") or "").strip()
    if srcset:
        best_u = ""
        best_w = -1
        for chunk in srcset.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            bits = chunk.split()
            u = bits[0].strip()
            w = -1
            if len(bits) > 1 and bits[1].endswith("w"):
                try:
                    w = int(bits[1][:-1])
                except ValueError:
                    w = -1
            if u and not u.lower().startswith("data:"):
                if w >= best_w:
                    best_w = w
                    best_u = u
        if best_u:
            candidates.append(best_u)
        else:
            for chunk in srcset.split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                u = chunk.split()[0].strip()
                if u and not u.lower().startswith("data:"):
                    candidates.append(u)
                    break
    src = (img.get("src") or "").strip()
    if src and not src.lower().startswith("data:") and not _PLACEHOLDER_IMG.search(src):
        candidates.append(src)
    elif src and not src.lower().startswith("data:"):
        candidates.append(src)
    for c in candidates:
        abs_u = urljoin(page_url, c)
        if abs_u.lower().startswith(("http://", "https://")) and not _SKIP_IMG_HOST.search(abs_u):
            return abs_u
    return ""


def _profile_image_url_is_brand_or_chrome(url: str) -> bool:
    """Sitewide logos, favicons, and header marks — not official portrait photos."""
    from scripts.discovery.contact_extract_from_html import is_decorative_profile_image_url

    if is_decorative_profile_image_url(url):
        return True
    if not url or not url.lower().startswith(("http://", "https://")):
        return True
    path = (urlparse(url).path or "").lower()
    base = path.rsplit("/", 1)[-1] if path else ""
    blob = f"{path} {base} {url.lower()}"
    if re.search(r"(^|/)(favicon|apple-touch-icon|site-icon|mstile)(/|\.|-)", blob, re.I):
        return True
    if re.search(r"/(logos?|branding|identity)/", blob, re.I):
        return True
    if re.search(r"[-_/]logo[-_.]|[-_]logo\.(png|jpe?g|gif|webp)(\?|$)", blob, re.I):
        return True
    if re.search(r"\b(logo|wordmark|lockup|site-logo|header-logo)\b", base, re.I):
        return True
    return False


def _img_looks_oversized_decorative(img: Any) -> bool:
    """Skip site logos, group commission photos, and other non-headshot assets."""
    try:
        w = int(str(img.get("width") or "0"))
        h = int(str(img.get("height") or "0"))
    except ValueError:
        w, h = 0, 0
    if w >= 900 or h >= 900:
        return True
    u = (img.get("src") or img.get("data-src") or "").lower()
    if any(tok in u for tok in ("commission_2024", "fbog_v01", "tuscco-logo", "favicon")):
        return True
    return False


def _name_from_portrait_url(url: str) -> str:
    """``stan-acker.webp`` → ``Stan Acker`` when the page has no ``h3``."""
    base = (urlparse(url).path or "").rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    if not stem or stem.isdigit() or len(stem) < 4:
        return ""
    parts = [p for p in re.split(r"[-_]+", stem) if p and p.isalpha()]
    if len(parts) < 2:
        return ""
    return " ".join(p.title() for p in parts)


def _label_is_non_person_photo_subject(name: Optional[str], title: Optional[str]) -> bool:
    blob = f"{name or ''} {title or ''}".strip()
    if not blob:
        return True
    if _NON_PERSON_NAME_LINE_RE.search(blob):
        return True
    if _NON_PERSON_PHOTO_SUBJECT_RE.search(blob):
        return True
    # Long marketing / intro blurbs used as subtitle next to decorative images.
    if (title or "").strip():
        t = (title or "").strip()
        if len(t) > 140 and re.search(r"\b(for answers|to learn more|click here|visit our)\b", t, re.I):
            return True
    return False


def collect_person_jsonld_image_urls(person_obj: Dict[str, Any], page_url: str) -> List[str]:
    """Resolve ``image`` / ``ImageObject`` URLs on a single ``Person`` JSON-LD dict."""
    img_raw = person_obj.get("image")
    urls: List[str] = []
    if isinstance(img_raw, str) and img_raw.strip():
        urls.append(img_raw.strip())
    elif isinstance(img_raw, dict):
        u = str(img_raw.get("url") or img_raw.get("@id") or "").strip()
        if u:
            urls.append(u)
    elif isinstance(img_raw, list):
        for it in img_raw:
            if isinstance(it, str) and it.strip():
                urls.append(it.strip())
            elif isinstance(it, dict):
                u = str(it.get("url") or "").strip()
                if u:
                    urls.append(u)
    out: List[str] = []
    for u in urls:
        abs_u = urljoin(page_url, u)
        if not abs_u.lower().startswith(("http://", "https://")):
            continue
        if _SKIP_IMG_HOST.search(abs_u) or _profile_image_url_is_brand_or_chrome(abs_u):
            continue
        out.append(abs_u)
    return out


def score_person_adjacent_images(html: str, page_url: str = "") -> int:
    """
    Heuristic count of “person near profile image” cues (JSON-LD ``Person`` + ``image``,
    ``<img>`` with portrait-ish classes/alt near headings, etc.). Capped for stability.
    """
    from bs4 import BeautifulSoup

    score = 0
    soup = BeautifulSoup(html or "", "html.parser")

    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        score += _json_ld_person_image_score(data)

    for img in soup.find_all("img"):
        src = img_best_abs_url(img, page_url)
        if not src:
            continue
        cls = " ".join(img.get("class") or [])
        alt = (img.get("alt") or "").strip()
        if _IMG_CLASS_HINT.search(cls) or _IMG_CLASS_HINT.search(alt):
            score += 3
        elif len(alt) >= 4 and _NAMEISH.search(alt) and not alt.lower().startswith("logo"):
            score += 2
        elif "wp-image-" in cls or "wp-block-image" in cls:
            if not _profile_image_url_is_brand_or_chrome(src):
                score += 2
        w = str(img.get("width") or "").strip()
        h = str(img.get("height") or "").strip()
        if w.isdigit() and h.isdigit():
            wi, hi = int(w), int(h)
            if 40 <= wi <= 800 and 40 <= hi <= 800:
                score += 1

    for h in soup.find_all(["h2", "h3", "h4", "h5", "h6"]):
        prev = h.find_previous_sibling()
        if prev is not None and prev.name in ("figure", "div"):
            img0 = prev.find("img")
            u0 = img_best_abs_url(img0, page_url) if img0 else ""
            if u0 and not _profile_image_url_is_brand_or_chrome(u0):
                score += 3
                break

    return int(min(score, 80))


def _json_ld_person_image_score(obj: Any) -> int:
    n = 0
    if isinstance(obj, dict):
        types = obj.get("@type")
        tset: Set[str] = set()
        if isinstance(types, str):
            tset.add(types.strip().lower())
        elif isinstance(types, list):
            tset.update(str(x).strip().lower() for x in types if x)
        if "person" in tset and obj.get("image"):
            n += 4
        for v in obj.values():
            n += _json_ld_person_image_score(v)
    elif isinstance(obj, list):
        for it in obj:
            n += _json_ld_person_image_score(it)
    return n


def extract_profile_image_jobs(html: str, page_url: str, *, max_jobs: int = 80) -> List[Dict[str, Any]]:
    """
    Return download jobs: ``person_name``, ``title_or_role``, ``image_url`` (absolute).

    Sources: JSON-LD ``Person`` ``image``; ``<img>`` near headings / portrait-ish classes.
    """
    from bs4 import BeautifulSoup
    from scripts.discovery.contact_extract_from_html import (
        extract_caboose_background_profile_jobs,
        is_generic_district_label,
        split_office_holder_fields,
    )

    out: List[Dict[str, Any]] = []
    seen_url: Set[str] = set()
    soup = BeautifulSoup(html or "", "html.parser")

    for job in extract_caboose_background_profile_jobs(html, page_url, max_jobs=max_jobs):
        u = str(job.get("image_url") or "")
        if u and u not in seen_url:
            seen_url.add(u)
            out.append(job)

    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        _json_ld_collect_person_images(data, page_url, out, seen_url, max_jobs=max_jobs)

    from scripts.discovery.contact_extract_from_html import (
        _iter_elementor_official_bands,
        _parse_elementor_official_band,
    )

    # Fusion / Avada theme person cards — very common in municipal WordPress sites
    # (e.g. dekalbcountyal.us/members/). Structure is consistent:
    #   <div class="person-img"><img alt="<Person Name>" src="..."></div>
    #   <div class="person-desc">
    #     <span class="person-name">Mr. Ricky Harcrow</span>
    #     <span class="person-title">Commissioner President</span>
    #   </div>
    # Without this block the generic pass picks up ``person-title`` text as person_name
    # and the saved image filename becomes the role ("commission_president.png") instead
    # of the person ("ricky_harcrow.png").
    for card_img in soup.select("img.person-img, div.person-img img, .person-img img"):
        if len(out) >= max_jobs:
            break
        abs_u = img_best_abs_url(card_img, page_url)
        if not abs_u or abs_u in seen_url or _SKIP_IMG_HOST.search(abs_u):
            continue
        if _profile_image_url_is_brand_or_chrome(abs_u):
            continue
        # Walk up to a shared ancestor that contains both .person-img and .person-desc.
        person_card = card_img.find_parent(
            lambda tag: bool(tag and tag.name and tag.find(class_="person-desc"))
        )
        name_guess = ""
        title_guess = ""
        if person_card:
            name_el = person_card.find(class_="person-name")
            title_el = person_card.find(class_="person-title")
            if name_el:
                name_guess = re.sub(r"\s+", " ", name_el.get_text(" ", strip=True))[:200]
            if title_el:
                title_guess = re.sub(r"\s+", " ", title_el.get_text(" ", strip=True))[:200]
        # Fall back to the img alt attribute if the .person-name span wasn't found.
        if not name_guess:
            alt = (card_img.get("alt") or "").strip()
            if alt and len(alt) >= 3 and not alt.lower().startswith(("logo", "menu")):
                name_guess = alt[:200]
        if not name_guess:
            continue
        if _label_is_non_person_photo_subject(name_guess, title_guess):
            continue
        seen_url.add(abs_u)
        out.append({
            "person_name": name_guess,
            "title_or_role": title_guess or None,
            "image_url": abs_u,
            "match_method": "fusion_person_card",
        })

    for band in _iter_elementor_official_bands(soup):
        if len(out) >= max_jobs:
            break
        if not band.select(".elementor-widget-image img"):
            continue
        row = _parse_elementor_official_band(band)
        if not row:
            continue
        name_guess = (row.get("person_name") or "").strip() or None
        title_guess = (row.get("title_or_role") or "").strip() or None
        for img in band.select(".elementor-widget-image img"):
            if len(out) >= max_jobs:
                break
            if _img_looks_oversized_decorative(img):
                continue
            abs_u = img_best_abs_url(img, page_url)
            if not abs_u or abs_u in seen_url or _SKIP_IMG_HOST.search(abs_u):
                continue
            if _profile_image_url_is_brand_or_chrome(abs_u):
                continue
            pname = name_guess or _name_from_portrait_url(abs_u)
            if not pname and not title_guess:
                continue
            if _label_is_non_person_photo_subject(pname, title_guess):
                continue
            seen_url.add(abs_u)
            out.append(
                {
                    "person_name": pname,
                    "title_or_role": title_guess,
                    "image_url": abs_u,
                    "match_method": "elementor_official_row",
                }
            )

    for img in soup.find_all("img"):
        if len(out) >= max_jobs:
            break
        abs_u = img_best_abs_url(img, page_url)
        if not abs_u:
            continue
        if _SKIP_IMG_HOST.search(abs_u):
            continue
        if _profile_image_url_is_brand_or_chrome(abs_u):
            continue
        if abs_u in seen_url:
            continue
        cls = " ".join(img.get("class") or [])
        alt = (img.get("alt") or "").strip()
        if alt and re.match(r"^(menu|logo)$", alt, re.I):
            continue
        if "logo" in cls.lower():
            continue
        wpish = "wp-image-" in cls or "wp-block-image" in cls
        portrait_hint = bool(
            _IMG_CLASS_HINT.search(cls)
            or _IMG_CLASS_HINT.search(alt)
            or (len(alt) >= 4 and _NAMEISH.search(alt) and not alt.lower().startswith("logo"))
        )
        if not (portrait_hint or wpish):
            continue

        if wpish and not portrait_hint:
            rn, rt = _role_name_from_following_heading(img)
            if rn and rt and _ROLE_HEADING_HINT.search(rt):
                name_guess, title_guess = rn, rt
            elif rn and _looks_like_person_name_line(rn) and rt and len(rt) < 110:
                name_guess, title_guess = rn, rt
            else:
                continue
        else:
            name_guess, title_guess = _name_title_from_img_context(img)
            if wpish and not name_guess and not title_guess:
                name_guess, title_guess = _role_name_from_following_heading(img)
        if not name_guess and alt and _NAMEISH.search(alt) and not alt.lower().startswith("logo"):
            name_guess = alt[:200]
        if not name_guess and not title_guess:
            continue
        if is_generic_district_label(name_guess) and not title_guess:
            continue
        person, honor, dept = split_office_holder_fields(name_guess, title_guess)
        if not person:
            continue
        if not _looks_like_person_name_line(person):
            continue
        if _label_is_non_person_photo_subject(person, honor or dept):
            continue
        seen_url.add(abs_u)
        out.append(
            {
                "person_name": person,
                "title_or_role": honor,
                "department": dept,
                "image_url": abs_u,
                "match_method": "html_img_context",
            }
        )

    for h in soup.find_all(["h2", "h3", "h4", "h5", "h6"]):
        if len(out) >= max_jobs:
            break
        prev = h.find_previous_sibling()
        if prev is None or prev.name not in ("figure", "div"):
            continue
        img_tag = prev.find("img") if hasattr(prev, "find") else None
        if not img_tag:
            continue
        pcls = " ".join(prev.get("class") or [])
        if prev.name != "figure" and "wp-block-image" not in pcls:
            continue
        abs_u = img_best_abs_url(img_tag, page_url)
        if not abs_u or abs_u in seen_url or _SKIP_IMG_HOST.search(abs_u):
            continue
        if _profile_image_url_is_brand_or_chrome(abs_u):
            continue
        title_line = re.sub(r"\s+", " ", h.get_text(" ", strip=True) or "").strip()
        if not title_line or len(title_line) > 220:
            continue
        if _label_is_non_person_photo_subject(title_line, None):
            continue
        name_guess, title_guess = "", title_line
        for sib in h.find_next_siblings(limit=6):
            if not hasattr(sib, "get_text"):
                continue
            if getattr(sib, "name", None) in ("h1", "h2", "h3", "h4", "h5", "h6"):
                break
            t = re.sub(r"\s+", " ", sib.get_text(" ", strip=True) or "").strip()
            if not t or _line_is_contact_label(t):
                continue
            if _looks_like_person_name_line(t):
                name_guess = t[:200]
                break
        if not name_guess:
            continue
        if _label_is_non_person_photo_subject(name_guess, title_guess):
            continue
        seen_url.add(abs_u)
        out.append(
            {
                "person_name": name_guess or None,
                "title_or_role": title_guess,
                "image_url": abs_u,
                "match_method": "wp_figure_before_heading",
            }
        )

    return out[:max_jobs]


def _json_ld_collect_person_images(
    obj: Any,
    page_url: str,
    out: List[Dict[str, Any]],
    seen_url: Set[str],
    *,
    max_jobs: int,
) -> None:
    if len(out) >= max_jobs or obj is None:
        return
    if isinstance(obj, dict):
        types = obj.get("@type")
        tset: Set[str] = set()
        if isinstance(types, str):
            tset.add(types.strip().lower())
        elif isinstance(types, list):
            tset.update(str(x).strip().lower() for x in types if x)
        if "person" in tset:
            name = obj.get("name") or obj.get("givenName")
            if isinstance(name, list):
                name = " ".join(str(x) for x in name if x).strip()
            else:
                name = str(name or "").strip()
            title = obj.get("jobTitle") or obj.get("worksFor")
            if isinstance(title, dict):
                title = str(title.get("name") or "").strip()
            else:
                title = str(title or "").strip()
            urls = collect_person_jsonld_image_urls(obj, page_url)
            for abs_u in urls:
                if abs_u in seen_url or _profile_image_url_is_brand_or_chrome(abs_u):
                    continue
                seen_url.add(abs_u)
                out.append(
                    {
                        "person_name": name[:512] if name else None,
                        "title_or_role": title[:512] if title else None,
                        "image_url": abs_u,
                        "match_method": "json_ld_person_image",
                    }
                )
                if len(out) >= max_jobs:
                    return
        for v in obj.values():
            _json_ld_collect_person_images(v, page_url, out, seen_url, max_jobs=max_jobs)
    elif isinstance(obj, list):
        for it in obj:
            _json_ld_collect_person_images(it, page_url, out, seen_url, max_jobs=max_jobs)


def _line_is_contact_label(line: str) -> bool:
    s = (line or "").strip()
    if len(s) < 2:
        return True
    return bool(re.match(r"^(mailing\s+address|phone|email|fax|office|cell)\b", s, re.I))


def _looks_like_person_name_line(s: str) -> bool:
    s = (s or "").strip()
    if len(s) < 3 or len(s) > 140:
        return False
    if _NON_PERSON_NAME_LINE_RE.search(s):
        return False
    if _line_is_contact_label(s):
        return False
    if re.search(r"\d{3}\s*[-.)]\s*\d{3}", s):
        return False
    if "@" in s:
        return False
    if len(s.split()) > 8:
        return False
    letters = re.sub(r"[^A-Za-z]", "", s)
    if len(letters) < 4:
        return False
    return bool(_NAMEISH.search(s))


def _role_name_from_following_heading(img: Any) -> Tuple[str, str]:
    """WordPress ``figure.wp-block-image`` / ``div.wp-block-image`` often precedes ``h*`` + name."""
    from bs4 import NavigableString, Tag

    if not isinstance(img, Tag):
        return "", ""
    fig: Optional[Tag] = None
    if isinstance(img.parent, Tag) and img.parent.name == "figure":
        fig = img.parent
    else:
        pfig = img.find_parent("figure")
        if isinstance(pfig, Tag):
            fig = pfig
        else:
            divp = img.find_parent("div", class_=re.compile(r"wp-block-image", re.I))
            if isinstance(divp, Tag):
                fig = divp
    if not isinstance(fig, Tag):
        return "", ""
    sib: Any = fig.next_sibling
    while sib is not None and isinstance(sib, NavigableString) and not str(sib).strip():
        sib = sib.next_sibling
    if not isinstance(sib, Tag) or sib.name not in ("h2", "h3", "h4", "h5", "h6"):
        return "", ""
    title = re.sub(r"\s+", " ", sib.get_text(" ", strip=True) or "").strip()
    name = ""
    for nx in sib.find_next_siblings(limit=8):
        if isinstance(nx, Tag) and nx.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            break
        if not isinstance(nx, Tag):
            continue
        t = re.sub(r"\s+", " ", nx.get_text(" ", strip=True) or "").strip()
        if not t or _line_is_contact_label(t):
            continue
        if _looks_like_person_name_line(t):
            name = t[:200]
            break
    return name, title


def _name_title_from_img_context(img: Any) -> Tuple[str, str]:
    """Walk ancestors for a heading-like name and a subtitle line."""
    from bs4 import NavigableString, Tag

    if not isinstance(img, Tag):
        return "", ""
    cur: Any = img
    for _ in range(8):
        parent = cur.parent
        if parent is None or not isinstance(parent, Tag):
            break
        cur = parent
        h = cur.find(["h1", "h2", "h3", "h4", "h5"])
        if h:
            name = h.get_text(" ", strip=True)
            if name and len(name) < 200:
                sub = ""
                for sib in h.find_next_siblings(limit=4):
                    if isinstance(sib, Tag) and sib.name in ("p", "div", "span"):
                        t = sib.get_text(" ", strip=True)
                        if t and 3 < len(t) < 220:
                            sub = t
                            break
                return name[:200], sub[:220]
    return "", ""


def normalize_profile_image_file_to_png(path: Path) -> str:
    """
    Ensure a saved profile image is PNG. Converts WebP, JPEG, GIF, etc. in place (deletes source).

    Returns the final basename (always ``*.png`` when conversion succeeds).
    """
    if path.suffix.lower() == ".png":
        return path.name
    from PIL import Image

    dest = path.with_suffix(".png")
    with Image.open(path) as im:
        im.load()
        if im.mode in ("RGBA", "LA"):
            pass
        elif im.mode == "P" and "transparency" in im.info:
            im = im.convert("RGBA")
        else:
            im = im.convert("RGB")
        im.save(dest, format="PNG", optimize=True)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return dest.name


def _extension_from_response(url: str, content_type: str, body: bytes) -> str:
    ct = (content_type or "").lower()
    if "png" in ct:
        return ".png"
    if "gif" in ct:
        return ".gif"
    if "webp" in ct:
        return ".webp"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    m = _IMG_EXT_RE.search(url)
    if m:
        ext = m.group(1).lower()
        return ".jpg" if ext == "jpeg" else f".{ext}"
    if body.startswith(b"\x89PNG"):
        return ".png"
    if body.startswith(b"GIF8"):
        return ".gif"
    if body.startswith(b"RIFF") and b"WEBP" in body[:20]:
        return ".webp"
    if body.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    return ".jpg"


async def download_profile_images(
    client: httpx.AsyncClient,
    jobs: List[Dict[str, Any]],
    out_dir: Path,
    *,
    referer: str,
    max_images: int = 48,
    max_bytes: int = 6_000_000,
    save_as_png: bool = True,
) -> List[Dict[str, Any]]:
    """
    GET each ``image_url``; write ``{stem}{ext}`` under ``out_dir``. Named contacts use
    :func:`contact_profile_image_stem_from_name`; duplicates get ``_2``, ``_3``, ….
    Contacts with no usable name use ``unknown``, then ``unknown_2``, ``unknown_3``, ….

    Returns manifest rows with ``saved_filename`` or ``error``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    stem_counts: Dict[str, int] = {}
    unnamed_seq = 0
    n_ok = 0
    for job in jobs:
        if n_ok >= max_images:
            break
        url = str(job.get("image_url") or "").strip()
        if not url:
            continue
        named_stem = contact_profile_image_stem_from_name(job.get("person_name"))
        if named_stem is None:
            unnamed_seq += 1
            stem = "unknown" if unnamed_seq == 1 else f"unknown_{unnamed_seq}"
        else:
            stem_base = named_stem
            n = stem_counts.get(stem_base, 0) + 1
            stem_counts[stem_base] = n
            stem = stem_base if n == 1 else f"{stem_base}_{n}"
        try:
            r = await client.get(
                url,
                follow_redirects=True,
                headers={"Referer": referer or url},
            )
        except Exception as exc:
            results.append({"image_url": url, "error": f"request:{exc!r}", "person_stem": stem})
            continue
        if r.status_code != 200:
            results.append({"image_url": url, "error": f"http_{r.status_code}", "person_stem": stem})
            continue
        body = r.content or b""
        if len(body) > max_bytes or len(body) < 80:
            results.append(
                {
                    "image_url": url,
                    "error": f"size_{len(body)}",
                    "person_stem": stem,
                }
            )
            continue
        ct = r.headers.get("content-type") or ""
        if "image" not in ct.lower() and not _looks_like_image_bytes(body):
            results.append({"image_url": url, "error": f"non_image_ct={ct!r}", "person_stem": stem})
            continue
        ext = _extension_from_response(url, ct, body)
        dest = out_dir / f"{stem}{ext}"
        try:
            dest.write_bytes(body)
            if save_as_png:
                rel = normalize_profile_image_file_to_png(dest)
            else:
                rel = dest.name
        except OSError as exc:
            results.append({"image_url": url, "error": f"write:{exc!r}", "person_stem": stem})
            continue
        except Exception as exc:
            results.append({"image_url": url, "error": f"png_convert:{exc!r}", "person_stem": stem})
            continue
        results.append(
            {
                "image_url": url,
                "person_name": job.get("person_name"),
                "title_or_role": job.get("title_or_role"),
                "email": job.get("email"),
                "department": job.get("department"),
                "person_stem": stem,
                "saved_filename": rel,
                "match_method": job.get("match_method"),
            }
        )
        n_ok += 1
    return results


def _looks_like_image_bytes(body: bytes) -> bool:
    if len(body) < 12:
        return False
    return (
        body.startswith(b"\xff\xd8\xff")
        or body.startswith(b"\x89PNG")
        or body.startswith(b"GIF8")
        or (body.startswith(b"RIFF") and b"WEBP" in body[:20])
    )


def partition_nav_for_photo_priority(
    nav_links: List[str],
    *,
    page_host: str,
    photo_score: int,
    min_photo_score: int,
) -> Tuple[List[str], List[str]]:
    """
    When ``photo_score`` is high, return ``(priority, rest)`` so priority URLs (directory-ish
    paths on the same host) can be enqueued ahead of the rest.
    """
    if photo_score < min_photo_score or not page_host:
        return [], list(nav_links)
    frag = (
        "board",
        "council",
        "commission",
        "official",
        "member",
        "staff",
        "mayor",
        "contact",
        "directory",
        "team",
        "leadership",
        "trustee",
        "elected",
        "department",
    )
    path_markers = (
        "commissioner-bios",
        "county-commissioners",
        "county-officials",
        "major-council",
        "mayor-council",
    )
    prio: List[str] = []
    rest: List[str] = []
    for link in nav_links:
        try:
            p = urlparse(link)
            host = (p.netloc or "").lower()
            blob = f"{(p.path or '').lower()}?{(p.query or '').lower()}"
        except Exception:
            host = ""
            blob = ""
        same_host = bool(host and page_host and host == page_host)
        frag_hit = same_host and any(f"/{f}" in blob or f"/{f}/" in blob for f in frag)
        path_hit = same_host and any(m in blob for m in path_markers)
        if frag_hit or path_hit:
            prio.append(link)
        else:
            rest.append(link)
    return prio, rest
