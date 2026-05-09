"""
Map Wikibase `wbgetentities` JSON blobs into WDQS-result-shaped dicts for
`_parse_jurisdiction_results` reuse (website, lat, youtube, identifiers, …).

Same logical read path as Pywikibot `ItemPage.get()`, without requiring Pywikibot.

Optional Pywikibot: set ``WIKIDATA_ENRICH_USE_PYWIKIBOT=1`` plus ``pip install pywikibot``.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple, Set


def _first_claim_sv(claims: dict, pid: str) -> Optional[Any]:
    c = claims.get(pid) if claims else None
    if not c:
        return None
    mainsnak = (c[0] or {}).get("mainsnak") or {}
    dv = mainsnak.get("datavalue")
    if dv is None:
        return None
    return dv.get("value")


def _commons_thumb(fn: Optional[str]) -> Optional[str]:
    if not fn:
        return None
    fs = str(fn).replace(" ", "_")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{fs}"


def entity_to_wdqs_like_row(entity: dict, qid: str) -> Dict[str, Any]:
    labels = entity.get("labels") or {}
    lbl = ""
    lb_en = labels.get("en") or {}
    lbl = lb_en.get("value") or ""
    if not lbl:
        for _lang, blob in sorted(labels.items()):
            if blob and blob.get("value"):
                lbl = blob["value"]
                break

    claims = entity.get("claims") or {}
    row: Dict[str, Any] = {"item": f"http://www.wikidata.org/entity/{qid}", "itemLabel": lbl}

    v = _first_claim_sv(claims, "P856")
    if isinstance(v, str):
        row["website"] = v

    v = _first_claim_sv(claims, "P1082")
    if isinstance(v, dict) and v.get("type") == "quantity":
        row["population"] = (v.get("amount") or "").lstrip("+")

    v = _first_claim_sv(claims, "P2046")
    if isinstance(v, dict) and v.get("type") == "quantity":
        row["area"] = (v.get("amount") or "").lstrip("+")

    v = _first_claim_sv(claims, "P2013")
    if isinstance(v, str):
        row["facebook"] = v

    v = _first_claim_sv(claims, "P2002")
    if isinstance(v, str):
        row["twitter"] = v.strip().lstrip("@")

    v = _first_claim_sv(claims, "P2397")
    if isinstance(v, str):
        row["youtube"] = v

    fn = _first_claim_sv(claims, "P18")
    row["image"] = _commons_thumb(fn if isinstance(fn, str) else None)

    fn = _first_claim_sv(claims, "P242")
    row["locatorMap"] = _commons_thumb(fn if isinstance(fn, str) else None)

    fn = _first_claim_sv(claims, "P948")
    row["banner"] = _commons_thumb(fn if isinstance(fn, str) else None)

    v = _first_claim_sv(claims, "P625")
    if isinstance(v, dict) and v.get("type") == "globecoordinate":
        row["lat"] = str(v["latitude"])
        row["lon"] = str(v["longitude"])

    fv = _first_claim_sv(claims, "P774")
    fv2 = _first_claim_sv(claims, "P882")
    for raw in (fv, fv2):
        if isinstance(raw, str):
            row["fips"] = raw.replace("-", "")
            break

    fal = _first_claim_sv(claims, "P3006")
    if isinstance(fal, str):
        row["fipsAlt"] = fal.replace("-", "")

    gv = _first_claim_sv(claims, "P590")
    if isinstance(gv, str):
        row["gnis"] = gv.replace("-", "")

    nv = _first_claim_sv(claims, "P6545")
    if isinstance(nv, str):
        row["nces"] = nv.replace("-", "")

    gv_geo = _first_claim_sv(claims, "P1566")
    if isinstance(gv_geo, str):
        row["geonamesId"] = gv_geo

    pc = _first_claim_sv(claims, "P281")
    if isinstance(pc, str):
        row["postalCode"] = pc

    am = _first_claim_sv(claims, "P3529")
    if isinstance(am, dict) and am.get("type") == "quantity":
        row["perCapitaIncome"] = (am.get("amount") or "").lstrip("+")

    d = _first_claim_sv(claims, "P473")
    if isinstance(d, str):
        row["dialingCode"] = d

    gmc = _first_claim_sv(claims, "P3749")
    if isinstance(gmc, str):
        row["googleMapsCustomerId"] = gmc

    hh = _first_claim_sv(claims, "P1538")
    if isinstance(hh, dict) and hh.get("type") == "quantity":
        row["households"] = (hh.get("amount") or "").lstrip("+")

    ma = _first_claim_sv(claims, "P1310")
    if isinstance(ma, dict) and ma.get("type") == "quantity":
        row["medianAge"] = (ma.get("amount") or "").lstrip("+")

    tz = _first_claim_sv(claims, "P421")
    if isinstance(tz, dict) and tz.get("type") == "wikibase-entityid":
        row["timeZone"] = tz.get("id")

    bp = _first_claim_sv(claims, "P2390")
    if isinstance(bp, str):
        row["ballotpediaId"] = bp

    ta = _first_claim_sv(claims, "P3134")
    if isinstance(ta, str):
        row["tripadvisorId"] = ta

    sr = _first_claim_sv(claims, "P3984")
    if isinstance(sr, str):
        row["subreddit"] = sr

    return row


def entities_response_to_rows(payload: dict) -> List[Dict[str, Any]]:
    ents = payload.get("entities") or {}
    rows: List[Dict[str, Any]] = []
    for qid, entity in ents.items():
        if not str(qid).startswith("Q"):
            continue
        if isinstance(entity, dict) and entity.get("missing"):
            continue
        rows.append(entity_to_wdqs_like_row(entity, qid))
    return rows


def _statement_rank_key(st: dict) -> int:
    r = st.get("rank")
    if r == "preferred":
        return 2
    if r == "deprecated":
        return 0
    return 1


def _item_id_from_claim_statement(st: dict) -> Optional[str]:
    ms = st.get("mainsnak") or {}
    if ms.get("snaktype") != "value":
        return None
    val = (ms.get("datavalue") or {}).get("value")
    if isinstance(val, dict):
        q = val.get("id")
        if isinstance(q, str) and q.startswith("Q"):
            return q
    return None


def _p580_statement_time(st: dict) -> Optional[str]:
    qualifiers = st.get("qualifiers") or {}
    for qsnak in qualifiers.get("P580") or []:
        if qsnak.get("snaktype") != "value":
            continue
        tv = (qsnak.get("datavalue") or {}).get("value")
        if isinstance(tv, dict) and tv.get("time"):
            return str(tv["time"])
    return None


def pick_best_head_of_government(claims: dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Prefer P6 statements with ``preferred`` rank; among those prefer the newest P580 start time,
    mirroring ORDER BY DESC(?headStart) LIMIT 1 behavior.
    """
    rows_raw: List[dict] = []
    for st in claims.get("P6") or []:
        if not isinstance(st, dict):
            continue
        qid = _item_id_from_claim_statement(st)
        if not qid:
            continue
        rows_raw.append({"q": qid, "rk": _statement_rank_key(st), "tk": _p580_statement_time(st)})
    if not rows_raw:
        return None, None
    pref = [r for r in rows_raw if r["rk"] >= 2]
    pool = pref if pref else rows_raw
    dated = [r for r in pool if r["tk"]]
    if dated:
        best = max(dated, key=lambda r: str(r["tk"] or ""))
        return str(best["q"]), best["tk"]
    best = max(pool, key=lambda r: int(r["rk"]))
    return str(best["q"]), None


def collect_state_related_qids(entity: dict) -> List[str]:
    claims = entity.get("claims") or {}
    ids: Set[str] = set()
    for pid in ("P36", "P85", "P37", "P407", "P421", "P1906"):
        for st in claims.get(pid) or []:
            q = _item_id_from_claim_statement(st)
            if q:
                ids.add(q)
    for st in claims.get("P6") or []:
        q = _item_id_from_claim_statement(st)
        if q:
            ids.add(q)
    return sorted(ids)


def _join_pipe_unique(values: List[str]) -> Optional[str]:
    if not values:
        return None
    return "||".join(dict.fromkeys([v for v in values if str(v).strip()]))


def entity_en_label(entity: dict) -> str:
    labels = entity.get("labels") or {}
    en = labels.get("en") or {}
    v = en.get("value")
    return str(v).strip() if v else ""


def _mono_claim_texts_prefer_en(claims: dict, pid: str) -> List[str]:
    """Monolingual string claims; prefer ``language=en``."""
    out_en: List[str] = []
    out_other: List[str] = []
    for st in claims.get(pid) or []:
        ms = st.get("mainsnak") or {}
        if ms.get("snaktype") != "value":
            continue
        val = (ms.get("datavalue") or {}).get("value")
        if isinstance(val, dict) and val.get("text") is not None:
            txt, lang = str(val["text"]), val.get("language")
            if lang == "en":
                out_en.append(txt)
            else:
                out_other.append(txt)
    return out_en if out_en else out_other


def state_entity_to_sparql_shaped_row(
    entity: dict,
    state_q_code: str,
    related_labels: Dict[str, str],
) -> Tuple[Dict[str, Any], Optional[Dict[str, Optional[str]]]]:
    """
    Map a state's ``wbgetentities`` / EntityData blob into WDQS-result-shaped keys
    consumed by ``JurisdictionsWikiDataLoader`` state assembly logic.
    """
    base_row = entity_to_wdqs_like_row(entity, state_q_code)
    row: Dict[str, Any] = dict(base_row)

    descriptions = entity.get("descriptions") or {}
    de = descriptions.get("en") or {}
    row["itemDescription"] = de.get("value")

    aliases = entity.get("aliases") or {}
    al_en = aliases.get("en") or []
    alt_lab: List[str] = []
    if isinstance(al_en, list):
        for a in al_en:
            if isinstance(a, dict) and a.get("value"):
                alt_lab.append(str(a["value"]))
    row["altLabels"] = _join_pipe_unique(alt_lab)

    claims = entity.get("claims") or {}

    nl = _mono_claim_texts_prefer_en(claims, "P1705")
    row["nativeLabel"] = nl[0] if nl else None

    nick_parts = _mono_claim_texts_prefer_en(claims, "P1448") + _mono_claim_texts_prefer_en(claims, "P2561")
    row["nicknames"] = _join_pipe_unique(nick_parts)

    row["shortNames"] = _join_pipe_unique(_mono_claim_texts_prefer_en(claims, "P1813"))

    demonyms: List[str] = []
    for st in claims.get("P1549") or []:
        ms = st.get("mainsnak") or {}
        if ms.get("snaktype") != "value":
            continue
        val = (ms.get("datavalue") or {}).get("value")
        if isinstance(val, dict) and val.get("text") is not None:
            demonyms.append(str(val["text"]))
        elif isinstance(val, str):
            demonyms.append(val)
    row["demonyms"] = _join_pipe_unique(demonyms)

    ols: List[str] = []
    for st in claims.get("P37") or []:
        q = _item_id_from_claim_statement(st)
        if q:
            lbl = related_labels.get(q)
            if lbl:
                ols.append(lbl)
    row["officialLanguages"] = _join_pipe_unique(ols)

    hog_office_q: Optional[str] = None
    for st in claims.get("P1906") or []:
        q = _item_id_from_claim_statement(st)
        if q:
            hog_office_q = q
            break
    row["hogOfficeLabel"] = related_labels.get(hog_office_q) if hog_office_q else None

    motto = _mono_claim_texts_prefer_en(claims, "P1451")
    row["motto"] = motto[0] if motto else None

    anthems: List[str] = []
    for st in claims.get("P85") or []:
        q = _item_id_from_claim_statement(st)
        if q:
            lb = related_labels.get(q)
            if lb:
                anthems.append(lb)
    row["anthems"] = _join_pipe_unique(anthems)

    caps: List[str] = []
    for st in claims.get("P36") or []:
        q = _item_id_from_claim_statement(st)
        if q:
            lb = related_labels.get(q)
            if lb:
                caps.append(lb)
    row["capitals"] = _join_pipe_unique(caps)

    inception_raw = None
    for st in claims.get("P571") or []:
        ms = st.get("mainsnak") or {}
        if ms.get("snaktype") != "value":
            continue
        tv = (ms.get("datavalue") or {}).get("value")
        if isinstance(tv, dict) and tv.get("time"):
            inception_raw = str(tv["time"])
            break
    row["inception"] = inception_raw

    iso_val = None
    for st in claims.get("P300") or []:
        ms = st.get("mainsnak") or {}
        if ms.get("snaktype") != "value":
            continue
        val = (ms.get("datavalue") or {}).get("value")
        if isinstance(val, str):
            iso_val = val.replace("-", "")
            break
    row["iso31662"] = iso_val

    gsh = _first_claim_sv(claims, "P3896")
    row["geoshape"] = gsh if isinstance(gsh, str) else None

    pronunciation = None
    for st in claims.get("P443") or []:
        ms = st.get("mainsnak") or {}
        if ms.get("snaktype") != "value":
            continue
        val = (ms.get("datavalue") or {}).get("value")
        if isinstance(val, str):
            pronunciation = val
            break
    row["pronunciationAudio"] = pronunciation

    lw: List[str] = []
    for st in claims.get("P407") or []:
        q = _item_id_from_claim_statement(st)
        if q:
            lb = related_labels.get(q)
            if lb:
                lw.append(lb)
    joined_lw = _join_pipe_unique(lw)
    row["languageLabel"] = joined_lw.replace("||", ", ") if joined_lw else None

    tz_id = row.get("timeZone")
    if isinstance(tz_id, str) and tz_id.startswith("Q"):
        row["timeZoneLabel"] = related_labels.get(tz_id)

    gov_q, gov_t = pick_best_head_of_government(claims)
    hog_row = None
    if gov_q:
        cal = gov_t.lstrip("+")[:10] if isinstance(gov_t, str) and len(gov_t.lstrip("+")) >= 10 else None
        hog_row = {"headOfGovLabel": related_labels.get(gov_q), "headStart": cal}
    return row, hog_row


def try_pywikibot_rows(qids: List[str]) -> Optional[List[Dict[str, Any]]]:
    if os.getenv("WIKIDATA_ENRICH_USE_PYWIKIBOT", "").strip().lower() not in ("1", "true", "yes"):
        return None
    try:
        import pywikibot  # type: ignore
    except ImportError:
        return None

    site = pywikibot.Site("wikidata", "wikidata")
    repo = site.data_repository()
    out: List[Dict[str, Any]] = []
    for q in qids:
        if not str(q).startswith("Q"):
            continue
        it = pywikibot.ItemPage(repo, q)
        it.get()
        inner = getattr(it, "_content", None)
        if not isinstance(inner, dict):
            inner = {}
        ents = {"entities": {str(q): inner}}
        out.extend(entities_response_to_rows(ents))
    return out if out else None
