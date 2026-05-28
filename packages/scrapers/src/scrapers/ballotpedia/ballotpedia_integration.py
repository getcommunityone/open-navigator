"""
Ballotpedia Integration - REFERENCE IMPLEMENTATION ONLY

⚠️ WARNING: Ballotpedia API is a PAID SERVICE
   This code is provided for reference only for those with API access.
   NOT RECOMMENDED for free/open-source projects.

Ballotpedia.org is the definitive source for:
- Elected officials (federal, state, local)
- Ballot measures and initiatives
- Election results and candidates
- Political positions and voting records

PRICING:
- Ballotpedia API v3.0 requires payment (contact for pricing)
- API Docs: https://ballotpedia.org/API_documentation
- Announcement: https://ballotpedia.org/Just_launched:_Ballotpedia's_API_Version_3.0

FREE ALTERNATIVES (RECOMMENDED):
- Google Civic Information API - Free, 25k requests/day
- Open States API - Free, 50k requests/month (state-level)
- NCES - Free public data for school boards

INTEGRATION METHODS (if you have paid API access):
1. **Ballotpedia API v3.0** - Official REST API (REQUIRES PAYMENT)
2. **Web Scraping** - Fallback for public data (rate-limited, respectful)

OFFICIAL API (v3.0):
    from scripts.discovery.ballotpedia_integration import BallotpediaAPI
    
    api = BallotpediaAPI(api_key="your-api-key")
    
    # Get officials for a jurisdiction
    officials = await api.get_officials("Tuscaloosa", "AL")
    
    # Get ballot measures
    measures = await api.get_ballot_measures("Alabama", year=2024)

WEB SCRAPING (Fallback):
    from scripts.discovery.ballotpedia_integration import BallotpediaDiscovery
    
    discovery = BallotpediaDiscovery()
    
    # Search for a specific leader
    leader = await discovery.search_leader("Walt Maddox")

NOTES:
- Ballotpedia API v3.0 launched recently - OFFICIAL API available!
- For production use, get official API key from Ballotpedia
- Web scraping included as fallback for testing/development
- API documentation: https://ballotpedia.org/API_documentation
"""
import asyncio
import re
import random
import os
import json
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import httpx
from bs4 import BeautifulSoup
from loguru import logger

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    from playwright_stealth import stealth_async
    STEALTH_MODE = "legacy"
    PLAYWRIGHT_STEALTH_AVAILABLE = True
except ImportError:
    try:
        from playwright_stealth import Stealth
        STEALTH_MODE = "class"
        PLAYWRIGHT_STEALTH_AVAILABLE = True
    except ImportError:
        STEALTH_MODE = "none"
        PLAYWRIGHT_STEALTH_AVAILABLE = False

try:
    from pyspark.sql import SparkSession, DataFrame
    from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType
    SPARK_AVAILABLE = True
except ImportError:
    SPARK_AVAILABLE = False
    logger.warning("PySpark not available - will save to JSON instead of Delta Lake")

try:
    from config.settings import settings
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False
    settings = None


# ============================================================================
# OFFICIAL BALLOTPEDIA API v3.0 (RECOMMENDED)
# ============================================================================

class BallotpediaAPI:
    """
    Official Ballotpedia API v3.0 client.
    
    API Documentation: https://ballotpedia.org/API_documentation
    Announcement: https://ballotpedia.org/Just_launched:_Ballotpedia's_API_Version_3.0
    
    To get API access:
    1. Visit https://ballotpedia.org/API_documentation
    2. Contact Ballotpedia for API key
    3. Add to .env: BALLOTPEDIA_API_KEY=your-key
    
    This is the RECOMMENDED method for production use.
    """
    
    # API base URL (update when official endpoint is confirmed)
    BASE_URL = "https://api.ballotpedia.org/v3"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Ballotpedia API client.
        
        Args:
            api_key: Ballotpedia API key. If not provided, will try settings.ballotpedia_api_key
        """
        if api_key:
            self.api_key = api_key
        elif SETTINGS_AVAILABLE and hasattr(settings, 'ballotpedia_api_key'):
            self.api_key = settings.ballotpedia_api_key
        else:
            self.api_key = None
            logger.warning("⚠️  BALLOTPEDIA_API_KEY not found")
            logger.warning("   Get API access at: https://ballotpedia.org/API_documentation")
            logger.warning("   Add to .env: BALLOTPEDIA_API_KEY=your-key")
        
        self.cache_dir = Path("data/cache/ballotpedia_api")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def get_officials(
        self,
        jurisdiction: str,
        state: Optional[str] = None,
        office_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Get elected officials using official API.
        
        Args:
            jurisdiction: City/county name
            state: State code or name
            office_type: Filter by office type (e.g., 'mayor', 'council', 'commissioner')
        
        Returns:
            List of official dicts
        """
        if not self.api_key:
            raise ValueError("Ballotpedia API key required. Get one at https://ballotpedia.org/API_documentation")
        
        # NOTE: Actual endpoint structure needs to be confirmed with Ballotpedia API docs
        # This is a placeholder structure based on typical REST API patterns
        
        params = {
            "jurisdiction": jurisdiction,
            "api_key": self.api_key
        }
        
        if state:
            params["state"] = state
        if office_type:
            params["office_type"] = office_type
        
        logger.info(f"Fetching officials via API for {jurisdiction}, {state}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/officials",
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"✅ API returned {len(data.get('officials', []))} officials")
                return data.get('officials', [])
                
            except httpx.HTTPStatusError as e:
                logger.error(f"API error: {e.response.status_code}")
                logger.warning("⚠️  Falling back to web scraping...")
                # Fall back to web scraping
                return []
            except Exception as e:
                logger.error(f"Error calling Ballotpedia API: {e}")
                raise
    
    async def get_ballot_measures(
        self,
        state: str,
        year: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Get ballot measures using official API.
        
        Args:
            state: State name or code
            year: Election year
            status: Filter by status (e.g., 'passed', 'failed', 'upcoming')
        
        Returns:
            List of ballot measure dicts
        """
        if not self.api_key:
            raise ValueError("Ballotpedia API key required")
        
        params = {
            "state": state,
            "api_key": self.api_key
        }
        
        if year:
            params["year"] = year
        if status:
            params["status"] = status
        
        logger.info(f"Fetching ballot measures via API for {state} ({year or 'all years'})")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/ballot-measures",
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"✅ API returned {len(data.get('measures', []))} ballot measures")
                return data.get('measures', [])
                
            except Exception as e:
                logger.error(f"Error calling Ballotpedia API: {e}")
                raise
    
    def save_to_json(self, data: List[Dict], filename: str):
        """Save API data to JSON cache."""
        import json
        
        filepath = self.cache_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"💾 Saved {len(data)} records to {filepath}")


# ============================================================================
# WEB SCRAPING FALLBACK (For testing/development without API key)
# ============================================================================

class BallotpediaDiscovery:
    """
    Discover and fetch data from Ballotpedia.org.
    
    Data Sources:
    - Elected officials (mayors, city council, county commissioners, state legislators)
    - Ballot measures (local, state, federal)
    - Election results
    - Candidates and campaigns
    """
    
    BASE_URL = "https://ballotpedia.org"
    STATE_NAME_BY_CODE = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
        "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
        "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
        "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
        "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
        "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
        "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
        "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
        "DC": "District of Columbia",
    }
    
    def __init__(
        self,
        cache_dir: str = "data/cache/ballotpedia",
        user_agent: str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ):
        """
        Initialize Ballotpedia discovery.
        
        Args:
            cache_dir: Directory for caching responses
            user_agent: User agent for HTTP requests (be respectful!)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent
        self.session = None
        self.max_retries = int(os.getenv("BALLOTPEDIA_HTTP_RETRIES", "4"))
        self.base_backoff_seconds = 2.0
        # Ballotpedia often returns HTTP 202 (Cloudflare async) to httpx; retrying 4× wastes ~30s.
        self.httpx_202_fast_escalate = os.getenv("BALLOTPEDIA_HTTP_202_FAST_ESCALATE", "1").strip().lower() not in {"0", "false", "no"}
        self.use_playwright_fallback = os.getenv("BALLOTPEDIA_USE_PLAYWRIGHT", "1").strip().lower() not in {"0", "false", "no"}
        # Ballotpedia returns HTTP 202 to httpx almost always — default to Playwright directly.
        # Set BALLOTPEDIA_PLAYWRIGHT_ONLY=0 to probe with httpx first (usually wastes time).
        self.playwright_only = os.getenv("BALLOTPEDIA_PLAYWRIGHT_ONLY", "1").strip().lower() not in {"0", "false", "no"}
        self.playwright_timeout_ms = int(os.getenv("BALLOTPEDIA_PLAYWRIGHT_TIMEOUT_MS", "90000"))
        self.inter_request_delay = float(os.getenv("BALLOTPEDIA_INTER_REQUEST_DELAY", "2.0"))
        self.state_scrape_delay = float(os.getenv("BALLOTPEDIA_STATE_DELAY", "10.0"))
        self.playwright_content_retries = int(os.getenv("BALLOTPEDIA_PLAYWRIGHT_CONTENT_RETRIES", "3"))
        # Supported values: new (default), legacy, headed (or false/0/no/off)
        self.playwright_headless_mode = os.getenv("BALLOTPEDIA_PLAYWRIGHT_HEADLESS_MODE", "new").strip().lower()
        if self.playwright_headless_mode in {"0", "false", "no", "off"}:
            self.playwright_headless_mode = "headed"
        # Backward compatibility for existing boolean env var.
        if "BALLOTPEDIA_PLAYWRIGHT_HEADLESS" in os.environ:
            legacy_headless = os.getenv("BALLOTPEDIA_PLAYWRIGHT_HEADLESS", "1").strip().lower() not in {"0", "false", "no"}
            self.playwright_headless_mode = "legacy" if legacy_headless else "headed"
        self.playwright_channel = os.getenv("BALLOTPEDIA_PLAYWRIGHT_CHANNEL", "").strip() or None
        self.debug_verbose = os.getenv("BALLOTPEDIA_DEBUG_VERBOSE", "0").strip().lower() in {"1", "true", "yes"}
        self.playwright_artifact_dir = Path(os.getenv("BALLOTPEDIA_PLAYWRIGHT_ARTIFACT_DIR", "data/cache/ballotpedia/playwright_debug"))
        self.fetch_debug_dir = Path(os.getenv("BALLOTPEDIA_FETCH_DEBUG_DIR", "data/cache/ballotpedia/fetch_debug"))
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._playwright_lock = asyncio.Lock()
        self._playwright_warmed_up = False
        self._last_playwright_error: str | None = None

    # Word-boundary-anchored markers. The substring ``captcha`` previously matched
    # the literal ``recaptcha`` that Ballotpedia loads on every page via Google's
    # reCAPTCHA JS (e.g. ``https://www.gstatic.com/recaptcha/releases/.../recaptcha__en.js``).
    # That false-positive caused real article pages to be classified as challenge pages.
    #
    # The markers are also anchored with ``\b`` so a phrase like ``ad blocker`` in a
    # footer doesn't match if it appears as part of a longer token (it won't, but be safe).
    # ``CHALLENGE_TEXT_ONLY_RE`` strips HTML tags before scanning so script-src attributes,
    # CSS class names, and inline JS don't contribute false positives.
    _CHALLENGE_PATTERNS = (
        re.compile(r"\bchecking your browser\b", re.IGNORECASE),
        re.compile(r"\bplease enable javascript\b", re.IGNORECASE),
        re.compile(r"\bad ?blocker\b", re.IGNORECASE),
        re.compile(r"\baccess denied\b", re.IGNORECASE),
        re.compile(r"(?<![a-z])captcha(?![a-z])", re.IGNORECASE),     # not ``recaptcha`` / ``captchabox``
        re.compile(r"\bsecurity check\b", re.IGNORECASE),
        re.compile(r"\bverify you are human\b", re.IGNORECASE),
        re.compile(r"\bcloudflare\b.*\bray id\b", re.IGNORECASE),
    )
    _TAG_STRIP_RE = re.compile(r"<(?:script|style)[^>]*>.*?</(?:script|style)>", re.IGNORECASE | re.DOTALL)
    _HTML_TAG_RE  = re.compile(r"<[^>]+>")

    @classmethod
    def _visible_text(cls, html: str) -> str:
        """Strip <script>/<style> blocks and HTML tags so attribute values / JS / CSS
        class names don't trigger challenge detection."""
        if not html:
            return ""
        cleaned = cls._TAG_STRIP_RE.sub(" ", html)
        cleaned = cls._HTML_TAG_RE.sub(" ", cleaned)
        return cleaned

    # The MediaWiki content container Ballotpedia uses for the actual article body.
    # The page-shell HTML (header, footer, sidebar, search box, captcha form) is
    # always present and ~70KB even when the article didn't render — so we have to
    # measure the article body itself, not the whole document.
    _ARTICLE_BODY_SELECTORS = ("#mw-content-text", ".mw-parser-output", "#bodyContent")
    _ARTICLE_BODY_MIN_TEXT  = 2_000   # real article bodies are 20KB+ of text; shell-only pages << 1KB

    @classmethod
    def _article_body_text(cls, html: str) -> str:
        if not html:
            return ""
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return ""
        for sel in cls._ARTICLE_BODY_SELECTORS:
            elem = soup.select_one(sel)
            if elem:
                return elem.get_text(" ", strip=True)
        return ""

    @classmethod
    def _is_empty_but_valid_article(cls, html: str) -> bool:
        """True when Ballotpedia returned a real (possibly empty) article shell, not a bot block."""
        if not html:
            return False
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return False
        if soup.select_one(".noarticletext, .mw-empty-article"):
            return True
        title = cls._page_title_from_html(html)
        if not title or "ballotpedia" not in title.lower():
            return False
        if soup.select_one("#firstHeading, .mw-page-title-main, h1.firstHeading"):
            body_len = len(cls._article_body_text(html))
            if body_len < cls._ARTICLE_BODY_MIN_TEXT:
                # Real page title + heading but thin body (empty year page, stub, etc.)
                return True
        return False

    @classmethod
    def _is_challenge_html(cls, html: str) -> bool:
        """
        Detect non-article responses. The MediaWiki shell (header, footer, search box,
        Ballotpedia's correction form with its captcha UI, reCAPTCHA JS, etc.) is
        always present and ~70KB even when the article body itself didn't render.
        So we judge "real article" by the size of the article body, not the page.

        We treat the page as a non-article (i.e. "challenge"-like — caller should
        retry or give up) when:
          * the article body text is < 2,000 chars (shell-only render, was observed
            during high traffic / bot challenges), OR
          * one of the Cloudflare/captcha challenge phrases appears in the visible
            text AND the article body is below the size threshold.

        Real article pages produce 20KB+ of body text and are accepted even if the
        site loads reCAPTCHA JS (which it does on every page for the correction form).
        Empty-but-valid article pages (``noarticletext``, year stubs) are accepted.
        """
        if cls._is_empty_but_valid_article(html):
            return False
        body_text = cls._article_body_text(html)
        if len(body_text) < cls._ARTICLE_BODY_MIN_TEXT:
            return True
        text = cls._visible_text(html)
        # Real article body present; ignore generic captcha/recaptcha noise. Only treat
        # as challenge if a hard interstitial marker appears in the visible page text
        # alongside an unusually small body (handled by the size check above).
        explicit_block = re.compile(
            r"\b(?:attention required|just a moment|access denied|cloudflare\b.*\bray id)\b",
            re.IGNORECASE,
        )
        return bool(explicit_block.search(text))

    @classmethod
    def _challenge_markers_found(cls, html: str) -> List[str]:
        text = cls._visible_text(html)
        return [pat.pattern for pat in cls._CHALLENGE_PATTERNS if pat.search(text)]

    @staticmethod
    def _page_title_from_html(html: str) -> str:
        if not html:
            return ""
        try:
            soup = BeautifulSoup(html, "html.parser")
            title = (soup.title.string if soup.title else "") or ""
            return title.strip()
        except Exception:
            return ""

    def _write_fetch_debug_report(
        self,
        url: str,
        report_type: str,
        status_history: List[Dict],
        error: Optional[str] = None,
        challenge_markers: Optional[List[str]] = None,
        final_page_title: Optional[str] = None,
        playwright_used: bool = False,
        playwright_succeeded: bool = False,
        playwright_artifacts: Optional[List[str]] = None,
    ) -> Optional[Path]:
        try:
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            slug = re.sub(r"[^a-z0-9]+", "_", url.lower()).strip("_")[:120]
            self.fetch_debug_dir.mkdir(parents=True, exist_ok=True)
            report_path = self.fetch_debug_dir / f"{slug}_{ts}_{report_type}.json"
            payload = {
                "timestamp_utc": ts,
                "url": url,
                "report_type": report_type,
                "status_history": status_history,
                "error": error,
                "challenge_markers": challenge_markers or [],
                "final_page_title": final_page_title,
                "playwright_used": playwright_used,
                "playwright_succeeded": playwright_succeeded,
                "playwright_artifacts": playwright_artifacts or [],
            }
            report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return report_path
        except Exception as exc:
            logger.warning(f"Failed to write fetch debug report for {url}: {exc}")
            return None

    def _log_fetch_failure_summary(
        self,
        url: str,
        status_history: List[Dict],
        reason: str,
        report_path: Optional[Path] = None,
        challenge_markers: Optional[List[str]] = None,
        playwright_artifacts: Optional[List[str]] = None,
    ) -> None:
        statuses = [str(item.get("status")) for item in status_history if item.get("status") is not None]
        attempts = len(status_history)
        marker_text = ", ".join(challenge_markers or [])
        artifact_text = ", ".join(playwright_artifacts or [])
        logger.error(
            "Ballotpedia fetch failed | "
            f"reason={reason} attempts={attempts} statuses=[{','.join(statuses)}] "
            f"url={url} markers=[{marker_text}] "
            f"debug_report={report_path if report_path else 'n/a'} "
            f"artifacts=[{artifact_text}]"
        )

    async def _save_playwright_artifacts(self, page, url: str, reason: str) -> List[Path]:
        try:
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            slug = re.sub(r"[^a-z0-9]+", "_", url.lower()).strip("_")[:120]
            base = self.playwright_artifact_dir
            base.mkdir(parents=True, exist_ok=True)

            html_path = base / f"{slug}_{ts}_{reason}.html"
            png_path = base / f"{slug}_{ts}_{reason}.png"
            txt_path = base / f"{slug}_{ts}_{reason}.txt"

            content = await page.content()
            title = await page.title()
            meta = f"url={page.url}\nrequested_url={url}\ntitle={title}\nreason={reason}\n"

            html_path.write_text(content, encoding="utf-8")
            txt_path.write_text(meta, encoding="utf-8")
            await page.screenshot(path=str(png_path), full_page=True)
            logger.info(f"Saved Playwright debug artifacts: {html_path}, {png_path}, {txt_path}")
            return [html_path, png_path, txt_path]
        except Exception as exc:
            logger.warning(f"Failed to save Playwright artifacts for {url}: {exc}")
            return []
        
    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session with rate limiting."""
        if self.session is None:
            self.session = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Referer": "https://ballotpedia.org/",
                },
                follow_redirects=True,
                http2=False,
            )
        return self.session
    
    async def _fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch a page from Ballotpedia with rate limiting and caching.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content or None if failed
        """
        if self.playwright_only:
            html, pw_artifacts = await self._fetch_page_with_playwright(url)
            if html:
                return html

            report_path = self._write_fetch_debug_report(
                url=url,
                report_type="playwright_only_failed",
                status_history=[],
                error="playwright_only_mode_failed",
                playwright_used=True,
                playwright_succeeded=False,
                playwright_artifacts=[str(path) for path in pw_artifacts],
            )
            self._log_fetch_failure_summary(
                url=url,
                status_history=[],
                reason="playwright_only_failed",
                report_path=report_path,
                playwright_artifacts=[str(path) for path in pw_artifacts],
            )
            return None

        session = await self._get_session()
        saw_challenge_status = False
        status_history: List[Dict] = []
        last_exception: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                # Rate limiting - be respectful and add light jitter.
                await asyncio.sleep(self.inter_request_delay + random.random())
                response = await session.get(url)
                status_history.append({"attempt": attempt, "status": response.status_code})

                if response.status_code == 200:
                    if self._is_challenge_html(response.text or ""):
                        saw_challenge_status = True
                        if self.debug_verbose:
                            logger.debug(
                                f"Challenge-like HTTP 200 content detected for {url}; escalating to browser fallback"
                            )
                        break
                    return response.text

                if response.status_code in (202, 429, 503):
                    saw_challenge_status = True
                    if self.httpx_202_fast_escalate and response.status_code == 202 and self.use_playwright_fallback:
                        if self.debug_verbose:
                            logger.debug(
                                f"HTTP 202 for {url}; fast-escalating to Playwright (skip httpx retries)"
                            )
                        break
                    retry_after_raw = response.headers.get("Retry-After")
                    retry_after = float(retry_after_raw) if retry_after_raw and retry_after_raw.isdigit() else 0.0
                    backoff = max(retry_after, self.base_backoff_seconds * (2 ** (attempt - 1)))
                    if self.debug_verbose:
                        logger.debug(
                            f"Retryable fetch status {response.status_code} for {url} "
                            f"(attempt {attempt}/{self.max_retries}); sleeping {backoff:.1f}s"
                        )
                    if attempt < self.max_retries:
                        await asyncio.sleep(backoff)
                        continue
                    # Final retryable response: let the function fall through to Playwright fallback.
                    break

                report_path = self._write_fetch_debug_report(
                    url=url,
                    report_type="http_failure",
                    status_history=status_history,
                    error=f"unexpected_http_status:{response.status_code}",
                )
                self._log_fetch_failure_summary(
                    url=url,
                    status_history=status_history,
                    reason="unexpected_http_status",
                    report_path=report_path,
                )
                return None

            except Exception as e:
                last_exception = str(e)
                status_history.append({"attempt": attempt, "status": None, "error": str(e)})
                if self.debug_verbose:
                    logger.debug(f"Error fetching {url} (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.base_backoff_seconds * (2 ** (attempt - 1)))
                    continue
                report_path = self._write_fetch_debug_report(
                    url=url,
                    report_type="request_exception",
                    status_history=status_history,
                    error=last_exception,
                )
                self._log_fetch_failure_summary(
                    url=url,
                    status_history=status_history,
                    reason="request_exception",
                    report_path=report_path,
                )
                return None

        if saw_challenge_status and self.use_playwright_fallback:
            html, pw_artifacts = await self._fetch_page_with_playwright(url)
            if html:
                return html

            markers: List[str] = []
            final_title = ""
            if pw_artifacts:
                for artifact in pw_artifacts:
                    if artifact.suffix == ".html":
                        try:
                            html_text = artifact.read_text(encoding="utf-8")
                            markers = self._challenge_markers_found(html_text)
                            final_title = self._page_title_from_html(html_text)
                        except Exception:
                            pass

            pw_hint = ""
            if not PLAYWRIGHT_AVAILABLE:
                pw_hint = " (playwright package not importable — pip install playwright && playwright install chromium)"
            elif not pw_artifacts and self._last_playwright_error:
                pw_hint = f" (playwright: {self._last_playwright_error})"

            report_path = self._write_fetch_debug_report(
                url=url,
                report_type="challenge_blocked",
                status_history=status_history,
                error=(self._last_playwright_error or "challenge_or_bot_block_after_retries") + pw_hint,
                challenge_markers=markers,
                final_page_title=final_title,
                playwright_used=True,
                playwright_succeeded=False,
                playwright_artifacts=[str(path) for path in pw_artifacts],
            )
            self._log_fetch_failure_summary(
                url=url,
                status_history=status_history,
                reason="challenge_blocked",
                report_path=report_path,
                challenge_markers=markers,
                playwright_artifacts=[str(path) for path in pw_artifacts],
            )
            await self._close_playwright()
        elif saw_challenge_status and not self.use_playwright_fallback:
            report_path = self._write_fetch_debug_report(
                url=url,
                report_type="challenge_no_playwright",
                status_history=status_history,
                error="challenge_detected_and_playwright_disabled",
            )
            self._log_fetch_failure_summary(
                url=url,
                status_history=status_history,
                reason="challenge_no_playwright",
                report_path=report_path,
            )
        elif saw_challenge_status:
            report_path = self._write_fetch_debug_report(
                url=url,
                report_type="challenge_unknown",
                status_history=status_history,
                error="challenge_detected_unknown_terminal_state",
            )
            self._log_fetch_failure_summary(
                url=url,
                status_history=status_history,
                reason="challenge_unknown",
                report_path=report_path,
            )

        return None

    async def _fetch_page_with_playwright(self, url: str) -> tuple[Optional[str], List[Path]]:
        self._last_playwright_error = None
        if not PLAYWRIGHT_AVAILABLE:
            self._last_playwright_error = "playwright_not_installed"
            logger.warning(
                "Playwright fetch requested but playwright is not installed. "
                "Run: pip install playwright && playwright install chromium"
            )
            return None, []

        logger.info(f"Fetching with Playwright: {url}")
        artifacts: List[Path] = []
        page = None
        try:
            page = await self._get_playwright_page()
            content = ""
            for attempt in range(1, max(1, self.playwright_content_retries) + 1):
                if attempt > 1:
                    logger.info(f"Playwright reload attempt {attempt}/{self.playwright_content_retries} for {url}")
                    await page.reload(wait_until="commit", timeout=self.playwright_timeout_ms)
                else:
                    await page.goto(url, wait_until="commit", timeout=self.playwright_timeout_ms)
                await page.wait_for_selector("body", timeout=self.playwright_timeout_ms)

                for _ in range(5):
                    try:
                        await page.wait_for_load_state("networkidle", timeout=12000)
                    except Exception:
                        pass
                    try:
                        await page.wait_for_selector(
                            "#mw-content-text, .mw-parser-output, #bodyContent",
                            timeout=8000,
                        )
                    except Exception:
                        pass
                    await page.wait_for_timeout(3000)
                    content = await page.content()
                    if content and not self._is_challenge_html(content):
                        break

                if content and not self._is_challenge_html(content):
                    break

            final_url = page.url
            title = await page.title()

            if self._is_challenge_html(content or ""):
                logger.warning(
                    f"Playwright fetched challenge page for {url} (final_url={final_url}, title={title})"
                )
                self._last_playwright_error = f"challenge_page title={title!r}"
                artifacts = await self._save_playwright_artifacts(page, url, "challenge")
                return None, artifacts

            logger.info(f"Playwright fetch succeeded for {url} (final_url={final_url})")
            return content, []
        except Exception as exc:
            self._last_playwright_error = str(exc)
            logger.warning(f"Playwright fetch failed for {url}: {exc}")
            if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc).lower():
                logger.error(
                    "Chromium browser missing. Run from repo root: "
                    "./.venv/bin/playwright install chromium"
                )
            try:
                if page is None:
                    page = await self._get_playwright_page()
                artifacts = await self._save_playwright_artifacts(page, url, "exception")
            except Exception as save_exc:
                logger.warning(f"Could not save Playwright failure artifacts: {save_exc}")
            return None, artifacts

    async def _close_playwright(self) -> None:
        """Tear down browser so the next fetch gets a fresh context (helps after blocks)."""
        async with self._playwright_lock:
            try:
                if self._page:
                    await self._page.close()
            except Exception:
                pass
            self._page = None
            try:
                if self._context:
                    await self._context.close()
            except Exception:
                pass
            self._context = None
            try:
                if self._browser:
                    await self._browser.close()
            except Exception:
                pass
            self._browser = None
            try:
                if self._pw:
                    await self._pw.stop()
            except Exception:
                pass
            self._pw = None
            self._playwright_warmed_up = False

    async def _get_playwright_page(self):
        async with self._playwright_lock:
            if self._page:
                return self._page

            browser_args = ["--disable-blink-features=AutomationControlled", "--start-maximized"]
            launch_kwargs: Dict[str, Any] = {
                "headless": self.playwright_headless_mode != "headed",
                "args": browser_args,
            }
            if self.playwright_headless_mode == "new":
                launch_kwargs["args"] = [*browser_args, "--headless=new"]
            if self.playwright_channel:
                launch_kwargs["channel"] = self.playwright_channel

            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(**launch_kwargs)
            self._context = await self._browser.new_context(
                user_agent=self.user_agent,
                viewport=None if self.playwright_headless_mode == "headed" else {"width": 1366, "height": 768},
                locale="en-US",
            )
            await self._context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            self._page = await self._context.new_page()
            if PLAYWRIGHT_STEALTH_AVAILABLE:
                try:
                    if STEALTH_MODE == "legacy":
                        await stealth_async(self._page)
                    else:
                        await Stealth().apply_stealth_async(self._page)
                except Exception as exc:
                    logger.warning(f"playwright-stealth installed but failed to apply stealth patches: {exc}")
            else:
                logger.warning("playwright-stealth is not installed; running Playwright fallback without stealth patches")

            if not self._playwright_warmed_up:
                try:
                    logger.info("Playwright warmup: visiting Ballotpedia main page")
                    await self._page.goto(
                        f"{self.BASE_URL}/Main_Page",
                        wait_until="commit",
                        timeout=self.playwright_timeout_ms,
                    )
                    await self._page.wait_for_timeout(2500)
                    self._playwright_warmed_up = True
                except Exception as exc:
                    logger.warning(f"Playwright warmup failed (continuing anyway): {exc}")

            return self._page
    
    async def search_leader(self, name: str, state: Optional[str] = None) -> Optional[Dict]:
        """
        Search for a specific leader on Ballotpedia.
        
        Args:
            name: Leader's name (e.g., "Walt Maddox")
            state: Optional state filter (e.g., "Alabama" or "AL")
            
        Returns:
            Leader information dict or None
        """
        # Ballotpedia uses URL patterns like:
        # https://ballotpedia.org/Walt_Maddox
        search_name = name.replace(" ", "_")
        url = f"{self.BASE_URL}/{search_name}"
        
        logger.info(f"Searching for leader: {name} at {url}")
        
        html = await self._fetch_page(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract leader information from infobox
        infobox = soup.find('table', {'class': 'infobox'})
        if not infobox:
            logger.warning(f"No infobox found for {name}")
            return None
        
        leader_data = {
            "name": name,
            "ballotpedia_url": url,
            "office": None,
            "party": None,
            "jurisdiction": None,
            "term_start": None,
            "term_end": None,
            "source": "ballotpedia",
            "scraped_at": datetime.utcnow().isoformat()
        }
        
        # Parse infobox rows
        for row in infobox.find_all('tr'):
            header = row.find('th')
            data = row.find('td')
            
            if header and data:
                header_text = header.get_text(strip=True).lower()
                data_text = data.get_text(strip=True)
                
                if 'office' in header_text or 'position' in header_text:
                    leader_data['office'] = data_text
                elif 'party' in header_text:
                    leader_data['party'] = data_text
                elif 'assumed office' in header_text or 'took office' in header_text:
                    leader_data['term_start'] = data_text
                elif 'term ends' in header_text or 'leaving office' in header_text:
                    leader_data['term_end'] = data_text
        
        logger.info(f"✅ Found leader: {name} - {leader_data.get('office')}")
        return leader_data
    
    @classmethod
    def build_city_url(cls, city: str, state: str) -> str:
        """
        Canonical Ballotpedia URL for a city page (e.g.
        ``https://ballotpedia.org/Tuscaloosa,_Alabama``). ``state`` may be either a
        2-letter code (``AL``) or the full name (``Alabama``); both resolve to the
        same URL using the state-name form Ballotpedia requires.
        """
        state_clean = (state or "").strip()
        state_name = cls.STATE_NAME_BY_CODE.get(state_clean.upper(), state_clean)
        city_page = f"{city},_{state_name}".replace(" ", "_")
        return f"{cls.BASE_URL}/{city_page}"

    async def get_city_officials(self, city: str, state: str) -> List[Dict]:
        """
        Get elected officials for a city.

        Args:
            city: City name (e.g., "Tuscaloosa")
            state: State name or code (e.g., "Alabama" or "AL")

        Returns:
            List of official dicts. Two parsing strategies in order:
              1. Heading-anchored ``<ul>`` lists (legacy MediaWiki article shape).
              2. ``<table>``-based "Office | Name | Party | Date" rosters (the
                 current Ballotpedia format for state-executive / city-leader
                 listings).
        """
        url = self.build_city_url(city, state)
        
        logger.info(f"Fetching officials for {city}, {state} from {url}")
        
        html = await self._fetch_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        officials = []
        
        # Look for "City council" or "Mayor" sections
        for heading in soup.find_all(['h2', 'h3']):
            heading_text = heading.get_text(strip=True).lower()
            
            if any(term in heading_text for term in ['mayor', 'city council', 'council members']):
                # Find the list of officials after this heading
                next_elem = heading.find_next_sibling()
                
                while next_elem and next_elem.name != 'h2':
                    if next_elem.name == 'ul':
                        for li in next_elem.find_all('li'):
                            official_name = li.get_text(strip=True)
                            
                            # Extract name and position
                            # Format often like: "John Smith (District 1)"
                            match = re.match(r'(.*?)\s*\((.*?)\)', official_name)
                            if match:
                                name = match.group(1).strip()
                                position = match.group(2).strip()
                            else:
                                name = official_name
                                position = heading_text.title()
                            
                            officials.append({
                                "name": name,
                                "position": position,
                                "jurisdiction": f"{city}, {state}",
                                "source": "ballotpedia",
                                "source_url": url,
                                "scraped_at": datetime.utcnow().isoformat()
                            })
                    
                    next_elem = next_elem.find_next_sibling()
        
        # Strategy 2: table-based extraction. Ballotpedia's current format puts
        # officials in a 4-column table with headers like Office / Name / Party /
        # Date assumed office. This applies both to the actual city-officials block
        # on the Tuscaloosa page AND to the state-executives fallback table shown
        # on smaller-city pages (e.g. Andalusia, Alabama).
        if not officials:
            for table in soup.find_all("table"):
                rows = table.find_all("tr")
                if len(rows) < 2:
                    continue
                # Header row — accept either <th> or the first <tr>'s text cells
                header_cells = rows[0].find_all(["th", "td"])
                headers = [c.get_text(" ", strip=True).lower() for c in header_cells]
                if "office" not in headers or "name" not in headers:
                    continue
                idx_office = headers.index("office")
                idx_name   = headers.index("name")
                idx_party  = headers.index("party") if "party" in headers else None
                idx_date   = next((i for i, h in enumerate(headers) if "date" in h), None)
                for tr in rows[1:]:
                    cells = tr.find_all(["td", "th"])
                    if len(cells) <= max(idx_office, idx_name):
                        continue
                    name_txt = cells[idx_name].get_text(" ", strip=True)
                    if not name_txt:
                        continue
                    officials.append({
                        "name":      name_txt,
                        "position":  cells[idx_office].get_text(" ", strip=True),
                        "party":     cells[idx_party].get_text(" ", strip=True) if idx_party is not None and len(cells) > idx_party else None,
                        "assumed":   cells[idx_date].get_text(" ", strip=True)  if idx_date  is not None and len(cells) > idx_date  else None,
                        "jurisdiction": f"{city}, {state}",
                        "source": "ballotpedia",
                        "source_url": url,
                        "scraped_at": datetime.utcnow().isoformat(),
                    })

        logger.info(f"✅ Found {len(officials)} officials for {city}, {state}")
        return officials
    
    # ------------------------------------------------------------------------------
    # Jurisdiction-level ballot measures
    # URL pattern: https://ballotpedia.org/<Jurisdiction>,_<State>_ballot_measures
    # e.g. /Orleans_Parish,_Louisiana_ballot_measures
    # ------------------------------------------------------------------------------

    @classmethod
    def build_jurisdiction_ballot_measures_url(cls, jurisdiction: str, state: str) -> str:
        """Canonical URL for a jurisdiction's ballot-measures page on Ballotpedia."""
        state_clean = (state or "").strip()
        state_name = cls.STATE_NAME_BY_CODE.get(state_clean.upper(), state_clean)
        slug = f"{jurisdiction},_{state_name}_ballot_measures".replace(" ", "_")
        return f"{cls.BASE_URL}/{slug}"

    async def get_jurisdiction_ballot_measures(
        self, jurisdiction: str, state: str,
    ) -> List[Dict]:
        """
        Extract ballot measures from a jurisdiction-specific page like
        ``Orleans_Parish,_Louisiana_ballot_measures``. Returns a list of measure
        dicts; empty when the page doesn't exist or has no measures section.
        """
        url = self.build_jurisdiction_ballot_measures_url(jurisdiction, state)
        logger.info(f"Fetching jurisdiction ballot measures: {url}")
        html = await self._fetch_page(url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        out: List[Dict] = []
        for table in soup.find_all("table"):
            cls_list = table.get("class") or []
            if any("infobox" in c.lower() for c in cls_list):
                continue
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            headers = [c.get_text(" ", strip=True).lower()
                       for c in rows[0].find_all(["th", "td"])]
            # Heuristic match: measure tables have a name/title col + an outcome/status col
            name_idx = next((i for i, h in enumerate(headers)
                             if any(k in h for k in ("measure", "title", "ballot", "name"))), None)
            status_idx = next((i for i, h in enumerate(headers)
                               if any(k in h for k in ("outcome", "status", "result"))), None)
            if name_idx is None or status_idx is None:
                continue
            for tr in rows[1:]:
                cells = tr.find_all(["td", "th"])
                if len(cells) <= max(name_idx, status_idx):
                    continue
                name_txt = cells[name_idx].get_text(" ", strip=True)
                if not name_txt:
                    continue
                link = cells[name_idx].find("a")
                measure_url = None
                if link and link.get("href"):
                    href = link["href"].strip()
                    if href.startswith("http"):
                        measure_url = href
                    elif href.startswith("/"):
                        measure_url = f"{self.BASE_URL}{href}"
                outcome = cells[status_idx].get_text(" ", strip=True)
                out.append({
                    "measure_title": name_txt,
                    "measure_name": name_txt,
                    "measure_outcome": outcome,
                    "status": outcome,
                    "jurisdiction": jurisdiction,
                    "state": state,
                    "scope": "jurisdiction",
                    "source": "ballotpedia",
                    "source_url": url,
                    "measure_url": measure_url,
                    "scraped_at": datetime.utcnow().isoformat(),
                })
        logger.info(f"✅ Found {len(out)} ballot measure(s) for {jurisdiction}, {state}")
        return out

    # ------------------------------------------------------------------------------
    # External link extraction (called by the loader for each fetched article)
    # ------------------------------------------------------------------------------

    _BALLOTPEDIA_HOST_RE = re.compile(r"(?:^|\.)ballotpedia\.org$", re.IGNORECASE)
    _GOV_HOST_RE         = re.compile(r"\.(gov|us|mil)(?:$|/)", re.IGNORECASE)
    _SOCIAL_HOST_RE      = re.compile(
        r"^(?:www\.)?(facebook|twitter|x|instagram|youtube|linkedin|tiktok|threads|bsky)\.",
        re.IGNORECASE,
    )
    _NEWS_HOST_RE        = re.compile(
        r"\.(?:nytimes|washingtonpost|nola|advocate|cnn|foxnews|wsj|npr|apnews|reuters|bloomberg|axios|politico)\.",
        re.IGNORECASE,
    )
    _WIKIPEDIA_HOST_RE   = re.compile(r"(?:^|\.)wikipedia\.org$", re.IGNORECASE)

    @classmethod
    def classify_external_host(cls, host: str) -> str:
        h = (host or "").lower()
        if not h:
            return "other"
        if cls._GOV_HOST_RE.search(h):       return "gov"
        if cls._SOCIAL_HOST_RE.search(h):    return "social"
        if cls._WIKIPEDIA_HOST_RE.search(h): return "wikipedia"
        if cls._NEWS_HOST_RE.search(h):      return "news"
        return "other"

    @classmethod
    def extract_external_links(cls, html: str, source_page_url: str) -> List[Dict]:
        """
        Return a list of dicts for every outbound <a href> on the page that points
        OFF Ballotpedia. Internal /wiki/... and same-host links are excluded.
        Each dict: ``target_url``, ``target_host``, ``target_kind``, ``anchor_text``, ``rel``.
        """
        if not html:
            return []
        from urllib.parse import urlparse
        soup = BeautifulSoup(html, "html.parser")
        out: List[Dict] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("#") or href.startswith("mailto:"):
                continue
            parsed = urlparse(href)
            if not parsed.scheme or not parsed.netloc:
                continue                                    # internal /wiki/... skipped
            host = parsed.netloc.lower()
            if cls._BALLOTPEDIA_HOST_RE.search(host):
                continue
            if href in seen:
                continue
            seen.add(href)
            out.append({
                "target_url":  href,
                "target_host": host,
                "target_kind": cls.classify_external_host(host),
                "anchor_text": a.get_text(" ", strip=True) or None,
                "rel":         " ".join(a.get("rel") or []) or None,
                "source_page_url": source_page_url,
            })
        return out

    async def fetch_and_extract_external_links(
        self, url: str,
    ) -> tuple[Optional[str], List[Dict]]:
        """Fetch a Ballotpedia page and return (html, list-of-external-link-dicts)."""
        html = await self._fetch_page(url)
        return html, self.extract_external_links(html or "", url)

    @classmethod
    def build_state_ballot_measures_url(cls, state: str, year: int | None = None) -> str:
        """Canonical URL for a state's ballot-measures page (optional year suffix)."""
        if year:
            return f"{cls.BASE_URL}/{state}_ballot_measures,_{year}"
        return f"{cls.BASE_URL}/{state}_ballot_measures"

    async def get_ballot_measures(
        self,
        state: str,
        year: Optional[int] = None,
        measure_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Get ballot measures for a state.

        Args:
            state: State name (e.g., "Alabama")
            year: Optional year filter (e.g., 2024)
            measure_type: Optional type filter (e.g., "local", "state")

        Returns:
            List of ballot measure dicts
        """
        # Ballotpedia ballot measures page
        url = self.build_state_ballot_measures_url(state, year)
        
        logger.info(f"Fetching ballot measures from {url}")
        
        html = await self._fetch_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        measures = []
        
        for table in soup.find_all('table'):
            cls_list = table.get('class') or []
            if any('infobox' in c.lower() for c in cls_list):
                continue
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue
            headers = [c.get_text(' ', strip=True).lower()
                       for c in rows[0].find_all(['th', 'td'])]
            name_idx = next((i for i, h in enumerate(headers)
                             if any(k in h for k in ('measure', 'title', 'ballot', 'name', 'description'))), None)
            type_idx = next((i for i, h in enumerate(headers)
                             if any(k in h for k in ('type', 'classification'))), None)
            status_idx = next((i for i, h in enumerate(headers)
                               if any(k in h for k in ('outcome', 'status', 'result'))), None)
            year_idx = next((i for i, h in enumerate(headers)
                             if 'year' in h or 'date' in h or 'election' in h), None)

            if name_idx is None and len(headers) >= 2:
                # Legacy 2-column tables: col0=type/code, col1=title
                type_idx, name_idx = 0, 1

            for tr in rows[1:]:
                cells = tr.find_all(['td', 'th'])
                if not cells:
                    continue
                if name_idx is not None and len(cells) <= name_idx:
                    continue
                title_txt = cells[name_idx].get_text(' ', strip=True) if name_idx is not None else ''
                type_txt = cells[type_idx].get_text(' ', strip=True) if type_idx is not None and len(cells) > type_idx else None
                status_txt = cells[status_idx].get_text(' ', strip=True) if status_idx is not None and len(cells) > status_idx else None
                year_txt = cells[year_idx].get_text(' ', strip=True) if year_idx is not None and len(cells) > year_idx else None

                # When col0 is a short type code (LRCA, CI) and col1 is the long title, prefer col1.
                if type_txt and title_txt and len(type_txt) <= 6 and len(title_txt) > len(type_txt):
                    measure_title, measure_type = title_txt, type_txt
                elif title_txt:
                    measure_title, measure_type = title_txt, type_txt
                elif status_txt:
                    measure_title, measure_type = status_txt, type_txt
                else:
                    continue

                link = cells[name_idx].find('a') if name_idx is not None and len(cells) > name_idx else None
                measure_url = None
                if link and link.get('href'):
                    href = link['href'].strip()
                    if href.startswith('http'):
                        measure_url = href
                    elif href.startswith('/'):
                        measure_url = f"{self.BASE_URL}{href}"

                measures.append({
                    "measure_name": measure_title,
                    "measure_title": measure_title,
                    "measure_type": measure_type,
                    "status": status_txt or measure_type,
                    "measure_outcome": status_txt,
                    "state": state,
                    "year": str(year) if year is not None else (year_txt or None),
                    "scope": "state",
                    "source_url": url,
                    "measure_url": measure_url,
                    "source": "ballotpedia",
                    "scraped_at": datetime.utcnow().isoformat(),
                })
        
        logger.info(f"✅ Found {len(measures)} ballot measures for {state} ({year or 'all years'})")
        return measures
    
    async def close(self):
        """Close HTTP session and Playwright browser."""
        if self.session:
            await self.session.aclose()
            self.session = None
        await self._close_playwright()
    
    def save_to_json(self, data: List[Dict], filename: str):
        """Save data to JSON cache."""
        filepath = self.cache_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"💾 Saved {len(data)} records to {filepath}")
        return filepath

    def save_measures_snapshot(
        self,
        measures: List[Dict],
        *,
        state_code: str,
        scope: str,
        jurisdiction_id: str | None = None,
        jurisdiction_name: str | None = None,
        jurisdiction_type: str | None = None,
        election_year: str | None = None,
        source_url: str | None = None,
        debug_reason: str | None = None,
    ) -> Path:
        """Write a timestamped ballot-measures JSON file under the cache tree."""
        from scripts.gemini.transcript_cache_paths import (
            cache_type_segment,
            jurisdiction_cache_folder_name,
        )

        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        year_suffix = f"_{election_year}" if election_year else ""
        if scope == "state":
            rel = Path(state_code.upper()) / "state" / f"state_ballot_measures{year_suffix}_{ts}.json"
        else:
            jkey = jurisdiction_id or "unknown"
            segment = cache_type_segment(jkey, jurisdiction_type=jurisdiction_type or "municipality")
            folder = jurisdiction_cache_folder_name(
                jkey,
                place_name=jurisdiction_name,
            )
            rel = (
                Path(state_code.upper())
                / segment
                / folder
                / f"{jkey}_ballot_measures{year_suffix}_{ts}.json"
            )
        filepath = self.cache_dir / rel
        filepath.parent.mkdir(parents=True, exist_ok=True)
        count = len(measures)
        payload = {
            "state_code": state_code.upper(),
            "scope": scope,
            "jurisdiction_id": jurisdiction_id,
            "election_year": election_year,
            "source_url": source_url,
            "scraped_at": datetime.utcnow().isoformat() + "Z",
            "cache_written_at": datetime.utcnow().isoformat() + "Z",
            "measure_count": count,
            "debug_status": "success" if count else "empty",
            "debug_reason": debug_reason or ("measures_found" if count else "no_measures_on_page"),
            "measures": measures,
        }
        filepath.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info(f"💾 Saved {count} ballot measure(s) → {filepath}")
        return filepath
    
    def save_to_bronze_layer(
        self,
        data: List[Dict],
        table_name: str,
        spark: Optional[SparkSession] = None
    ) -> Dict[str, int]:
        """
        Save discovered data to Bronze layer (Delta Lake).
        
        Args:
            data: List of dicts to save
            table_name: Table name (e.g., "ballotpedia_officials")
            spark: Optional SparkSession (creates one if not provided)
            
        Returns:
            Stats dict
        """
        if not SPARK_AVAILABLE:
            logger.warning("PySpark not available - saving to JSON instead")
            self.save_to_json(data, f"{table_name}.json")
            return {"records_written": len(data), "format": "json"}
        
        from delta import configure_spark_with_delta_pip
        from config.settings import settings
        
        # Create Spark session if needed
        if spark is None:
            builder = SparkSession.builder \
                .appName(f"BallotpediaIngestion_{table_name}") \
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
                .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
            spark = configure_spark_with_delta_pip(builder).getOrCreate()
        
        # Convert to DataFrame
        df = spark.createDataFrame(data)
        
        # Write to Bronze layer
        bronze_path = f"{settings.delta_lake_path}/bronze/{table_name}"
        df.write \
            .format("delta") \
            .mode("append") \
            .option("mergeSchema", "true") \
            .save(bronze_path)
        
        logger.info(f"✅ Wrote {len(data)} records to {bronze_path}")
        
        return {
            "records_written": len(data),
            "table_name": table_name,
            "path": bronze_path,
            "format": "delta"
        }


# ============================================================================
# Usage Examples
# ============================================================================

async def example_usage():
    """
    Example usage of Ballotpedia integration.
    
    Shows both official API (v3.0) and web scraping fallback methods.
    """
    
    logger.info("\n" + "="*80)
    logger.info("BALLOTPEDIA INTEGRATION EXAMPLES")
    logger.info("="*80)
    
    # Check if API key is available
    api_available = False
    if SETTINGS_AVAILABLE and hasattr(settings, 'ballotpedia_api_key') and settings.ballotpedia_api_key:
        api_available = True
    
    # ==========================================================================
    # METHOD 1: Official API (RECOMMENDED for production)
    # ==========================================================================
    if api_available:
        logger.info("\n" + "="*80)
        logger.info("METHOD 1: Using Official Ballotpedia API v3.0 (RECOMMENDED)")
        logger.info("="*80)
        
        api = BallotpediaAPI()
        
        try:
            # Example 1: Get officials via API
            logger.info("\nExample 1: Get Tuscaloosa officials via API")
            officials = await api.get_officials("Tuscaloosa", state="Alabama")
            
            if officials:
                print(f"\n✅ API returned {len(officials)} officials:")
                for official in officials[:5]:
                    print(f"   • {official.get('name')} - {official.get('office')}")
                api.save_to_json(officials, "tuscaloosa_officials_api.json")
            
            # Example 2: Get ballot measures via API
            logger.info("\nExample 2: Get Alabama ballot measures via API")
            measures = await api.get_ballot_measures("Alabama", year=2024)
            
            if measures:
                print(f"\n✅ API returned {len(measures)} ballot measures:")
                for measure in measures[:5]:
                    print(f"   • {measure.get('title')} - {measure.get('status')}")
                api.save_to_json(measures, "alabama_measures_api.json")
            
        except Exception as e:
            logger.error(f"API error: {e}")
            logger.info("Falling back to web scraping...")
    else:
        logger.info("\n" + "="*80)
        logger.info("⚠️  Ballotpedia API key not found - using web scraping fallback")
        logger.info("   Get API access at: https://ballotpedia.org/API_documentation")
        logger.info("   Add to .env: BALLOTPEDIA_API_KEY=your-key")
        logger.info("="*80)
    
    # ==========================================================================
    # METHOD 2: Web Scraping Fallback (for testing without API key)
    # ==========================================================================
    logger.info("\n" + "="*80)
    logger.info("METHOD 2: Using Web Scraping (Fallback)")
    logger.info("="*80)
    
    discovery = BallotpediaDiscovery()
    
    # 1. Search for a specific leader
    logger.info("\nExample 1: Search for Mayor Walt Maddox (web scraping)")
    
    leader = await discovery.search_leader("Walt Maddox", "Alabama")
    if leader:
        print(f"\n✅ Found: {leader['name']}")
        print(f"   Office: {leader['office']}")
        print(f"   Party: {leader['party']}")
        print(f"   URL: {leader['ballotpedia_url']}")
    
    # 2. Get city officials
    logger.info("\nExample 2: Get Tuscaloosa city officials (web scraping)")
    
    officials = await discovery.get_city_officials("Tuscaloosa", "Alabama")
    print(f"\n✅ Found {len(officials)} officials:")
    for official in officials[:5]:  # Show first 5
        print(f"   • {official['name']} - {official['position']}")
    
    # 3. Get ballot measures
    logger.info("\nExample 3: Get Alabama ballot measures (web scraping)")
    
    measures = await discovery.get_ballot_measures("Alabama", year=2024)
    print(f"\n✅ Found {len(measures)} ballot measures:")
    for measure in measures[:5]:  # Show first 5
        print(f"   • {measure['measure_name']} - {measure['status']}")
    
    # Save to cache
    if officials:
        discovery.save_to_json(officials, "tuscaloosa_officials_scraping.json")
    
    if measures:
        discovery.save_to_json(measures, "alabama_ballot_measures_scraping.json")
    
    # Close session
    await discovery.close()
    
    logger.info("\n✅ Integration examples complete!")
    logger.info("\n" + "="*80)
    logger.info("RECOMMENDATION: Get official API key for production use")
    logger.info("Visit: https://ballotpedia.org/API_documentation")
    logger.info("="*80)


if __name__ == "__main__":
    # Run examples
    asyncio.run(example_usage())
