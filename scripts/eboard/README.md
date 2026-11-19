# eBoard and cookie helpers

- `export_chrome_cookies.py` - exports YouTube cookies from a local Chrome profile (for yt-dlp).

`debug_eboard.py` and `try_scrape_with_cookies.py` moved to `archive/datasources/eboard/` (#462): nothing imported
them, and both used `playwright_stealth`, which the project no longer uses. Scrapers run a plain browser and report
bot protection as blocked (`scrapers.discovery.browser_block`).
