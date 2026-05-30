"""
Convert Part 1 ``diagram_*_lines`` into valid Mermaid ``timeline`` / ``mindmap`` strings.
"""

from __future__ import annotations

import re
from typing import Any, List, Tuple, Union

TimelineInput = Union[str, List[str], None]
MindmapInput = Union[str, List[str], None]

# Mermaid timeline: ONE colon per line separates period from event; commas/colons in
# the period label often break the parser (see mermaid-js/mermaid#4175).


def _as_lines(value: TimelineInput) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [ln.strip() for ln in text.replace("\\n", "\n").splitlines() if ln.strip()]


def is_timeline_mermaid(text: str) -> bool:
    return bool(text.strip()) and text.strip().splitlines()[0].strip().lower() == "timeline"


def is_mindmap_mermaid(text: str) -> bool:
    return bool(text.strip()) and text.strip().splitlines()[0].strip().lower() == "mindmap"


def _sanitize_timeline_period(label: str) -> str:
    """Time/period token (left of the single colon). No commas, slashes, or colons."""
    label = (label or "").strip().lstrip("- ").strip()
    label = label.replace(",", "").replace("/", "-").replace(":", " ")
    label = label.replace(".", " ")
    label = re.sub(r"\s+", " ", label).strip()
    if re.search(r"\d{1,2}:\d{2}", label):
        label = re.sub(r"(\d{1,2}):(\d{2})", r"\1h\2", label)
    # Reject sentence-like period labels the model invented (e.g. ``aggregate vs regular``).
    if len(label.split()) > 3 or re.search(r"\bvs\b", label, re.I):
        return "When"
    if len(label) > 36:
        label = label[:36].rstrip()
    return label or "When"


def _sanitize_timeline_event(event: str) -> str:
    """Event text (right of colon). No colons; no leading list markers."""
    event = (event or "").strip()
    event = re.sub(r"^[-*•]\s+", "", event)
    event = event.replace(":", " -")
    event = re.sub(r"\.{3,}\s*$", "", event)
    event = re.sub(r"\s+", " ", event).strip()
    return _truncate_label(event, max_len=80) if event else "Event"


def _dedupe_timeline_period_label(label: str, seen: set[str]) -> str:
    """Mermaid timeline periods must be unique within a section."""
    base = label or "When"
    if base not in seen:
        seen.add(base)
        return base
    n = 2
    while f"{base} {n}" in seen:
        n += 1
    unique = f"{base} {n}"
    seen.add(unique)
    return unique


def _split_timeline_event_line(line: str) -> Tuple[str, str, str] | None:
    """Return (indent, period, event) for ``period : event`` lines."""
    m = re.match(r"^(\s+)(\S(?:.*\S)?)\s*:\s*(.+)$", line)
    if not m:
        return None
    return m.group(1), m.group(2).strip(), m.group(3).strip()


def sanitize_timeline_mermaid(text: str) -> str:
    """Repair model-generated timeline blocks so Mermaid Live / preview render."""
    raw = (text or "").strip()
    if not raw:
        return ""
    if not is_timeline_mermaid(raw):
        return lines_to_timeline_mermaid(raw)

    out: List[str] = []
    seen_periods: set[str] = set()
    for line in raw.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if lower == "timeline":
            out.append("timeline")
            seen_periods.clear()
            continue
        if lower.startswith("title "):
            title = stripped[6:].strip()
            out.append(f"    title {_sanitize_timeline_event(title)}")
            continue
        if lower.startswith("section "):
            sec = stripped[8:].strip()
            out.append(f"    section {_sanitize_timeline_event(sec)}")
            seen_periods.clear()
            continue

        parts = _split_timeline_event_line(line)
        if parts:
            indent, period, event = parts
            period = _dedupe_timeline_period_label(
                _sanitize_timeline_period(period), seen_periods
            )
            event = _sanitize_timeline_event(event)
            out.append(f"{indent}{period} : {event}")
        elif stripped and ":" in stripped:
            # Model used ``label : event`` without matching our split (e.g. period contains ``.``)
            left, _, right = stripped.partition(":")
            period = _dedupe_timeline_period_label(
                _sanitize_timeline_period(left), seen_periods
            )
            event = _sanitize_timeline_event(right)
            out.append(f"        {period} : {event}")
        elif stripped:
            out.append(line)
    return "\n".join(out)


def _label_from_event_line(line: str, index: int, total: int) -> str:
    paren = re.search(r"\(([^)]+)\)", line)
    if paren:
        return _sanitize_timeline_period(paren.group(1))
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", line)
    if iso:
        return iso.group(1)
    month = re.search(
        r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"[^\d]{0,3}(\d{4})\b",
        line,
        re.I,
    )
    if month:
        return _sanitize_timeline_period(f"{month.group(1)} {month.group(2)}")
    if index == 0:
        return "Earlier"
    if index >= total - 1:
        return "Next"
    return f"Step {index + 1}"


def _clean_event_text(line: str) -> str:
    text = re.sub(r"^\s*->\s*", "", line.strip())
    return _sanitize_timeline_event(text)


def lines_to_timeline_mermaid(
    value: TimelineInput,
    *,
    title: str = "Decision lifecycle",
) -> str:
    if isinstance(value, str) and is_timeline_mermaid(value):
        return sanitize_timeline_mermaid(value)
    lines = _as_lines(value)
    if not lines:
        return ""
    if lines and is_timeline_mermaid(lines[0]):
        return sanitize_timeline_mermaid("\n".join(lines))

    safe_title = _sanitize_timeline_event(title)[:60]
    out = ["timeline", f"    title {safe_title}", "    section Lifecycle"]
    for i, line in enumerate(lines):
        label = _label_from_event_line(line, i, len(lines))
        event = _clean_event_text(line)
        out.append(f"        {label} : {event}")
    return sanitize_timeline_mermaid("\n".join(out))


def _balance_parentheses(text: str) -> str:
    """Close ``(`` left open after truncation so Mermaid mindmap parsers do not fail."""
    extra = text.count("(") - text.count(")")
    if extra > 0:
        text += ")" * extra
    return text


def _truncate_label(text: str, max_len: int = 80) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return _balance_parentheses(text)
    cut = text[: max_len - 3].rsplit(" ", 1)[0]
    return _balance_parentheses(cut + "...")


def _sanitize_mindmap_node(node: str) -> str:
    node = (node or "").strip()
    node = re.sub(r"^[-*•]\s+", "", node)
    # Unbalanced or inline ``(…)`` breaks mindmap parsers (treated as new nodes).
    node = re.sub(r"\(([^)]*)\)", r" - \1", node)
    node = node.replace("(", " ").replace(")", " ")
    node = node.replace(":", " -")
    node = node.replace(",", ";")
    node = re.sub(r"\s+", " ", node).strip()
    return _truncate_label(node, max_len=80) if node else ""


# Branch labels the model usually emits as parents (children follow until the next parent).
_MINDMAP_PARENT_LABELS = frozenset(
    {
        "arguments for",
        "arguments for revocation",
        "arguments against",
        "stakeholders",
        "stakeholder",
        "proposal",
        "outcome",
        "decision",
        "concerns",
        "reasoning",
        "considerations",
        "commission approval",
        "project details",
        "material decision",
        "key considerations",
        "discussion topic",
        "supporters",
        "opponents",
        "public comment",
        "staff recommendation",
        "vote",
        "result",
        "prior",
        "next steps",
        "this meeting",
        "background",
        "next",
        "proposal",
        "concerns",
        "reasoning",
        "considerations",
        "problem",
        "problems",
        "solution",
        "solutions",
        "funding",
        "timeline",
        "scope",
        "risks",
        "benefits",
        "context",
        "process",
        "design",
        "implementation",
        "coordination",
        "impacts",
        "issues",
        "options",
        "approach",
        "overview",
        "status",
        "cost",
        "costs",
        "grants",
        "construction",
        "alternatives",
        "recommendation",
        "recommendations",
        "access",
        "traffic",
        "safety",
    }
)

_MINDMAP_PARENT_PREFIXES = (
    "arguments ",
    "stakeholder",
    "proposal",
    "outcome",
    "decision",
    "concern",
    "reasoning",
    "consideration",
    "commission ",
    "project ",
    "material ",
    "key ",
    "discussion ",
    "public ",
    "staff ",
    "supporter",
    "opponent",
    "problem",
    "solution",
    "fund",
    "timelin",
    "impact",
    "issue",
    "option",
    "benefit",
    "risk",
    "scope",
    "design",
    "construct",
    "coordinat",
    "implement",
    "alternativ",
    "recommend",
)


def _normalize_mindmap_label(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _looks_like_mindmap_detail(text: str) -> bool:
    """Leaf/detail nodes should stay nested under a section parent."""
    if not text:
        return True
    if any(ch in text for ch in ";,"):
        return True
    if text[0].islower():
        return True
    if re.search(r"\b\d+[-–]\d+\b|\(\d", text):
        return True
    if "$" in text or re.search(r"\b\d{4}\b", text):
        return True
    if re.search(r"\s+-\s+", text):
        return True
    if len(text.split()) > 6:
        return True
    return False


def _is_mindmap_parent_label(text: str) -> bool:
    if _looks_like_mindmap_detail(text):
        return False
    key = _normalize_mindmap_label(text)
    if key in _MINDMAP_PARENT_LABELS:
        return True
    if any(key.startswith(p) for p in _MINDMAP_PARENT_PREFIXES):
        return len(text.split()) <= 5
    return False


def _structure_flat_mindmap_nodes(nodes: List[str]) -> List[str]:
    """
    Re-indent flat Gemini mindmaps so section labels are parents and following lines are children.

    Mermaid mindmap hierarchy is **indentation only**; a flat list renders as a star around root.
    """
    if not nodes:
        return []
    out: List[str] = []
    i = 0
    while i < len(nodes):
        node = nodes[i]
        if _is_mindmap_parent_label(node):
            out.append(f"    {node}")
            i += 1
            while i < len(nodes) and not _is_mindmap_parent_label(nodes[i]):
                out.append(f"      {nodes[i]}")
                i += 1
        else:
            out.append(f"    {node}")
            i += 1
    return out


def _mindmap_body_needs_restructure(body_lines: List[str]) -> bool:
    """True when every branch is a direct child of root (no nested indentation)."""
    indents: List[int] = []
    for line in body_lines:
        stripped = line.strip()
        if not stripped or stripped.lower() == "mindmap" or stripped.startswith("root(("):
            continue
        indents.append(len(line) - len(line.lstrip()))
    if not indents:
        return False
    return max(indents) <= 4


def _sanitize_mindmap_root_line(line: str) -> str:
    """``root((...))`` must not contain inner ``(`` — Mermaid treats them as new nodes."""
    stripped = line.strip()
    if not stripped.lower().startswith("root(("):
        return line.rstrip()
    m = re.match(r"^(\s*)root\(\((.*)\)\)\s*$", stripped, re.DOTALL)
    if not m:
        return line.rstrip()
    indent, inner = m.group(1), m.group(2).strip()
    inner = re.sub(r"\(([^)]*)\)", r" - \1", inner)
    inner = inner.replace("(", " ").replace(")", " ")
    inner = _sanitize_mindmap_node(inner) or "Decision"
    root_indent = indent if indent.strip() else "  "
    return f"{root_indent}root(({inner}))"


def sanitize_mindmap_mermaid(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    if not is_mindmap_mermaid(raw):
        return lines_to_mindmap_mermaid(raw)

    header: List[str] = []
    body_nodes: List[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower == "mindmap":
            header.append("mindmap")
            continue
        if stripped.startswith("root(("):
            header.append(_sanitize_mindmap_root_line(line))
            continue
        if stripped.startswith(("-", "*", "•")):
            stripped = stripped.lstrip("-*• ").strip()
        node = _sanitize_mindmap_node(stripped)
        if node:
            body_nodes.append(node)

    if len(header) < 2:
        return ""
    if _mindmap_body_needs_restructure(
        [f"    {n}" for n in body_nodes]
    ):
        body_lines = _structure_flat_mindmap_nodes(body_nodes)
    else:
        body_lines = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.lower() == "mindmap" or stripped.startswith("root(("):
                continue
            node = _sanitize_mindmap_node(stripped.lstrip("-*• ").strip())
            if not node:
                continue
            leading = len(line) - len(line.lstrip())
            if leading >= 6:
                body_lines.append(f"      {node}")
            elif leading >= 4:
                body_lines.append(f"    {node}")
            else:
                body_lines.append(f"  {node}")
    return "\n".join(header + body_lines)


def _mindmap_node_text(line: str) -> str:
    text = line.strip()
    if text.startswith("->"):
        text = text[2:].strip()
    return _sanitize_mindmap_node(text)


def _mindmap_branch_depth(line: str) -> int:
    stripped = line.lstrip()
    if not stripped:
        return 0
    leading = len(line) - len(stripped)
    if stripped.startswith("->"):
        return max(1, leading // 2)
    return 0


def lines_to_mindmap_mermaid(value: MindmapInput) -> str:
    if isinstance(value, str) and is_mindmap_mermaid(value):
        return sanitize_mindmap_mermaid(value)
    lines = _as_lines(value)
    if not lines:
        return ""
    if lines and is_mindmap_mermaid(lines[0]):
        return sanitize_mindmap_mermaid("\n".join(lines))

    root = _mindmap_node_text(lines[0])
    out = ["mindmap", f"  root(({root}))"]
    for line in lines[1:]:
        depth = _mindmap_branch_depth(line)
        node = _mindmap_node_text(line)
        if not node:
            continue
        indent = "  " * (depth + 1)
        out.append(f"{indent}{node}")
    return sanitize_mindmap_mermaid("\n".join(out))


def normalize_decision_diagrams(decision: dict[str, Any]) -> None:
    """In-place: ensure ``diagram_timeline`` / ``diagram_mindmap`` render in Mermaid."""
    if not isinstance(decision, dict):
        return
    headline = str(decision.get("headline") or "Decision")[:60]
    t_src = decision.get("diagram_timeline") or decision.get("diagram_timeline_lines")
    m_src = decision.get("diagram_mindmap") or decision.get("diagram_mindmap_lines")
    timeline = lines_to_timeline_mermaid(t_src, title=headline)
    mindmap = lines_to_mindmap_mermaid(m_src)
    if timeline:
        decision["diagram_timeline"] = timeline
    if mindmap:
        decision["diagram_mindmap"] = mindmap


_MERMAID_FENCE_RE = re.compile(
    r"```mermaid\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def repair_mermaid_fences_in_markdown(markdown: str) -> str:
    """Fix fenced diagram blocks in Part 2 reports before save."""

    def _fix_block(match: re.Match[str]) -> str:
        body = match.group(1)
        stripped = body.strip()
        if is_timeline_mermaid(stripped):
            fixed = sanitize_timeline_mermaid(stripped)
        elif is_mindmap_mermaid(stripped):
            fixed = sanitize_mindmap_mermaid(stripped)
        else:
            return match.group(0)
        return f"```mermaid\n{fixed}\n```"

    return _MERMAID_FENCE_RE.sub(_fix_block, markdown)
