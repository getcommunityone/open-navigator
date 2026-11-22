# Rendering

Same tooling as `health-transformation-lab-nlp` / `milliman-panel-notes`.

```bash
# Terminal A — draw.io export page
cd diagrams/youtube-api-audit/_build/drawio/src/main/webapp
python3 -m http.server 8765

# Terminal B — build + render
cd diagrams/youtube-api-audit/_build
python3 build_drawio.py
python3 build_user_flow_drawio.py
python3 render_drawio.py ../yt1_architecture.drawio ../yt2_user_flow.drawio

# Mermaid user-flow alternate (standard flowchart shapes)
mmdc -i ../flows/yt2_user_flow.mmd -o ../flows/yt2_user_flow.png -s 2 -b white
```
