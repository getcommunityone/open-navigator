#!/usr/bin/env python3
"""
Debug script to examine eBoard page structure
"""
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re


async def main():
    url = "https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=2088"
    base_url = "https://simbli.eboardsolutions.com"
    
    print(f"Loading: {url}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=user_agent,
            locale='en-US',
            timezone_id='America/Chicago',
        )
        
        page = await context.new_page()
        
        # Apply stealth
        stealth = Stealth()
        await stealth.apply_stealth_async(page)
        
        # Navigate
        response = await page.goto(url, wait_until='networkidle', timeout=60000)
        print(f"Response status: {response.status}")
        
        # Wait for JavaScript
        await page.wait_for_timeout(5000)
        
        content = await page.content()
        print(f"Page size: {len(content)} bytes\n")
        
        # Save full HTML for inspection
        with open('/tmp/eboard_page.html', 'w') as f:
            f.write(content)
        print("Saved full HTML to /tmp/eboard_page.html\n")
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find all links
        all_links = soup.find_all('a', href=True)
        print(f"Total links found: {len(all_links)}\n")
        
        # Categorize links
        mid_links = []
        meetingdetail_links = []
        pdf_links = []
        other_links = []
        
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text().strip()
            
            if 'MID=' in href.upper():
                mid_links.append((href, text))
            elif 'meetingdetail' in href.lower():
                meetingdetail_links.append((href, text))
            elif href.lower().endswith('.pdf'):
                pdf_links.append((href, text))
            elif href and not href.startswith('#') and not href.startswith('javascript:'):
                other_links.append((href, text[:50]))
        
        print(f"Links with MID=: {len(mid_links)}")
        for href, text in mid_links[:10]:
            print(f"  - {text[:60]}: {href[:80]}")
        
        print(f"\nLinks with 'meetingdetail': {len(meetingdetail_links)}")
        for href, text in meetingdetail_links[:10]:
            print(f"  - {text[:60]}: {href[:80]}")
        
        print(f"\nPDF links: {len(pdf_links)}")
        for href, text in pdf_links[:10]:
            print(f"  - {text[:60]}: {href[:80]}")
        
        print(f"\nOther significant links: {len(other_links)}")
        for href, text in other_links[:20]:
            print(f"  - {text[:60]}: {href[:80]}")
        
        # Look for ASP.NET ViewState and other dynamic content indicators
        print("\n" + "="*80)
        print("Page Analysis:")
        print("="*80)
        
        viewstate = soup.find('input', {'id': '__VIEWSTATE'})
        if viewstate:
            print(f"✓ ASP.NET ViewState present ({len(viewstate.get('value', ''))} chars)")
        
        # Look for tables or grids that might contain meetings
        tables = soup.find_all('table')
        print(f"Tables found: {len(tables)}")
        for i, table in enumerate(tables[:5]):
            rows = table.find_all('tr')
            print(f"  Table {i+1}: {len(rows)} rows")
            if rows:
                first_row_text = rows[0].get_text().strip()[:100]
                print(f"    First row: {first_row_text}")
        
        # Look for JavaScript-rendered content
        scripts = soup.find_all('script')
        print(f"\nJavaScript blocks: {len(scripts)}")
        
        # Check for common eBoard element IDs
        meeting_list_elem = soup.find(id=re.compile(r'meeting.*list', re.I))
        if meeting_list_elem:
            print(f"✓ Found element with 'meeting' and 'list' in ID: {meeting_list_elem.get('id')}")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
