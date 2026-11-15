# Review: PR #334 (closes #332)

**Verdict: approve, pending the Modal rerun.**

- Root cause matches the log: ctranslate2 4.4.0 came from the numpy<2 pin colliding with whisperx 3.8.6 metadata (checked from the PyPI wheel).
- The local `requirements-transcript-diarize.txt` keeps numpy<2 for its own venv. Only the Modal image changes, so local use is untouched.
- `exit_code` is plain and tested, and `main` raises SystemExit(1) after writing usage.jsonl, so failed rows still upload.
- Risk: whisperx 3.8 with pyannote 4 needs the community-1 model accepted on Hugging Face, which the guide already says. `make_diarization_pipeline` handles the `token=` API.
