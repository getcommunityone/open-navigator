"""The Part 1 analysis as typed models: what a valid answer to ``prompts/policy_analysis_part_1.md`` looks like (#511).

The prompt's "JSON Schema" section describes the answer; until now nothing checked an answer against it beyond
``_part1_json_ok`` (a ``meeting`` object and a ``decisions`` list). These pydantic models check the structure the
promote -> bronze -> dbt path reads: the top-level arrays, the id each row is keyed by, and the types of the fields
dbt extracts (votes, anchors, refs). They are deliberately tolerant of what the prompt leaves open: extra keys are
kept, most scalars may be null, and a number may arrive as a string (the pipeline's own analyses do that).

    from llm.gemini.part1_schema import parse_and_validate

    result = parse_and_validate(model_text)
    if result.ok:
        analysis = result.data          # the parsed dict, unchanged
    else:
        result.errors                   # short, human-readable reasons (used in the repair prompt)

Pure: no network, no database, no model client, so it runs on a Colab GPU box with only pydantic installed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

Number = Union[int, float, str]   # "7", 7 and 7.0 all occur in saved analyses
MAX_ERRORS = 12


class _Row(BaseModel):
    """Every object in the answer: unknown keys are kept, never dropped."""

    model_config = ConfigDict(extra="allow")


def _str_list(value: Any) -> list[str]:
    """A list of ids: ``None`` is an empty list, null entries are dropped, ids are strings."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("must be a list")
    return [str(v) for v in value if v is not None and str(v).strip()]


class SessionInfo(_Row):
    is_multi_session: Optional[bool] = None
    session_number: Optional[Number] = None
    total_sessions: Optional[Number] = None


class Meeting(_Row):
    meeting_id: Optional[str] = None
    body_name: Optional[str] = None
    meeting_date: Optional[str] = None
    jurisdiction: Optional[str] = None
    session_info: Optional[SessionInfo] = None
    meeting_summary: Optional[str] = None
    agenda_summary: Optional[str] = None


class Person(_Row):
    person_id: str
    full_name: Optional[str] = None
    role: Optional[str] = None
    appeared_as: Optional[str] = None


class Organization(_Row):
    org_id: str
    org_name: Optional[str] = None
    org_type: Optional[str] = None
    ntee_code: Optional[str] = None


class Legislation(_Row):
    leg_id: str
    leg_type: Optional[str] = None
    official_number: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None


class FinancialItem(_Row):
    financial_item_id: str
    event_description: Optional[str] = None
    amount: Optional[Number] = None
    amount_type: Optional[str] = None
    funding_source: Optional[str] = None
    item_date: Optional[str] = None
    item_date_type: Optional[str] = None


class JobClaim(_Row):
    phase: Optional[str] = None
    headcount_low: Optional[Number] = None
    headcount_high: Optional[Number] = None
    project_type: Optional[str] = None
    speaker_person_id: Optional[str] = None
    start_seconds: Optional[Number] = None
    quote: str   # "No quote, no row."


class Place(_Row):
    place_id: str
    raw_text: Optional[str] = None
    normalized_address: Optional[str] = None
    place_type: Optional[str] = None
    latitude: Optional[Number] = None
    longitude: Optional[Number] = None
    linked_decision_ids: list[str] = []
    linked_item_ids: list[str] = []

    _ids = field_validator("linked_decision_ids", "linked_item_ids", mode="before")(_str_list)


class Subject(_Row):
    subject_id: str
    subject_label: Optional[str] = None
    canonical_leg_id: Optional[str] = None
    primary_place_id: Optional[str] = None


class MediaAnchor(_Row):
    timestamp_start_seconds: Optional[Number] = None
    timestamp_end_seconds: Optional[Number] = None
    duration_seconds: Optional[Number] = None


class Motion(_Row):
    moved_by_person_id: Optional[str] = None
    seconded_by_person_id: Optional[str] = None


class VoteTally(_Row):
    yes: Optional[Number] = None
    no: Optional[Number] = None


class _Item(_Row):
    headline: str
    outcome: Optional[str] = None
    subject_id: Optional[str] = None
    primary_place_id: Optional[str] = None
    primary_theme: Optional[str] = None
    place_refs: list[str] = []
    legislation_refs: list[str] = []
    financial_item_refs: list[str] = []
    media_anchor: Optional[MediaAnchor] = None

    _refs = field_validator("place_refs", "legislation_refs", "financial_item_refs", mode="before")(_str_list)


class UncontestedItem(_Item):
    item_id: str
    vote: Optional[Number] = None
    one_line_summary: Optional[str] = None
    presenter_person_ids: list[str] = []
    council_question_person_ids: list[str] = []
    motion: Optional[Motion] = None

    _people = field_validator("presenter_person_ids", "council_question_person_ids", mode="before")(_str_list)


class Decision(_Item):
    decision_id: str
    decision_statement: Optional[str] = None
    vote_tally: Optional[VoteTally] = None
    speaker_segments: list[dict[str, Any]] = []
    human_element: Optional[dict[str, Any]] = None
    competing_views: Optional[dict[str, Any]] = None
    evidence_metrics: list[dict[str, Any]] = []
    smart_brevity: Optional[dict[str, Any]] = None
    diagram_timeline: Optional[str] = None
    diagram_mindmap: Optional[str] = None

    @field_validator("speaker_segments", "evidence_metrics", mode="before")
    @classmethod
    def _rows(cls, value: Any) -> Any:
        return [] if value is None else value


class PublicComment(_Row):
    """One public speaker's comment and their stance toward the action being decided.

    ``stance`` is kept as the model wrote it; dbt maps it to a bucket (``public_stance_bucket``)."""

    speaker_id: Optional[str] = None
    decision_id: Optional[str] = None
    stance: Optional[str] = None
    stance_evidence: Optional[str] = None
    heat: Optional[Number] = None
    speaker_role: Optional[str] = None
    summary: Optional[str] = None
    timestamp_start_seconds: Optional[Number] = None
    timestamp_end_seconds: Optional[Number] = None


class Part1Analysis(_Row):
    """The whole answer. ``meeting``, ``decisions`` and ``uncontested_items`` are what every consumer reads."""

    meeting: Meeting
    people: list[Person] = []
    organizations: list[Organization] = []
    legislation: list[Legislation] = []
    financial_items: list[FinancialItem] = []
    job_claims: list[JobClaim] = []
    places: list[Place] = []
    subjects: list[Subject] = []
    public_participation: list[PublicComment] = []
    uncontested_items: list[UncontestedItem] = []
    decisions: list[Decision]

    @field_validator(
        "people", "organizations", "legislation", "financial_items", "job_claims", "places", "subjects",
        "public_participation",
        "uncontested_items", mode="before",
    )
    @classmethod
    def _null_list(cls, value: Any) -> Any:
        return [] if value is None else value


# --------------------------------------------------------------------------------------------- parsing
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


def extract_json_object(text: str | None) -> Any:
    """The answer's JSON: the whole text, else inside a markdown fence, else the first ``{...}`` with a ``meeting``.

    A one-element array around the object (Gemma does that) is unwrapped. ``None`` when nothing parses."""
    if not text or not text.strip():
        return None
    candidates = [text.strip()]
    fenced = _FENCE.match(text)
    if fenced:
        candidates.insert(0, fenced.group(1))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list) and len(data) == 1:
            data = data[0]
        return data
    # Prose around the object: the first object that parses AND has a ``meeting`` key. An inner object of a cut-off
    # answer (``"meeting": {...}`` alone) must never pass for the answer.
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            data, _ = decoder.raw_decode(text, start)
            if isinstance(data, dict) and "meeting" in data:
                return data
        except json.JSONDecodeError:
            pass
        start = text.find("{", start + 1)
    return None


def _format_error(err: dict[str, Any]) -> str:
    loc = ".".join(str(p) for p in err.get("loc") or ()) or "(root)"
    return f"{loc}: {err.get('msg', 'invalid')}"


@dataclass
class ValidationResult:
    """``ok`` with ``data`` (the parsed dict, as the model wrote it), or the reasons it isn't valid."""

    ok: bool
    data: Optional[dict[str, Any]] = None
    errors: list[str] = field(default_factory=list)
    item_count: int = 0
    truncated: bool = False


def validate_part1(data: Any) -> ValidationResult:
    """Check parsed JSON against :class:`Part1Analysis`. Zero items is still valid (the pipeline saves such an
    answer with an ``_error`` and keeps it out of the site); ``item_count`` says how many there were."""
    if not isinstance(data, dict):
        kind = "nothing" if data is None else type(data).__name__
        return ValidationResult(ok=False, errors=[f"(root): expected one JSON object, got {kind}"])
    try:
        parsed = Part1Analysis.model_validate(data)
    except ValidationError as exc:
        errs = [_format_error(e) for e in exc.errors()]
        more = len(errs) - MAX_ERRORS
        return ValidationResult(ok=False, errors=errs[:MAX_ERRORS] + ([f"... and {more} more"] if more > 0 else []))
    return ValidationResult(ok=True, data=data, item_count=len(parsed.decisions) + len(parsed.uncontested_items))


def parse_and_validate(text: str | None, *, hit_token_limit: bool = False) -> ValidationResult:
    """Parse a model's raw answer and validate it. ``hit_token_limit`` marks an answer cut off by the output cap."""
    data = extract_json_object(text)
    result = validate_part1(data)
    if data is None and text and text.strip():
        result.errors = ["(root): the reply is not valid JSON"]
    if hit_token_limit and not result.ok:
        result.errors.insert(0, "(root): the reply was cut off at the output token limit")
    result.truncated = hit_token_limit
    return result
