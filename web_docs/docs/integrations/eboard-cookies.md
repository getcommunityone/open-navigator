# eBoard Cookie Extraction Guide

## Quick Start (10 Minutes)

This guide shows you how to bypass Incapsula bot protection using **manual session cookies**. This is the fastest no-cost workaround to scrape Tuscaloosa school district data.

---

## Step 1: Export Cookies from Your Browser

### Option A: Using EditThisCookie Extension (Recommended)

1. **Install Extension:**
   - Chrome: https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg
   - Edge: https://microsoftedge.microsoft.com/addons/detail/editthiscookie/ajfboaconbpkglpfanbmlfgojgndmhmc

2. **Visit eBoard Site:**
   ```
   https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=2088
   ```

3. **Solve Any CAPTCHA:**
   - Wait for "Verifying you are human" screen to complete
   - Click around the page (view a few meetings) to ensure cookies are fully populated

4. **Export Cookies:**
   - Click the EditThisCookie icon in your browser
   - Click the "Export" button (looks like a download icon)
   - Cookies are copied to clipboard

5. **Save to File:**
   ```bash
   cd /home/developer/projects/open-navigator
   nano eboard_cookies.json
   ```
   - Paste the copied cookies
   - Save and exit (Ctrl+X, then Y, then Enter)

### Option B: Using Browser DevTools (Manual)

1. **Visit eBoard Site:**
   ```
   https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=2088
   ```

2. **Open DevTools:**
   - Press F12
   - Go to **Application** tab (Chrome) or **Storage** tab (Firefox)
   - Click **Cookies** → `https://simbli.eboardsolutions.com`

3. **Find Key Cookies:**
   Look for these cookie names (the numbers will vary):
   - `incap_ses_XXXXX_2088`
   - `visid_incap_XXXXX_2088`
   - `nlbi_XXXXX`

4. **Create JSON File:**
   ```bash
   cd /home/developer/projects/open-navigator
   nano eboard_cookies.json
   ```

5. **Format as JSON:**
   ```json
   [
     {
       "name": "incap_ses_7050_2088",
       "value": "YOUR_ACTUAL_VALUE_FROM_BROWSER",
       "domain": ".eboardsolutions.com",
       "path": "/"
     },
     {
       "name": "visid_incap_2227783",
       "value": "YOUR_ACTUAL_VALUE_FROM_BROWSER",
       "domain": ".eboardsolutions.com",
       "path": "/"
     },
     {
       "name": "nlbi_2227783",
       "value": "YOUR_ACTUAL_VALUE_FROM_BROWSER",
       "domain": ".eboardsolutions.com",
       "path": "/"
     }
   ]
   ```

---

## Step 2: Verify Cookie File

```bash
cd /home/developer/projects/open-navigator

# Check file exists
ls -la eboard_cookies.json

# Verify JSON format
python -c "import json; print(f'Loaded {len(json.load(open(\"eboard_cookies.json\")))} cookies')"
```

Should output: `Loaded 3 cookies` (or however many you exported)

---

## Step 3: Run the Scraper

The scraper will automatically detect and use `eboard_cookies.json`:

### Tuscaloosa City Schools
```bash
source .venv/bin/activate

python main.py scrape \
  --state AL \
  --municipality "Tuscaloosa City Schools" \
  --url http://simbli.eboardsolutions.com/index.aspx?s=2088 \
  --platform eboard \
  --max-events 0 \
  --start-year 0 \
  --no-include-social
```

### Tuscaloosa County Schools
```bash
python main.py scrape \
  --state AL \
  --municipality "Tuscaloosa County Schools" \
  --url http://simbli.eboardsolutions.com/index.aspx?s=2092 \
  --platform eboard \
  --max-events 0 \
  --start-year 0 \
  --no-include-social
```

---

## Expected Output

### Without Cookies (Blocked):
```
INFO     | agents.scraper:_scrape_eboard - No cookie file found
INFO     | agents.scraper:_scrape_eboard - Loading Meeting Listing page...
ERROR    | agents.scraper:_scrape_eboard - Still blocked by Incapsula (964 bytes)
```

### With Cookies (Success):
```
SUCCESS  | agents.scraper:_scrape_eboard - ✓ Loaded 3 cookies from eboard_cookies.json
SUCCESS  | agents.scraper:_scrape_eboard - ✓ Cookies injected into browser session
SUCCESS  | agents.scraper:_scrape_eboard - ✓ Bypassed Incapsula! Got 246327 bytes
INFO     | agents.scraper:_scrape_eboard - Found 47 meeting/document links
```

---

## Troubleshooting

### Problem: "Still blocked by Incapsula"

**Cause:** Cookies expired or User-Agent mismatch

**Solution:**
1. Re-export cookies (they expire every few hours)
2. Ensure you're using the same browser as cookie export:
   - If you exported from **Chrome 123**, the script uses Chrome 123 UA ✓
   - If you exported from **Firefox**, you need to update the User-Agent in the code

### Problem: "Found 0 meeting links"

**Cause:** Page structure changed or still being challenged

**Solution:**
1. Check if cookies are still valid (re-export)
2. Try visiting the site manually first, then immediately run scraper
3. Increase wait time in script (already randomized 5-7 seconds)

### Problem: "Cookies expired after 10 meetings"

**Cause:** Incapsula's "Advanced Mode" detected automated pattern

**Solution:**
- Scraper already implements:
  - ✅ Randomized delays (3-7 seconds between requests)
  - ✅ Mouse movements to simulate human behavior
  - ✅ Varied User-Agent fingerprinting
  
- If still detected, try:
  1. Reduce number of meetings (`--max-events 25`)
  2. Run multiple smaller batches instead of one large batch
  3. Wait 10-15 minutes between batches

---

## Cookie Lifespan

- **Typical Duration:** 2-4 hours
- **Activity Extension:** Each page view extends expiration
- **Re-export Needed:** When scraper gets blocked again

**Pro Tip:** For daily scraping, just re-export cookies each morning before running the scraper.

---

## Security Notes

- **Keep cookies private:** They grant access to the site as "you"
- **Single machine:** Don't share cookies between different IP addresses
- **Browser match:** Use same browser for export and scraping
- **.gitignore:** The file `eboard_cookies.json` is already in `.gitignore` (won't be committed)

---

## Advanced: Multiple School Districts

To scrape both Tuscaloosa City and County schools:

```bash
# 1. Export cookies while visiting EITHER school's site
#    (cookies work for all eboardsolutions.com sites)

# 2. Scrape City Schools
python main.py scrape --platform eboard \
  --url http://simbli.eboardsolutions.com/index.aspx?s=2088 \
  --municipality "Tuscaloosa City Schools" --state AL

# Wait 30 seconds (let cookies settle)
sleep 30

# 3. Scrape County Schools (same cookies)
python main.py scrape --platform eboard \
  --url http://simbli.eboardsolutions.com/index.aspx?s=2092 \
  --municipality "Tuscaloosa County Schools" --state AL
```

---

## Success Metrics

You'll know it's working when you see:
- ✅ `Bypassed Incapsula! Got 200000+ bytes`
- ✅ `Found XX meeting/document links` (where XX > 0)
- ✅ `✓ Scraped PDF: ...` (individual documents being downloaded)

Typical results for Tuscaloosa:
- **City Schools (S=2088):** 30-50 meetings
- **County Schools (S=2092):** 40-60 meetings
