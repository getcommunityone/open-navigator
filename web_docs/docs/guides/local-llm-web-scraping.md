---
sidebar_position: 9
---

# Local LLM web scraping (Ollama + Gemma)

Government sites change layout often. CSS selectors and regex break; a **local LLM** can extract **meetings, dates, and contacts** from cleaned page text without sending data to a cloud API.

Open Navigator implements this as an optional layer on top of the existing meeting crawl (httpx / Playwright / BeautifulSoup).

## Pipeline

```text
[ Target URL ]
       │  httpx (Playwright fallback on 403/TLS)
       ▼
[ Raw HTML ]
       │  BeautifulSoup: drop script/style/nav noise
       ▼
[ Markdown-like text ]
       │  Pydantic schema + prompt
       ▼
[ Ollama — Gemma 4 (or compatible) ]
       ▼
[ JSON — meetings, contacts, dates ]
```

**Do not** paste full raw HTML into the model. Thousands of nested `<motion.div>` nodes waste context and hurt accuracy. The repo converts HTML to compact text first (`scripts/scraping/html_to_markdown.py`), and the jurisdiction crawler already writes `page_*.readable.txt` sidecars.

## Install Ollama and Gemma

1. Install [Ollama](https://ollama.com/download) (Linux, macOS, Windows).
2. Pull a Gemma model (name may vary by Ollama catalog):

```bash
./scripts/scraping/setup_ollama_gemma.sh
# or manually:
ollama pull gemma4
```

3. Optional LangChain Ollama bindings:

```bash
.venv/bin/pip install -r requirements-ollama-scraping.txt
```

4. Verify:

```bash
.venv/bin/python scripts/scraping/extract_page_structured.py --check-ollama
```

## Extract from a single URL

```bash
cd /path/to/open-navigator

.venv/bin/python scripts/scraping/extract_page_structured.py \
  --url "https://www.example-county.gov/meetings/" \
  --markdown-out /tmp/page.md \
  --out /tmp/extraction.json
```

Or from an existing crawl sidecar:

```bash
.venv/bin/python scripts/scraping/extract_page_structured.py \
  --readable-txt data/cache/scraped_meetings/AL/county/.../_crawl_html/page_agenda.readable.txt \
  --out /tmp/extraction.json
```

Output shape (Pydantic `JurisdictionPageExtraction`):

- `jurisdiction_name`, `page_summary`
- `meetings[]` — title, `meeting_date`, agenda/minutes URLs
- `contacts[]` — name, role, email, phone
- `contact_email`, `notes`

## Hook into the meeting crawl

During `comprehensive_discovery_pipeline_jurisdiction`, after each `page_*.readable.txt` is written:

```bash
export SCRAPED_MEETINGS_OLLAMA_EXTRACT=1
export SCRAPED_MEETINGS_OLLAMA_EXTRACT_MAX_PAGES=5   # cap per run (slow on CPU)
export SCRAPED_MEETINGS_OLLAMA_MODEL=gemma4
export OLLAMA_HOST=http://127.0.0.1:11434

.venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction \
  --state AL --geoid 01001 --type county --url "https://..."
```

Writes `page_*.ollama.json` next to the readable file under `_crawl_html/`.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama API base URL |
| `SCRAPED_MEETINGS_OLLAMA_MODEL` | `gemma4` | Model tag for `ollama pull` |
| `SCRAPED_MEETINGS_OLLAMA_EXTRACT` | off | Enable crawl sidecar |
| `SCRAPED_MEETINGS_OLLAMA_EXTRACT_MAX_PAGES` | `3` | Max LLM calls per crawl run |
| `SCRAPED_MEETINGS_OLLAMA_TIMEOUT_SECONDS` | `300` | Ollama request timeout |
| `SCRAPED_MEETINGS_OLLAMA_USE_LANGCHAIN` | off | Use `langchain-ollama` instead of raw HTTP |

## Hardware expectations

| Setup | Behavior |
|-------|----------|
| GPU (8GB+ VRAM) | Fast enough for interactive testing |
| CPU-only laptop (16GB RAM) | Works for **batch** jobs; expect seconds per page |
| Thousands of pages/day | Queue locally or sample pages; do not LLM every link |

## Limitations

- **Hallucinated dates** — prompt asks for YYYY-MM-DD only when explicit; always validate against PDFs.
- **Sequential throughput** — unlike cloud APIs, one local model usually processes one page at a time.
- **Model availability** — if `gemma4` is not in your Ollama library, set `SCRAPED_MEETINGS_OLLAMA_MODEL` to a pulled tag (`ollama list`).

## Related docs

- [Scraper improvements](./scraper-improvements.md) — Legistar API and platform heuristics
- [Jurisdiction setup](./jurisdiction-setup.md) — discovery and crawl entrypoints
- [Specialized AI models](./specialized-ai-models.md) — cloud and domain-specific models for legislative text

## Code map

| File | Role |
|------|------|
| `scripts/scraping/html_to_markdown.py` | HTML → clean text |
| `scripts/scraping/schemas.py` | Pydantic output schema |
| `scripts/scraping/ollama_extract.py` | Ollama HTTP + optional LangChain |
| `scripts/scraping/extract_page_structured.py` | CLI for URL / file / readable.txt |
| `scripts/scraping/crawl_llm_sidecar.py` | Optional hook after crawl |
| `scripts/scraping/setup_ollama_gemma.sh` | Install helper |
