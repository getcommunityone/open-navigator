"""
YouTube Channel Discovery & Statistics

Enhanced discovery that:
1. Finds ALL YouTube channels (not just first match)
2. Fetches channel statistics (video count, subscribers)
3. Ranks channels by activity
4. Stores all channels found

Requires YouTube Data API v3 key (optional - falls back to scraping)
"""
import asyncio
import re
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from loguru import logger
import os

from scripts.discovery.scrape_http import async_get_with_vpn_bypass, make_scrape_async_client


class YouTubeChannelDiscovery:
    """
    Comprehensive YouTube channel discovery for government entities.
    
    Strategies:
    1. Scrape government website for embedded/linked channels
    2. Search YouTube API by government name
    3. Test common handle patterns (@CityNameAL, @CityOfName, etc.)
    4. Fetch statistics for all discovered channels
    5. Rank by video count and recency
    """
    
    # Common channel handle patterns for cities
    CITY_HANDLE_PATTERNS = [
        "{city}City",           # TuscaloosaCity
        "{city}CityAL",         # TuscaloosaCityAL  
        "{city}City{state}",    # TuscaloosaCityAlabama
        "CityOf{city}",         # CityOfTuscaloosa
        "City{city}",           # CityTuscaloosa
        "{city}Alabama",        # TuscaloosaAlabama
        "{city}AL",             # TuscaloosaAL
        "{city}Gov",            # TuscaloosaGov
        "{city}Government",     # TuscaloosaGovernment
        "Official{city}",       # OfficialTuscaloosa
    ]
    
    # Common for counties
    COUNTY_HANDLE_PATTERNS = [
        "{county}County",       # TuscaloosaCounty
        "{county}CountyAL",     # TuscaloosaCountyAL
        "{county}Co",           # TuscaloosaCo
        "{county}CoAL",         # TuscaloosaCoAL
    ]
    
    def __init__(self, youtube_api_key: Optional[str] = None):
        """
        Initialize YouTube discovery.
        
        Args:
            youtube_api_key: YouTube Data API v3 key (optional)
                            Get from: https://console.cloud.google.com/
                            Falls back to scraping if not provided
        """
        self.api_key = youtube_api_key or os.getenv("YOUTUBE_API_KEY")
        # Each dict: channel_url, checked_at (UTC ISO), discovery_method,
        # outcome in found | not_found | error | skipped_invalid_url,
        # http_status?, reason?, channel_title? when found.
        self.last_channel_probe_results: List[Dict[str, Any]] = []
        self.client = make_scrape_async_client(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OralHealthPolicyBot/2.0)"},
        )
        
        # Keywords for identifying policy/meeting-focused channels
        self.policy_channel_keywords = (
            'city council', 'town council', 'county commission', 'board meeting',
            'government', 'official', 'meetings', 'public meetings', 'city tv',
            'municipal', 'civic', 'city clerk', 'legislative', 'session'
        )

    _PLACE_LSAD_SUFFIX = re.compile(
        r"\s*,?\s*(city|town|village|borough|county|cdp|municipality)\s*$",
        re.IGNORECASE,
    )

    def _compact_name_for_handles(self, raw: str) -> str:
        """
        Strip Census/LSAD-style suffixes ("Howell city" → Howell) then remove spaces/apostrophes.

        Without this, patterns like "{city}City" turn "Howell city" → Howellcity → HowellcityCity.
        """
        s = (raw or "").strip()
        if not s:
            return ""
        prev = None
        while prev != s:
            prev = s
            s = self._PLACE_LSAD_SUFFIX.sub("", s).strip()
        compact = re.sub(r"\s+", "", s).replace("'", "")
        # YouTube handles: keep only safe characters before we build URLs
        return re.sub(r"[^0-9A-Za-z_-]", "", compact)

    def _score_channel_for_policy_content(self, channel_title: str) -> int:
        """
        Score a channel based on how likely it is to contain policy/meeting content.
        
        Higher scores indicate more relevant channels.
        
        Args:
            channel_title: Channel title to score
            
        Returns:
            Score from 0-10
        """
        if not channel_title:
            return 0
        
        title_lower = channel_title.lower()
        score = 0
        
        # High relevance keywords (5 points each)
        high_priority = ['city council', 'town council', 'board meeting', 'city tv', 'county commission']
        for keyword in high_priority:
            if keyword in title_lower:
                score += 5
        
        # Medium relevance keywords (3 points each)
        medium_priority = ['government', 'official', 'meetings', 'municipal', 'public']
        for keyword in medium_priority:
            if keyword in title_lower:
                score += 3
        
        # Low relevance keywords (1 point each)
        low_priority = ['civic', 'city', 'town', 'county']
        for keyword in low_priority:
            if keyword in title_lower:
                score += 1
        
        return min(score, 10)  # Cap at 10
    
    async def discover_channels(
        self,
        city_name: Optional[str],
        state_code: str,
        county_name: Optional[str] = None,
        homepage_url: Optional[str] = None
    ) -> List[Dict]:
        """
        Discover ALL YouTube channels for a jurisdiction.
        
        Args:
            city_name: City name (e.g., "Tuscaloosa")
            state_code: State code (e.g., "AL")
            county_name: County name (e.g., "Tuscaloosa County")
            homepage_url: Government website to scrape
            
        Returns:
            List of channel dictionaries with statistics:
            [
                {
                    "channel_url": "https://www.youtube.com/@TuscaloosaCityAL",
                    "channel_id": "UCxxx",
                    "channel_title": "City of Tuscaloosa",
                    "video_count": 245,
                    "subscriber_count": 1500,
                    "view_count": 50000,
                    "latest_upload": "2026-04-15",
                    "discovery_method": "pattern_match",
                    "confidence": 0.95
                },
                ...
            ]
        """
        resolved_city_name = city_name
        if not resolved_city_name and county_name:
            resolved_city_name = county_name.replace(" County", "").strip()
        if not resolved_city_name:
            logger.warning("No city or county name provided for YouTube discovery")
            return []

        self.last_channel_probe_results = []

        logger.info(f"Discovering YouTube channels for {resolved_city_name}, {state_code}")
        
        discovered = []
        tested_urls = set()
        
        # Strategy 1: Test common handle patterns
        patterns_to_test = self._generate_handle_patterns(
            resolved_city_name, state_code, county_name
        )
        
        logger.info(f"Testing {len(patterns_to_test)} common handle patterns...")
        
        j_display_name = (county_name or resolved_city_name or "").strip()
        can_pattern_match = bool((homepage_url or "").strip())

        for handle in patterns_to_test:
            url = f"https://www.youtube.com/@{handle}"
            
            if url in tested_urls:
                continue
            tested_urls.add(url)
            
            channel_info = await self._check_channel_exists(url, "pattern_match")
            if not channel_info:
                await asyncio.sleep(0.3)
                continue

            if not can_pattern_match:
                self._record_channel_probe(
                    {
                        "channel_url": url,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "discovery_method": "pattern_match",
                        "outcome": "rejected_pattern_gate",
                        "http_status": None,
                        "reason": "no_jurisdiction_homepage_for_backlink_check",
                        "channel_id": channel_info.get("channel_id"),
                        "channel_title": (channel_info.get("channel_title") or "")[:500],
                    }
                )
                await asyncio.sleep(0.3)
                continue

            from scripts.datasources.jurisdiction_pilot.youtube_channel_enrich import (
                enrich_channel,
            )
            from scripts.datasources.youtube.pattern_match_gate import (
                passes_pattern_match_gate,
            )

            try:
                enriched = await asyncio.to_thread(
                    enrich_channel,
                    channel=channel_info,
                    jurisdiction_name=j_display_name,
                    jurisdiction_state_code=state_code,
                    jurisdiction_homepage=homepage_url,
                )
            except Exception as exc:
                logger.debug("pattern_match enrich failed for {}: {}", url, exc)
                await asyncio.sleep(0.3)
                continue

            if not passes_pattern_match_gate(
                channel_title=str(enriched.get("channel_title") or ""),
                channel_description=str(enriched.get("channel_description") or ""),
                jurisdiction_name=j_display_name,
                jurisdiction_state_code=state_code,
                jurisdiction_homepage=homepage_url or "",
                external_links=enriched.get("external_links"),
                backlinks_to_jurisdiction=enriched.get(
                    "back_links_to_jurisdiction_website"
                ),
            ):
                self._record_channel_probe(
                    {
                        "channel_url": url,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "discovery_method": "pattern_match",
                        "outcome": "rejected_pattern_gate",
                        "http_status": None,
                        "reason": "missing_state_backlink_or_meeting_signal",
                        "channel_id": enriched.get("channel_id"),
                        "channel_title": (enriched.get("channel_title") or "")[:500],
                    }
                )
                await asyncio.sleep(0.3)
                continue

            discovered.append(enriched)
            logger.success(
                "✓ pattern_match accepted: {} (conf={})",
                url,
                enriched.get("official_meeting_confidence"),
            )
            
            # Rate limiting
            await asyncio.sleep(0.3)
        
        # Strategy 2: Scrape homepage if provided
        if homepage_url:
            logger.info(f"Scraping {homepage_url} for YouTube links...")
            scraped_channels = await self._scrape_website_for_channels(homepage_url)
            
            for url in scraped_channels:
                if url not in tested_urls:
                    tested_urls.add(url)
                    channel_info = await self._check_channel_exists(url, "website_scrape")
                    if channel_info:
                        discovered.append(channel_info)
                        logger.success(f"✓ Found: {url}")
        
        # Strategy 3: YouTube API search (if key available)
        if self.api_key:
            logger.info(f"Searching YouTube API for '{resolved_city_name}'...")
            api_channels = await self._search_youtube_api(resolved_city_name, state_code)

            for channel in api_channels:
                url = channel['channel_url']
                if url not in tested_urls:
                    tested_urls.add(url)
                    discovered.append(channel)
                    logger.success(f"✓ Found via API: {url}")

        # Strategy 4: Domain-anchored YouTube API search. Searches for the jurisdiction's
        # bare host (e.g. "cambridgema.gov") rather than the name. Domains are unique, so
        # any channel surfaced this way is overwhelmingly the actual jurisdiction channel
        # — much higher precision than name-token matching (which collides with arbitrary
        # "Adams" / "John Adams" / "Mass B TV" results).
        if self.api_key and homepage_url:
            domain_channels = await self._search_youtube_by_domain(homepage_url)
            if domain_channels:
                logger.info(f"Domain search returned {len(domain_channels)} channel(s) for {homepage_url}")
            for channel in domain_channels:
                url = channel['channel_url']
                if url not in tested_urls:
                    tested_urls.add(url)
                    discovered.append(channel)
                    logger.success(f"✓ Found via domain search: {url}")
                else:
                    # Already discovered via another strategy — boost its confidence since
                    # the domain search corroborates it.
                    for existing in discovered:
                        if existing.get('channel_url') == url:
                            existing['discovery_method'] = 'domain_search+' + existing.get('discovery_method', '')
                            existing['confidence'] = max(existing.get('confidence', 0.0), 0.98)
                            break

        # Deduplicate by channel_id
        seen_ids = set()
        unique_channels = []
        for channel in discovered:
            channel_id = (channel.get('channel_id') or '').strip()
            if not channel_id:
                continue
            if channel_id not in seen_ids:
                seen_ids.add(channel_id)
                unique_channels.append(channel)
        
        # Add policy relevance score to each channel
        for channel in unique_channels:
            channel['policy_score'] = self._score_channel_for_policy_content(
                channel.get('channel_title', '')
            )
        
        # Sort by policy score first (descending), then by video count (descending)
        unique_channels.sort(
            key=lambda x: (x.get('policy_score', 0), x.get('video_count', 0)),
            reverse=True
        )
        
        # Log channel rankings
        logger.success(f"✓ Total channels found: {len(unique_channels)}")
        for i, channel in enumerate(unique_channels[:5], 1):
            logger.info(
                f"  #{i}: {channel.get('channel_title', 'Unknown')} "
                f"(policy score: {channel.get('policy_score', 0)}, "
                f"videos: {channel.get('video_count', 0)})"
            )
        
        return unique_channels
    
    def _generate_handle_patterns(
        self,
        city_name: str,
        state_code: str,
        county_name: Optional[str]
    ) -> List[str]:
        """Generate common handle patterns to test."""
        patterns: List[str] = []
        seen: set[str] = set()

        def _add(pat: str) -> None:
            h = pat.strip().lstrip("@")
            if h and h not in seen:
                seen.add(h)
                patterns.append(h)

        city_clean = self._compact_name_for_handles(city_name)
        if not city_clean:
            return []

        # City patterns
        for pattern in self.CITY_HANDLE_PATTERNS:
            _add(pattern.format(city=city_clean, state=state_code))

        # County patterns
        if county_name:
            cn = county_name.replace("County", "").replace("county", "")
            county_clean = self._compact_name_for_handles(cn)
            if county_clean:
                for pattern in self.COUNTY_HANDLE_PATTERNS:
                    _add(pattern.format(county=county_clean, state=state_code))

        return patterns
    
    def _record_channel_probe(self, probe: Dict[str, Any]) -> None:
        """Append one audit row (persist via pipeline ``youtube_channel_checks`` in payload)."""
        self.last_channel_probe_results.append(probe)

    async def _check_channel_exists(
        self,
        channel_url: str,
        discovery_method: str
    ) -> Optional[Dict]:
        """
        Check if channel exists and extract statistics.

        Records one row per attempt in ``self.last_channel_probe_results`` with ``checked_at`` (UTC ISO)
        and ``outcome`` (found | not_found | error | skipped_invalid_url) for Postgres payload audit.

        Returns channel info dict or None if not found.
        """
        raw_url = channel_url or ""
        checked_at = datetime.now(timezone.utc).isoformat()

        try:
            channel_url = raw_url.strip().split()[0].rstrip(".,);]") if raw_url.strip() else ""
            if not channel_url or "youtube.com" not in channel_url.lower():
                self._record_channel_probe(
                    {
                        "channel_url": raw_url.strip()[:2048],
                        "checked_at": checked_at,
                        "discovery_method": discovery_method,
                        "outcome": "skipped_invalid_url",
                        "http_status": None,
                        "reason": "not_youtube_or_empty",
                    }
                )
                return None

            response = await async_get_with_vpn_bypass(self.client, channel_url)
            final_url = str(response.url)

            if response.status_code != 200:
                self._record_channel_probe(
                    {
                        "channel_url": channel_url,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "discovery_method": discovery_method,
                        "outcome": "not_found",
                        "http_status": response.status_code,
                        "reason": "http_non_200",
                    }
                )
                return None

            html = response.text

            # Extract channel statistics from page HTML
            stats = self._extract_channel_stats(
                html,
                final_url=final_url,
                requested_url=channel_url,
            )

            if not stats:
                self._record_channel_probe(
                    {
                        "channel_url": channel_url,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "discovery_method": discovery_method,
                        "outcome": "not_found",
                        "http_status": response.status_code,
                        "reason": "no_channel_stats_in_html",
                    }
                )
                return None

            channel_id = (stats.get("channel_id") or "").strip()
            if not channel_id:
                self._record_channel_probe(
                    {
                        "channel_url": channel_url,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "discovery_method": discovery_method,
                        "outcome": "not_found",
                        "http_status": response.status_code,
                        "reason": "channel_id_not_resolved",
                    }
                )
                return None

            title = stats.get("title", "Unknown") or "Unknown"
            self._record_channel_probe(
                {
                    "channel_url": channel_url,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "discovery_method": discovery_method,
                    "outcome": "found",
                    "http_status": response.status_code,
                    "reason": None,
                    "channel_id": channel_id,
                    "channel_title": title[:500],
                    "video_count": stats.get("video_count", 0),
                }
            )

            return {
                "channel_url": final_url or channel_url,
                "channel_id": channel_id,
                "channel_title": title,
                "video_count": stats.get("video_count", 0),
                "subscriber_count": stats.get("subscriber_count", 0),
                "view_count": stats.get("view_count", 0),
                "latest_upload": stats.get("latest_upload"),
                "discovery_method": discovery_method,
                "discovered_at": datetime.now().isoformat(),
                "confidence": (
                    0.9
                    if discovery_method == "website_scrape"
                    else 0.1
                    if discovery_method == "pattern_match"
                    else 0.5
                ),
            }

        except Exception as e:
            msg = str(e)[:500]
            logger.trace(f"YouTube probe failed for {channel_url!r}: {e}")
            self._record_channel_probe(
                {
                    "channel_url": (channel_url or raw_url).strip()[:2048],
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "discovery_method": discovery_method,
                    "outcome": "error",
                    "http_status": None,
                    "reason": msg or "exception",
                }
            )
            return None

    def _extract_channel_id_from_url(self, url: str) -> Optional[str]:
        """Extract UC... id from a canonical /channel/<id> URL when present."""
        raw = (url or "").strip()
        if not raw:
            return None
        m = re.search(r'/channel/((?:UC)[A-Za-z0-9_-]{20,})', raw)
        if m:
            return m.group(1)
        return None
    
    def _extract_channel_stats(
        self,
        html: str,
        *,
        final_url: str = "",
        requested_url: str = "",
    ) -> Optional[Dict]:
        """
        Extract channel statistics from YouTube channel page HTML.
        
        YouTube embeds data in JavaScript objects in the page source.
        """
        stats: Dict[str, Any] = {}
        
        try:
            # YouTube frequently embeds escaped JSON with \/ path separators.
            normalized = html.replace('\\/', '/')

            # Prefer canonical/redirect URL when it already contains /channel/UC...
            cid_from_url = self._extract_channel_id_from_url(final_url) or self._extract_channel_id_from_url(requested_url)
            if cid_from_url:
                stats['channel_id'] = cid_from_url

            # Extract channel ID
            match = re.search(r'"channelId"\s*:\s*"((?:UC)[A-Za-z0-9_-]{20,})"', normalized)
            if match:
                stats['channel_id'] = match.group(1)

            # Additional channel-id patterns seen in ytInitialData / metadata payloads
            if 'channel_id' not in stats:
                match = re.search(r'"externalId"\s*:\s*"((?:UC)[A-Za-z0-9_-]{20,})"', normalized)
                if match:
                    stats['channel_id'] = match.group(1)
            if 'channel_id' not in stats:
                match = re.search(r'"browseId"\s*:\s*"((?:UC)[A-Za-z0-9_-]{20,})"', normalized)
                if match:
                    stats['channel_id'] = match.group(1)
            if 'channel_id' not in stats:
                match = re.search(r'https?://www\.youtube\.com/channel/((?:UC)[A-Za-z0-9_-]{20,})', normalized)
                if match:
                    stats['channel_id'] = match.group(1)
            if 'channel_id' not in stats:
                match = re.search(r'feeds/videos\.xml\?channel_id=((?:UC)[A-Za-z0-9_-]{20,})', normalized)
                if match:
                    stats['channel_id'] = match.group(1)
            
            # Extract channel title
            match = re.search(r'"channelMetadataRenderer".*?"title":"([^"]+)"', normalized)
            if match:
                stats['title'] = match.group(1)
            if 'title' not in stats:
                match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', normalized, re.IGNORECASE)
                if match:
                    stats['title'] = match.group(1)
            
            # Extract subscriber count
            # Pattern: "subscriberCountText":{"simpleText":"1.2K subscribers"}
            match = re.search(r'"subscriberCountText".*?"(?:simpleText|text)":"([\d.KMB]+)\s*subscribers?"', normalized)
            if match:
                stats['subscriber_count'] = self._parse_count(match.group(1))
            
            # Extract video count  
            # Pattern: "videosCountText":{"runs":[{"text":"245"},{"text":" videos"}]}
            match = re.search(r'"videosCountText".*?"text":"([\d,]+)"', normalized)
            if match:
                stats['video_count'] = int(match.group(1).replace(',', ''))
            
            # Alternative video count pattern
            if 'video_count' not in stats:
                match = re.search(r'(\d+)\s*videos?', normalized, re.IGNORECASE)
                if match:
                    stats['video_count'] = int(match.group(1))

            # Reject generic placeholder pages that don't resolve a real channel id.
            if not stats.get('channel_id'):
                return None
            
            return stats if stats else None
        
        except Exception as e:
            logger.debug(f"Error extracting stats: {e}")
            return None
    
    def _parse_count(self, count_str: str) -> int:
        """Parse subscriber/view counts like '1.2K', '500K', '1.5M'."""
        count_str = count_str.upper().strip()
        
        multipliers = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}
        
        for suffix, multiplier in multipliers.items():
            if suffix in count_str:
                number = float(count_str.replace(suffix, ''))
                return int(number * multiplier)
        
        # No suffix = literal number
        try:
            return int(count_str.replace(',', ''))
        except:
            return 0
    
    # Site-search queries, ordered most-specific first.
    _SITE_SEARCH_QUERIES = ("youtube meeting", "youtube")

    _FOLLOWUP_ANCHOR_HINTS = (
        "video archive",
        "meeting video",
        "youtube",
        "watch meeting",
        "commission meeting",
        "live stream",
        "webcast",
        "meeting archive",
        "county commission",
        "meeting calendar",
        "agendas & minutes",
        "agendas and minutes",
    )
    _FOLLOWUP_PATH_HINTS = (
        "/commission",
        "/meetings",
        "/meeting",
        "/video",
        "/agenda",
        "/calendar",
        "/broadcast",
    )

    @staticmethod
    def _youtube_int_env(name: str, default: int) -> int:
        try:
            return max(0, int((os.getenv(name) or str(default)).strip()))
        except ValueError:
            return default

    def _collect_youtube_followup_page_urls(
        self, html: str, *, base_url: str, max_pages: int
    ) -> list[str]:
        """Same-host pages likely to link a commission YouTube channel (e.g. /commission/)."""
        if not html or max_pages <= 0:
            return []

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return []

        parsed_base = urlparse(base_url)
        if not parsed_base.scheme or not parsed_base.netloc:
            return []

        scored: list[tuple[int, str]] = []
        seen: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = str(link.get("href") or "").strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in ("http", "https"):
                continue
            if parsed.netloc.lower() != parsed_base.netloc.lower():
                continue
            if self._normalize_youtube_channel_url(absolute):
                continue

            text = " ".join((link.get_text() or "").split()).lower()
            path = (parsed.path or "").lower()
            score = 0
            if any(h in text for h in self._FOLLOWUP_ANCHOR_HINTS):
                score += 10
            if any(h in path for h in self._FOLLOWUP_PATH_HINTS):
                score += 8
            if "commission" in text or "commission" in path:
                score += 6
            if "video" in text or "video" in path:
                score += 4
            if score <= 0:
                continue

            norm = f"{parsed.scheme}://{parsed.netloc}{path}".rstrip("/") or absolute
            if norm in seen:
                continue
            seen.add(norm)
            scored.append((score, absolute))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [u for _, u in scored[:max_pages]]

    async def _fetch_page_html(self, url: str) -> tuple[Optional[str], str]:
        """httpx (+ VPN bypass), then Playwright when the plain GET fails entirely."""
        try:
            response = await async_get_with_vpn_bypass(self.client, url)
            if response.status_code == 200 and (response.text or "").strip():
                return response.text, ""
        except Exception as exc:
            logger.debug(f"httpx fetch failed for {url}: {exc}")

        html = await self._fetch_search_html_via_playwright(url)
        if html:
            logger.info(f"YouTube scrape: Playwright recovered HTML for {url}")
            return html, ""
        return None, "fetch_failed"

    async def _scrape_website_for_channels(self, url: str) -> List[str]:
        """Scrape a website for YouTube channel links.

        Layered fallback:

        1. Extract YouTube links from the seed page HTML (anchors, iframes, embedded URLs).
        2. If none: follow same-host commission/meeting/video pages (e.g. ``/commission/``).
        3. If none: site search via httpx (capped), then Playwright on a few search URLs.
        """
        channels: list[str] = []
        seen: set[str] = set()

        def add_channels(items: list[str]) -> None:
            for item in items:
                if item and item not in seen:
                    seen.add(item)
                    channels.append(item)

        followup_max = self._youtube_int_env("YOUTUBE_WEBSITE_FOLLOWUP_MAX", 12)
        search_http_max = self._youtube_int_env("YOUTUBE_SITE_SEARCH_HTTP_MAX", 8)
        search_pw_max = self._youtube_int_env("YOUTUBE_SITE_SEARCH_PLAYWRIGHT_MAX", 2)

        homepage_html, _err = await self._fetch_page_html(url)
        if homepage_html:
            add_channels(self._extract_youtube_links_from_html(homepage_html, base_url=url))
        else:
            logger.debug(f"Could not load homepage HTML for YouTube scrape: {url}")

        if channels:
            return channels

        if not homepage_html:
            # Avoid dozens of blind search/Playwright probes when the seed page never loaded.
            search_http_max = min(search_http_max, 3)
            search_pw_max = 0

        if homepage_html and followup_max > 0:
            for follow_url in self._collect_youtube_followup_page_urls(
                homepage_html, base_url=url, max_pages=followup_max
            ):
                page_html, _ = await self._fetch_page_html(follow_url)
                if not page_html:
                    continue
                add_channels(self._extract_youtube_links_from_html(page_html, base_url=follow_url))
                if channels:
                    logger.info(
                        "YouTube channel(s) from follow-up page {follow} (seed {seed})",
                        follow=follow_url,
                        seed=url,
                    )
                    return channels

        attempted_search_urls: list[str] = []
        http_attempts = 0

        for query in self._SITE_SEARCH_QUERIES:
            discovered_urls = (
                self._discover_site_search_urls(homepage_html, base_url=url, query=query)
                if homepage_html
                else []
            )
            guessed_urls = self._build_site_search_urls(url, query=query)
            for search_url in (*discovered_urls, *guessed_urls):
                if search_url in attempted_search_urls:
                    continue
                if http_attempts >= search_http_max:
                    break
                attempted_search_urls.append(search_url)
                http_attempts += 1
                try:
                    search_resp = await async_get_with_vpn_bypass(self.client, search_url)
                    if search_resp.status_code == 200:
                        add_channels(
                            self._extract_youtube_links_from_html(
                                search_resp.text, base_url=search_url
                            )
                        )
                except Exception as exc:
                    logger.trace(f"Site search scrape failed for {search_url}: {exc}")
                if channels:
                    return channels
            if http_attempts >= search_http_max:
                break

        for search_url in attempted_search_urls[:search_pw_max]:
            html = await self._fetch_search_html_via_playwright(search_url)
            if not html:
                continue
            add_channels(self._extract_youtube_links_from_html(html, base_url=search_url))
            if channels:
                break

        return channels

    def _build_site_search_urls(self, homepage_url: str, query: str) -> list[str]:
        parsed = urlparse(homepage_url)
        if not parsed.scheme or not parsed.netloc:
            return []

        base = f"{parsed.scheme}://{parsed.netloc}"
        q = quote_plus(query)
        return [
            f"{base}/search?q={q}",
            f"{base}/search?query={q}",
            f"{base}/search-results?q={q}",
            f"{base}/search-results?query={q}",
            f"{base}/?s={q}",
        ]

    # Heuristic markers used to identify a search <form> on a homepage.
    _SEARCH_FORM_HINTS = ("search", "find", "query")
    # Common names/ids for the actual text input within a search form.
    _SEARCH_INPUT_NAMES = ("q", "query", "s", "search", "searchtext", "keywords", "k")

    def _discover_site_search_urls(
        self, html: str, *, base_url: str, query: str
    ) -> list[str]:
        """Find the site's real search endpoint by inspecting homepage forms.

        Returns absolute GET URLs (form action + query string) for every
        plausible search form on the page. Returns an empty list when
        nothing search-like is found.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return []

        urls: list[str] = []
        seen: set[str] = set()

        for form in soup.find_all("form"):
            method = (form.get("method") or "get").strip().lower()
            if method != "get":
                # POST forms can't be replayed via a simple GET; skip.
                continue

            action = str(form.get("action") or "").strip()
            form_blob = " ".join(
                str(form.get(attr) or "") for attr in ("id", "class", "name", "role", "action")
            ).lower()
            if not any(hint in form_blob for hint in self._SEARCH_FORM_HINTS):
                # Form doesn't self-identify as search-related; skip to
                # avoid hitting login/newsletter endpoints with our query.
                if not any(hint in action.lower() for hint in self._SEARCH_FORM_HINTS):
                    continue

            input_name = self._pick_search_input_name(form)
            if not input_name:
                continue

            action_url = urljoin(base_url, action) if action else base_url
            extras = self._collect_hidden_form_params(form, exclude=input_name)
            params = [(input_name, query), *extras]
            qs = "&".join(f"{quote_plus(k)}={quote_plus(v)}" for k, v in params)
            full_url = f"{action_url}?{qs}" if qs else action_url
            if full_url not in seen:
                seen.add(full_url)
                urls.append(full_url)

        return urls

    def _pick_search_input_name(self, form: Any) -> Optional[str]:
        """Return the most likely search-input name within ``form``."""
        text_inputs: list[tuple[int, str]] = []
        for inp in form.find_all("input"):
            itype = (inp.get("type") or "text").strip().lower()
            if itype not in ("text", "search", ""):
                continue
            name = (inp.get("name") or "").strip()
            if not name:
                continue
            # Lower score = better match (we sort ascending).
            lowered = name.lower()
            try:
                priority = self._SEARCH_INPUT_NAMES.index(lowered)
            except ValueError:
                priority = len(self._SEARCH_INPUT_NAMES)
            text_inputs.append((priority, name))

        if not text_inputs:
            return None
        text_inputs.sort(key=lambda item: item[0])
        return text_inputs[0][1]

    def _collect_hidden_form_params(
        self, form: Any, *, exclude: str
    ) -> list[tuple[str, str]]:
        """Return hidden ``<input>`` name/value pairs so we replay the form intact."""
        params: list[tuple[str, str]] = []
        for inp in form.find_all("input"):
            itype = (inp.get("type") or "").strip().lower()
            if itype != "hidden":
                continue
            name = (inp.get("name") or "").strip()
            if not name or name == exclude:
                continue
            value = str(inp.get("value") or "")
            params.append((name, value))
        return params

    async def _fetch_search_html_via_playwright(self, url: str) -> Optional[str]:
        """Render ``url`` with Playwright; return HTML or ``None`` on failure.

        Used as the final tier of site-search fallback when the static
        HTML returned by httpx contained no YouTube channel links — many
        municipal sites (CivicPlus, Granicus) render search results via
        JavaScript so the link list is invisible without a browser.
        """
        try:
            from scripts.discovery.meetings_playwright_fetch import (
                fetch_html_via_playwright,
                playwright_fallback_enabled,
            )
        except ImportError:
            return None

        if not playwright_fallback_enabled():
            return None

        user_agent = self.client.headers.get(
            "User-Agent",
            "Mozilla/5.0 (compatible; OralHealthPolicyBot/2.0)",
        )
        try:
            html, reason, _final = await fetch_html_via_playwright(
                url,
                timeout_ms=20_000,
                user_agent=user_agent,
            )
        except Exception as exc:
            logger.trace(f"Playwright site-search fetch failed for {url}: {exc}")
            return None

        if not html:
            logger.trace(f"Playwright site-search produced no html for {url}: {reason}")
            return None
        return html

    def _extract_youtube_links_from_html(self, html: str, *, base_url: str) -> list[str]:
        channels: list[str] = []
        seen: set[str] = set()

        def _add(candidate: str) -> None:
            normalized = self._normalize_youtube_channel_url(candidate)
            if normalized and normalized not in seen:
                seen.add(normalized)
                channels.append(normalized)

        if not (html or "").strip():
            return channels

        for match in re.finditer(
            r"https?://(?:www\.)?youtube\.com/(?:channel/[A-Za-z0-9_-]+|@[A-Za-z0-9_-]+|user/[A-Za-z0-9_-]+|c/[A-Za-z0-9_-]+)",
            html,
            re.IGNORECASE,
        ):
            _add(match.group(0))

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return channels

        for link in soup.find_all("a", href=True):
            href = str(link.get("href") or "").strip()
            _add(urljoin(base_url, href))

        for tag in soup.find_all(["iframe", "embed"]):
            for attr in ("src", "data-src", "href"):
                raw = str(tag.get(attr) or "").strip()
                if raw:
                    _add(urljoin(base_url, raw))

        return channels

    def _normalize_youtube_channel_url(self, url: str) -> Optional[str]:
        candidate = (url or "").strip()
        if not candidate:
            return None

        match = re.search(
            r"(?:https?://)?(?:www\.)?youtube\.com/("
            r"@[A-Za-z0-9_-]+|"
            r"channel/[A-Za-z0-9_-]+|"
            r"user/[A-Za-z0-9_-]+|"
            r"c/[A-Za-z0-9_-]+)",
            candidate,
            re.IGNORECASE,
        )
        if not match:
            return None

        return f"https://www.youtube.com/{match.group(1)}"
    
    async def _search_youtube_api(
        self,
        city_name: str,
        state_code: str
    ) -> List[Dict]:
        """
        Search YouTube API for channels matching city name.
        
        Requires YouTube Data API v3 key.
        """
        if not self.api_key:
            return []
        
        channels = []
        
        try:
            # Search for channels
            search_query = f"{city_name} {state_code} government"
            api_url = "https://www.googleapis.com/youtube/v3/search"
            
            params = {
                "part": "snippet",
                "q": search_query,
                "type": "channel",
                "maxResults": 10,
                "key": self.api_key
            }
            
            response = await async_get_with_vpn_bypass(self.client, api_url, params=params)
            data = response.json()
            
            if "items" in data:
                for item in data["items"]:
                    channel_id = item["id"]["channelId"]
                    title = item["snippet"]["title"]
                    
                    # Get channel statistics
                    stats_url = "https://www.googleapis.com/youtube/v3/channels"
                    stats_params = {
                        "part": "statistics,snippet",
                        "id": channel_id,
                        "key": self.api_key
                    }
                    
                    stats_response = await async_get_with_vpn_bypass(
                        self.client, stats_url, params=stats_params
                    )
                    stats_data = stats_response.json()
                    
                    if "items" in stats_data and stats_data["items"]:
                        stats = stats_data["items"][0]["statistics"]
                        
                        channels.append({
                            "channel_url": f"https://www.youtube.com/channel/{channel_id}",
                            "channel_id": channel_id,
                            "channel_title": title,
                            "video_count": int(stats.get("videoCount", 0)),
                            "subscriber_count": int(stats.get("subscriberCount", 0)),
                            "view_count": int(stats.get("viewCount", 0)),
                            "discovery_method": "youtube_api",
                            "confidence": 0.95
                        })
        
        except Exception as e:
            logger.warning(f"YouTube API search failed: {e}")

        return channels

    async def _search_youtube_by_domain(self, homepage_url: str) -> List[Dict]:
        """
        Search YouTube Data API for channels whose title/description mentions the
        jurisdiction's bare host (e.g. ``cambridgema.gov``, ``co.adams.wa.us``).

        Rationale: domains are unique; name-token searches collide ("Adams" returns
        "John Adams", "Mass B TV", etc.). A channel that puts the jurisdiction's
        website in its About text is overwhelmingly that jurisdiction's channel.

        Returns channel dicts with ``discovery_method='domain_search'`` and
        ``confidence=0.98`` when the queried host appears in the channel description,
        else ``confidence=0.85``.
        """
        if not self.api_key or not homepage_url:
            return []

        host = (urlparse(homepage_url).netloc or "").lower()
        host = re.sub(r"^www\.", "", host)
        if not host or "." not in host:
            return []

        channels: List[Dict[str, Any]] = []
        try:
            search_resp = await async_get_with_vpn_bypass(
                self.client,
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": host,
                    "type": "channel",
                    "maxResults": 10,
                    "key": self.api_key,
                },
            )
            search_data = search_resp.json()
            for item in search_data.get("items", []):
                cid = item.get("id", {}).get("channelId")
                if not cid:
                    continue
                title = item.get("snippet", {}).get("title", "")
                # Pull full statistics + description so we can confirm the back-link
                # without a second fetch from the enricher.
                stats_resp = await async_get_with_vpn_bypass(
                    self.client,
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={
                        "part": "statistics,snippet",
                        "id": cid,
                        "key": self.api_key,
                    },
                )
                stats_items = stats_resp.json().get("items") or []
                if not stats_items:
                    continue
                stats = stats_items[0].get("statistics", {})
                snippet = stats_items[0].get("snippet", {})
                full_description = (snippet.get("description") or "").lower()

                domain_in_description = host in full_description
                channels.append({
                    "channel_url": f"https://www.youtube.com/channel/{cid}",
                    "channel_id": cid,
                    "channel_title": title,
                    "video_count": int(stats.get("videoCount", 0) or 0),
                    "subscriber_count": int(stats.get("subscriberCount", 0) or 0),
                    "view_count": int(stats.get("viewCount", 0) or 0),
                    "discovery_method": "domain_search",
                    "confidence": 0.98 if domain_in_description else 0.85,
                    "domain_search_host": host,
                    "domain_in_description": domain_in_description,
                })
        except Exception as e:
            logger.warning(f"YouTube domain search failed for {host}: {e}")

        return channels

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.close()


# Example usage
async def main():
    """Example: Discover all Tuscaloosa YouTube channels."""
    
    # Initialize (with or without API key)
    async with YouTubeChannelDiscovery() as discovery:
        
        channels = await discovery.discover_channels(
            city_name="Tuscaloosa",
            state_code="AL",
            county_name="Tuscaloosa County",
            homepage_url="https://www.tuscaloosa.com"
        )
        
        print(f"\n{'='*70}")
        print(f"FOUND {len(channels)} YOUTUBE CHANNELS")
        print(f"{'='*70}\n")
        
        for i, channel in enumerate(channels, 1):
            print(f"{i}. {channel['channel_url']}")
            print(f"   Title: {channel['channel_title']}")
            print(f"   Videos: {channel['video_count']:,}")
            print(f"   Subscribers: {channel.get('subscriber_count', 0):,}")
            print(f"   Method: {channel['discovery_method']}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
