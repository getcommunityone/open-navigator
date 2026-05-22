#!/usr/bin/env python3
"""
Official Government Website Scraper

Scrapes official .gov domains from GSA registry to extract:
- Meeting schedules and agendas
- Official contact information
- Department directories
- YouTube channels
- Social media accounts

Data Source: GSA .gov domains in jurisdiction (discovery_status='gsa_only' or has gov_domains)

Type: ENRICHMENT LOAD (adds meeting/video data to existing jurisdictions)
"""
import asyncio
import re
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger


# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "database": "open_navigator",
    "user": "postgres",
    "password": "password"
}

CACHE_DIR = Path("data/cache/govwebsites")


class GovWebsiteScraper:
    """Scrape official government websites for civic engagement data."""
    
    # YouTube URL patterns
    YOUTUBE_PATTERNS = [
        r'youtube\.com/(?:c|channel|user)/([a-zA-Z0-9_-]+)',
        r'youtube\.com/@([a-zA-Z0-9_-]+)',
        r'youtube\.com/(?:c|channel)/(UC[a-zA-Z0-9_-]+)',
    ]
    
    # Meeting/agenda page patterns
    MEETING_KEYWORDS = [
        'agenda', 'minutes', 'meeting', 'calendar', 'schedule',
        'board', 'council', 'commission', 'committee'
    ]
    
    def __init__(self):
        """Initialize scraper."""
        self.cache_dir = CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = None
        self.youtube_channels = set()
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "OpenNavigator/1.0 (Civic Research; contact@example.com)"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.aclose()
    
    async def scrape_website(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Scrape a government website for civic engagement data.
        
        Args:
            domain: Domain name (e.g., 'bostonma.gov')
        
        Returns:
            Dictionary with scraped data
        """
        url = f"https://{domain}"
        
        try:
            response = await self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            data = {
                'domain': domain,
                'title': soup.title.string if soup.title else None,
                'youtube_channels': self._extract_youtube_channels(soup, url),
                'meeting_pages': self._find_meeting_pages(soup, url),
                'contact_emails': self._extract_emails(soup),
                'social_media': self._extract_social_media(soup),
                'scraped_at': datetime.now()
            }
            
            logger.debug(f"Scraped {domain}: {len(data['youtube_channels'])} YouTube channels, "
                        f"{len(data['meeting_pages'])} meeting pages")
            
            return data
            
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error for {domain}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error scraping {domain}: {e}")
            return None
    
    def _extract_youtube_channels(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract YouTube channel URLs from page."""
        channels = []
        
        # Find all links
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Check for YouTube URLs
            for pattern in self.YOUTUBE_PATTERNS:
                match = re.search(pattern, href)
                if match:
                    channel = match.group(1)
                    if channel not in channels:
                        channels.append(channel)
        
        return channels
    
    def _find_meeting_pages(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Find links to meeting/agenda pages."""
        meeting_pages = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True).lower()
            
            # Check if link text contains meeting keywords
            if any(keyword in text for keyword in self.MEETING_KEYWORDS):
                # Check if URL also suggests meetings
                if any(keyword in href.lower() for keyword in self.MEETING_KEYWORDS):
                    full_url = urljoin(base_url, href)
                    meeting_pages.append({
                        'url': full_url,
                        'text': link.get_text(strip=True)
                    })
        
        return meeting_pages
    
    def _extract_emails(self, soup: BeautifulSoup) -> List[str]:
        """Extract email addresses from page."""
        emails = []
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        # Search in text and mailto links
        text = soup.get_text()
        for email in re.findall(email_pattern, text):
            if email not in emails:
                emails.append(email)
        
        return emails
    
    def _extract_social_media(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Extract social media links."""
        social = {
            'facebook': [],
            'twitter': [],
            'instagram': [],
            'linkedin': []
        }
        
        for link in soup.find_all('a', href=True):
            href = link['href'].lower()
            
            if 'facebook.com' in href:
                social['facebook'].append(href)
            elif 'twitter.com' in href or 'x.com' in href:
                social['twitter'].append(href)
            elif 'instagram.com' in href:
                social['instagram'].append(href)
            elif 'linkedin.com' in href:
                social['linkedin'].append(href)
        
        return social


async def main(states: Optional[str] = None, limit: int = 100, dry_run: bool = False):
    """
    Main entry point for government website scraper.
    
    Args:
        states: Comma-separated state codes (e.g., "AL,GA,MA")
        limit: Maximum number of websites to scrape
        dry_run: If True, don't update database
    """
    logger.info("=" * 80)
    logger.info("Government Website Scraper")
    logger.info("=" * 80)
    
    # Get jurisdictions with .gov domains from database
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    state_filter = ""
    if states:
        state_list = [s.strip().upper() for s in states.split(',')]
        state_filter = f"AND state_code IN ({','.join(repr(s) for s in state_list)})"
        logger.info(f"Filtering to states: {', '.join(state_list)}")
    
    query = f"""
        SELECT 
            jurisdiction_id,
            name AS jurisdiction_name,
            state_code,
            gov_domains->0 as primary_domain
        FROM jurisdiction
        WHERE gov_domains IS NOT NULL 
          AND jsonb_array_length(gov_domains) > 0
          {state_filter}
        LIMIT {limit}
    """
    
    cur.execute(query)
    jurisdictions = cur.fetchall()
    cur.close()
    conn.close()
    
    logger.info(f"Found {len(jurisdictions)} jurisdictions to scrape")
    
    results = []
    
    async with GovWebsiteScraper() as scraper:
        for jurisdiction in jurisdictions:
            domain = jurisdiction['primary_domain'].strip('"')
            
            logger.info(f"Scraping {jurisdiction['jurisdiction_name']} ({domain})...")
            
            data = await scraper.scrape_website(domain)
            if data:
                data['jurisdiction_id'] = jurisdiction['jurisdiction_id']
                results.append(data)
            
            # Rate limiting
            await asyncio.sleep(2)
    
    # TODO: Update database with scraped data
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Websites scraped: {len(results)}")
    logger.info(f"YouTube channels found: {sum(len(r.get('youtube_channels', [])) for r in results)}")
    logger.info(f"Meeting pages found: {sum(len(r.get('meeting_pages', [])) for r in results)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape official government websites")
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated state codes (e.g., AL,GA,MA,WA,WI)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum number of websites to scrape'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be scraped without updating database'
    )
    
    args = parser.parse_args()
    
    asyncio.run(main(states=args.states, limit=args.limit, dry_run=args.dry_run))
