"""
Platform detection for municipal websites.

Based on patterns from:
- biglocalnews/civic-scraper (Apache 2.0)
- city-scrapers/city-scrapers (MIT)

Detects which content management system or meeting platform a municipality uses,
enabling optimized scraping strategies.
"""
from typing import Optional, Dict, List
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from loguru import logger


# Platform URL patterns (most specific first)
PLATFORM_PATTERNS = {
    'legistar': [
        'legistar.com',
        '/Legistar/',
        '/LegislationDetail.aspx',
        '/Calendar.aspx',
        '/MeetingDetail.aspx',
        'WebApi/odata'
    ],
    'granicus': [
        'granicus.com',
        '/Mediasite/',
        '/ViewPublisher.php',
        '/MetaViewer.php',
        'granicus-cdn.com'
    ],
    'municode': [
        'municode.com',
        '/meeting_minutes',
        '/MuniCode/'
    ],
    'civicplus': [
        'civicplus.com',
        '/AgendaCenter/',
        '/DocumentCenter/',
        '/CivicSend/'
    ],
    'primegov': [
        'primegov.com',
        '/Portal/',
        '/Public/0/'
    ],
    'calagenda': [
        'ca-ilg.civicplus.com',
        '/AgendaCenter/ViewFile/'
    ],
    'swagit': [
        'swagit.com',
        '/play/',
        '/videos/'
    ],
    'zoomgov': [
        'zoom.us/rec/',
        'zoomgov.com'
    ]
}

# HTML meta tag patterns that indicate platforms
META_PATTERNS = {
    'legistar': [
        'Legistar',
        'InSite',
        'Granicus'  # Granicus owns Legistar
    ],
    'civicplus': [
        'CivicPlus',
        'CivicEngage'
    ]
}

# Common CMS patterns (WordPress, Drupal, etc.)
CMS_PATTERNS = {
    'wordpress': [
        'wp-content',
        'wp-includes',
        'wordpress'
    ],
    'drupal': [
        '/sites/default/',
        'drupal.js',
        'Drupal.settings'
    ],
    'joomla': [
        '/components/com_',
        '/modules/mod_'
    ]
}


def detect_platform(url: str, html_content: Optional[str] = None) -> Optional[str]:
    """
    Detect which platform a municipality website uses.
    
    Performs two-stage detection:
    1. URL pattern matching (fast, works without fetching)
    2. HTML content analysis (slower, more accurate)
    
    Args:
        url: Municipality website URL
        html_content: Optional HTML content for deeper analysis
        
    Returns:
        Platform name or None if unknown
        
    Examples:
        >>> detect_platform("https://chicago.legistar.com/Calendar.aspx")
        'legistar'
        >>> detect_platform("https://example.gov/meetings")
        None
    """
    url_lower = url.lower()
    
    # Stage 1: URL pattern matching
    for platform, patterns in PLATFORM_PATTERNS.items():
        if any(pattern.lower() in url_lower for pattern in patterns):
            logger.debug(f"Detected {platform} from URL pattern: {url}")
            return platform
    
    # Stage 2: HTML content analysis (if provided)
    if html_content:
        platform = detect_from_html(html_content)
        if platform:
            logger.debug(f"Detected {platform} from HTML content: {url}")
            return platform
    
    # Stage 3: Check for generic CMS
    for cms, patterns in CMS_PATTERNS.items():
        if any(pattern.lower() in url_lower for pattern in patterns):
            logger.debug(f"Detected generic CMS {cms}: {url}")
            return 'generic'
    
    logger.debug(f"No platform detected for: {url}")
    return None


def detect_from_html(html_content: str) -> Optional[str]:
    """
    Detect platform from HTML content analysis.
    
    Checks:
    - Meta tags (generator, description)
    - Script sources
    - Link hrefs
    - Specific HTML structures
    
    Args:
        html_content: Raw HTML content
        
    Returns:
        Platform name or None
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check meta tags
        for platform, keywords in META_PATTERNS.items():
            meta_generator = soup.find('meta', attrs={'name': 'generator'})
            if meta_generator:
                content = meta_generator.get('content', '').lower()
                if any(keyword.lower() in content for keyword in keywords):
                    return platform
        
        # Check scripts and links
        all_text = html_content.lower()
        for platform, patterns in PLATFORM_PATTERNS.items():
            if any(pattern.lower() in all_text for pattern in patterns):
                return platform
        
    except Exception as e:
        logger.warning(f"Error parsing HTML for platform detection: {e}")
    
    return None


async def detect_platform_async(url: str, fetch_html: bool = True) -> Dict[str, any]:
    """
    Async version that can fetch HTML content for deeper detection.
    
    Args:
        url: Municipality website URL
        fetch_html: Whether to fetch HTML for content analysis
        
    Returns:
        Dictionary with detection results:
        {
            'platform': str,
            'confidence': float,
            'features': List[str],
            'scraper_available': bool
        }
    """
    result = {
        'url': url,
        'platform': None,
        'confidence': 0.0,
        'features': [],
        'scraper_available': False
    }
    
    # Quick URL check
    platform = detect_platform(url)
    if platform:
        result['platform'] = platform
        result['confidence'] = 0.7
        result['features'].append('url_pattern')
    
    # Fetch and analyze HTML if requested
    if fetch_html:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                
                platform_from_html = detect_from_html(response.text)
                if platform_from_html:
                    result['platform'] = platform_from_html
                    result['confidence'] = 0.9
                    result['features'].append('html_content')
                    
        except Exception as e:
            logger.warning(f"Could not fetch {url} for platform detection: {e}")
    
    # Check if we have a scraper for this platform
    if result['platform'] in ['legistar', 'granicus', 'civicplus']:
        result['scraper_available'] = True
    
    return result


def get_platform_capabilities(platform: str, *, jurisdiction_name: str = "") -> Dict[str, any]:
    """
    Get capabilities and scraping strategies for a platform.
    
    Args:
        platform: Platform name
        jurisdiction_name: Named in the error when the platform is unknown
        
    Returns:
        Dictionary describing platform capabilities

    Raises:
        ingestion.meetings.UnsupportedPlatformError: for a platform this table doesn't describe. There is no generic
        scraper to fall back on, so callers record the gap instead of reporting no meetings (#252).
    """
    capabilities = {
        'legistar': {
            'has_api': True,
            'api_docs': 'https://webapi.legistar.com/Help',
            'supports_bulk_download': True,
            'common_endpoints': [
                '/events',
                '/matters',
                '/bodies'
            ],
            'rate_limit': 'Unknown',
            'scraper_class': 'scrapers.legistar.LegistarScraper'
        },
        'granicus': {
            'has_api': True,
            'supports_bulk_download': True,
            'common_endpoints': [
                '/ViewPublisher.php',
                '/MetaViewer.php'
            ],
            'rate_limit': 'Unknown',
            'scraper_class': 'scrapers.granicus.GranicusScraper'
        },
        'civicplus': {
            'has_api': False,
            'supports_bulk_download': False,
            'requires_html_parsing': True,
            'scraper_class': 'scrapers.civicplus.CivicPlusScraper'
        },
    }
    
    if platform not in capabilities:
        from ingestion.meetings import UnsupportedPlatformError
        raise UnsupportedPlatformError(platform, jurisdiction_name or "unknown")
    return capabilities[platform]


def get_scraper_class(platform: str, *, jurisdiction_name: str = ""):
    """
    Get the meeting adapter class for a platform, from ``ingestion.meetings`` (CORE-3.1).
    
    Args:
        platform: Platform name
        jurisdiction_name: Named in the error when no adapter exists
        
    Returns:
        The registered adapter class (``ingestion.meetings.adapter_for``)

    Raises:
        ingestion.meetings.UnsupportedPlatformError: when no adapter exists for the platform. Report it as a gap
        (``ingestion.meetings.coverage_report``), never as a council with no meetings (#252).
    """
    from ingestion.meetings import adapter_for

    return adapter_for(platform, jurisdiction_name=jurisdiction_name or "unknown")


# Example usage
if __name__ == "__main__":
    # Test URL detection
    test_urls = [
        "https://chicago.legistar.com/Calendar.aspx",
        "https://birminghamal.gov/meetings",
        "https://example.civicplus.com/AgendaCenter",
        "https://unknown-city.gov/council"
    ]
    
    for url in test_urls:
        platform = detect_platform(url)
        print(f"{url}\n  → Platform: {platform}\n")
