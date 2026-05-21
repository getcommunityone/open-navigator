"""
Convert Part 1 ``diagram_*_lines`` into valid Mermaid ``timeline`` / ``mindmap`` strings.
"""

from __future__ import annotations

import re
from typing import Any, List, Union

TimelineInput = Union[str, List[str], None]
MindmapInput = Union[str, List[str], None]


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


def _sanitize_timeline_label(raw: str) -> str:
    """Mermaid timeline labels must not contain unquoted colons like 09:00."""
    label = (raw or "").strip()[:40]
    label = label.replace('"', "'")
    if re.search(r"\d{1,2}:\d{2}", label):
        label = re.sub(r"(\d{1,2}):(\d{2})", r"\1h\2", label)
    return label or "Event"


def _label_from_event_line(line: str, index: int, total: int) -> str:
    paren = re.search(r"\(([^)]+)\)", line)
    if paren:
        return _sanitize_timeline_label(paren.group(1))
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", line):
        return _sanitize_timeline_label(re.search(r"\b\d{4}-\d{2}-\d{2}\b", line).group(0))
    if index == 0:
        return "Earlier"
    if index >= total - 1:
        return "Next"
    return f"Step{index + 1}"


def _clean_event_text(line: str) -> str:
    text = re.sub(r"^\s*->\s*", "", line.strip())
    text = re.sub(r"\s+", " ", text)
    return text[:80] if text else "Event"


def lines_to_timeline_mermaid(
    value: TimelineInput,
    *,
    title: str = "Decision lifecycle",
) -> str:
    if isinstance(value, str) and is_timeline_mermaid(value):
        return value.strip()
    lines = _as_lines(value)
    if not lines:
        return ""
    if is_timeline_mermaid(lines[0]):
        return "\n".join(lines)

    safe_title = _clean_event_text(title)[:60]
    out = ["timeline", f"    title {safe_title}", "    section Lifecycle"]
    for i, line in enumerate(lines):
        label = _label_from_event_line(line, i, len(lines))
        event = _clean_event_text(line)
        out.append(f"        {label} : {event}")
    return "\n".join(out)


def _mindmap_node_text(line: str) -> str:
    text = line.strip()
    if text.startswith("->"):
        text = text[2:].strip()
    return _clean_event_text(text)[:50]


def _mindmap_branch_depth(line: str) -> int:
    """Depth from leading spaces before ``->`` (2 spaces per level)."""
    stripped = line.lstrip()
    if not stripped:
        return 0
    leading = len(line) - len(stripped)
    if stripped.startswith("->"):
        return max(1, leading // 2)
    return 0


def lines_to_mindmap_mermaid(value: MindmapInput) -> str:
    if isinstance(value, str) and is_mindmap_mermaid(value):
        return value.strip()
    lines = _as_lines(value)
    if not lines:
        return ""
    if is_mindmap_mermaid(lines[0]):
        return "\n".join(lines)

    root = _mindmap_node_text(lines[0])
    out = ["mindmap", f"  root(({root}))"]
    for line in lines[1:]:
        depth = _mindmap_branch_depth(line)
        node = _mindmap_node_text(line)
        if not node:
            continue
        # mindmap: 2 spaces under root, +2 per branch level
        indent = "  " * (depth + 1)
        out.append(f"{indent}{node}")
    return "\n".join(out)


def normalize_decision_diagrams(decision: dict[str, Any]) -> None:
    """In-place: ensure ``diagram_timeline`` / ``diagram_mindmap`` are valid Mermaid."""
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
