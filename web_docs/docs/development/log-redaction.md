---
title: Keeping keys out of logs
description: How API keys and tokens are kept out of log lines, what is covered, what is not, and what to do when a key has leaked.
---

# Keeping keys out of logs (#878)

Client libraries put credentials in the request URL. The YouTube Data API sends its key as `?key=…`, and when a call
fails, the error message quotes the whole URL. Logging that error wrote the key into
`data/cache/batch_jobs/launch_catalog_*.log`.

## What does it

`packages/core-lib/src/core_lib/redact.py`:

- `redact_secrets(text)` replaces credentials with `***` and keeps the rest of the line. It covers credential
  parameters (`key=`, `api_key=`, `access_token=`, `token=`, `client_secret=`, `password=`), authorization headers
  and bearer tokens, recognisable key shapes (Google `AIza…`, `sk-…`, `hf_…`, GitHub tokens), and the value of any
  environment variable named like a credential (`…_KEY`, `…_TOKEN`, `…_SECRET`, `…PASSWORD`) that is at least twelve
  characters long.
- `install_log_redaction()` applies it to every loguru message in the process, whatever sinks are added later.

It is installed by `configure_youtube_loader_logging` (the YouTube loaders), by `scrape_youtube_channels` and by
`core_lib.logging.setup_logging`. The channel scraper's error line also redacts the error text directly.

## Adding it to a new entry point

```python
from core_lib.redact import install_log_redaction

def main() -> None:
    install_log_redaction()
    ...
```

## What is not covered

- **Output that does not go through loguru.** A library that prints or uses the standard `logging` module writes
  straight to the batch log. If you see a key in a line without the loguru format, wrap that call's error text in
  `redact_secrets`.
- **Tracebacks.** `logger.exception` renders the traceback separately from the message. Where an error's text can
  carry a URL, log it with `logger.error` and the error's text.
- **Log files written before this change.** They are not rewritten.
- **The log tail shown in the batch tab.** It shows the file as it is.

## When a key has leaked

1. Rotate it at the provider. For the YouTube Data API: Google Cloud Console, APIs and Services, Credentials.
2. Put the new key in `.env` and restart the services.
3. Treat the old log files as sensitive: delete them or keep them private. Find them with:

   ```bash
   grep -rl "key=AIza" data/cache/batch_jobs/ logs/ 2>/dev/null
   ```

4. If the key was pasted anywhere outside the machine, rotating is the only fix.
