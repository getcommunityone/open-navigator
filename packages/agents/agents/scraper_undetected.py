"""
Alternative eBoard scraper using undetected-chromedriver
This bypasses Incapsula without manual cookies
"""
import asyncio
import re
from typing import Dict, Any, List
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import hashlib

from loguru import logger


class UndetectedEboardScraper:
    """
    Scrape eBoard using undetected-chromedriver to bypass Incapsula.
    
    This library patches Selenium ChromeDriver to avoid detection by:
    - Removing Selenium markers from navigator.webdriver
    - Randomizing browser fingerprints
    - Using real Chrome instead of ChromeDriver
    """
    
    async def scrape_eboard(
        self,
        url: str,
        municipality: str,
        state: str,
        school_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape eBoard platform without manual cookies.
        
        Args:
            url: eBoard URL
            municipality: School district name
            state: State code
            school_id: Optional school ID (extracted from URL if not provided)
        
        Returns:
            List of meeting documents
        """
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import time
            import random
        except ImportError:
            logger.error("Missing undetected-chromedriver. Install: pip install undetected-chromedriver")
            return []
        
        # Extract school ID
        if not school_id:
            match = re.search(r'[?&]s=(\d+)', url, re.IGNORECASE)
            school_id = match.group(1) if match else None
        
        if not school_id:
            logger.error(f"Could not extract school ID from URL: {url}")
            return []
        
        base_url = "https://simbli.eboardsolutions.com"
        meetings_url = f"{base_url}/SB_Meetings/SB_MeetingListing.aspx?S={school_id}"
        
        logger.info(f"Using undetected-chromedriver to bypass Incapsula")
        logger.info(f"Target: {meetings_url}")
        
        documents = []
        
        try:
            # Create undetected Chrome instance
            options = uc.ChromeOptions()
            # options.add_argument('--headless')  # Headless may still be detected
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            # Create driver with version management
            driver = uc.Chrome(options=options, version_main=None)
            
            logger.info("Chrome launched with anti-detection patches")
            
            # Navigate to meetings page
            driver.get(meetings_url)
            logger.info(f"Loaded page: {driver.title[:100]}")
            
            # Wait for Incapsula challenge to complete
            # The challenge usually takes 3-5 seconds
            wait_time = random.uniform(5.0, 8.0)
            logger.info(f"Waiting {wait_time:.1f}s for Incapsula challenge...")
            time.sleep(wait_time)
            
            # Check if we bypassed Incapsula
            page_source = driver.page_source
            
            if 'Incapsula' in page_source and len(page_source) < 10000:
                logger.error("Still blocked by Incapsula")
                logger.warning("Try running with headless=False or use Option 2 (Residential Proxies)")
                driver.quit()
                return []
            
            logger.success(f"✓ Bypassed Incapsula! Page size: {len(page_source)} bytes")
            
            # Parse the page
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract meeting links
            meeting_links = []
            
            # Method 1: Look for MID parameter
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text().strip()
                
                if 'MID=' in href.upper() or 'meetingdetail' in href.lower():
                    full_url = urljoin(base_url, href)
                    meeting_links.append({
                        'url': full_url,
                        'text': text,
                        'type': 'meeting'
                    })
                elif href.lower().endswith('.pdf'):
                    full_url = urljoin(base_url, href)
                    meeting_links.append({
                        'url': full_url,
                        'text': text,
                        'type': 'pdf'
                    })
            
            logger.info(f"Found {len(meeting_links)} meeting/document links")
            
            # If no links found, try JavaScript execution
            if len(meeting_links) == 0:
                logger.warning("No links found in HTML, checking for JavaScript-rendered content...")
                
                # Wait for dynamic content
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "a"))
                    )
                    time.sleep(3)  # Additional wait for JS
                    
                    # Re-parse
                    page_source = driver.page_source
                    soup = BeautifulSoup(page_source, 'html.parser')
                    
                    for link in soup.find_all('a', href=True):
                        href = link.get('href', '')
                        text = link.get_text().strip()
                        
                        if 'MID=' in href.upper() or href.lower().endswith('.pdf'):
                            full_url = urljoin(base_url, href)
                            meeting_links.append({
                                'url': full_url,
                                'text': text,
                                'type': 'pdf' if href.lower().endswith('.pdf') else 'meeting'
                            })
                    
                    logger.info(f"After JS wait: Found {len(meeting_links)} links")
                except Exception as e:
                    logger.warning(f"JS content wait failed: {e}")
            
            # Process meeting links (limit to prevent overwhelming)
            for idx, meeting_info in enumerate(meeting_links[:50]):
                if idx > 0 and idx % 10 == 0:
                    logger.info(f"Progress: {idx}/{min(50, len(meeting_links))}")
                
                # Human-like delay
                time.sleep(random.uniform(2.0, 5.0))
                
                try:
                    meeting_url = meeting_info['url']
                    meeting_title = meeting_info['text']
                    
                    if meeting_info['type'] == 'pdf':
                        # Download PDF directly
                        logger.debug(f"  Downloading PDF: {meeting_title[:50]}")
                        # TODO: Implement PDF download
                        # For now, just record the URL
                        doc = {
                            'document_id': hashlib.md5(f"{meeting_url}{municipality}".encode()).hexdigest(),
                            'source_url': meeting_url,
                            'municipality': municipality,
                            'state': state,
                            'meeting_date': datetime.now(),
                            'meeting_type': 'Board Meeting',
                            'title': meeting_title,
                            'content': '',  # Would need PDF extraction
                            'metadata': {
                                'platform': 'eboard',
                                'school_id': school_id,
                                'scraped_with': 'undetected_chromedriver'
                            }
                        }
                        documents.append(doc)
                    else:
                        # Navigate to meeting detail page
                        logger.debug(f"  Loading meeting: {meeting_title[:50]}")
                        driver.get(meeting_url)
                        time.sleep(random.uniform(2.0, 4.0))
                        
                        meeting_soup = BeautifulSoup(driver.page_source, 'html.parser')
                        
                        # Extract PDFs from meeting page
                        for link in meeting_soup.find_all('a', href=True):
                            href = link.get('href', '')
                            if href.lower().endswith('.pdf'):
                                doc_url = urljoin(base_url, href)
                                doc_title = link.get_text().strip()
                                
                                doc = {
                                    'document_id': hashlib.md5(f"{doc_url}{municipality}".encode()).hexdigest(),
                                    'source_url': doc_url,
                                    'municipality': municipality,
                                    'state': state,
                                    'meeting_date': datetime.now(),
                                    'meeting_type': 'Board Meeting',
                                    'title': doc_title or meeting_title,
                                    'content': '',
                                    'metadata': {
                                        'platform': 'eboard',
                                        'meeting_page': meeting_url,
                                        'school_id': school_id,
                                        'scraped_with': 'undetected_chromedriver'
                                    }
                                }
                                documents.append(doc)
                                logger.success(f"    ✓ Found: {doc_title[:50]}")
                
                except Exception as e:
                    logger.error(f"Error processing {meeting_info.get('text', 'unknown')}: {e}")
                    continue
            
            driver.quit()
            logger.success(f"Scraping complete: {len(documents)} documents")
            return documents
            
        except Exception as e:
            logger.error(f"Error in undetected scraper: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []


# Example usage
async def main():
    scraper = UndetectedEboardScraper()
    docs = await scraper.scrape_eboard(
        url="http://simbli.eboardsolutions.com/index.aspx?s=2088",
        municipality="Tuscaloosa City Schools",
        state="AL"
    )
    print(f"Scraped {len(docs)} documents")


if __name__ == "__main__":
    asyncio.run(main())
