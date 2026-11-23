---
sidebar_position: 11
title: Starting and stopping the local app
description: ./start-all.sh clears its ports, starts the API, web app and docs without asking anything, and checks they answer (#787).
---

# Starting and stopping the local app

Issue [#787](https://github.com/getcommunityone/open-navigator/issues/787).

## Run it

```bash
cd ~/projects/open-navigator
./start-all.sh
```

That is the whole procedure. It does the following, in order, and never asks a question:

1. Checks the `.venv` and the `node_modules` folders (installs the Node ones if missing).
2. Frees ports **3000** (docs), **5173** (web app) and **8001** (API). It asks old processes to stop, forces them
   if they ignore that, and waits until each port is really free. If a port stays busy it stops with the PID.
3. Starts the API, the web app and the docs site, in a `tmux` session named `open-navigator` (or as background
   processes when `tmux` is missing or `START_ALL_NO_TMUX=1` is set).
4. Waits up to 90 seconds for `http://localhost:8001/docs` and `http://localhost:5173/` to answer, and prints
   `OK` or `FAILED` for each one, with the last lines of its log when it fails.

It exits `0` only when the API and the web app both answer. The docs site is reported but never fails the run.

## Options

| Option | Effect |
|---|---|
| `--attach` | Attach to the `tmux` session at the end (the old behavior). |
| `--no-docs` | Do not start the documentation site (port 3000). |

## Stop it

```bash
./stop-all.sh
```

## When something fails

- Read the `FAILED` lines: they show the end of `logs/api.log` or `logs/dashboard.log`.
- The web app uses `strictPort`, so it **fails** if 5173 is taken instead of moving to 5174. Google sign-in
  redirects to 5173, so a hop would break login without an error.
- Run it from the folder that has the `.venv`. A second git worktree needs its own `.venv`
  (`./install.sh`), or run from the original folder.
