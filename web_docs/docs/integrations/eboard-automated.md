# Automated eBoard Scraping Solutions

This guide covers **fully automated** solutions to bypass Incapsula protection without manual cookie extraction.

---

## Summary of Options

| Solution | Cost | Difficulty | Success Rate | Speed |
|----------|------|------------|--------------|-------|
| **1. Undetected ChromeDriver** | Free | Easy | 70-85% | Medium |
| **2. Playwright + Residential Proxies** | $10-50/month | Medium | 90-95% | Fast |
| **3. Browser Automation Services** | $30-100/month | Easy | 95-99% | Fast |
| **4. Captcha Solving Service** | $1-3/1000 solves | Medium | 85-90% | Slow |

---

## Option 1: Undetected ChromeDriver (Recommended for Free Solution)

### Why It Works
`undetected-chromedriver` patches Selenium to bypass bot detection:
- Removes `navigator.webdriver` flag
- Uses real Chrome binary (not ChromeDriver)
- Randomizes browser fingerprints
- Avoids common detection patterns

### Installation

```bash
source .venv/bin/activate
pip install undetected-chromedriver
```

### Usage

```python
# Run the new scraper
python agents/scraper_undetected.py
```

Or integrate into main scraper:

```bash
python main.py scrape \
  --state AL \
  --municipality "Tuscaloosa City Schools" \
  --url http://simbli.eboardsolutions.com/index.aspx?s=2088 \
  --platform eboard \
  --use-undetected \
  --max-events 0
```

### Pros
- ✅ Free
- ✅ No external services required
- ✅ Works for most Incapsula sites
- ✅ Easy to implement

### Cons
- ❌ May still fail on very strict Incapsula settings
- ❌ Requires GUI environment (can't run headless on some systems)
- ❌ Slower than Playwright

---

## Option 2: Residential Proxies (Best Success Rate)

### Why It Works
Incapsula detects datacenter IPs. Residential proxies route through real home IPs that appear legitimate.

### Recommended Providers

**BrightData (formerly Luminati)**
- Cost: ~$15/GB or $500/month unlimited
- Success rate: 95%+
- Rotating residential IPs
- https://brightdata.com

**SmartProxy**
- Cost: $75/month for 5GB
- Easy to use
- Good for small projects
- https://smartproxy.com

**Oxylabs**
- Cost: $15/GB
- Enterprise-grade
- https://oxylabs.io

### Implementation

```python
# Install
pip install playwright

# Configure proxy in scraper
async with async_playwright() as p:
    browser = await p.chromium.launch(
        proxy={
            'server': 'http://proxy.smartproxy.com:10000',
            'username': 'your_username',
            'password': 'your_password'
        }
    )
    # ... rest of scraping code
```

### Add to agents/scraper.py

```python
# In _scrape_eboard method, add:
import os

proxy_config = None
if os.getenv('RESIDENTIAL_PROXY_URL'):
    proxy_config = {
        'server': os.getenv('RESIDENTIAL_PROXY_URL'),
        'username': os.getenv('PROXY_USERNAME'),
        'password': os.getenv('PROXY_PASSWORD')
    }

browser = await p.chromium.launch(
    proxy=proxy_config,
    headless=True
)
```

### .env Configuration

```bash
# Add to .env file
RESIDENTIAL_PROXY_URL=http://proxy.smartproxy.com:10000
PROXY_USERNAME=your_username
PROXY_PASSWORD=your_password
```

### Pros
- ✅ Highest success rate (95%+)
- ✅ Works on any Incapsula configuration
- ✅ Can run headless
- ✅ Fast and reliable

### Cons
- ❌ Costs money ($10-50/month for small projects)
- ❌ Requires account setup
- ❌ May have usage limits

---

## Option 3: Browser Automation Services (Easiest)

### Why It Works
These services run real browsers in the cloud and handle all anti-bot evasion automatically.

### Recommended Services

**Browserless.io**
- Cost: $40/month for 20 hours
- Managed Playwright/Puppeteer
- Built-in proxy rotation
- https://browserless.io

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.connect(
        'wss://chrome.browserless.io?token=YOUR_TOKEN'
    )
    page = await browser.new_page()
    await page.goto('https://simbli.eboardsolutions.com/...')
```

**ScrapingBee**
- Cost: $49/month for 100k credits
- Handles all anti-bot automatically
- Simple REST API
- https://scrapingbee.com

```python
import requests

response = requests.get(
    'https://app.scrapingbee.com/api/v1/',
    params={
        'api_key': 'YOUR_API_KEY',
        'url': 'https://simbli.eboardsolutions.com/...',
        'render_js': 'true',
        'premium_proxy': 'true'
    }
)
content = response.text
```

**Apify**
- Cost: $49/month
- Pre-built scrapers for common sites
- Can create custom scrapers
- https://apify.com

### Pros
- ✅ Fully managed (no maintenance)
- ✅ Very high success rate
- ✅ Handles updates to anti-bot automatically
- ✅ Can scale easily

### Cons
- ❌ Most expensive option
- ❌ Requires external service dependency
- ❌ May have rate limits

---

## Option 4: Captcha Solving Service

### Why It Works
If Incapsula shows a CAPTCHA, these services solve it automatically using AI or human workers.

### Recommended Services

**2Captcha**
- Cost: $2.99 per 1000 CAPTCHAs
- Supports reCAPTCHA, hCaptcha, Incapsula
- https://2captcha.com

**Anti-Captcha**
- Cost: $2 per 1000 CAPTCHAs
- Fast (10-30 seconds)
- https://anti-captcha.com

### Implementation

```bash
pip install 2captcha-python
```

```python
from twocaptcha import TwoCaptcha
import os

solver = TwoCaptcha(os.getenv('2CAPTCHA_API_KEY'))

# When Incapsula shows CAPTCHA
try:
    result = solver.recaptcha(
        sitekey='SITE_KEY_FROM_PAGE',
        url='https://simbli.eboardsolutions.com/...'
    )
    
    # Inject solution into page
    await page.evaluate(f'document.getElementById("g-recaptcha-response").innerHTML="{result["code"]}";')
    await page.click('button[type="submit"]')
    
except Exception as e:
    logger.error(f"CAPTCHA solving failed: {e}")
```

### Pros
- ✅ Solves CAPTCHAs automatically
- ✅ Relatively cheap
- ✅ Works with existing scraper

### Cons
- ❌ Only useful if CAPTCHA appears
- ❌ Slower (10-30 seconds per solve)
- ❌ Not 100% success rate
- ❌ Costs money per use

---

## Option 5: Reverse Engineer the API

### Why It Works
eBoard likely has backend APIs that mobile apps or internal tools use. These APIs may have weaker protection.

### How to Find APIs

1. **Use browser DevTools**:
   ```bash
   # Open eBoard site in Chrome
   # Press F12 → Network tab
   # Look for XHR/Fetch requests
   # Check requests to:
   #   - /api/
   #   - .ashx files
   #   - .asmx files (SOAP endpoints)
   ```

2. **Check for mobile app**:
   - Search App Store / Google Play for "eBoard Solutions"
   - Decompile APK to find API endpoints
   - Use mitmproxy to intercept app traffic

3. **Look for GraphQL/REST endpoints**:
   ```bash
   curl -I https://simbli.eboardsolutions.com/api/meetings
   curl -I https://simbli.eboardsolutions.com/graphql
   ```

### Example (if API exists)

```python
import httpx

# Hypothetical API endpoint
async with httpx.AsyncClient() as client:
    response = await client.get(
        'https://simbli.eboardsolutions.com/api/v1/meetings',
        params={'school_id': 2088},
        headers={'User-Agent': 'eBoard-Mobile/1.0'}
    )
    meetings = response.json()
```

### Pros
- ✅ Fastest option
- ✅ No bot detection
- ✅ Free
- ✅ Most reliable

### Cons
- ❌ Requires reverse engineering skills
- ❌ API may not exist
- ❌ API may require authentication
- ❌ May violate Terms of Service

---

## Recommended Approach

### For Personal/Research Projects (Free)
**Start with Option 1 (Undetected ChromeDriver)**

```bash
# Install
pip install undetected-chromedriver

# Run test
python agents/scraper_undetected.py
```

If that fails, use **manual cookies** (current approach) as fallback.

### For Production/Reliable Scraping ($)
**Use Option 2 (Residential Proxies)**

Budget: ~$15-75/month depending on volume

Best provider for this use case: **SmartProxy** ($75/month for 5GB)

```bash
# Sign up at smartproxy.com
# Add credentials to .env
# Enable proxy in scraper

RESIDENTIAL_PROXY_URL=http://proxy.smartproxy.com:10000
PROXY_USERNAME=your_username
PROXY_PASSWORD=your_password
```

### For Large Scale / Enterprise
**Use Option 3 (Browserless.io or ScrapingBee)**

Budget: $40-100/month

Most reliable, fully managed solution.

---

## Implementation Plan

### Phase 1: Try Free Options
1. ✅ Install undetected-chromedriver
2. ✅ Test on Tuscaloosa City Schools
3. ✅ Measure success rate over 10 runs
4. If success rate > 80%, use this going forward

### Phase 2: Add Proxy Support (If Phase 1 Fails)
1. Add proxy configuration to existing Playwright scraper
2. Sign up for SmartProxy trial
3. Test with residential proxy
4. If successful, add to production

### Phase 3: Optimize
1. Add retry logic with exponential backoff
2. Rotate between different methods
3. Cache successful cookies for reuse
4. Monitor success rate and adjust

---

## Next Steps

Would you like me to:

1. **Integrate undetected-chromedriver into the main scraper** (1-click solution)
2. **Add residential proxy support** to existing code (requires proxy account)
3. **Try to reverse engineer the eBoard API** (advanced, may take time)
4. **Create a hybrid approach** that tries multiple methods automatically

Let me know which direction you'd prefer!
