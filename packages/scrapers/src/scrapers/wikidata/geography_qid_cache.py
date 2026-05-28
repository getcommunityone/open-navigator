"""
Persistent cache: Census-side identifier literals → Wikidata Q-id.

Stored separately from full SPARQL response JSON files so incremental runs can
reuse id→Q without re-hitting WDQS-heavy OPTIONAL pipelines.

Path: <WIKIDATA_CACHE_DIR>/geography_qid_mapping_v1.json
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from loguru import logger

_LOCK = threading.Lock()


def norm_lit(x: str) -> str:
    return re.sub(r"[\s\-]+", "", str(x).strip())


def cache_key(task: str, pid: str, literal: str) -> str:
    return f"{task}|{pid}|{norm_lit(literal)}"


class GeographyQidCache:
    def __init__(self, cache_dir: Path | None = None) -> None:
        base = cache_dir or Path(os.getenv("WIKIDATA_CACHE_DIR", "data/cache/wikidata"))
        self.path = base.resolve() / "geography_qid_mapping_v1.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: Dict[str, Dict[str, object]] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text())
            self._entries = dict(raw.get("entries") or {})
        except Exception as exc:
            logger.warning(f"Could not read geography Q-id cache {self.path}: {exc}")
            self._entries = {}

    def save(self) -> None:
        if not self._dirty:
            return
        tmp = self.path.with_suffix(".tmp")
        payload = {"version": 1, "entries": self._entries, "saved_at_epoch": time.time()}
        with _LOCK:
            tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
            tmp.replace(self.path)
        self._dirty = False
        logger.debug(f"Wrote geography Q-id cache ({len(self._entries)} keys) → {self.path}")

    def get_q(self, key: str) -> Optional[str]:
        row = self._entries.get(key)
        if not row:
            return None
        q = row.get("q")
        return str(q).strip() if q else None

    def set_q(self, key: str, q: str) -> None:
        q = str(q).strip()
        if not q.startswith("Q"):
            return
        old = self._entries.get(key)
        if old and old.get("q") == q:
            return
        self._entries[key] = {"q": q, "t": time.time()}
        self._dirty = True

    def remember_muni(self, qid: str, fips: Optional[str], gnis: Optional[str]) -> None:
        if fips:
            self.set_q(cache_key("muni", "774", fips), qid)
        if gnis:
            self.set_q(cache_key("muni", "590", gnis), qid)

    def remember_county(self, qid: str, fips: Optional[str], fips_alt: Optional[str], gnis: Optional[str]) -> None:
        if fips:
            v = norm_lit(fips)
            self.set_q(cache_key("county", "882", v), qid)
        if fips_alt:
            v = norm_lit(fips_alt)
            self.set_q(cache_key("county", "3006", v), qid)
        if gnis:
            self.set_q(cache_key("county", "590", norm_lit(gnis)), qid)

    def remember_school(self, qid: str, fips: Optional[str], gnis: Optional[str], nces: Optional[str]) -> None:
        for raw, pid in [(fips, "882"), (gnis, "590"), (nces, "6545")]:
            if raw:
                self.set_q(cache_key("school", pid, raw), qid)

    def lookup_q_for_municipality(self, fips_lits, gnis_lits) -> Optional[str]:
        for lit in fips_lits:
            q = self.get_q(cache_key("muni", "774", lit))
            if q:
                return q
        for lit in gnis_lits:
            q = self.get_q(cache_key("muni", "590", lit))
            if q:
                return q
        return None

    def lookup_q_for_county(self, fips_lits) -> Optional[str]:
        for lit in fips_lits:
            v = norm_lit(lit)
            for pid in ("882", "3006", "774"):
                q = self.get_q(cache_key("county", pid, v))
                if q:
                    return q
        return None

    def lookup_q_for_school(self, id_lits) -> Optional[str]:
        for lit in id_lits:
            v = norm_lit(lit)
            for pid in ("6545", "882"):
                q = self.get_q(cache_key("school", pid, v))
                if q:
                    return q
        return None

    def warm_from_enriched_rows(
        self, warm_task: str, state_code: str, rows: Iterable[Tuple[str, Optional[str], str]]
    ) -> None:
        if warm_task not in ("city", "county", "school_district"):
            return
        from scrapers.wikidata.load_jurisdictions_wikidata import (
            STATE_MAP,
            _county_fips_literal_alternatives,
            _municipality_wd_literal_sets,
            _school_id_literal_alternatives,
        )

        sf = STATE_MAP.get(state_code, {}).get("fips")

        for geoid, ansi, qid in rows:
            if not geoid or not qid or not str(qid).startswith("Q"):
                continue
            if warm_task == "city":
                fl, gl = _municipality_wd_literal_sets(geoid, ansi)
                for lit in fl:
                    self.remember_muni(qid, lit, None)
                for lit in gl:
                    self.remember_muni(qid, None, lit)
            elif warm_task == "county":
                for lit in _county_fips_literal_alternatives(geoid, sf):
                    self.remember_county(qid, lit, None, None)
            elif warm_task == "school_district":
                for lit in _school_id_literal_alternatives(geoid):
                    v = norm_lit(lit)
                    self.set_q(cache_key("school", "6545", v), qid)
                    self.set_q(cache_key("school", "882", v), qid)
