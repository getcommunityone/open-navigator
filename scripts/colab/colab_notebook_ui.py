"""
Jupyter / Colab / VS Code notebook visibility during Run All.

After §1 (or any import + ``install_notebook_cell_hooks()``):

- Every **code** cell prints loud ``▶ RUNNING`` / ``✓ FINISHED`` / ``✗ ERROR`` banners.
- A **sticky HTML status** block updates at the top of the output (easy to spot locally).

Tag cells (optional, clearer labels):

    # @cell §4 API keys
"""

from __future__ import annotations

import os
import re
import traceback
from typing import Any, Optional

_CELL_TAG_RE = re.compile(r"^\s*#\s*@cell\s+(.+?)\s*$", re.MULTILINE)
_SECTION_RE = re.compile(r"^\s*#\s*(§\s*\d+[^\n#]{0,40})", re.MULTILINE)
_INSTALLED = False
_LAST_LABEL: Optional[str] = None
_RUN_INDEX = 0
_STATUS_DISPLAY_ID = "open-navigator-notebook-status"


def parse_cell_label(source: str) -> Optional[str]:
    """Read ``# @cell §4 API keys`` from the first few lines."""
    if not source:
        return None
    for line in source.splitlines()[:8]:
        m = _CELL_TAG_RE.match(line)
        if m:
            return m.group(1).strip()
    return None


def infer_cell_label(source: str, *, run_index: int) -> str:
    """Best label for banners: @cell tag, § comment, or run index."""
    tagged = parse_cell_label(source)
    if tagged:
        return tagged
    if source:
        m = _SECTION_RE.search(source)
        if m:
            return m.group(1).strip()
        for line in source.splitlines()[:12]:
            s = line.strip()
            if s.startswith("#") and len(s) > 2:
                return s.lstrip("# ").strip()[:56]
    return f"code cell #{run_index}"


def _banner(title: str, detail: str = "", *, char: str = "=") -> None:
    width = 60
    print()
    print(char * width)
    print(title)
    if detail:
        print(detail)
    print(char * width)
    print(flush=True)


def _status_html(label: str, state: str) -> str:
    colors = {
        "running": ("#1a56db", "#eff6ff", "▶ RUNNING"),
        "done": ("#047857", "#ecfdf5", "✓ DONE"),
        "error": ("#b91c1c", "#fef2f2", "✗ ERROR"),
    }
    border, bg, prefix = colors.get(state, colors["running"])
    safe = (
        label.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return (
        f'<motion.div style="margin:8px 0;padding:12px 14px;border:3px solid {border};'
        f'background:{bg};font-family:system-ui,sans-serif;font-size:15px;line-height:1.4">'
        f"<strong>{prefix}</strong> — {safe}"
        f"</motion.div>"
    )


def _update_status_display(label: str, state: str) -> None:
    if os.environ.get("GOVERNANCE_NOTEBOOK_STATUS_HTML", "1").strip().lower() in (
        "0",
        "false",
        "no",
    ):
        return
    try:
        from IPython.display import HTML, display, update_display
    except ImportError:
        return
    html = HTML(_status_html(label, state))
    global _STATUS_DISPLAY_ID
    try:
        update_display(html, display_id=_STATUS_DISPLAY_ID)
    except Exception:
        display(html, display_id=_STATUS_DISPLAY_ID)


def cell_start(label: str, *, run_index: Optional[int] = None) -> None:
    global _LAST_LABEL
    _LAST_LABEL = label
    idx = f" [{run_index}]" if run_index is not None else ""
    _banner(
        f"▶ RUNNING{idx}: {label}",
        "In Cursor/VS Code: left gutter shows [*] on this cell. "
        "Stop kernel if this is wrong.",
    )
    _update_status_display(label, "running")


def cell_done(label: str, *, run_index: Optional[int] = None) -> None:
    idx = f" [{run_index}]" if run_index is not None else ""
    _banner(
        f"✓ FINISHED{idx}: {label}",
        "Run All will continue to the next code cell.",
        char="-",
    )
    _update_status_display(label, "done")


def cell_error(label: str, exc: BaseException, *, run_index: Optional[int] = None) -> None:
    idx = f" [{run_index}]" if run_index is not None else ""
    _banner(
        f"✗ ERROR{idx}: {label}",
        f"{type(exc).__name__}: {exc}\n\nFix this cell before Run All continues.",
        char="!",
    )
    _update_status_display(label, "error")
    traceback.print_exc()


def install_notebook_cell_hooks() -> None:
    """Register IPython hooks — works with Run All and single-cell Run."""
    global _INSTALLED, _RUN_INDEX
    if _INSTALLED:
        print("Notebook cell hooks already installed.")
        return
    try:
        ip = get_ipython()  # type: ignore[name-defined]
    except NameError:
        print(
            "Not in IPython — hooks skipped. "
            "Open this file in Jupyter / VS Code / Colab and run §1."
        )
        return

    def _pre_run_cell(info: Any) -> None:
        global _RUN_INDEX, _LAST_LABEL
        raw = getattr(info, "raw_cell", None) or ""
        if not str(raw).strip():
            return
        _RUN_INDEX += 1
        label = infer_cell_label(str(raw), run_index=_RUN_INDEX)
        _LAST_LABEL = label
        cell_start(label, run_index=_RUN_INDEX)

    def _post_run_cell(result: Any) -> None:
        global _LAST_LABEL, _RUN_INDEX
        if not _LAST_LABEL:
            return
        label = _LAST_LABEL
        idx = _RUN_INDEX
        err = getattr(result, "error_in_exec", None)
        if err is not None:
            if isinstance(err, BaseException):
                cell_error(label, err, run_index=idx)
            else:
                cell_error(label, RuntimeError(str(err)), run_index=idx)
        else:
            cell_done(label, run_index=idx)
        _LAST_LABEL = None

    ip.events.register("pre_run_cell", _pre_run_cell)
    ip.events.register("post_run_cell", _post_run_cell)
    _INSTALLED = True
    print("Notebook cell hooks installed (all code cells, including Run All).")
    print("Watch: left gutter [*] + banners below + blue/green status box.")


def begin_cell(label: str) -> None:
    """Manual banner when hooks are not used."""
    cell_start(label)


def end_cell(label: str) -> None:
    """Manual done banner when hooks are not used."""
    cell_done(label)
