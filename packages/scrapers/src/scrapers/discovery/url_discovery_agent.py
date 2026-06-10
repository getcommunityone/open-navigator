"""
URL Discovery Agent - Pattern-Based Approach

Discovers official government websites using sustainable, vendor-neutral methods:

✅ Pattern Matching: Generate URLs from jurisdiction names using common patterns
✅ GSA Domain Matching: Direct matching with .gov domain registry
✅ Web Crawling & Verification: Test candidate URLs and discover minutes pages
✅ CMS Detection: Identify government CMS platforms
✅ Confidence Scoring: Rank results by validation signals

This approach is:
✅ Free (no API costs)
✅ Reliable (no API quotas or rate limits)
✅ Reproducible (deterministic patterns)
✅ Sustainable (vendor-neutral, future-proof)

Note: Does NOT use Google Custom Search or Bing APIs - those are deprecated
for production use and not recommended for new systems.
"""
import asyncio
import re
from typing import List, Optional, Set, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from difflib import SequenceMatcher


@dataclass
class JurisdictionURL:
    """Discovered URL for a jurisdiction."""
    jurisdiction_id: str
    jurisdiction_name: str
    state: str
    homepage_url: Optional[str] = None
    minutes_url: Optional[str] = None
    cms_platform: Optional[str] = None
    is_gov_domain: bool = False
    discovery_method: str = "unknown"
    confidence_score: float = 0.0
    last_verified: Optional[datetime] = None


class URLDiscoveryAgent:
    """Pattern-based URL discovery agent."""
    
    # CMS platform signatures
    CMS_SIGNATURES = {
        "granicus": ["granicus.com", "legistar.com"],
        "civicclerk": ["civicclerk.com", "civicweb.net"],
        "municode": ["municode.com"],
        "laserfiche": ["laserfiche.com"],
        "primegov": ["primegov.com"],
        "govos": ["govos.com"],
        "swagit": ["swagit.com"]
    }
    
    # Minutes page keywords
    MINUTES_KEYWORDS = [
        "minutes", "agendas", "meetings", "council", "board",
        "government", "sessions", "agenda center"
    ]
    
    def __init__(self, gsa_domains: Set[str], gsa_domain_data: Optional[List[Dict]] = None):
        """
        Initialize discovery agent.
        
        Args:
            gsa_domains: Set of .gov domains from GSA registry
            gsa_domain_data: Full GSA domain data with org names
        """
        self.gsa_domains = gsa_domains
        self.gsa_domain_data = gsa_domain_data or []
        self.client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; OralHealthPolicyBot/2.0)"
            }
        )
        
        # Build fast lookup index
        self.domain_lookup = self._build_domain_lookup()
        
    def _build_domain_lookup(self) -> Dict[str, Dict]:
        """Build normalized name -> domain lookup."""
        lookup = {}
        for item in self.gsa_domain_data:
            org_name = item.get("Organization", "")
            if org_name:
                normalized = self._normalize_name(org_name)
                lookup[normalized] = item
        return lookup
    
    def _normalize_name(self, name: str) -> str:
        """Normalize jurisdiction name for matching."""
        name = name.lower()
        # Remove common prefixes/suffixes
        name = re.sub(r'\b(city of|town of|county of|village of|township of)\b', '', name)
        name = re.sub(r'\b(government|county|city|town)\b', '', name)
        name = re.sub(r'[^a-z0-9\s]', '', name)
        return ' '.join(name.split()).strip()
    
    def _similarity_score(self, str1: str, str2: str) -> float:
        """Calculate string similarity (0-1)."""
        return SequenceMatcher(None, str1, str2).ratio()
    
    def _generate_url_patterns(self, jurisdiction_name: str, state: str, 
                               jurisdiction_type: str) -> List[Tuple[str, float]]:
        """
        Generate candidate URLs using common government patterns.
        
        Government URLs typically follow predictable patterns based on:
        - Jurisdiction type (county, city, school district)
        - Naming conventions (.gov, .us, .org)
        - Common formats (cityofX, co.X, Xschools)
        
        Args:
            jurisdiction_name: Name (e.g., "Sacramento")
            state: State abbreviation (e.g., "CA")
            jurisdiction_type: Type (county, municipality, school_district, etc.)
            
        Returns:
            List of (url, confidence_score) tuples
        """
        # Normalize name for URLs
        name_clean = self._normalize_name(jurisdiction_name)
        name_slug = name_clean.replace(' ', '')
        name_dash = name_clean.replace(' ', '-')
        state_lower = state.lower()
        
        patterns = []
        
        if jurisdiction_type == "county":
            # County URL patterns
            patterns.extend([
                (f"https://www.co.{name_slug}.{state_lower}.us", 0.9),
                (f"https://{name_slug}county.gov", 0.9),
                (f"https://www.{name_slug}county.gov", 0.85),
                (f"https://{name_slug}.{state_lower}.gov", 0.8),
                (f"https://www.{name_slug}county.us", 0.7),
                (f"https://co-{name_dash}.{state_lower}.gov", 0.75),
                (f"https://{name_slug}county.org", 0.6),
            ])
            
        elif jurisdiction_type == "municipality":
            # City/town URL patterns
            patterns.extend([
                (f"https://www.{name_slug}.gov", 0.9),
                (f"https://{name_slug}.gov", 0.9),
                (f"https://www.cityof{name_slug}.gov", 0.85),
                (f"https://cityof{name_slug}.gov", 0.85),
                (f"https://www.{name_slug}.{state_lower}.gov", 0.8),
                (f"https://{name_slug}.{state_lower}.gov", 0.8),
                (f"https://www.{name_dash}.gov", 0.75),
                (f"https://www.{name_slug}.us", 0.7),
                (f"https://{name_slug}.us", 0.7),
                (f"https://www.{name_slug}.org", 0.6),
            ])
            
        elif jurisdiction_type == "school_district":
            # School district patterns
            patterns.extend([
                (f"https://www.{name_slug}schools.org", 0.8),
                (f"https://{name_slug}schools.org", 0.8),
                (f"https://www.{name_slug}schools.net", 0.75),
                (f"https://www.{name_slug}sd.org", 0.75),
                (f"https://{name_slug}sd.org", 0.75),
                (f"https://www.{name_slug}.k12.{state_lower}.us", 0.85),
                (f"https://{name_slug}.k12.{state_lower}.us", 0.85),
                (f"https://www.{name_slug}usd.org", 0.7),
            ])
            
        elif jurisdiction_type == "township":
            # Township patterns
            patterns.extend([
                (f"https://www.{name_slug}township.gov", 0.8),
                (f"https://{name_slug}township.gov", 0.8),
                (f"https://www.{name_slug}.{state_lower}.gov", 0.75),
                (f"https://{name_slug}twp.org", 0.7),
            ])
            
        else:
            # Generic patterns for special districts, etc.
            patterns.extend([
                (f"https://www.{name_slug}.gov", 0.7),
                (f"https://{name_slug}.gov", 0.7),
                (f"https://www.{name_slug}.org", 0.5),
                (f"https://{name_slug}.org", 0.5),
            ])
        
        return patterns
    
    def _match_gsa_domain(self, jurisdiction_name: str, state: str) -> Optional[Tuple[str, float]]:
        """
        Match jurisdiction to GSA .gov domain registry.
        
        Uses exact and fuzzy matching against the authoritative list.
        
        Args:
            jurisdiction_name: Jurisdiction name
            state: State name or abbreviation
            
        Returns:
            (domain_url, confidence) tuple or None
        """
        normalized_name = self._normalize_name(jurisdiction_name)
        
        # Try exact match first
        if normalized_name in self.domain_lookup:
            domain_info = self.domain_lookup[normalized_name]
            domain = domain_info.get("Domain Name", "")
            if domain:
                return (f"https://{domain}", 1.0)
        
        # Fuzzy matching with state filter
        best_match = None
        best_score = 0.0
        
        for org_name, domain_info in self.domain_lookup.items():
            # Filter by state
            domain_state = domain_info.get("State", "")
            if domain_state and domain_state.lower() not in [state.lower(), state[:2].lower()]:
                continue
            
            # Calculate similarity
            score = self._similarity_score(normalized_name, org_name)
            if score > best_score and score > 0.75:  # High threshold for fuzzy
                best_score = score
                domain = domain_info.get("Domain Name", "")
                if domain:
                    best_match = (f"https://{domain}", score * 0.95)  # Slight penalty for fuzzy
        
        return best_match
    
    async def _verify_url(self, url: str) -> bool:
        """
        Verify URL is accessible.
        
        Args:
            url: URL to check
            
        Returns:
            True if accessible (status < 400)
        """
        try:
            response = await self.client.head(url, timeout=10.0)
            return response.status_code < 400
        except:
            # Some servers don't support HEAD, try GET
            try:
                response = await self.client.get(url, timeout=10.0)
                return response.status_code < 400
            except:
                return False
    
    async def crawl_for_minutes(self, homepage_url: str) -> Optional[str]:
        """
        Crawl homepage to find meeting minutes/agendas page.
        
        Args:
            homepage_url: Homepage URL
            
        Returns:
            Minutes page URL or None
        """
        try:
            response = await self.client.get(homepage_url, timeout=15.0)
            if response.status_code >= 400:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Search for links containing keywords
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text(strip=True).lower()
                
                # Check text and href for keywords
                combined = f"{text} {href}".lower()
                if any(keyword in combined for keyword in self.MINUTES_KEYWORDS):
                    # Construct absolute URL
                    full_url = urljoin(homepage_url, href)
                    return full_url
            
            return None
            
        except Exception as e:
            logger.debug(f"Error crawling {homepage_url}: {e}")
            return None
    
    async def detect_cms_platform(self, url: str) -> Optional[str]:
        """
        Detect government CMS platform.
        
        Args:
            url: URL to check
            
        Returns:
            CMS platform name or None
        """
        try:
            response = await self.client.get(url, timeout=15.0)
            if response.status_code >= 400:
                return None
            
            html = response.text.lower()
            final_url = str(response.url).lower()
            
            # Check URL and HTML for CMS signatures
            for cms, signatures in self.CMS_SIGNATURES.items():
                if any(sig in final_url or sig in html for sig in signatures):
                    return cms
            
            return None
            
        except Exception as e:
            logger.debug(f"Error detecting CMS for {url}: {e}")
            return None
    
    def _calculate_confidence(
        self,
        base_confidence: float,
        is_gov_domain: bool,
        has_minutes_url: bool,
        has_cms_platform: bool
    ) -> float:
        """Calculate final confidence score."""
        confidence = base_confidence
        
        # Bonuses for positive signals
        if is_gov_domain:
            confidence = min(confidence + 0.1, 1.0)
        if has_minutes_url:
            confidence = min(confidence + 0.1, 1.0)
        if has_cms_platform:
            confidence = min(confidence + 0.05, 1.0)
        
        return confidence
    
    async def _analyze_url(
        self, 
        url: str, 
        jurisdiction_id: str, 
        jurisdiction_name: str,
        state: str, 
        discovery_method: str, 
        base_confidence: float
    ) -> JurisdictionURL:
        """
        Analyze discovered URL for minutes and CMS.
        
        Args:
            url: Homepage URL
            jurisdiction_id: Jurisdiction ID
            jurisdiction_name: Jurisdiction name
            state: State
            discovery_method: How URL was found
            base_confidence: Base confidence score
            
        Returns:
            Complete JurisdictionURL object
        """
        # Check if .gov domain
        domain = urlparse(url).netloc
        is_gov_domain = domain in self.gsa_domains or domain.endswith('.gov')
        
        # Find minutes page
        minutes_url = await self.crawl_for_minutes(url)
        
        # Detect CMS
        cms_platform = await self.detect_cms_platform(url)
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            base_confidence=base_confidence,
            is_gov_domain=is_gov_domain,
            has_minutes_url=minutes_url is not None,
            has_cms_platform=cms_platform is not None
        )
        
        return JurisdictionURL(
            jurisdiction_id=jurisdiction_id,
            jurisdiction_name=jurisdiction_name,
            state=state,
            homepage_url=url,
            minutes_url=minutes_url,
            cms_platform=cms_platform,
            is_gov_domain=is_gov_domain,
            discovery_method=discovery_method,
            confidence_score=confidence,
            last_verified=datetime.now()
        )
    
    async def discover_jurisdiction(
        self, 
        jurisdiction_id: str,
        jurisdiction_name: str,
        state: str,
        jurisdiction_type: str
    ) -> JurisdictionURL:
        """
        Discover URLs for a jurisdiction using pattern-based approach.
        
        Strategy:
        1. Try GSA domain registry matching (highest confidence)
        2. Try common URL patterns (good confidence)
        3. Verify and analyze discovered URLs
        
        Args:
            jurisdiction_id: Unique ID (FIPS code)
            jurisdiction_name: Name
            state: State name
            jurisdiction_type: Type (county, municipality, etc.)
            
        Returns:
            JurisdictionURL with discovered info
        """
        logger.debug(f"Discovering: {jurisdiction_name}, {state} ({jurisdiction_type})")
        
        # Strategy 1: GSA domain matching (most reliable)
        gsa_match = self._match_gsa_domain(jurisdiction_name, state)
        if gsa_match:
            url, confidence = gsa_match
            if await self._verify_url(url):
                logger.info(f"✓ GSA match: {jurisdiction_name} -> {url}")
                return await self._analyze_url(
                    url, jurisdiction_id, jurisdiction_name, 
                    state, "gsa_registry", confidence
                )
        
        # Strategy 2: URL pattern matching
        patterns = self._generate_url_patterns(jurisdiction_name, state, jurisdiction_type)
        
        for url, pattern_confidence in patterns:
            if await self._verify_url(url):
                logger.info(f"✓ Pattern match: {jurisdiction_name} -> {url}")
                return await self._analyze_url(
                    url, jurisdiction_id, jurisdiction_name,
                    state, "pattern_match", pattern_confidence
                )
        
        # No valid URL found
        logger.warning(f"✗ No URL found for {jurisdiction_name}, {state}")
        return JurisdictionURL(
            jurisdiction_id=jurisdiction_id,
            jurisdiction_name=jurisdiction_name,
            state=state,
            discovery_method="not_found"
        )
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
