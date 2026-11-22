# YouTube API audit diagrams (#737)

draw.io sources built with the same Python helper pattern as
`health-transformation-lab-nlp/diagrams/_build` and `milliman-panel-notes`.

```bash
cd diagrams/youtube-api-audit/_build
python3 build_drawio.py   # writes ../yt1_architecture.drawio, ../yt2_user_flow.drawio
python3 render_png.py     # PNG next to sources + copies into form-ready evidence folder
```

| File | Form field |
|------|------------|
| `yt1_architecture.drawio` / `.png` | Architecture Diagram |
| `yt2_user_flow.drawio` / `.png` | User Flow Diagrams |

Form-ready copies (descriptive names):

- `data/cache/youtube-api-audit-screenshots/form-ready/architecture-diagram.png`
- `data/cache/youtube-api-audit-screenshots/form-ready/user-flow-diagram.png`

**Scope note:** CommunityOne uses YouTube Data API v3 for **public metadata only**
and embeds / links out for playback. We **do not upload** videos to YouTube, so the
form’s “upload script / screencast of upload to YouTube” requirement does not apply;
use the player-embed screenshot as evidence of the playback path instead.
