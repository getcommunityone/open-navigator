# YouTube API audit diagrams (#737)

Same pattern as `health-transformation-lab-nlp` / `milliman-panel-notes`:
Python → `.drawio` (AWS icons + medallion lanes), PNG via draw.io’s export engine.

| File | Form field |
|------|------------|
| `yt1_architecture.drawio` / `.png` | Architecture Diagram (medallion: Source → Ingest → Bronze/Silver/Gold → Serve → Consumer) |
| `yt2_user_flow.drawio` / `.png` | User Flow Diagrams (standard oval / rect / diamond / predefined-process) |
| `flows/yt2_user_flow.mmd` | Mermaid alternate of the same journey |

```bash
cd diagrams/youtube-api-audit/_build
# once: git sparse-clone draw.io webapp (see render.md)
python3 -m http.server 8765 --directory drawio/src/main/webapp   # terminal A
python3 build_drawio.py && python3 build_user_flow_drawio.py
python3 render_drawio.py ../yt1_architecture.drawio ../yt2_user_flow.drawio
```

Form copies: `web_docs/static/img/legal/youtube-api-audit/{architecture,user-flow}-diagram.png`
