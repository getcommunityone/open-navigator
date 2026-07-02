"""
ELGL & NACo Integration for Video Channel Discovery

Two highly curated sources for finding the most active local government
YouTube channels and county digital innovation hubs.

Data Sources:
1. ELGL (Engaging Local Government Leaders)
   - "Top Local Government YouTube Channels" lists
   - Curated, high-quality channels
   - Most active local governments nationwide
   
2. NACo (National Association of Counties)
   - Database of 3,143 county websites
   - Digital innovation showcase
   - County media hubs and video portals
"""
import asyncio
import re
from typing import List, Dict, Optional
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from loguru import logger


class ELGLYouTubeDiscovery:
    """
    Discover YouTube channels from ELGL's curated lists.
    
    ELGL (Engaging Local Government Leaders) regularly publishes lists of
    top local government YouTube channels. These are the most active and
    innovative channels across the country.
    
    Sources:
    - ELGL Blog: https://elgl.org/
    - Annual "Top Local Gov YouTube Channels" articles
    - Conference presentations and webinars
    """
    
    ELGL_SOURCES = [
        {
            "name": "ELGL Top Channels 2024",
            "url": "https://elgl.org/top-local-government-youtube-channels-2024/",
            "type": "article"
        },
        {
            "name": "ELGL Top Channels 2023", 
            "url": "https://elgl.org/top-local-government-youtube-channels-2023/",
            "type": "article"
        },
        {
            "name": "ELGL Digital Innovation",
            "url": "https://elgl.org/category/communication/",
            "type": "category"
        }
    ]
    
    def __init__(self):
        """Initialize ELGL discovery."""
        self.client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; OralHealthPolicyBot/2.0)"
            }
        )
    
    async def scrape_elgl_top_channels(self) -> List[Dict[str, str]]:
        """
        Scrape ELGL's "Top Local Government YouTube Channels" articles.
        
        These articles typically list:
        - YouTube channel URLs
        - Municipality/county name
        - State
        - Brief description
        - Subscriber count and activity metrics
        
        Returns:
            List of dicts with channel info:
            {
                'jurisdiction_name': 'Seattle',
                'state': 'WA',
                'youtube_url': 'https://www.youtube.com/channel/UCu2IUja1ASnGIr_ORrtLReg',
                'source': 'ELGL Top Channels 2024',
                'description': 'City council meetings and city updates',
                'subscribers': '15000',
                'is_top_ranked': True
            }
        """
        logger.info("Scraping ELGL Top YouTube Channels lists")
        
        all_channels = []
        
        for source in self.ELGL_SOURCES:
            try:
                logger.info(f"Fetching {source['name']}...")
                response = await self.client.get(source['url'])
                
                if response.status_code == 200:
                    channels = self._parse_elgl_article(
                        response.content,
                        source['name']
                    )
                    all_channels.extend(channels)
                    logger.success(f"✓ Found {len(channels)} channels from {source['name']}")
                
                await asyncio.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"Error fetching {source['name']}: {e}")
        
        # Deduplicate by YouTube URL
        unique_channels = {}
        for channel in all_channels:
            url = channel['youtube_url']
            if url not in unique_channels:
                unique_channels[url] = channel
        
        logger.success(f"✓ Total unique channels from ELGL: {len(unique_channels)}")
        
        return list(unique_channels.values())
    
    def _parse_elgl_article(self, content: bytes, source_name: str) -> List[Dict]:
        """
        Parse ELGL article HTML to extract YouTube channels.
        
        ELGL articles typically have patterns like:
        - Links to YouTube channels
        - Municipality names in headers or lists
        - Descriptions of channel content
        """
        soup = BeautifulSoup(content, 'html.parser')
        channels = []
        
        # Find all YouTube links in the article
        youtube_pattern = r'youtube\.com/(?:c/|channel/|user/|@)([\w-]+)'
        
        # Strategy 1: Find links in article body
        article_body = soup.find('article') or soup.find('div', class_='entry-content')
        
        if article_body:
            # Extract all links
            links = article_body.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                match = re.search(youtube_pattern, href)
                
                if match:
                    # Try to extract context (city name, state)
                    context = self._extract_channel_context(link, soup)
                    
                    channel = {
                        'youtube_url': href,
                        'source': source_name,
                        'jurisdiction_name': context.get('name', 'Unknown'),
                        'state': context.get('state', ''),
                        'description': context.get('description', ''),
                        'is_top_ranked': True,
                        'discovered_at': datetime.utcnow().isoformat()
                    }
                    
                    channels.append(channel)
        
        return channels
    
    def _extract_channel_context(self, link_element, soup) -> Dict[str, str]:
        """
        Extract context around a YouTube link (city name, state, description).
        
        Looks at:
        - Parent heading (h2, h3)
        - Preceding text
        - List item text
        """
        context = {}
        
        # Try to find parent heading
        parent = link_element.find_parent(['h2', 'h3', 'h4', 'li', 'p'])
        
        if parent:
            text = parent.get_text().strip()
            
            # Extract city and state pattern: "City Name, ST"
            city_state_match = re.search(r'([^,]+),\s*([A-Z]{2})', text)
            if city_state_match:
                context['name'] = city_state_match.group(1).strip()
                context['state'] = city_state_match.group(2)
            
            # Use full text as description if it's a paragraph
            if parent.name == 'p':
                context['description'] = text[:200]  # Truncate
        
        return context
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


class NACoCountyDiscovery:
    """
    Discover county websites and video channels from NACo database.
    
    NACo (National Association of Counties) maintains:
    - Database of all 3,143 U.S. counties
    - County website URLs
    - Digital innovation showcase
    - County media and communication hubs
    
    Sources:
    - NACo County Explorer: https://ce.naco.org/
    - NACo Digital Counties Survey
    - NACo Communications & Media Awards
    """
    
    NACO_SOURCES = {
        "county_explorer": "https://ce.naco.org/",
        "digital_innovation": "https://www.naco.org/resources/featured/digital-counties-survey",
        "achievement_awards": "https://www.naco.org/resources/programs-and-services/naco-achievement-awards"
    }
    
    def __init__(self):
        """Initialize NACo discovery."""
        self.client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; OralHealthPolicyBot/2.0)"
            }
        )
    
    async def get_naco_county_websites(self) -> List[Dict[str, str]]:
        """
        Get county website URLs from NACo County Explorer.
        
        The County Explorer provides:
        - Official county website URLs for all 3,143 counties
        - County demographics and facts
        - Contact information
        
        Returns:
            List of counties with official websites:
            {
                'county_name': 'King County',
                'state': 'WA',
                'homepage_url': 'https://kingcounty.gov',
                'population': 2269675,
                'source': 'NACo County Explorer',
                'fips_code': '53033'
            }
        """
        logger.info("Fetching NACo County Explorer data")
        
        # Note: NACo County Explorer may require API access or scraping
        # This is a placeholder for the actual implementation
        
        counties = []
        
        try:
            # Strategy 1: Check if NACo provides a data export or API
            # Strategy 2: Scrape County Explorer if no API available
            # Strategy 3: Use Census data + NACo verification
            
            logger.info("NACo County Explorer integration requires API/data access")
            logger.info("Recommendation: Contact NACo for data partnership or bulk export")
            
            # Placeholder: Return empty for now
            # In production, implement actual data retrieval
            
        except Exception as e:
            logger.error(f"Error accessing NACo data: {e}")
        
        return counties
    
    async def scrape_naco_digital_innovation(self) -> List[Dict[str, str]]:
        """
        Scrape NACo's digital innovation showcase for media hubs.
        
        NACo highlights counties with innovative digital services:
        - Video streaming platforms
        - Social media engagement
        - Digital communication tools
        
        Returns:
            List of counties with digital innovation:
            {
                'county_name': 'Fairfax County',
                'state': 'VA',
                'innovation_type': 'Video Streaming',
                'description': 'Live streaming of board meetings',
                'platform_url': 'https://fairfaxcounty.gov/cableconsumer/channel-16',
                'source': 'NACo Digital Counties Survey'
            }
        """
        logger.info("Scraping NACo Digital Innovation showcase")
        
        innovations = []
        
        try:
            response = await self.client.get(self.NACO_SOURCES['digital_innovation'])
            
            if response.status_code == 200:
                # Parse digital innovation examples
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for case studies, awards, or highlighted counties
                # This will vary based on NACo's website structure
                
                logger.debug("Parsing NACo digital innovation content")
                
        except Exception as e:
            logger.warning(f"Error scraping NACo digital innovation: {e}")
        
        return innovations
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


async def integrate_curated_sources() -> Dict[str, List[Dict]]:
    """
    Integration function to get channels from ELGL and NACo.
    
    This combines:
    1. ELGL's curated top YouTube channels (most active)
    2. NACo's county website database (comprehensive)
    3. NACo's digital innovation showcase (innovative counties)
    
    Returns:
        Dictionary with results from each source:
        {
            'elgl_channels': [...],
            'naco_counties': [...],
            'naco_innovations': [...]
        }
    """
    logger.info("=== Integrating ELGL & NACo Curated Sources ===")
    
    results = {
        'elgl_channels': [],
        'naco_counties': [],
        'naco_innovations': []
    }
    
    # ELGL YouTube Channels
    async with ELGLYouTubeDiscovery() as elgl:
        results['elgl_channels'] = await elgl.scrape_elgl_top_channels()
    
    # NACo County Data
    async with NACoCountyDiscovery() as naco:
        results['naco_counties'] = await naco.get_naco_county_websites()
        results['naco_innovations'] = await naco.scrape_naco_digital_innovation()
    
    # Summary
    total = (
        len(results['elgl_channels']) +
        len(results['naco_counties']) +
        len(results['naco_innovations'])
    )
    
    logger.success(f"✓ Total curated sources: {total}")
    logger.info(f"  • ELGL YouTube channels: {len(results['elgl_channels'])}")
    logger.info(f"  • NACo counties: {len(results['naco_counties'])}")
    logger.info(f"  • NACo innovations: {len(results['naco_innovations'])}")
    
    return results


async def main():
    """Example usage."""
    
    # Get curated sources
    results = await integrate_curated_sources()
    
    # Print results
    import json
    
    if results['elgl_channels']:
        print("\n=== ELGL Top YouTube Channels ===")
        for channel in results['elgl_channels'][:5]:  # First 5
            print(f"  • {channel['jurisdiction_name']}, {channel['state']}")
            print(f"    {channel['youtube_url']}")
            print(f"    Source: {channel['source']}")
    
    if results['naco_counties']:
        print("\n=== NACo County Websites ===")
        for county in results['naco_counties'][:5]:  # First 5
            print(f"  • {county['county_name']}, {county['state']}")
            print(f"    {county['homepage_url']}")
    
    if results['naco_innovations']:
        print("\n=== NACo Digital Innovation ===")
        for innovation in results['naco_innovations'][:5]:  # First 5
            print(f"  • {innovation['county_name']}, {innovation['state']}")
            print(f"    Type: {innovation['innovation_type']}")


if __name__ == "__main__":
    asyncio.run(main())
