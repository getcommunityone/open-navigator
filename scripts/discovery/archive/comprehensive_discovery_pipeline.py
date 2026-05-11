"""
Comprehensive Discovery Pipeline for ALL U.S. Cities and Counties

Automates discovery of:
- Government websites
- YouTube channels (with statistics)
- Vimeo channels
- Meeting platforms (Legistar, SuiteOne, Granicus, etc.)
- Agenda portals and document systems
- Social media accounts
- Meeting schedules and archives

Scale: 3,143 counties + 19,000+ cities = ~22,000 jurisdictions

Usage:
    # Run for all jurisdictions
    python scripts/discovery/comprehensive_discovery_pipeline.py --all
    
    # Run for specific state
    python scripts/discovery/comprehensive_discovery_pipeline.py --state AL
    
    # Run for top 100 cities
    python scripts/discovery/comprehensive_discovery_pipeline.py --top 100
"""
import asyncio
import argparse
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timezone
import json

from loguru import logger
from tqdm.asyncio import tqdm
import pandas as pd
import polars as pl

# Add parent directory to path for imports
import os
import sys
from pathlib import Path

if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.discovery.url_discovery_agent import URLDiscoveryAgent
from scripts.datasources.youtube.youtube_channel_discovery import YouTubeChannelDiscovery
from scripts.datasources.social_media.social_media_discovery import SocialMediaDiscovery
from scripts.discovery.platform_detector import detect_platform
from scripts.datasources.wikidata.wikidata_integration import WikidataQuery
import httpx


class ComprehensiveDiscoveryPipeline:
    """
    Master pipeline for discovering all data sources for U.S. jurisdictions.
    
    Designed to scale to 22,000+ cities and counties nationwide.
    """
    
    def __init__(
        self,
        youtube_api_key: Optional[str] = None,
        max_concurrent: int = 10,
        output_dir: str = "data/bronze/discovered_sources",
        gold_output_dir: str = "data/gold",
        incremental: bool = True,
        refresh_days: int = 90,
        enable_wikidata: bool = False,
    ):
        """
        Initialize discovery pipeline.
        
        Args:
            youtube_api_key: YouTube Data API v3 key (optional but recommended)
            max_concurrent: Max concurrent requests (rate limiting)
            output_dir: Where to save discovered data
        """
        self.youtube_api_key = youtube_api_key
        self.max_concurrent = max_concurrent
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.gold_output_dir = Path(gold_output_dir)
        self.gold_output_dir.mkdir(parents=True, exist_ok=True)
        self.incremental = incremental
        self.refresh_days = refresh_days
        self.enable_wikidata = bool(enable_wikidata)
        
        # Load existing discoveries for incremental mode
        self.existing_discoveries = self._load_existing_discoveries() if incremental else {}
        
        # Load LocalView channels if available
        self.localview_channels = self._load_localview_channels()
        
        # Initialize discovery agents
        # Note: URLDiscoveryAgent is optional - we use direct pattern matching
        self.semaphore = asyncio.Semaphore(max_concurrent)
        # Wikidata is powerful but can be slow / rate-limited; keep optional.
        self.wikidata = WikidataQuery() if self.enable_wikidata else None
    
    async def discover_jurisdiction(
        self,
        jurisdiction: Dict
    ) -> Dict:
        """
        Comprehensive discovery for a single jurisdiction.
        
        Args:
            jurisdiction: Dict with keys: name, state_code, type (city/county), population
            
        Returns:
            Complete discovery results
        """
        async with self.semaphore:
            name = jurisdiction['name']
            state = jurisdiction['state_code']
            jtype = jurisdiction.get('type', 'city')
            
            logger.info(f"Discovering: {name}, {state} ({jtype})")
            
            results = {
                'jurisdiction': jurisdiction,
                'jurisdiction_id': jurisdiction.get('GEOID', ''),
                'discovery_timestamp': datetime.now().isoformat(),
                'websites': [],
                'youtube_channels': [],
                # URL probes including not_found/error with checked_at (UTC ISO); see youtube_channel_discovery
                'youtube_channel_checks': [],
                'other_video': [],
                'meeting_platforms': [],
                'social_media': {},
                'agenda_portals': [],
                'status': 'success'
            }
            
            try:
                # Step 1: Discover official website
                logger.debug(f"  Step 1/6: Finding website for {name}")
                website = await self._discover_website(name, state, jtype)
                
                if website:
                    results['websites'].append(website)
                    homepage_url = website.get('url')
                else:
                    logger.warning(f"  No website found for {name}, {state}")
                    results['status'] = 'partial'
                    homepage_url = None
                
                # Step 2: Discover YouTube channels
                logger.debug(f"  Step 2/6: Finding YouTube channels")
                yt_timeout_s = float(
                    os.getenv("JURISDICTION_DISCOVERY_YOUTUBE_TIMEOUT_SECONDS", "90") or "90"
                )
                if yt_timeout_s <= 0:
                    youtube_channels, youtube_channel_checks = await self._discover_youtube(
                        name, state, jtype, homepage_url
                    )
                else:
                    try:
                        youtube_channels, youtube_channel_checks = await asyncio.wait_for(
                            self._discover_youtube(name, state, jtype, homepage_url),
                            timeout=yt_timeout_s,
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "YouTube discovery timed out after {:.0f}s for {}, {} — continuing without channels",
                            yt_timeout_s,
                            name,
                            state,
                        )
                        youtube_channels = []
                        youtube_channel_checks = [
                            {
                                "outcome": "timeout",
                                "checked_at": datetime.now(timezone.utc).isoformat(),
                                "discovery_method": "youtube_discovery_batch",
                                "reason": (
                                    "exceeded {:.0f}s (JURISDICTION_DISCOVERY_YOUTUBE_TIMEOUT_SECONDS)".format(
                                        yt_timeout_s
                                    )
                                ),
                            }
                        ]
                
                # Add LocalView channels if available
                localview_channel = self._get_localview_channel(name, state)
                if localview_channel:
                    youtube_channels.append(localview_channel)
                
                results['youtube_channels'] = youtube_channels
                results['youtube_channel_checks'] = youtube_channel_checks or []
                
                # Step 3: Discover other video platforms (Vimeo, etc.)
                if homepage_url:
                    logger.debug(f"  Step 3/6: Finding other video platforms")
                    other_video = await self._discover_other_video(homepage_url)
                    results['other_video'] = other_video
                
                # Step 4: Detect meeting platforms
                if homepage_url:
                    logger.debug(f"  Step 4/6: Detecting meeting platforms")
                    platforms = await self._detect_meeting_platforms(
                        name, state, homepage_url
                    )
                    results['meeting_platforms'] = platforms
                
                # Step 5: Discover social media
                if homepage_url:
                    logger.debug(f"  Step 5/6: Finding social media accounts")
                    social = await self._discover_social_media(homepage_url, name, state)
                    results['social_media'] = social
                
                # Step 6: Find agenda portals
                if homepage_url:
                    logger.debug(f"  Step 6/6: Finding agenda portals")
                    agendas = await self._find_agenda_portals(homepage_url, name)
                    results['agenda_portals'] = agendas
                
                # Step 7: Wikidata enrichment (fallback for missing data)
                if self.enable_wikidata and (not homepage_url or results['status'] == 'partial'):
                    logger.debug(f"  Step 7/7: Wikidata enrichment (filling gaps)")
                    wd_timeout_s = float(
                        os.getenv("WIKIDATA_DISCOVERY_ENRICH_TIMEOUT_SECONDS", "60") or "60"
                    )
                    if wd_timeout_s <= 0:
                        await self._enrich_with_wikidata(results, name, state, jtype)
                    else:
                        try:
                            await asyncio.wait_for(
                                self._enrich_with_wikidata(results, name, state, jtype),
                                timeout=wd_timeout_s,
                            )
                        except asyncio.TimeoutError:
                            logger.warning(
                                "Wikidata enrichment timed out after {:.0f}s for {}, {} — continuing without it "
                                "(set WIKIDATA_DISCOVERY_ENRICH_TIMEOUT_SECONDS=0 to disable this cap)",
                                wd_timeout_s,
                                name,
                                state,
                            )
                
                # Calculate completeness score
                results['completeness_score'] = self._calculate_completeness(results)
                
                logger.success(f"✓ {name}: {results['completeness_score']:.0%} complete")
                
            except Exception as e:
                logger.error(f"  Error discovering {name}: {e}")
                results['status'] = 'error'
                results['error'] = str(e)
            
            return results

    async def _discover_jurisdiction_safe(self, jurisdiction: Dict) -> Dict:
        """
        Run ``discover_jurisdiction`` but never raise — one bad row must not abort the whole batch
        (otherwise Postgres ``*_scraped`` never gets a final commit).
        """
        try:
            return await self.discover_jurisdiction(jurisdiction)
        except Exception as e:
            logger.exception(
                "Discovery task crashed for GEOID={} name={}: {}",
                jurisdiction.get("GEOID"),
                jurisdiction.get("name"),
                e,
            )
            return {
                "jurisdiction": jurisdiction,
                "jurisdiction_id": str(jurisdiction.get("GEOID") or ""),
                "discovery_timestamp": datetime.now().isoformat(),
                "websites": [],
                "youtube_channels": [],
                "youtube_channel_checks": [],
                "other_video": [],
                "meeting_platforms": [],
                "social_media": {},
                "agenda_portals": [],
                "status": "error",
                "error": str(e),
                "completeness_score": 0.0,
            }
    
    async def _discover_website(
        self,
        name: str,
        state: str,
        jtype: str
    ) -> Optional[Dict]:
        """Discover official government website."""
        # Try common URL patterns
        name_clean = name.lower().replace(' ', '').replace("'", '')
        
        if jtype == 'county':
            name_clean = name_clean.replace('county', '')
        
        patterns = [
            f'https://www.{name_clean}{state.lower()}.gov',
            f'https://{name_clean}{state.lower()}.gov',
            f'https://www.{name_clean}.gov',
            f'https://{name_clean}.gov',
            f'https://www.{name_clean}.{state.lower()}.gov',
            f'https://www.cityof{name_clean}.com',
            f'https://www.{name_clean}.com',
        ]
        
        if jtype == 'county':
            patterns.extend([
                f'https://www.{name_clean}co.com',
                f'https://{name_clean}county.com',
                f'https://www.{name_clean}county.gov',
            ])
        
        client = httpx.AsyncClient(timeout=10, follow_redirects=True)
        
        for url in patterns:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    await client.aclose()
                    return {
                        'url': url,
                        'final_url': str(response.url),
                        'status': 'active',
                        'discovery_method': 'pattern_match'
                    }
            except:
                continue
        
        await client.aclose()
        return None
    
    async def _discover_youtube(
        self,
        name: str,
        state: str,
        jtype: str,
        homepage_url: Optional[str]
    ) -> Tuple[List[Dict], List[Dict[str, Any]]]:
        """Discover YouTube channels and probe audit rows (includes not_found/error + checked_at)."""
        city_name = name if jtype == 'city' else name.replace(' County', '').strip()
        county_name = name if jtype == 'county' else None

        async with YouTubeChannelDiscovery(self.youtube_api_key) as discovery:
            channels = await discovery.discover_channels(
                city_name=city_name,
                county_name=county_name,
                state_code=state,
                homepage_url=homepage_url
            )
            checks = list(getattr(discovery, "last_channel_probe_results", None) or [])
        return channels, checks
    
    async def _discover_other_video(self, homepage_url: str) -> List[Dict]:
        """Discover Vimeo and other video platforms."""
        video_platforms = []
        
        async with SocialMediaDiscovery() as discovery:
            social = await discovery._scrape_page_for_social(homepage_url)
            
            if social.get('vimeo'):
                for vimeo_url in social['vimeo']:
                    video_platforms.append({
                        'platform': 'vimeo',
                        'url': vimeo_url,
                        'discovery_method': 'website_scrape'
                    })
            
            if social.get('archive_org'):
                for archive_url in social['archive_org']:
                    video_platforms.append({
                        'platform': 'archive.org',
                        'url': archive_url,
                        'discovery_method': 'website_scrape'
                    })
        
        return video_platforms
    
    async def _detect_meeting_platforms(
        self,
        name: str,
        state: str,
        homepage_url: str
    ) -> List[Dict]:
        """Detect meeting platforms (Legistar, SuiteOne, Granicus, etc.)."""
        platforms = []
        
        client = httpx.AsyncClient(timeout=15, follow_redirects=True)
        
        # Check website for platform
        try:
            response = await client.get(homepage_url)
            if response.status_code == 200:
                platform_type = detect_platform(homepage_url, response.text)
                
                if platform_type:
                    platforms.append({
                        'type': platform_type,
                        'detected_on': homepage_url,
                        'method': 'html_analysis'
                    })
        except:
            pass
        
        # Check for Legistar API
        name_clean = name.lower().replace(' ', '').replace("'", '')
        legistar_slugs = [
            name_clean,
            f'{name_clean}{state.lower()}',
            f'{name_clean}county' if 'county' not in name_clean else name_clean
        ]
        
        for slug in legistar_slugs:
            try:
                url = f'https://webapi.legistar.com/v1/{slug}/events'
                response = await client.get(url, params={'$top': 1}, timeout=5)
                
                if response.status_code == 200:
                    platforms.append({
                        'type': 'legistar',
                        'api_url': url,
                        'slug': slug,
                        'method': 'api_test'
                    })
                    break
            except:
                continue
        
        # Check for SuiteOne (like Tuscaloosa)
        suiteone_patterns = [
            f'https://{name_clean}{state.lower()}.suiteonemedia.com',
            f'https://{name_clean}.suiteonemedia.com',
        ]
        
        for url in suiteone_patterns:
            try:
                response = await client.get(url, timeout=5)
                if response.status_code == 200 and 'suiteonemedia' in response.text.lower():
                    platforms.append({
                        'type': 'suiteone',
                        'url': url,
                        'method': 'url_test'
                    })
                    break
            except:
                continue
        
        # Check for Granicus
        granicus_patterns = [
            f'https://{name_clean}.granicus.com',
            f'https://{name_clean}{state.lower()}.granicus.com',
        ]
        
        for url in granicus_patterns:
            try:
                response = await client.get(url, timeout=5)
                if response.status_code == 200:
                    platforms.append({
                        'type': 'granicus',
                        'url': url,
                        'method': 'url_test'
                    })
                    break
            except:
                continue
        
        await client.aclose()
        return platforms
    
    async def _discover_social_media(
        self,
        homepage_url: str,
        name: str,
        state: str
    ) -> Dict[str, List[str]]:
        """Discover all social media accounts."""
        async with SocialMediaDiscovery() as discovery:
            social = await discovery.discover_from_website(
                homepage_url=homepage_url,
                jurisdiction_name=name,
                state=state
            )
        return social
    
    async def _find_agenda_portals(
        self,
        homepage_url: str,
        name: str
    ) -> List[Dict]:
        """Find agenda/document portals."""
        portals = []
        
        client = httpx.AsyncClient(timeout=15, follow_redirects=True)
        
        # Check main page for agenda links
        try:
            response = await client.get(homepage_url)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for agenda-related links
                for link in soup.find_all('a', href=True):
                    text = link.get_text().lower()
                    href = link.get('href', '')
                    
                    if any(word in text for word in ['agenda', 'minutes', 'meeting']):
                        # Check if it's an external portal
                        if any(domain in href for domain in ['suiteonemedia', 'granicus', 'civicclerk', 'municode']):
                            from urllib.parse import urljoin
                            full_url = urljoin(homepage_url, href)
                            
                            portals.append({
                                'url': full_url,
                                'link_text': text,
                                'discovery_method': 'homepage_scrape'
                            })
        except:
            pass
        
        await client.aclose()
        return portals
    
    async def _enrich_with_wikidata(
        self,
        results: Dict,
        name: str,
        state: str,
        jtype: str
    ):
        """
        Enrich discovery results with Wikidata (free fallback for missing data).
        
        Wikidata can provide:
        - Official website URL
        - Population
        - Social media accounts (Facebook, Twitter, YouTube)
        
        This is especially useful for smaller jurisdictions where direct discovery fails.
        """
        try:
            if not self.wikidata:
                return
            wiki_info = await self.wikidata.get_jurisdiction_info(name, state, jtype)
            
            if not wiki_info:
                return
            
            # Fill in website if missing
            if not results['websites'] and wiki_info.get('website'):
                results['websites'].append({
                    'url': wiki_info['website'],
                    'final_url': wiki_info['website'],
                    'status': 'active',
                    'discovery_method': 'wikidata',
                    'confidence': 0.8
                })
                logger.info(f"   ✓ Added website from Wikidata: {wiki_info['website']}")
                results['status'] = 'success'  # Upgrade from partial
            
            # Add YouTube channel if found
            if wiki_info.get('youtube_channel_id'):
                channel_exists = any(
                    c.get('channel_id') == wiki_info['youtube_channel_id']
                    for c in results['youtube_channels']
                )
                if not channel_exists:
                    results['youtube_channels'].append({
                        'channel_url': f"https://www.youtube.com/channel/{wiki_info['youtube_channel_id']}",
                        'channel_id': wiki_info['youtube_channel_id'],
                        'discovery_method': 'wikidata',
                        'confidence': 0.8
                    })
                    logger.info(f"   ✓ Added YouTube channel from Wikidata")
            
            # Add social media links if missing
            if not results.get('social_media'):
                results['social_media'] = {}
            
            if wiki_info.get('facebook') and not results['social_media'].get('facebook'):
                fb_url = f"https://www.facebook.com/{wiki_info['facebook']}"
                results['social_media']['facebook'] = [fb_url]
                logger.info(f"   ✓ Added Facebook from Wikidata: {fb_url}")
            
            if wiki_info.get('twitter') and not results['social_media'].get('twitter'):
                tw_url = f"https://twitter.com/{wiki_info['twitter']}"
                results['social_media']['twitter'] = [tw_url]
                logger.info(f"   ✓ Added Twitter from Wikidata: {tw_url}")
            
            # Update population if missing
            if wiki_info.get('population'):
                results['jurisdiction']['population'] = int(wiki_info['population'])
                
        except Exception as e:
            logger.debug(f"Wikidata enrichment failed for {name}, {state}: {e}")
    
    def _calculate_completeness(self, results: Dict) -> float:
        """Calculate how complete the discovery is (0.0 to 1.0)."""
        score = 0.0
        total = 6.0  # 6 data categories
        
        if results['websites']:
            score += 1.0
        if results['youtube_channels']:
            score += 1.0
        if results['meeting_platforms']:
            score += 1.0
        if results['social_media'] and any(results['social_media'].values()):
            score += 1.0
        if results['other_video']:
            score += 0.5
        if results['agenda_portals']:
            score += 1.5
        
        return min(score / total, 1.0)
    
    async def discover_batch(
        self,
        jurisdictions: List[Dict],
        save_interval: int = 100
    ) -> List[Dict]:
        """
        Discover data for a batch of jurisdictions with progress tracking.
        
        Args:
            jurisdictions: List of jurisdiction dicts
            save_interval: Save results every N jurisdictions
            
        Returns:
            List of discovery results
        """
        results = []
        
        logger.info(f"Starting batch discovery for {len(jurisdictions)} jurisdictions")
        
        # Process with progress bar (safe per task so one failure cannot skip the final persist)
        tasks = [self._discover_jurisdiction_safe(j) for j in jurisdictions]

        try:
            for i, task in enumerate(tqdm.as_completed(tasks, total=len(tasks))):
                result = await task
                results.append(result)

                if (i + 1) % save_interval == 0:
                    self._save_results(results, f'batch_{i+1}')
                    logger.info(f"Saved {i+1} results")

            self._save_results(results, 'final')
        except BaseException:
            if results:
                logger.warning(
                    "Batch interrupted or failed after {} result(s); attempting one last persist",
                    len(results),
                )
                try:
                    self._save_results(results, 'partial_recovery')
                except Exception as save_err:
                    logger.error("Partial persist failed: {}", save_err, exc_info=save_err)
            raise

        return results
    
    def _save_results(self, results: List[Dict], suffix: str = ''):
        """Save results to JSON and CSV."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save detailed JSON
        json_file = self.output_dir / f'discovery_results_{suffix}_{timestamp}.json'
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Saved JSON: {json_file}")
        
        # Save summary CSV
        summary = []
        for r in results:
            j = r['jurisdiction']
            summary.append({
                'name': j['name'],
                'state': j['state_code'],
                'type': j.get('type', 'city'),
                'population': j.get('population', 0),
                'website': r['websites'][0]['url'] if r['websites'] else '',
                'youtube_channels': len(r['youtube_channels']),
                'meeting_platforms': len(r['meeting_platforms']),
                'agenda_portals': len(r['agenda_portals']),
                'completeness': r.get('completeness_score', 0.0),
                'status': r['status']
            })
        
        csv_file = self.output_dir / f'discovery_summary_{suffix}_{timestamp}.csv'
        pd.DataFrame(summary).to_csv(csv_file, index=False)
        
        logger.info(f"Saved CSV: {csv_file}")
        
        # Save to Gold parquet with GEOID linking (merge with existing if incremental)
        gold_data = []
        for r in results:
            j = r['jurisdiction']
            gold_data.append({
                'jurisdiction_id': r.get('jurisdiction_id', ''),
                'jurisdiction_name': j.get('name', j.get('NAME', '')),
                'state': j.get('state_code', j.get('USPS', '')),
                'jurisdiction_type': j.get('type', j.get('jurisdiction_type', 'city')),
                'population': j.get('population', 0),
                'discovery_timestamp': r['discovery_timestamp'],
                'website_url': r['websites'][0]['url'] if r['websites'] else None,
                'youtube_channel_count': len(r['youtube_channels']),
                'youtube_channels': str(r['youtube_channels']),  # JSON string
                'meeting_platform_count': len(r['meeting_platforms']),
                'meeting_platforms': str(r['meeting_platforms']),  # JSON string
                'social_media': str(r['social_media']),  # JSON string
                'agenda_portal_count': len(r['agenda_portals']),
                'status': r['status']
            })
        
        gold_file = self.gold_output_dir / f'jurisdictions_details.parquet'
        
        # Handle empty results
        if not gold_data:
            logger.warning("No new discoveries to save")
            if gold_file.exists():
                logger.info(f"Keeping existing gold file: {gold_file}")
            return
        
        new_df = pl.DataFrame(gold_data)
        
        # Merge with existing if incremental mode
        if self.incremental and gold_file.exists():
            existing_df = pl.read_parquet(gold_file)
            # Remove old entries for jurisdictions we just discovered
            new_jurisdiction_ids = set(new_df['jurisdiction_id'].to_list())
            existing_df = existing_df.filter(
                ~pl.col('jurisdiction_id').is_in(new_jurisdiction_ids)
            )
            # Combine and sort
            merged_df = pl.concat([existing_df, new_df]).sort('jurisdiction_id')
            merged_df.write_parquet(gold_file)
            logger.info(f"Merged {len(new_df)} new + {len(existing_df)} existing = {len(merged_df)} total")
        else:
            new_df.write_parquet(gold_file)
        
        logger.info(f"Saved Gold parquet: {gold_file}")
    
    def _load_localview_channels(self) -> Dict[str, Dict]:
        """Load LocalView municipality channels from CSV."""
        channels_file = Path('data/cache/localview/municipality_channels.csv')
        if not channels_file.exists():
            logger.warning("LocalView channels file not found")
            return {}
        
        try:
            df = pl.read_csv(channels_file)
            # Create lookup: (city, state) -> channel_data
            channels = {}
            for row in df.iter_rows(named=True):
                # Parse "City, ST" format
                muni = row['municipality']
                if ',' in muni:
                    city = muni.split(',')[0].strip()
                    state = row['state']
                    key = (city.lower(), state.upper())
                    channels[key] = {
                        'channel_id': row['channel_id'],
                        'url': f"https://youtube.com/channel/{row['channel_id']}",
                        'source': 'localview',
                        'municipality': muni
                    }
            logger.info(f"Loaded {len(channels)} LocalView channels")
            return channels
        except Exception as e:
            logger.warning(f"Error loading LocalView channels: {e}")
            return {}
    
    def _get_localview_channel(self, name: str, state: str) -> Optional[Dict]:
        """Get LocalView channel for a jurisdiction if available."""
        key = (name.lower(), state.upper())
        return self.localview_channels.get(key)
    
    def _load_existing_discoveries(self) -> Dict[str, Dict]:
        """Load existing discoveries from gold parquet for incremental mode."""
        gold_file = self.gold_output_dir / 'jurisdictions_details.parquet'
        if not gold_file.exists():
            logger.info("No existing discoveries found (first run)")
            return {}
        
        try:
            from datetime import datetime, timedelta
            
            df = pl.read_parquet(gold_file)
            discoveries = {}
            
            # Create lookup: jurisdiction_id -> discovery data
            for row in df.iter_rows(named=True):
                jurisdiction_id = row['jurisdiction_id']
                timestamp = row['discovery_timestamp']
                
                # Check if discovery is stale (older than refresh_days)
                try:
                    discovery_date = datetime.fromisoformat(timestamp)
                    age_days = (datetime.now() - discovery_date).days
                    is_stale = age_days > self.refresh_days
                except:
                    is_stale = True  # Invalid timestamp = stale
                
                discoveries[jurisdiction_id] = {
                    'data': row,
                    'is_stale': is_stale,
                    'age_days': age_days if not is_stale else self.refresh_days + 1
                }
            
            fresh_count = sum(1 for d in discoveries.values() if not d['is_stale'])
            stale_count = len(discoveries) - fresh_count
            
            logger.info(f"Loaded {len(discoveries)} existing discoveries")
            logger.info(f"  Fresh (< {self.refresh_days} days): {fresh_count}")
            logger.info(f"  Stale (> {self.refresh_days} days): {stale_count}")
            
            return discoveries
        except Exception as e:
            logger.warning(f"Error loading existing discoveries: {e}")
            return {}
    
    def load_jurisdictions(
        self,
        state_filter: Optional[str] = None,
        top_n: Optional[int] = None
    ) -> List[Dict]:
        """
        Load jurisdiction list: **Postgres bronze** when ``DATABASE_URL`` / ``NEON_*`` is set,
        else legacy Parquet under ``data/gold/``.
        """
        db_url = (
            os.getenv("OPEN_NAVIGATOR_DATABASE_URL", "").strip()
            or os.getenv("NEON_DATABASE_URL_DEV", "").strip()
            or os.getenv("NEON_DATABASE_URL", "").strip()
            or os.getenv("DATABASE_URL", "").strip()
        )
        if db_url:
            try:
                import psycopg2

                from scripts.discovery.jurisdiction_discovery_pipeline import load_jurisdictions_from_postgres

                logger.info("Loading jurisdiction list from Postgres bronze…")
                with psycopg2.connect(db_url) as conn:
                    jurisdictions = load_jurisdictions_from_postgres(
                        conn,
                        state_filter=state_filter,
                        top_n=top_n,
                        include_municipalities=True,
                        include_counties=True,
                        include_schools=False,
                    )
                if jurisdictions:
                    if self.incremental and self.existing_discoveries:
                        original_count = len(jurisdictions)
                        jurisdictions = [
                            j
                            for j in jurisdictions
                            if j.get("GEOID", "") not in self.existing_discoveries
                            or self.existing_discoveries[j["GEOID"]]["is_stale"]
                        ]
                        skipped = original_count - len(jurisdictions)
                        if skipped > 0:
                            logger.info(
                                f"Incremental (gold parquet index): skipped {skipped} fresh GEOIDs"
                            )
                    return jurisdictions
            except Exception as e:
                logger.warning(f"Postgres bronze load failed ({e}); falling back to gold Parquet")

        logger.info("Loading jurisdiction list from gold Parquet (legacy)…")
        
        # Load from gold parquet files
        cities_file = Path('data/gold/jurisdictions_cities.parquet')
        counties_file = Path('data/gold/jurisdictions_counties.parquet')
        
        jurisdictions = []
        
        if cities_file.exists():
            logger.info("Loading cities from gold table...")
            cities_df = pl.read_parquet(cities_file)
            
            # Filter by state if requested
            if state_filter:
                cities_df = cities_df.filter(pl.col('USPS') == state_filter)
            
            # Convert to list of dicts
            for row in cities_df.iter_rows(named=True):
                jurisdictions.append({
                    'GEOID': row['GEOID'],
                    'name': row['NAME'].replace(' city', '').replace(' town', ''),
                    'state_code': row['USPS'],
                    'type': 'city',
                    'population': 0,  # Add from census if available
                    'ANSICODE': row.get('ANSICODE', ''),
                    'full_name': row['NAME']
                })
            
            logger.info(f"Loaded {len(jurisdictions)} cities")
        
        if counties_file.exists() and not state_filter:
            # Only load counties if not filtering (too many)
            logger.info("Skipping counties (use --state to include)")
        
        # Apply top_n limit if requested
        if top_n and top_n < len(jurisdictions):
            jurisdictions = jurisdictions[:top_n]
            logger.info(f"Limited to top {top_n} jurisdictions")
        
        if not jurisdictions:
            logger.warning("No jurisdictions found in gold tables, using sample list")
            jurisdictions = self._generate_sample_list(state_filter, top_n)
        
        # Filter out already-discovered jurisdictions if incremental mode
        if self.incremental and self.existing_discoveries:
            original_count = len(jurisdictions)
            jurisdictions = [
                j for j in jurisdictions
                if j.get('GEOID', '') not in self.existing_discoveries
                or self.existing_discoveries[j['GEOID']]['is_stale']
            ]
            skipped = original_count - len(jurisdictions)
            if skipped > 0:
                logger.info(f"Incremental mode: Skipping {skipped} already-discovered jurisdictions")
                logger.info(f"Will discover {len(jurisdictions)} new/stale jurisdictions")
        
        return jurisdictions
    
    def _generate_sample_list(
        self,
        state_filter: Optional[str],
        top_n: Optional[int]
    ) -> List[Dict]:
        """Generate sample jurisdiction list."""
        # Top 100 U.S. cities by population (sample)
        sample_cities = [
            {'name': 'New York', 'state_code': 'NY', 'type': 'city', 'population': 8336817},
            {'name': 'Los Angeles', 'state_code': 'CA', 'type': 'city', 'population': 3979576},
            {'name': 'Chicago', 'state_code': 'IL', 'type': 'city', 'population': 2693976},
            {'name': 'Houston', 'state_code': 'TX', 'type': 'city', 'population': 2320268},
            {'name': 'Phoenix', 'state_code': 'AZ', 'type': 'city', 'population': 1680992},
            {'name': 'Philadelphia', 'state_code': 'PA', 'type': 'city', 'population': 1584064},
            {'name': 'San Antonio', 'state_code': 'TX', 'type': 'city', 'population': 1547253},
            {'name': 'San Diego', 'state_code': 'CA', 'type': 'city', 'population': 1423851},
            {'name': 'Dallas', 'state_code': 'TX', 'type': 'city', 'population': 1343573},
            {'name': 'San Jose', 'state_code': 'CA', 'type': 'city', 'population': 1021795},
            {'name': 'Tuscaloosa', 'state_code': 'AL', 'type': 'city', 'population': 99600},
            # Add more...
        ]
        
        if state_filter:
            sample_cities = [c for c in sample_cities if c['state_code'] == state_filter]
        
        if top_n:
            sample_cities = sample_cities[:top_n]
        
        return sample_cities


async def main():
    """Command-line interface for discovery pipeline."""
    parser = argparse.ArgumentParser(
        description='Discover data sources for all U.S. cities and counties'
    )
    parser.add_argument(
        '--state',
        type=str,
        help='Filter to specific state (e.g., AL, CA, TX)'
    )
    parser.add_argument(
        '--top',
        type=int,
        help='Limit to top N jurisdictions by population'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all jurisdictions (warning: 20,000+)'
    )
    parser.add_argument(
        '--youtube-api-key',
        type=str,
        help='YouTube Data API v3 key for accurate statistics'
    )
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=10,
        help='Maximum concurrent requests (default: 10)'
    )
    parser.add_argument(
        '--no-incremental',
        action='store_true',
        help='Disable incremental mode (rediscover all jurisdictions)'
    )
    parser.add_argument(
        '--refresh-days',
        type=int,
        default=90,
        help='Days before discovery is considered stale (default: 90)'
    )
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = ComprehensiveDiscoveryPipeline(
        youtube_api_key=args.youtube_api_key,
        max_concurrent=args.max_concurrent,
        incremental=not args.no_incremental,
        refresh_days=args.refresh_days
    )
    
    # Load jurisdictions
    jurisdictions = pipeline.load_jurisdictions(
        state_filter=args.state,
        top_n=args.top if not args.all else None
    )
    
    logger.info(f"Will process {len(jurisdictions)} jurisdictions")
    
    if len(jurisdictions) > 100 and not args.all:
        logger.warning(f"Large batch ({len(jurisdictions)}). Use --all to confirm.")
        return
    
    # Run discovery
    results = await pipeline.discover_batch(jurisdictions)
    
    # Summary statistics
    print("\n" + "="*80)
    print("DISCOVERY COMPLETE!")
    print("="*80)
    
    if results:
        successful = sum(1 for r in results if r['status'] == 'success')
        avg_completeness = sum(r.get('completeness_score', 0) for r in results) / len(results)
        print(f"Total jurisdictions discovered: {len(results)}")
        print(f"Successful: {successful} ({successful/len(results):.1%})")
        print(f"Average completeness: {avg_completeness:.1%}")
    else:
        print("No new jurisdictions discovered (all already up-to-date)")
    
    print(f"\nResults saved to: {pipeline.output_dir}")
    print("="*80)


if __name__ == '__main__':
    asyncio.run(main())
