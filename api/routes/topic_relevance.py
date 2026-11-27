"""
Is a decision about the topic, or does it only mention it? (#1293)

A topic story's Decisions screen lists decisions whose text matched the topic's keywords. A keyword hit is not a decision
on the topic: "firearms" in a training-range budget line or a store's sale permit is not gun control. This module splits
the list with deterministic rules, no model call:

1. ``off``: wording that marks the decision as something else (a budget move, a purchase, an award, a crime report, a
   tool called a gun). Checked first: an ``off`` match is "Mentioned in passing" whatever else it says.
2. ``on``: wording that names the policy the topic's question asks about (``llm.typesafe.topic_lean.TOPICS[slug]``:
   ``subject``, ``excludes``, ``advanced`` and ``blocked``; and ``utils/topicPositions.ts``). "On <topic>".
3. ``needs_reading``: wording that can be either (a gun store's sale permit): on the topic only when the meeting's AI
   reading (``topic_meeting_lean``) says the public took a side on the topic there. The body's action alone is not
   enough: approving a store's routine permit is "acting", but nobody debated a limit on firearms.
4. Anything else is unsure: on the topic only when the meeting's reading says the body acted on the topic (advanced,
   blocked, tabled or deferred). Otherwise, and for a topic with no rules here, "Mentioned in passing".

Patterns are matched case-insensitively on the decision's headline and statement together. The decision record and its
reasons: web_docs/docs/guides/data-stories.md, "Decisions: on the topic or in passing".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Relevance = Literal["on_topic", "in_passing"]


@dataclass(frozen=True)
class TopicRules:
    on: tuple[str, ...] = ()
    off: tuple[str, ...] = ()
    needs_reading: tuple[str, ...] = ()
    _compiled: dict[str, tuple[re.Pattern[str], ...]] = field(default_factory=dict, compare=False, repr=False)

    def match(self, kind: str, text: str) -> str | None:
        pats = self._compiled.get(kind)
        if pats is None:
            pats = tuple(re.compile(p, re.IGNORECASE) for p in getattr(self, kind))
            self._compiled[kind] = pats
        for p in pats:
            m = p.search(text)
            if m:
                return m.group(0)
        return None


_GUN = r"(?:fire\s?arms?|guns?|handguns?|weapons?|rifles?|automatic)"

#: Per topic slug. Topics not listed have no rules: their decisions are on the topic only on the meeting reading's word.
TOPIC_RULES: dict[str, TopicRules] = {
    # Gun control (topic_lean "guns"): a local measure that limits firearms, or a Second Amendment sanctuary resolution.
    # Not: police service weapons and their training or ranges, ammunition purchases, awards, crime reports, ShotSpotter.
    "guns": TopicRules(
        off=(
            r"\btraining\b",
            r"\bqualif",
            r"\bammunition\b",
            r"\bofficer of the month\b",
            r"\baward",
            r"\brecogni[sz]",
            r"\bcapital improvement",
            r"\breallocat",
            r"\btrap system\b",
            r"\bshot\s?spotter\b",
            r"\b(?:gun)?shot detection\b",
            r"\bcrime (?:statistics|update|trends|reduction)",
            r"\bpublic safety (?:report|concerns|initiatives)",
            r"\barchery\b",
            r"\beasement\b",
            r"\bgunshots\b",
            r"\bballistic\b",
            r"\bgrant\b",
            r"\bamerican rescue plan\b|\barp\b",
            r"\b(?:nail|staple|glue|caulk|spray|paint|radar|speed) guns?\b",
        ),
        on=(
            rf"\b{_GUN} ordinance",
            # Active verbs only: "prohibiting felons from possessing firearms", not "a list of people prohibited from ...".
            (
                rf"\b(?:prohibit(?:s|ing)?|bans?|banning|restrict(?:s|ing)?|regulat(?:e|es|ing)|limit(?:s|ing)?|requir(?:e|es|ing))"
                rf"\b[^.]{{0,60}}\b{_GUN}"
            ),
            rf"\b{_GUN}\b[^.]{{0,30}}\b(?:ban|prohibition|restriction|regulation)s?\b",
            r"\bgun (?:safety|control)\b",
            r"\bassault weapons?\b",
            r"\b(?:second|2nd) amendment\b",
            r"\b(?:concealed|open|permitless|constitutional) carry\b",
            r"\b(?:safe|secure) storage\b",
            r"\bghost guns?\b|\bbump stocks?\b|\bred flag\b|\bextreme risk\b",
            r"\bshooting ranges?\b[^.]{0,80}\b(?:regulat|rezon|zoning|cease and desist|enforcement|unpermitted)",
            r"\b(?:regulat|rezon|zoning|cease and desist|enforcement|unpermitted)\w*\b[^.]{0,80}\bshooting ranges?\b",
            r"\bresolution\b[^.]{0,40}\bgun (?:violence|safety)\b",
        ),
        needs_reading=(
            r"\bpermit\b",
            r"\blicen[cs]e\b",
            r"\bspecial use\b",
            r"\bffl\b",
            r"\bhome occupation\b",
            r"\b(?:sell|sale of|sales of) fire\s?arms\b|\bfire\s?arms? (?:sale|sales)\b",
            r"\bgun (?:shop|store|show)s?\b",
            r"\bshooting ranges?\b",
        ),
    ),
    # Water fluoridation: adding fluoride to the public water supply (starting, keeping, restoring or ending it).
    # Not: toothpaste or dental programs, other chemicals, a routine water quality report, feed equipment, removal services.
    "water-fluoridation": TopicRules(
        off=(
            r"\bremoval services?\b",
            r"\bwarehouses?\b",
            r"\bwater quality report\b|\bconsumer confidence\b",
            r"\btoothpaste\b|\bvarnish\b|\bdental (?:program|clinic)s?\b",
            r"\bfeed (?:system|equipment|pump)s?\b",
        ),
        on=(r"\bfluoridat", r"\bfluoride\b[^.]{0,40}\b(?:water|supply)\b", r"\b(?:water|supply)\b[^.]{0,40}\bfluoride\b"),
    ),
    # Short-term rentals (Airbnb, VRBO): permits, zoning, limits. Not: software subscriptions, hotel or motel taxes.
    "short-term-rentals": TopicRules(
        off=(r"\bsoftware\b", r"\bsubscription\b", r"\bhotel[ -]motel\b"),
        on=(r"\bshort[- ]term rentals?\b", r"\bvacation rentals?\b", r"\bairbnb\b", r"\bvrbo\b", r"\bstr (?:ordinance|permit|initiative)"),
    ),
    # License plate readers (ALPR, Flock): buying, renewing, expanding, limiting. Not: red-light, speed or body cameras.
    "license-plate-readers": TopicRules(
        off=(r"\bred[- ]light\b", r"\bspeed cameras?\b", r"\bbody[- ](?:worn )?cameras?\b", r"\bflock of\b", r"\bcrime statistics\b"),
        on=(r"\blicen[cs]e plate (?:readers?|cameras?)\b", r"\balpr\b", r"\blpr\b", r"\bflock\b"),
    ),
    # Pickleball courts: building, converting, lighting, noise, hours. Not: rates, memberships, sponsorships, tournaments.
    "pickleball": TopicRules(
        off=(r"\brates?\b", r"\bfees?\b", r"\bmembership\b", r"\bsponsorship\b", r"\btournament\b", r"\bsubcontractor\b", r"\bsplost\b"),
        on=(r"\bpickle\s?ball\b",),
    ),
    # Bike lanes and paths: building, keeping or removing them. Not: trail maintenance, feasibility updates, devices.
    "bike-lanes": TopicRules(
        off=(r"\bsegways?\b", r"\bpersonal assistive\b", r"\bculvert\b", r"\bmountain bike\b", r"\bfeasibility\b"),
        on=(r"\b(?:bike|bicycle) lanes?\b", r"\bbikeway\b", r"\bprotected lanes?\b", r"\broad diet\b", r"\bcycle tracks?\b"),
    ),
    # Data centers (the Data Center Story's decisions, data_center_decision): the decision names a data center project or
    # rule. Not: a procedural reshuffle, a candidate forum, a government's own server room.
    "data-centers": TopicRules(
        off=(
            r"\bagenda order\b",
            r"\bcandidate\b",
            r"\b(?:city|county|town|village)(?:'s)? (?:own )?data cent(?:er|re)\b",
            r"\bserver room\b",
            r"\bdisaster recovery\b",
        ),
        on=(r"\bdata cent(?:er|re)s?\b", r"\bhyperscale", r"\bserver farms?\b"),
    ),
}

#: The meeting reading's body actions that count as acting on the topic.
ACTED = ("advanced", "blocked", "tabled_or_deferred")


def classify_decision(
    slug: str | None,
    headline: str | None,
    statement: str | None,
    *,
    public_stance: str | None = None,
    vote: str | None = None,
) -> tuple[Relevance, str]:
    """("on_topic" | "in_passing", basis) for one decision.

    ``public_stance`` and ``vote`` are the meeting's AI reading for the topic (topic_meeting_lean): the public's side
    ('against' / 'for' / 'split' / 'silent' / None) and what the body did ('advanced' / 'blocked' / 'tabled_or_deferred'
    / None). The basis says which rule decided, for the API and the docs; it is never shown as a quote."""
    text = " ".join(x for x in (headline, statement) if x)
    rules = TOPIC_RULES.get(slug or "")
    acted = vote in ACTED
    took_side = public_stance in ("against", "for", "split")
    if rules:
        hit = rules.match("off", text)
        if hit:
            return "in_passing", f"off-topic wording: {hit.lower()}"
        hit = rules.match("on", text)
        if hit:
            return "on_topic", f"names the policy: {hit.lower()}"
        hit = rules.match("needs_reading", text)
        if hit:
            if took_side:
                return "on_topic", f"{hit.lower()}, and the meeting's reading says the public took a side"
            return "in_passing", f"{hit.lower()} only; the meeting's reading shows no public side on the topic"
    if acted:
        return "on_topic", "the meeting's reading says the body acted on the topic"
    return "in_passing", "keyword only; not enough evidence it is about the topic"
