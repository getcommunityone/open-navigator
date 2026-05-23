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
        self.client = httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OralHealthPolicyBot/2.0)"}
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
        
        for handle in patterns_to_test:
            url = f"https://www.youtube.com/@{handle}"
            
            if url in tested_urls:
                continue
            tested_urls.add(url)
            
            channel_info = await self._check_channel_exists(url, "pattern_match")
            if channel_info:
                discovered.append(channel_info)
                logger.success(f"✓ Found: {url} ({channel_info['video_count']} videos)")
            
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

            response = await self.client.get(channel_url)
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
                "confidence": 0.9 if discovery_method == "website_scrape" else 0.7,
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
    
    async def _scrape_website_for_channels(self, url: str) -> List[str]:
        """Scrape a website for YouTube channel links.

        Behavior: scrape homepage first; only if no YouTube link is found,
        try common site-search URL patterns for query "youtube".
        """
        channels: list[str] = []
        seen: set[str] = set()

        def add_channels(items: list[str]) -> None:
            for item in items:
                if item and item not in seen:
                    seen.add(item)
                    channels.append(item)

        try:
            response = await self.client.get(url)
            add_channels(self._extract_youtube_links_from_html(response.text, base_url=url))

            # Fallback to site search only when direct-page extraction fails.
            if not channels:
                for search_url in self._build_site_search_urls(url, query="youtube"):
                    try:
                        search_resp = await self.client.get(search_url)
                        add_channels(self._extract_youtube_links_from_html(search_resp.text, base_url=search_url))
                    except Exception as exc:
                        logger.trace(f"Site search scrape failed for {search_url}: {exc}")

        except Exception as e:
            logger.debug(f"Error scraping {url}: {e}")

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

    def _extract_youtube_links_from_html(self, html: str, *, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        channels: list[str] = []
        seen: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = str(link.get("href") or "").strip()
            absolute = urljoin(base_url, href)
            normalized = self._normalize_youtube_channel_url(absolute)
            if normalized and normalized not in seen:
                seen.add(normalized)
                channels.append(normalized)

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
            
            response = await self.client.get(api_url, params=params)
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
                    
                    stats_response = await self.client.get(stats_url, params=stats_params)
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
