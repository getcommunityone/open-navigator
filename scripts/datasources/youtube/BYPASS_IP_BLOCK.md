# Bypassing YouTube IP Blocks

If you're getting `IpBlocked` or rate limited when fetching YouTube transcripts, you have two options:

## Option 1: Use Browser Cookies (Recommended - Easier)

YouTube is more lenient with authenticated (logged-in) users. Export your browser cookies and use them with the script.

### Step 1: Install Browser Extension

**Chrome/Edge:**
- Install: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)

**Firefox:**
- Install: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

### Step 2: Export YouTube Cookies

1. Go to https://www.youtube.com in your browser
2. **Make sure you're logged in** to your YouTube/Google account
3. Click the extension icon
4. Click "Export" or "Get cookies.txt"
5. Save as `youtube_cookies.txt`

### Step 3: Use Cookies with Script

```bash
source .venv/bin/activate

# Load videos with cookies for authentication
python scripts/datasources/youtube/load_youtube_events_to_postgres.py \
  --states AL,GA,IN,MA,WA,WI \
  --max-videos 50 \
  --cookies youtube_cookies.txt \
  --transcript-delay 3.0
```

### Why This Helps

- YouTube allows **10,000+ transcript requests per day** for logged-in users
- Only **100-1,000 requests per day** for anonymous users
- Cookies make you appear as a logged-in user = higher limits

## Option 2: Use a Proxy (Advanced)

Route requests through a different IP address to bypass the block on your current IP.

### Using a Free Proxy

```bash
# Find a free proxy: https://free-proxy-list.net/
# Example:
python scripts/datasources/youtube/load_youtube_events_to_postgres.py \
  --states MA \
  --max-videos 10 \
  --proxy "http://123.45.67.89:8080"
```

### Using a Commercial Proxy Service

```bash
# Paid services like:
# - BrightData: https://brightdata.com
# - Oxylabs: https://oxylabs.io
# - SmartProxy: https://smartproxy.com

python scripts/datasources/youtube/load_youtube_events_to_postgres.py \
  --states AL,GA,IN,MA,WA,WI \
  --max-videos 100 \
  --proxy "http://username:password@proxy.provider.com:8080" \
  --transcript-delay 2.0
```

### Why This Helps

- Your IP is blocked, but a different IP is not
- Commercial proxies rotate IPs automatically
- Can be expensive ($50-500/month for good service)

## Option 3: Combine Both (Most Reliable)

Use cookies AND proxy together for best results:

```bash
python scripts/datasources/youtube/load_youtube_events_to_postgres.py \
  --states AL,GA,IN,MA,WA,WI \
  --max-videos 100 \
  --cookies youtube_cookies.txt \
  --proxy "http://username:password@proxy.com:8080" \
  --transcript-delay 2.0
```

## Option 4: Wait for IP Block to Expire (Free)

If you don't want to use cookies or proxies:

1. **Wait 24-48 hours** - IP blocks usually expire
2. Load videos WITHOUT transcripts now:
   ```bash
   python scripts/datasources/youtube/load_youtube_events_to_postgres.py \
     --states AL,GA,IN,MA,WA,WI \
     --max-videos 100 \
     --skip-transcripts
   ```
3. After IP block expires, backfill transcripts:
   ```bash
   python scripts/datasources/youtube/backfill_transcripts.py \
     --states AL,GA,IN,MA,WA,WI \
     --limit 1000
   ```

## Reducing API Calls to Avoid Blocks

If you want to minimize requests to YouTube:

```bash
# Disable yt-dlp fallback (fewer requests)
python scripts/datasources/youtube/load_youtube_events_to_postgres.py \
  --states MA \
  --max-videos 20 \
  --no-ytdlp-fallback \
  --transcript-delay 5.0
```

## Testing

Test with a small batch first:

```bash
# Test with cookies
python scripts/datasources/youtube/load_youtube_events_to_postgres.py \
  --states MA \
  --max-videos 5 \
  --cookies youtube_cookies.txt \
  --transcript-delay 3.0

# Check if transcripts were fetched
PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator -c "
SELECT COUNT(*) as transcript_count FROM events_text_search;
"
```

## Troubleshooting

**Cookies not working?**
- Make sure you're logged into YouTube before exporting
- Cookies expire - re-export if it's been a few days
- Try incognito mode, log in fresh, then export cookies

**Proxy not working?**
- Test the proxy with: `curl --proxy "http://proxy:port" https://www.youtube.com`
- Free proxies are often unreliable - try a different one
- Check if proxy requires authentication (username:password)

**Still getting blocked?**
- Increase `--transcript-delay` to 5-10 seconds
- Use `--no-ytdlp-fallback` to reduce total requests
- Consider commercial proxy service with rotating IPs

## Batch job dashboard

Priority-state runs (`run_priority_states_last_n.sh`) record progress under `data/cache/batch_jobs/`.

```bash
./scripts/datasources/youtube/run_priority_states_last_n.sh captions

# Another terminal — rebuild and open HTML dashboard:
.venv/bin/python scripts/datasources/youtube/batch_job_dashboard.py --build --open

# Or serve (re-run --build to refresh):
.venv/bin/python scripts/datasources/youtube/batch_job_dashboard.py --serve
```

Shows batches with processed / failed / remaining jurisdictions, elapsed time, ETA, video outcomes, and policy-cache file counts. Click a jurisdiction to drill down to per-video rows.

Disable: `BATCH_STATUS=0 ./scripts/datasources/youtube/run_priority_states_last_n.sh captions`
