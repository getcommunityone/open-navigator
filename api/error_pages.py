"""
Content-negotiated error responses for the API.

Browser navigations (e.g. the OAuth redirect endpoints, which the frontend
reaches via ``window.location.href``) should see a styled HTML page with a
clickable ``mailto:`` support link — not a wall of raw JSON. Programmatic API
clients still get JSON. ``error_response`` picks the representation from the
request's ``Accept`` header.
"""
from __future__ import annotations

from html import escape
from urllib.parse import quote
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

# Single source of truth for the support address — referenced by the HTML page,
# the mailto link, and the JSON ``support`` field.
SUPPORT_EMAIL = "support@communityone.com"


def wants_html(request: Request) -> bool:
    """True when the client prefers HTML (a browser) over JSON.

    A browser sends ``Accept: text/html,...`` and ranks it ahead of JSON;
    ``fetch``/``httpx`` clients typically send ``*/*`` or ``application/json``.
    """
    accept = request.headers.get("accept", "")
    if "text/html" not in accept:
        return False
    # If JSON is explicitly preferred over HTML, honour that (API tooling).
    if "application/json" in accept:
        return accept.index("text/html") < accept.index("application/json")
    return True


def _mailto(subject: str, body: str) -> str:
    """Build a ``mailto:`` link to support with a prefilled subject/body."""
    query = f"subject={quote(subject)}&body={quote(body)}"
    return f"mailto:{SUPPORT_EMAIL}?{query}"


def _html_page(
    *,
    status_code: int,
    title: str,
    message: str,
    suggestion: Optional[str],
    path: str,
) -> str:
    subject = f"CommunityOne support — {status_code} on {path or 'the site'}"
    body = (
        "Hi CommunityOne team,\n\n"
        f"I ran into a problem.\n\n"
        f"What I was doing: \n"
        f"Page / action: {path}\n"
        f"Error: {status_code} {title}\n\n"
        "Thanks!"
    )
    mailto = _mailto(subject, body)
    # Deep-link into the in-app support form (creates a GitHub-issue ticket),
    # prefilled with the failing path/status via query params it reads.
    report_url = (
        "/support?category=bug"
        f"&subject={quote(subject)}"
        f"&path={quote(path or '')}"
    )
    safe_title = escape(title)
    safe_message = escape(message)
    safe_suggestion = escape(suggestion) if suggestion else ""
    suggestion_html = (
        f'<p class="suggestion">{safe_suggestion}</p>' if safe_suggestion else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{status_code} · {safe_title} · CommunityOne</title>
  <style>
    :root {{ color-scheme: light dark; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; min-height: 100vh; display: flex; align-items: center;
      justify-content: center; padding: 24px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: #0f172a; color: #e2e8f0;
    }}
    .card {{
      max-width: 540px; width: 100%; background: #1e293b; border: 1px solid #334155;
      border-radius: 16px; padding: 40px; box-shadow: 0 10px 40px rgba(0,0,0,.35);
    }}
    .code {{ font-size: 13px; letter-spacing: .12em; text-transform: uppercase; color: #64748b; }}
    h1 {{ margin: 8px 0 12px; font-size: 26px; line-height: 1.2; color: #f8fafc; }}
    p {{ margin: 0 0 16px; line-height: 1.6; color: #cbd5e1; }}
    .suggestion {{ color: #94a3b8; font-size: 15px; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 28px; }}
    a.btn {{
      display: inline-block; padding: 11px 18px; border-radius: 10px;
      text-decoration: none; font-weight: 600; font-size: 15px;
    }}
    a.primary {{ background: #6366f1; color: #fff; }}
    a.primary:hover {{ background: #4f46e5; }}
    a.ghost {{ background: transparent; color: #cbd5e1; border: 1px solid #475569; }}
    a.ghost:hover {{ border-color: #94a3b8; color: #f1f5f9; }}
    .path {{ margin-top: 24px; font-size: 12px; color: #64748b; word-break: break-all; }}
  </style>
</head>
<body>
  <main class="card">
    <div class="code">Error {status_code}</div>
    <h1>{safe_title}</h1>
    <p>{safe_message}</p>
    {suggestion_html}
    <div class="actions">
      <a class="btn primary" href="{escape(report_url)}">Report this issue</a>
      <a class="btn ghost" href="{escape(mailto)}">Email support</a>
      <a class="btn ghost" href="/">Back to CommunityOne</a>
    </div>
    <div class="path">{escape(path)}</div>
  </main>
</body>
</html>"""


def error_response(
    request: Request,
    *,
    status_code: int,
    title: str,
    message: str,
    suggestion: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> HTMLResponse | JSONResponse:
    """Return an HTML error page for browsers, JSON otherwise.

    ``extra`` is merged into the JSON body only (e.g. validation ``errors``,
    a ``login`` URL); the HTML page stays intentionally simple.
    """
    path = request.url.path
    if wants_html(request):
        return HTMLResponse(
            status_code=status_code,
            content=_html_page(
                status_code=status_code,
                title=title,
                message=message,
                suggestion=suggestion,
                path=path,
            ),
        )

    body: dict[str, Any] = {
        "error": title,
        "message": message,
        "path": path,
        "support": SUPPORT_EMAIL,
    }
    if suggestion:
        body["suggestion"] = suggestion
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status_code, content=body)
