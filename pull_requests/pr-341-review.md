# Review: PR #341 (closes #340)

**Verdict: approve once the CCTV run confirms it.**

- `media_link_from_html` is plain and tested on a direct file link, a labelled download link (with relative path and HTML entities), and a page with none.
- Only HTML responses take the new path. A direct file URL is fetched exactly as before, though the first request is now opened and closed before the real download (one extra request).
- A regex is a loose HTML parser, but enough for anchors. A page that builds its link in JavaScript will fail with the clear error, not a wrong file.
