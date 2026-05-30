---
sidebar_position: 6
---

# Terminal Corruption Prevention

## What Happened

Terminal pagers (like `less`, `more`) use an "alternate screen buffer" that can get corrupted, causing command output to be written as files in your current directory. This is compounded when you're in the wrong directory (like `frontend/`).

## Symptoms

Random files appearing with names like:
- `= f.readlines()`
- `245 fluoride bills across all 50 states (was only 5 states)`
- `lativesession s ON b.legislative_session_id = s.id`

These are fragments of command output or SQL queries.

## Immediate Fix

**1. Clean up garbage files:**
```bash
bash scripts/cleanup_frontend_junk.sh
```

**2. Reset your terminal:**
```bash
reset
cd /home/developer/projects/open-navigator
```

## Prevention (CRITICAL)

**Add to your `~/.bashrc` or `~/.zshrc`:**
```bash
# Prevent pager corruption
export PAGER=cat
export GIT_PAGER=cat
export PSQL_PAGER=
export SYSTEMD_PAGER=cat

# Git config
git config --global core.pager cat
```

**Then reload your shell:**
```bash
source ~/.bashrc  # or source ~/.zshrc
```

## Best Practices

1. **Always check your working directory:**
   ```bash
   pwd  # Before running commands
   ```

2. **Run commands from project root:**
   ```bash
   cd /home/developer/projects/open-navigator
   # NOT from frontend/, api/, etc.
   ```

3. **Use `--no-pager` flags:**
   ```bash
   git log --no-pager
   psql --no-pager
   ```

4. **If terminal gets corrupted:**
   ```bash
   reset && stty sane
   ```

## Scripts Created

- ✅ `scripts/cleanup_frontend_junk.sh` - Cleanup script
- ✅ `scripts/prevent_terminal_corruption.sh` - Prevention config  
- ✅ `frontend/.gitignore` - Updated to ignore garbage files

## Why This Happens

1. **Alternate screen buffer** - Commands like `less`, `more`, `git log`, `psql` output
2. **Terminal state corruption** - Buffer doesn't close properly
3. **Wrong working directory** - Commands run from `frontend/` instead of project root
4. **Output redirection** - Corrupted state writes output as files

## One-Time Setup

Run this once:
```bash
source scripts/prevent_terminal_corruption.sh
```

Add to your shell profile permanently:
```bash
echo 'export PAGER=cat' >> ~/.bashrc
echo 'export GIT_PAGER=cat' >> ~/.bashrc
source ~/.bashrc
```
