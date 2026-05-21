# Gemini meeting analysis

## Cheap path: AI Studio + Flash-Lite + transcript

**`meeting_transcript_policy.py`** uses the [Google AI Studio API](https://aistudio.google.com) (not the gemini.google.com browser). It sends **text only** — best fit for free-tier volume on `gemini-2.5-flash-lite`.

| Step | Cost |
|------|------|
| Speaker hints from `contacts.json` | Free (local scrape cache) |
| YouTube captions | Free (`youtube-transcript-api`) |
| Optional WhisperX diarization | Local GPU/CPU + `HF_TOKEN` |
| Policy JSON | API tokens on transcript text |

### Setup

```bash
pip install -r requirements-gemini-api.txt
# Optional diarization:
# pip install -r requirements-transcript-diarize.txt
# export HF_TOKEN=...   # Hugging Face — pyannote diarization

export GEMINI_API_KEY=...   # https://aistudio.google.com/apikey
export GEMINI_FLASH_LITE_MODEL=gemini-2.5-flash-lite   # optional override
```

### Tuscaloosa: newest YouTube meetings first

**1. Refresh channel catalog in Postgres** (needs `YOUTUBE_API_KEY` in `.env`):

```bash
.venv/bin/python scripts/datasources/youtube/load_youtube_for_jurisdiction.py \
  --jurisdiction-id municipality_0177256 \
  --jurisdiction-name Tuscaloosa \
  --state AL \
  --channel-id UC74dczS0B3MhDhUHp2ZGRPA \
  --max-videos 100 --force
```

Or the Tuscaloosa-specific helper (title filter `committee` / `meeting`):

```bash
.venv/bin/python scripts/datasources/youtube/download_tuscaloosa_city_meeting_audio.py --catalog-only
```

**2. (Optional) Download Opus for WhisperX diarization** — newest `event_date` / `published_at` first:

```bash
.venv/bin/python scripts/datasources/youtube/download_tuscaloosa_city_meeting_audio.py --download-only --limit 5
```

**3. Transcripts / policy from bronze, newest `last_updated` first:**

```bash
# List what would run (no API)
.venv/bin/python scripts/gemini/meeting_transcript_policy.py \
  --from-bronze --jurisdiction-id municipality_0177256 --limit 10 --dry-run

# Captions only — no GEMINI_API_KEY spend
.venv/bin/python scripts/gemini/meeting_transcript_policy.py \
  --from-bronze --jurisdiction-id municipality_0177256 --state AL \
  --limit 10 --transcript-only

# Captions + speaker hints + Flash-Lite policy JSON
.venv/bin/python scripts/gemini/meeting_transcript_policy.py \
  --from-bronze --jurisdiction-id municipality_0177256 --state AL --limit 3

# Same batch + WhisperX when Opus exists on disk
.venv/bin/python scripts/gemini/meeting_transcript_policy.py \
  --from-bronze --jurisdiction-id municipality_0177256 --state AL \
  --limit 3 --diarize
```

Single video:

```bash
.venv/bin/python scripts/gemini/meeting_transcript_policy.py \
  --video-id ajsME66iXbY \
  --jurisdiction-id municipality_0177256 \
  --state AL
```

Outputs: `data/cache/gemini_transcript_policy/<jurisdiction_id>/` (`*_analysis.json`, `*_transcript.json`, `*_meta.json`, `_manifest.json`).

### Expensive path (avoid for bulk)

**`browser_policy_analysis.py`** — headed Chrome on gemini.google.com, often **Gemini 3.1 Pro + YouTube video** in the UI. Different quota and much higher cost than API Flash-Lite on text.
