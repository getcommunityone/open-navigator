# YouTube Channel Sanity Check Workflow

## Overview

**Before loading videos**, always validate and clean channels to avoid scraping junk content.

## Two-Step Process

### Step 1: Load & Validate Channels

```bash
# Load channels and auto-flag junk
python scripts/datasources/youtube/load_channels.py \
  --states AL,GA,IN,MA,WA,WI \
  --auto-flag

# Optional: Validate against WikiData (slower but more accurate)
python scripts/datasources/youtube/load_channels.py \
  --states AL,GA,IN,MA,WA,WI \
  --validate \
  --auto-flag
```

**What this does:**
- ✅ Extracts all channels from `jurisdictions_details_search`
- ✅ Checks if channel exists in LocalView (trusted historical data)
- ✅ Optional: Validates against WikiData for government YouTube channels
- ✅ Auto-flags junk channels (news, entertainment, political figures, etc.)
- ✅ Populates `events_channels_search` table with quality metadata

**Output:**
```
Channels processed: 300
Channels flagged as junk: 27
  Total channels: 229
  In LocalView: 0
  In WikiData: 0 (without --validate flag)
  Flagged as junk: 25
  Confirmed government: 0
```

### Step 2: Load Videos (Skips Flagged Channels)

```bash
# Now load videos - automatically skips flagged channels
python scripts/datasources/youtube/load_youtube_events_to_postgres.py \
  --states AL,GA,IN,MA,WA,WI \
  --max-videos 50 \
  --skip-transcripts
```

**What this does:**
- ✅ Checks `events_channels_search.flagged_as_junk` for each channel
- ✅ Skips channels where `is_government = FALSE`
- ✅ Only loads videos from validated government channels
- ✅ Logs: "Skipping flagged channel: CNN - News channel, not government"

## Channel Quality Tracking

### `events_channels_search` Table

Tracks all YouTube channels with quality metadata:

| Column | Description |
|--------|-------------|
| `channel_id` | YouTube channel ID (unique) |
| `channel_url` | Full YouTube URL |
| `channel_title` | Channel name |
| `channel_type` | municipal, county, state, school, unknown |
| `in_localview` | ✓ Channel exists in LocalView historical data |
| `in_jurisdictions_details` | ✓ Found in jurisdictions_details_search |
| `in_wikidata` | ✓ Validated in WikiData as government channel |
| `on_public_website` | Manual verification from jurisdiction website |
| `is_government` | NULL (unknown), TRUE (confirmed govt), FALSE (confirmed not govt) |
| `flagged_as_junk` | TRUE if auto-flagged as non-government |
| `flag_reason` | Why it was flagged |
| `jurisdictions` | JSONB array of associated jurisdictions |

### Auto-Flagged Patterns

Channels are automatically flagged if they match:

- **News channels:** CNN, Fox News, MSNBC, NBC, ABC, CBS
- **Entertainment:** Last Week Tonight, Daily Show, Hamilton, Broadway
- **Political figures:** Bernie Sanders, Adam Kinzinger, Elizabeth Warren
- **Music:** YouTube "-Topic" channels, VEVO
- **Federal agencies:** USAO, U.S. Attorney (not municipal)

## Manual Review

### View All Channels

```bash
psql -h localhost -p 5433 -U postgres -d open_navigator -c "
  SELECT channel_title, channel_type, in_localview, in_wikidata, 
         flagged_as_junk, flag_reason
  FROM events_channels_search
  ORDER BY flagged_as_junk DESC, channel_type, channel_title
  LIMIT 50;
"
```

### View Only Good Channels

```bash
psql -h localhost -p 5433 -U postgres -d open_navigator -c "
  SELECT channel_title, channel_type, channel_url
  FROM events_channels_search
  WHERE flagged_as_junk = FALSE
    AND (channel_type IN ('municipal', 'county', 'state', 'school') 
         OR is_government = TRUE)
  ORDER BY channel_type, channel_title;
"
```

### View Flagged Channels

```bash
psql -h localhost -p 5433 -U postgres -d open_navigator -c "
  SELECT channel_title, flag_reason, channel_url
  FROM events_channels_search
  WHERE flagged_as_junk = TRUE
  ORDER BY flag_reason;
"
```

### Manually Flag a Channel

```sql
UPDATE events_channels_search
SET flagged_as_junk = TRUE,
    is_government = FALSE,
    flag_reason = 'Personal YouTube channel, not government',
    last_updated = CURRENT_TIMESTAMP
WHERE channel_id = 'UCxxxxxxxxxxxxx';
```

### Manually Approve a Channel

```sql
UPDATE events_channels_search
SET flagged_as_junk = FALSE,
    is_government = TRUE,
    flag_reason = NULL,
    last_updated = CURRENT_TIMESTAMP
WHERE channel_id = 'UCxxxxxxxxxxxxx';
```

## Analysis Tools

### Analyze Channel Quality

```bash
# Show statistics and identify potential junk
python scripts/datasources/youtube/analyze_channels.py

# Show potential junk channels
python scripts/datasources/youtube/analyze_channels.py --show-junk

# Auto-flag junk channels
python scripts/datasources/youtube/analyze_channels.py --flag-junk
```

## Best Practices

1. **Always run channel loader first** before loading videos
2. **Use `--validate` flag** for initial loads to check WikiData
3. **Review flagged channels** manually before large video loads
4. **Re-run channel loader** when adding new jurisdictions
5. **Check `in_localview`** - channels in LocalView are trusted

## Troubleshooting

**Q: Why are some good channels flagged?**
- Review the `flag_reason` and manually approve if needed
- Pattern matching can have false positives

**Q: How do I add a missing channel?**
```sql
INSERT INTO events_channels_search (
    channel_id, channel_url, channel_title, channel_type,
    is_government, discovery_method, jurisdictions
) VALUES (
    'UCxxxxx', 
    'https://www.youtube.com/channel/UCxxxxx',
    'City of Example',
    'municipal',
    TRUE,
    'manual',
    '[{"jurisdiction_id": "12345", "jurisdiction_name": "Example City", "state_code": "AL"}]'::jsonb
);
```

**Q: Videos still loading from junk channels?**
- Check if channel is in `events_channels_search`
- Verify `flagged_as_junk = TRUE`
- Re-run the video loader (it checks DB on each run)

## Data Quality Metrics

After running both steps, check:

```sql
-- Channel quality summary
SELECT 
    COUNT(*) as total_channels,
    COUNT(*) FILTER (WHERE flagged_as_junk = FALSE) as valid_channels,
    COUNT(*) FILTER (WHERE in_localview = TRUE) as in_localview,
    COUNT(*) FILTER (WHERE in_wikidata = TRUE) as in_wikidata,
    COUNT(*) FILTER (WHERE is_government = TRUE) as confirmed_govt
FROM events_channels_search;

-- Events by channel type
SELECT 
    c.channel_type,
    COUNT(DISTINCT c.channel_id) as channels,
    COUNT(e.event_id) as events
FROM events_channels_search c
LEFT JOIN event e ON e.channel_id = c.channel_id
WHERE c.flagged_as_junk = FALSE
GROUP BY c.channel_type
ORDER BY events DESC;
```
