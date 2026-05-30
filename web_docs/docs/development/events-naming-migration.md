---
sidebar_position: 3
---

# File Migration to Events Naming Convention

This guide shows how to use the migration script to rename old meeting/contact files to the new events_ naming convention.

## Quick Start

```bash
# 1. Dry run to see what would be renamed (safe, no changes)
python scripts/migrate_to_events_naming.py --dry-run

# 2. Perform the migration WITH backups (recommended)
python scripts/migrate_to_events_naming.py

# 3. Skip backups if you already have external backups
python scripts/migrate_to_events_naming.py --no-backup

# 4. Clean up backup directories after verifying migration
python scripts/migrate_to_events_naming.py --cleanup-backups
```

## Migration Map

The script automatically renames:

| Old Name | New Name |
|----------|----------|
| `meetings.parquet` | `events.parquet` |
| `meetings_calendar.parquet` | `events.parquet` |
| `meetings_transcripts.parquet` | `events_documents.parquet` |
| `meetings_topics.parquet` | `event_agenda_items.parquet` |
| `meetings_demographics.parquet` | `events_participants.parquet` |
| `meetings_decisions.parquet` | `event_bills.parquet` |
| `contacts_meeting_attendance.parquet` | `events_participants.parquet` |
| `events_events.parquet` | `events.parquet` |
| `events_event_documents.parquet` | `events_documents.parquet` |
| `events_participants.parquet` | `events_participants.parquet` |
| `events_event_agenda_items.parquet` | `event_agenda_items.parquet` |
| `events_event_bills.parquet` | `event_bills.parquet` |
| `events_event_media.parquet` | `event_media.parquet` |

## Options

### `--dry-run`
Show what would be renamed without making changes:
```bash
python scripts/migrate_to_events_naming.py --dry-run
```

### `--no-backup`
Skip creating backups (NOT recommended unless you have external backups):
```bash
python scripts/migrate_to_events_naming.py --no-backup
```

### `--cleanup-backups`
Remove all `.migration_backup/` directories after verifying the migration:
```bash
# Dry run to see what would be deleted
python scripts/migrate_to_events_naming.py --cleanup-backups --dry-run

# Actually delete backups (will prompt for confirmation)
python scripts/migrate_to_events_naming.py --cleanup-backups
```

### `--directory`
Specify a different directory to scan (default: `data/gold`):
```bash
python scripts/migrate_to_events_naming.py --directory data/gold/states/AL
```

## Safe Migration Process

1. **Verify current files:**
   ```bash
   find data/gold -name "*.parquet" -type f | sort
   ```

2. **Run dry-run to preview changes:**
   ```bash
   python scripts/migrate_to_events_naming.py --dry-run
   ```

3. **Perform migration with backups:**
   ```bash
   python scripts/migrate_to_events_naming.py
   ```
   This creates backups in `.migration_backup/` directories (automatically gitignored).

4. **Verify the migration worked:**
   ```bash
   # Check new files exist
   find data/gold -name "events_*.parquet" -type f | sort
   
   # Check the API still works
   cd api && uvicorn main:app --reload
   ```

5. **Clean up backups (after verification):**
   ```bash
   python scripts/migrate_to_events_naming.py --cleanup-backups
   ```

## Backup Location

Backups are stored in `.migration_backup/` directories next to the original files:
```
data/gold/states/AL/
├── events_events.parquet          # New file
└── .migration_backup/
    └── meetings_20260429_153022.parquet  # Backup with timestamp
```

These directories are automatically ignored by git (see `.gitignore`).

## Troubleshooting

### "Target already exists"
If a new-named file already exists, the script will skip that file. You'll need to manually resolve:
```bash
# Option 1: Delete the old file if new one is correct
rm data/gold/states/AL/meetings.parquet

# Option 2: Compare and merge if needed
python -c "import pandas as pd; print(pd.read_parquet('old.parquet').equals(pd.read_parquet('new.parquet')))"
```

### "No files found"
If the script finds no files to rename, either:
- Files are already using new naming ✅
- You're scanning the wrong directory (use `--directory`)
- Files don't match the expected names

## Reverting Migration

If you need to revert (and backups still exist):
```bash
# Restore from backups manually
cd data/gold/states/AL/.migration_backup
for f in *.parquet; do
    original=$(echo $f | sed 's/_[0-9]\{8\}_[0-9]\{6\}//')
    cp "$f" "../$original"
done
```
