"""
Validate (and optionally repair) ```mermaid fences in Markdown via the website Mermaid build.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from llm.gemini.mermaid_diagrams import repair_mermaid_fences_in_markdown

_REPO = Path(__file__).resolve().parents[5]
_WEBSITE = _REPO / "website"
_FENCE_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass
class MermaidFenceError:
    fence_index: int
    fence_line: int
    diagram_type: str
    message: str
    mermaid_line: Optional[int] = None
    mermaid_column: Optional[int] = None
    snippet: str = ""


@dataclass
class MermaidValidationReport:
    path: Path
    fence_count: int = 0
    errors: List[MermaidFenceError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _fence_starts(markdown: str) -> List[int]:
    lines: List[int] = []
    for i, line in enumerate(markdown.splitlines(), start=1):
        if line.strip().lower().startswith("```mermaid"):
            lines.append(i)
    return lines


def extract_mermaid_fences(markdown: str) -> List[str]:
    return [m.group(1).strip() for m in _FENCE_RE.finditer(markdown)]


def _diagram_type(source: str) -> str:
    first = (source.strip().splitlines() or [""])[0].strip().lower()
    return first or "unknown"


def mermaid_cli_available() -> bool:
    return (_WEBSITE / "node_modules" / "mermaid").is_dir()


def run_mermaid_parse_checks(
    blocks: Sequence[str],
    *,
    labels: Optional[Sequence[str]] = None,
) -> List[Optional[MermaidFenceError]]:
    """Return one entry per block: None if OK, else MermaidFenceError fields (without fence_line)."""
    if not blocks:
        return []
    if not mermaid_cli_available():
        raise RuntimeError("Run: cd website && npm install")

    labels = list(labels or [f"fence_{i}" for i in range(len(blocks))])
    with tempfile.TemporaryDirectory() as tmp:
        paths: List[Path] = []
        for i, block in enumerate(blocks):
            p = Path(tmp) / f"fence_{i}.mmd"
            p.write_text(block, encoding="utf-8")
            paths.append(p)
        proc = subprocess.run(
            ["npm", "run", "check-mermaid", "--", "--json", *[str(p) for p in paths]],
            cwd=_WEBSITE,
            capture_output=True,
            text=True,
        )

    results: List[Optional[MermaidFenceError]] = [None] * len(blocks)
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        row = json.loads(line)
        idx = int(row["index"])
        if row.get("ok"):
            continue
        results[idx] = MermaidFenceError(
            fence_index=idx,
            fence_line=0,
            diagram_type=_diagram_type(blocks[idx]),
            message=str(row.get("message") or "parse error"),
            mermaid_line=row.get("line"),
            mermaid_column=row.get("column"),
            snippet=str(row.get("snippet") or blocks[idx][:500]),
        )
    # Node exited non-zero but no JSON rows — surface stderr
    if proc.returncode != 0 and all(r is None for r in results):
        msg = (proc.stderr or proc.stdout or "mermaid check failed").strip()[:500]
        for i in range(len(blocks)):
            results[i] = MermaidFenceError(
                fence_index=i,
                fence_line=0,
                diagram_type=_diagram_type(blocks[i]),
                message=msg,
                snippet=blocks[i][:500],
            )
    return results


def validate_markdown_text(markdown: str, *, path: Path = Path("-")) -> MermaidValidationReport:
    fence_lines = _fence_starts(markdown)
    blocks = extract_mermaid_fences(markdown)
    report = MermaidValidationReport(path=path, fence_count=len(blocks))
    if not blocks:
        return report

    checks = run_mermaid_parse_checks(blocks)
    for i, err in enumerate(checks):
        if err is None:
            continue
        err.fence_line = fence_lines[i] if i < len(fence_lines) else 0
        err.diagram_type = _diagram_type(blocks[i])
        report.errors.append(err)
    return report


def validate_markdown_file(path: Path) -> MermaidValidationReport:
    text = path.read_text(encoding="utf-8")
    return validate_markdown_text(text, path=path.resolve())


def repair_and_validate_markdown(path: Path, *, write: bool = True) -> MermaidValidationReport:
    text = path.read_text(encoding="utf-8")
    fixed = repair_mermaid_fences_in_markdown(text)
    if write and fixed != text:
        path.write_text(fixed + ("\n" if not fixed.endswith("\n") else ""), encoding="utf-8")
    return validate_markdown_text(fixed, path=path.resolve())


def format_report(report: MermaidValidationReport) -> str:
    if report.ok:
        return f"OK  {report.path}  ({report.fence_count} diagram(s))"
    lines = [f"FAIL  {report.path}  ({len(report.errors)}/{report.fence_count} diagram(s))"]
    for err in report.errors:
        loc = f"markdown line {err.fence_line}" if err.fence_line else f"fence #{err.fence_index}"
        inner = ""
        if err.mermaid_line is not None:
            inner = f", mermaid line {err.mermaid_line}"
        lines.append(f"  [{err.diagram_type}] {loc}{inner}: {err.message}")
        if err.snippet:
            preview = err.snippet.replace("\n", " | ")[:200]
            lines.append(f"    {preview}")
    return "\n".join(lines)


def write_errors_sidecar(report: MermaidValidationReport, sidecar_path: Path) -> None:
    payload = {
        "report": str(report.path),
        "ok": report.ok,
        "fence_count": report.fence_count,
        "errors": [
            {
                "fence_index": e.fence_index,
                "fence_line": e.fence_line,
                "diagram_type": e.diagram_type,
                "message": e.message,
                "mermaid_line": e.mermaid_line,
                "mermaid_column": e.mermaid_column,
                "snippet": e.snippet,
            }
            for e in report.errors
        ],
    }
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
