"""
Snippet extraction, Boydstun frame inventory, and Gemini prompt builders for
labeling question clusters and argument (key-point) clusters.

Two label paths exist for every cluster:
  * ``--use-llm``: one Gemini call per cluster -> polished canonical text.
  * default (no-llm): a deterministic label drawn from real in-data text, so the
    full stack can be validated at zero API cost. No fabricated values — labels
    are real headlines / view snippets from the clustered rows.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

# --- Boydstun et al. Policy Frames Codebook (15 dimensions) ----------------
# (frame_id, display label). Mirrors dbt_project/seeds/policy_frame.csv. Source:
# minio.la.utexas.edu/compagendas/codebookfiles/Policy_Frames_Codebook.pdf
FRAMES: List[Tuple[str, str]] = [
    ("economic", "Economic"),
    ("capacity_and_resources", "Capacity and resources"),
    ("morality", "Morality"),
    ("fairness_and_equality", "Fairness and equality"),
    ("legality_constitutionality_jurisprudence", "Legality, constitutionality and jurisprudence"),
    ("policy_prescription_and_evaluation", "Policy prescription and evaluation"),
    ("crime_and_punishment", "Crime and punishment"),
    ("security_and_defense", "Security and defense"),
    ("health_and_safety", "Health and safety"),
    ("quality_of_life", "Quality of life"),
    ("cultural_identity", "Cultural identity"),
    ("public_opinion", "Public opinion"),
    ("political", "Political"),
    ("external_regulation_and_reputation", "External regulation and reputation"),
    ("other", "Other"),
]
FRAME_IDS = {fid for fid, _ in FRAMES}

# keyword -> frame_id, for the no-llm heuristic frame guess
_FRAME_KEYWORDS: List[Tuple[Tuple[str, ...], str]] = [
    (("cost", "budget", "tax", "revenue", "fund", "economic", "money", "fee", "price", "afford"), "economic"),
    (("capacity", "staff", "resource", "workload", "shortage", "feasib"), "capacity_and_resources"),
    (("fair", "equit", "discrimin", "equal", "inclus"), "fairness_and_equality"),
    (("legal", "ordinance", "constitution", "statute", "lawsuit", "jurisdiction", "compliance"),
     "legality_constitutionality_jurisprudence"),
    (("crime", "police", "enforce", "violation", "penalt"), "crime_and_punishment"),
    (("safety", "health", "hazard", "danger", "flood", "fire risk"), "health_and_safety"),
    (("traffic", "noise", "neighborhood", "character", "quality of life", "congestion", "property value"),
     "quality_of_life"),
    (("heritage", "historic", "culture", "community identity"), "cultural_identity"),
    (("resident", "public", "opposition", "support", "constituent"), "public_opinion"),
    (("recommend", "evaluat", "effective", "implement"), "policy_prescription_and_evaluation"),
]

# heuristic source_role from held_by text / view_label keywords
_ROLE_KEYWORDS: List[Tuple[Tuple[str, ...], str]] = [
    (("applicant", "petitioner", "developer", "owner", "agent", "vendor", "contractor"), "applicant"),
    (("staff", "planner", "manager", "director", "engineer", "department", "administrator"), "staff"),
    (("resident", "citizen", "neighbor", "public", "community member", "speaker"), "resident"),
    (("council", "mayor", "commissioner", "board", "alderman", "member", "chair", "official"), "official"),
]


def _txt(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def _held_by_text(view: Dict[str, Any]) -> str:
    hb = view.get("held_by")
    if isinstance(hb, list):
        return " ".join(str(x) for x in hb)
    return _txt(hb)


def source_role(view: Dict[str, Any], is_dominant: bool) -> str:
    blob = (_held_by_text(view) + " " + _txt(view.get("view_label"))).lower()
    for keywords, role in _ROLE_KEYWORDS:
        if any(kw in blob for kw in keywords):
            return role
    # Institutional asymmetry: dominant view is usually staff rationale,
    # counter views are usually resident-voiced.
    return "staff" if is_dominant else "resident"


def frame_guess(text: str) -> str:
    low = (text or "").lower()
    for keywords, fid in _FRAME_KEYWORDS:
        if any(kw in low for kw in keywords):
            return fid
    return "other"


def _view_snippets(view: Dict[str, Any], source_view: str, is_dominant: bool) -> List[Dict[str, str]]:
    if not isinstance(view, dict):
        return []
    role = source_role(view, is_dominant)
    out: List[Dict[str, str]] = []
    for field in ("problem_diagnosis", "causal_story", "proposed_remedy",
                  "counter_argument", "plain_summary"):
        t = _txt(view.get(field))
        if len(t) >= 25:
            out.append({"text": t, "source_view": source_view, "source_role": role})
    return out


def extract_snippets(competing_views: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Pull every argument snippet from a decision's competing_views block."""
    if not isinstance(competing_views, dict):
        return []
    snippets: List[Dict[str, str]] = []
    dom = competing_views.get("dominant_view")
    if isinstance(dom, dict):
        snippets += _view_snippets(dom, "dominant", True)
    for key in ("counter_views", "additional_views"):
        arr = competing_views.get(key)
        if isinstance(arr, list):
            for cv in arr:
                snippets += _view_snippets(cv, "counter", False)
    return snippets


# --- Gemini prompt builders ------------------------------------------------

_QUESTION_SYS = (
    "You are a civic-policy analyst building a registry of recurring policy "
    "questions across U.S. local governments. Given several local decisions that "
    "cluster together, phrase the single jurisdiction-neutral, time-neutral "
    "POLICY QUESTION they are all instances of, as an actual yes/no or how-much "
    "question (e.g. 'Should short-term rentals be permitted in residential "
    "zones?'). Return ONLY JSON: {\"canonical_text\": str, \"scope\": "
    "\"local\"|\"state\"|\"both\", \"cap_topic_code\": str}. cap_topic_code is the "
    "Comparative Agendas Project US subtopic code that best fits, or \"\" if "
    "unsure. Do not invent facts; phrase only the question."
)


def question_prompt(coarse_theme: str, exemplars: List[str]) -> Tuple[str, str]:
    body = "\n".join(f"- {e}" for e in exemplars if e)
    user = f"Theme bucket: {coarse_theme}\nClustered decisions:\n{body}\n\nReturn the JSON."
    return _QUESTION_SYS, user


_ARGUMENT_SYS = (
    "You are doing Key Point Analysis on civic arguments. Given several raw "
    "argument snippets that cluster together under one policy question, write the "
    "single canonical 'key point' they express. Return ONLY JSON: {\"label\": str "
    "(<=10 words), \"summary\": str (one sentence), \"stance\": \"pro\"|\"con\", "
    "\"source_role\": \"staff\"|\"applicant\"|\"resident\"|\"official\"|"
    "\"legislative_staff\", \"frame_id\": one of " + ",".join(sorted(FRAME_IDS)) +
    "}. stance is relative to approving/enacting the question. Do not invent facts."
)


def argument_prompt(question_text: str, exemplars: List[str]) -> Tuple[str, str]:
    body = "\n".join(f"- {e}" for e in exemplars if e)
    user = f"Policy question: {question_text}\nClustered argument snippets:\n{body}\n\nReturn the JSON."
    return _ARGUMENT_SYS, user


def parse_json(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Best-effort JSON object parse from model output (fenced or bare)."""
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def clean_question_text(s: str) -> str:
    s = (s or "").strip().strip('"').strip()
    if s and not s.endswith("?"):
        # Heuristic labels (headlines) aren't questions; keep them as a short label.
        s = s.rstrip(".")
    return s[:300]
