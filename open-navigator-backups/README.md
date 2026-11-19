# Local Postgres dump landing (not in git)

Large `make backup` / `make restore` dumps land here, then go to Google Drive.
Contents are gitignored (`open-navigator-backups/**`).

**Do not replace this directory with a symlink to an unmounted Drive path.**
When the mount is missing, pytest collection of the repo root raises
`OSError: [Errno 19] No such device` (#612). Prefer a bind mount into this
directory when Drive is available, or copy dumps out after the run.
