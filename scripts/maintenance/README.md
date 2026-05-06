# Maintenance Scripts

System maintenance, cleanup, and development utilities.

## Cleanup Scripts

### cleanup_disk_space.sh
Frees up disk space by removing temporary files and caches.

**Usage:**
```bash
./scripts/maintenance/cleanup_disk_space.sh
```

**What it removes:**
- Docker images and containers
- Python cache files
- Node.js cache
- Temporary build artifacts

**⚠️ Does NOT remove:**
- Application data cache (`data/cache/`)
- Database files
- Important project data

### cleanup_frontend_junk.sh
Removes frontend build artifacts and dependencies.

**Usage:**
```bash
./scripts/maintenance/cleanup_frontend_junk.sh
```

### docker-cleanup.sh
Docker-specific cleanup (removes unused images, containers, volumes).

**Usage:**
```bash
./scripts/maintenance/docker-cleanup.sh
```

**What it cleans:**
- Stopped containers
- Unused images
- Dangling volumes
- Unused networks

## Project Maintenance

### clear_notebook_outputs.py
**🔒 Security:** Clears cell outputs from Jupyter notebooks to prevent sensitive data leaks.

**Usage:**
```bash
# Clear specific notebooks
python scripts/maintenance/clear_notebook_outputs.py path/to/notebook.ipynb

# Clear all notebooks in scripts/datasources/
python scripts/maintenance/clear_notebook_outputs.py
```

**Why this matters:**
- ✅ Prevents database credentials from being committed
- ✅ Removes API keys from cell outputs
- ✅ Cleans file paths that might contain usernames
- ✅ Removes execution counts (cleaner diffs)

**When to use:**
- Before committing Colab notebooks
- After running notebooks with sensitive data
- When notebook outputs contain database URLs

**Automatic protection:**
- Pre-push hook checks for outputs in staged notebooks
- Blocks commits if outputs detected
- Reminds you to clear outputs before pushing

**Example:**
```bash
# Edit notebook in Colab, run cells with secrets
# Before committing:
python scripts/maintenance/clear_notebook_outputs.py \
  scripts/datasources/youtube/load_youtube_events_colab.ipynb

git add scripts/datasources/youtube/load_youtube_events_colab.ipynb
git commit -m "Update YouTube loading notebook"
git push  # Pre-push hook automatically checks for outputs
```

### migrate-docs.sh
Migrates documentation from project root to website/docs/ (Docusaurus format).

**Usage:**
```bash
./scripts/maintenance/migrate-docs.sh
```

**What it does:**
- Moves .md files from root to website/docs/
- Adds YAML frontmatter
- Converts filenames to kebab-case

## System Utilities

### prevent_terminal_corruption.sh
Prevents terminal corruption from Unicode characters.

**Usage:**
```bash
source scripts/maintenance/prevent_terminal_corruption.sh
```

### move_secrets_to_home.sh
Moves secrets to home directory for security.

**Usage:**
```bash
./scripts/maintenance/move_secrets_to_home.sh
```

## Development

### test-app.py
Quick test script for application functionality.

**Usage:**
```bash
python scripts/maintenance/test-app.py
```
