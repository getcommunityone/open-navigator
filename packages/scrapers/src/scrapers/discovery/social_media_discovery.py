"""
Social Media & Video Channel Discovery from Government Websites

Discovers YouTube, Facebook, Vimeo, and other video channels by crawling
official government websites - specifically footer sections and contact pages.

This complements dataset-based discovery (MeetingBank, Open States) with
real-time web scraping to find channels that aren't in existing datasets.

Data Sources:
1. Government homepages (from url_discovery_agent)
2. USA.gov Local Directory (optional federal verification)
3. Common footer/contact page patterns

Pattern Examples:
- Footer: <a href="https://www.youtube.com/@cityofseattle">YouTube</a>
- Contact: "Follow us on YouTube: youtube.com/c/CityName"
- Social icons: <a class="social-youtube" href="...">
"""
import asyncio
import re
from typing import List, Dict, Optional, Set
from urllib.parse import urlparse, urljoin
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from loguru import logger

from scrapers.discovery.scrape_http import async_get_with_vpn_bypass, make_scrape_async_client


class SocialMediaDiscovery:
    """
    Discovers social media and video channels from government websites.
    
    Focuses on:
    - YouTube channels (primary for meeting videos)
    - Vimeo accounts
    - Facebook pages (often link to videos)
    - Archive.org collections
    - Granicus portals
    """
    
    SOCIAL_PATTERNS = {
        'youtube': [
            r'youtube\.com/(?:c/|channel/|user/|@)([\w-]+)',
            r'youtube\.com/(?:c/|channel/|user/|@)?([\w-]{24})',  # Channel ID
            r'youtu\.be/([\w-]+)',
        ],
        'vimeo': [
            r'vimeo\.com/([\w-]+)',
            r'player\.vimeo\.com/video/([\d]+)',
        ],
        'facebook': [
            r'facebook\.com/([\w.-]+)',
            r'fb\.com/([\w.-]+)',
        ],
        'twitter': [
            r'twitter\.com/([\w]+)',
            r'x\.com/([\w]+)',
        ],
        'archive_org': [
            r'archive\.org/details/([\w-]+)',
        ],
        'granicus': [
            r'granicus\.com/ViewPublisher\.php\?view_id=([\d]+)',
            r'[\w-]+\.granicus\.com',
        ]
    }
    
    # Common footer/contact page patterns
    FOOTER_SELECTORS = [
        'footer',
        '[class*="footer"]',
        '[id*="footer"]',
        '[class*="social"]',
        '[class*="connect"]',
    ]
    
    CONTACT_URLS = [
        '/contact',
        '/contact-us',
        '/about',
        '/about-us',
        '/connect',
        '/social-media',
    ]
    
    def __init__(self):
        """Initialize social media discovery."""
        self.client = make_scrape_async_client(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; OralHealthPolicyBot/2.0)"
            },
        )
        
        # Keywords that indicate official government channels likely to have policy/meeting content
        self.official_keywords = (
            'city', 'town', 'county', 'government', 'gov', 'official', 
            'municipal', 'municipality', 'council', 'city council', 
            'town council', 'board', 'commission', 'public', 'clerk',
            'meeting', 'session', 'chamber'
        )
    
    def _is_likely_official_channel(self, url: str, jurisdiction_name: str) -> bool:
        """
        Check if a social media URL is likely an official government channel.
        
        Prioritizes channels with:
        - Jurisdiction name in the URL
        - Official government keywords (city, council, government, etc.)
        - Meeting/policy related terms
        
        Args:
            url: Social media URL to check
            jurisdiction_name: Name of the jurisdiction
            
        Returns:
            True if likely an official government channel
        """
        url_lower = url.lower()
        jurisdiction_lower = jurisdiction_name.lower().replace(' ', '')
        
        # High priority: URL contains jurisdiction name
        if jurisdiction_lower in url_lower:
            return True
        
        # Medium priority: URL contains official government keywords
        if any(keyword in url_lower for keyword in self.official_keywords):
            return True
        
        return False
    
    async def discover_from_website(
        self,
        homepage_url: str,
        jurisdiction_name: str,
        state: str
    ) -> Dict[str, List[str]]:
        """
        Discover social media and video channels from a government website.
        
        Process:
        1. Check homepage footer for social links
        2. Check common contact/about pages
        3. Extract and validate URLs
        4. Categorize by platform
        
        Args:
            homepage_url: Government website URL
            jurisdiction_name: Name of jurisdiction
            state: State abbreviation
            
        Returns:
            Dictionary of platform -> list of URLs
            {
                'youtube': ['https://youtube.com/@cityname'],
                'vimeo': [...],
                'facebook': [...],
                'granicus': [...]
            }
        """
        logger.info(f"Discovering social media for {jurisdiction_name}, {state}")
        
        discovered = {
            'youtube': [],
            'vimeo': [],
            'facebook': [],
            'twitter': [],
            'archive_org': [],
            'granicus': []
        }
        
        # 1. Scrape homepage
        homepage_links = await self._scrape_page_for_social(homepage_url)
        for platform, urls in homepage_links.items():
            discovered[platform].extend(urls)
        
        # 2. Check contact pages
        for contact_path in self.CONTACT_URLS:
            contact_url = urljoin(homepage_url, contact_path)
            
            try:
                contact_links = await self._scrape_page_for_social(contact_url)
                for platform, urls in contact_links.items():
                    discovered[platform].extend(urls)
                
                # Rate limiting
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.debug(f"Could not check {contact_url}: {e}")
        
        # 3. Deduplicate and prioritize official channels
        for platform in discovered:
            unique_urls = list(set(discovered[platform]))
            
            # Separate official and non-official channels
            official = [url for url in unique_urls if self._is_likely_official_channel(url, jurisdiction_name)]
            non_official = [url for url in unique_urls if not self._is_likely_official_channel(url, jurisdiction_name)]
            
            # Prioritize official channels
            discovered[platform] = official + non_official
        
        # 4. Log findings with official channel indicators
        total = sum(len(urls) for urls in discovered.values())
        if total > 0:
            logger.success(f"✓ Found {total} social media links for {jurisdiction_name}")
            for platform, urls in discovered.items():
                if urls:
                    official_count = sum(1 for url in urls if self._is_likely_official_channel(url, jurisdiction_name))
                    logger.info(f"  {platform}: {len(urls)} URLs ({official_count} official)")
        else:
            logger.debug(f"No social media found for {jurisdiction_name}")
        
        return discovered
    
    async def _scrape_page_for_social(self, url: str) -> Dict[str, List[str]]:
        """
        Scrape a single page for social media links.
        
        Strategy:
        1. Focus on footer/social sections (most reliable)
        2. Extract all links from page
        3. Pattern match against known platforms
        4. Validate and clean URLs
        
        Args:
            url: Page URL to scrape
            
        Returns:
            Dictionary of platform -> URLs found on this page
        """
        found = {platform: [] for platform in self.SOCIAL_PATTERNS.keys()}
        
        try:
            response = await async_get_with_vpn_bypass(self.client, url)
            
            if response.status_code != 200:
                return found
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Strategy 1: Check footer sections (most reliable)
            footer_links = set()
            for selector in self.FOOTER_SELECTORS:
                footer_elements = soup.select(selector)
                for footer in footer_elements:
                    links = footer.find_all('a', href=True)
                    footer_links.update(link['href'] for link in links)
            
            # Strategy 2: Check all links if footer is empty
            if not footer_links:
                all_links = soup.find_all('a', href=True)
                footer_links = set(link['href'] for link in all_links)
            
            # Extract social media URLs
            for link in footer_links:
                # Handle relative URLs
                if link.startswith('/'):
                    link = urljoin(url, link)
                
                # Pattern match against each platform
                for platform, patterns in self.SOCIAL_PATTERNS.items():
                    for pattern in patterns:
                        match = re.search(pattern, link, re.IGNORECASE)
                        if match:
                            # Clean and validate URL
                            clean_url = self._clean_social_url(link, platform)
                            if clean_url and clean_url not in found[platform]:
                                found[platform].append(clean_url)
            
        except Exception as e:
            logger.debug(f"Error scraping {url}: {e}")
        
        return found
    
    def _clean_social_url(self, url: str, platform: str) -> Optional[str]:
        """
        Clean and validate social media URL.
        
        - Remove tracking parameters
        - Standardize format
        - Validate domain
        
        Args:
            url: Raw URL
            platform: Platform type
            
        Returns:
            Cleaned URL or None if invalid
        """
        try:
            parsed = urlparse(url)
            
            # Platform-specific cleaning
            if platform == 'youtube':
                # Standardize YouTube URLs
                if 'youtube.com' in parsed.netloc:
                    # Extract channel/user from path
                    path = parsed.path
                    if '/c/' in path or '/channel/' in path or '/user/' in path or '/@' in path:
                        return f"https://www.youtube.com{path.split('?')[0]}"
                    
            elif platform == 'vimeo':
                if 'vimeo.com' in parsed.netloc:
                    path = parsed.path.split('?')[0]
                    return f"https://vimeo.com{path}"
                    
            elif platform == 'facebook':
                if 'facebook.com' in parsed.netloc or 'fb.com' in parsed.netloc:
                    path = parsed.path.split('?')[0]
                    return f"https://www.facebook.com{path}"
            
            elif platform == 'granicus':
                if 'granicus.com' in parsed.netloc:
                    return url.split('?')[0] if '?' in url else url
            
            elif platform == 'archive_org':
                if 'archive.org' in parsed.netloc:
                    return url.split('?')[0] if '?' in url else url
            
            # Return cleaned URL if it passed validation
            return url
            
        except Exception as e:
            logger.debug(f"Error cleaning URL {url}: {e}")
            return None
    
    async def discover_batch(
        self,
        jurisdictions: List[Dict[str, str]]
    ) -> List[Dict[str, any]]:
        """
        Discover social media for multiple jurisdictions in parallel.
        
        Args:
            jurisdictions: List of dicts with:
                - homepage_url: Government website
                - jurisdiction_name: Name
                - state: State abbreviation
                - jurisdiction_id: Unique ID
                
        Returns:
            List of discovery results with social media links
        """
        tasks = []
        
        for jurisdiction in jurisdictions:
            task = self.discover_from_website(
                jurisdiction['homepage_url'],
                jurisdiction['jurisdiction_name'],
                jurisdiction['state']
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results with jurisdiction info
        output = []
        for jurisdiction, social_links in zip(jurisdictions, results):
            if isinstance(social_links, Exception):
                logger.warning(f"Error for {jurisdiction['jurisdiction_name']}: {social_links}")
                continue
            
            # Filter to only platforms with URLs
            filtered_links = {
                platform: urls 
                for platform, urls in social_links.items() 
                if urls
            }
            
            if filtered_links:
                output.append({
                    'jurisdiction_id': jurisdiction.get('jurisdiction_id'),
                    'jurisdiction_name': jurisdiction['jurisdiction_name'],
                    'state': jurisdiction['state'],
                    'homepage_url': jurisdiction['homepage_url'],
                    'social_media': filtered_links,
                    'discovered_at': datetime.utcnow().isoformat(),
                    'platform_count': len(filtered_links),
                    'total_urls': sum(len(urls) for urls in filtered_links.values())
                })
        
        logger.success(f"✓ Discovered social media for {len(output)}/{len(jurisdictions)} jurisdictions")
        
        return output
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


async def main():
    """Example usage."""
    
    # Example: Discover social media for a few cities
    jurisdictions = [
        {
            'jurisdiction_id': 'seattle-wa',
            'homepage_url': 'https://www.seattle.gov',
            'jurisdiction_name': 'Seattle',
            'state': 'WA'
        },
        {
            'jurisdiction_id': 'chicago-il',
            'homepage_url': 'https://www.chicago.gov',
            'jurisdiction_name': 'Chicago',
            'state': 'IL'
        },
        {
            'jurisdiction_id': 'austin-tx',
            'homepage_url': 'https://www.austintexas.gov',
            'jurisdiction_name': 'Austin',
            'state': 'TX'
        }
    ]
    
    async with SocialMediaDiscovery() as discovery:
        results = await discovery.discover_batch(jurisdictions)
        
        # Print results
        import json
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
