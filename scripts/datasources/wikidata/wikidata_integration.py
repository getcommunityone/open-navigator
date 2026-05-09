"""
Wikidata Integration for Civic Engagement Data

Wikidata is a collaborative knowledge base that powers Wikipedia's infoboxes.
It is the BEST FREE SOURCE for connecting people to organizations and locations.

SPARQL Endpoint: https://query.wikidata.org/sparql
REST API: https://www.wikidata.org/w/api.php
Query Service: https://query.wikidata.org/

KEY ADVANTAGES:
✅ Completely FREE - no API key required
✅ Highly interconnected - find person → see all linked organizations
✅ Structured data - triples (subject-predicate-object)
✅ Real Wikipedia data - millions of entities
✅ SPARQL queries - powerful graph queries

USE CASES FOR CIVIC ENGAGEMENT:
- Find all members of school boards in a state
- Find all mayors in a county
- Link people to their organizations
- Discover city council members
- Get organizational hierarchies

EXAMPLE QUERIES:
- "All school board members in Alabama"
- "All cities in Tuscaloosa County"
- "All elected officials in a city"
- "Organizations a person is affiliated with"

API DOCUMENTATION:
- SPARQL: https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service
- REST API: https://www.wikidata.org/w/api.php
- Query Examples: https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service/queries/examples

USAGE:
    from scripts.discovery.wikidata_integration import WikidataQuery
    
    wikidata = WikidataQuery()
    
    # Find school board members in Alabama
    members = await wikidata.find_school_board_members(state="Alabama")
    
    # Find all cities in a county
    cities = await wikidata.find_cities_in_county("Tuscaloosa County", "Alabama")
    
    # Find organizations a person is affiliated with
    orgs = await wikidata.find_person_organizations("Walt Maddox")
"""
import asyncio
from collections import defaultdict
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import httpx
import random
import hashlib
import json
import os
import time
from loguru import logger

try:
    from pyspark.sql import SparkSession
    from config.settings import settings
    SPARK_AVAILABLE = True
except ImportError:
    SPARK_AVAILABLE = False
    settings = None


def _env_truthy_integration(key: str, default: bool = False) -> bool:
    raw = (os.getenv(key) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


class WikidataQuery:
    """
    Query Wikidata using SPARQL for civic engagement data.
    
    Wikidata is completely FREE and provides structured knowledge
    about people, organizations, and places.
    """
    
    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
    REST_API = "https://www.wikidata.org/w/api.php"
    
    # Wikidata property IDs (for SPARQL queries)
    PROPERTIES = {
        "instance_of": "P31",  # What type of thing is this?
        "position_held": "P39",  # What position does this person hold?
        "member_of": "P463",  # What organization is this person a member of?
        "location": "P276",  # Where is this located?
        "located_in": "P131",  # Administrative territory
        "country": "P17",  # Country
        "state": "P131",  # State/province
        "occupation": "P106",  # Occupation
        "official_website": "P856",  # Official website
    }
    
    # Wikidata item IDs (common entities)
    ITEMS = {
        "human": "Q5",  # A human being
        "school_board": "Q7430706",  # School board
        "city": "Q515",  # City
        "county": "Q28575",  # County (US)
        "mayor": "Q30185",  # Mayor
        "city_council": "Q871419",  # City council
        "school_district": "Q1244442",  # School district
    }
    
    def __init__(self, cache_dir: str = "data/cache/wikidata"):
        """Initialize Wikidata query client."""
        cache_dir = os.getenv("WIKIDATA_CACHE_DIR", cache_dir)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # WDQS is easily overloaded; default spacing between requests is conservative.
        self._throttle_s = float(os.getenv("WIKIDATA_THROTTLE_SECONDS", "6") or "6")
        # After 429 / overload, temporarily add extra spacing (seconds, decays per successful request).
        self._burst_throttle_s = 0.0
        # WDQS often sends Retry-After: 120; sleeping two minutes per county stalls bulk loads.
        self._retry_after_cap_s = float(os.getenv("WIKIDATA_RETRY_AFTER_MAX_SECONDS", "45") or "45")
        self._cache_ttl_s = int(os.getenv("WIKIDATA_CACHE_TTL_SECONDS", str(7 * 24 * 60 * 60)))
        self._last_request_monotonic: float | None = None
        self._request_lock = asyncio.Lock()
        # When WDQS returns Retry-After (429) or overload-ish failures, apply a global cooldown
        # so other queries in this process don't immediately hammer the endpoint.
        self._cooldown_until_monotonic: float = 0.0
        # Transient TCP failures to WDQS — backoff can run longer than HTTP error retries.
        self._connect_retry_base_s = float(os.getenv("WIKIDATA_CONNECT_RETRY_BASE_SECONDS", "10") or "10")
        self._connect_retry_max_s = float(os.getenv("WIKIDATA_CONNECT_RETRY_MAX_SECONDS", "300") or "300")
        self._sparql_max_attempts = int(os.getenv("WIKIDATA_SPARQL_MAX_ATTEMPTS", "10") or "10")
        default_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        # Single UA, used when WIKIDATA_USER_AGENT_POOL is unset/empty.
        self._fallback_user_agent = (os.getenv("WIKIDATA_USER_AGENT") or "").strip() or default_ua
        # Multiple UAs separated by ### (commas occur inside typical Mozilla strings — do not split on comma).
        _pool_raw = (os.getenv("WIKIDATA_USER_AGENT_POOL") or "").strip()
        self._user_agent_pool = [s.strip() for s in _pool_raw.split("###") if s.strip()]
        self._user_agent_rr = 0
        self._headers_common = {
            "Accept": "application/sparql-results+json",
        }
        # Long throttles + VPN: reused keep-alive sockets often die → httpx.RemoteProtocolError.
        # Opt in with WIKIDATA_HTTP_KEEPALIVE=1 if you want pooled connections.
        _ka = (os.getenv("WIKIDATA_HTTP_KEEPALIVE") or "").strip().lower()
        self._http_keepalive = _ka in ("1", "true", "yes")

        # Per-slot network outcome counts (indexed when using WIKIDATA_USER_AGENT_POOL).
        self._ua_net: dict[str, dict[str, int]] = defaultdict(
            lambda: {"ok": 0, "429": 0, "5xx": 0, "tx": 0, "misc": 0},
        )
        self._wdqs_net_completed = 0
        self._log_ua_stats = _env_truthy_integration(
            "WIKIDATA_LOG_UA_STATS", default=bool(self._user_agent_pool)
        )
        self._ua_stats_every = max(
            1,
            int(os.getenv("WIKIDATA_UA_STATS_LOG_EVERY_NET", "10") or "10"),
        )

        if self._user_agent_pool:
            logger.info(
                f"WIKIDATA_USER_AGENT_POOL enabled: rotating {len(self._user_agent_pool)} User-Agent value(s)"
            )
            if self._log_ua_stats:
                logger.info(
                    f"UA net stats logging: every {self._ua_stats_every} WDQS completions "
                    "(WIKIDATA_LOG_UA_STATS / WIKIDATA_UA_STATS_LOG_EVERY_NET)"
                )

    def _ua_slot_label(self, user_agent: str) -> str:
        if user_agent in self._user_agent_pool:
            ix = self._user_agent_pool.index(user_agent)
            snip = user_agent.replace("\n", " ").strip()
            if len(snip) > 56:
                snip = snip[:53] + "…"
            return f"[slot {ix}] {snip}"
        snip = self._fallback_user_agent.replace("\n", " ").strip()
        if len(snip) > 56:
            snip = snip[:53] + "…"
        return f"[single] {snip}"

    def _record_ua_net(self, user_agent: str, outcome: str) -> None:
        label = self._ua_slot_label(user_agent)
        b = self._ua_net[label]
        if outcome == "ok":
            b["ok"] += 1
            self._wdqs_net_completed += 1
            if self._log_ua_stats and self._wdqs_net_completed % self._ua_stats_every == 0:
                self._log_wdqs_user_agent_stats()
            return
        if outcome == "429":
            b["429"] += 1
            return
        if outcome == "5xx":
            b["5xx"] += 1
            return
        if outcome == "tx":
            b["tx"] += 1
            return
        b["misc"] += 1

    def _log_wdqs_user_agent_stats(self) -> None:
        if not self._ua_net:
            return
        parts: List[str] = []
        total_ok = sum(d["ok"] for d in self._ua_net.values())
        total_bad = sum(
            d["429"] + d["5xx"] + d["tx"] + d["misc"] for d in self._ua_net.values()
        )
        denom = total_ok + total_bad if (total_ok + total_bad) else 1
        for label in sorted(self._ua_net.keys()):
            d = self._ua_net[label]
            o = d["ok"]
            t = d["429"] + d["5xx"] + d["tx"] + d["misc"]
            td = max(1, o + t)
            parts.append(f"{label} ok={o} errs={t} ok_share={(100.0 * o / td):.0f}%")
        logger.info(
            f"WDQS User-Agent net stats (overall ok_share={(100.0 * total_ok / denom):.0f}%): "
            + " │ ".join(parts)
        )

    def _pick_user_agent(self) -> str:
        if self._user_agent_pool:
            i = self._user_agent_rr % len(self._user_agent_pool)
            self._user_agent_rr += 1
            return self._user_agent_pool[i]
        return self._fallback_user_agent

    def _sparql_http_client(self, user_agent: str) -> httpx.AsyncClient:
        hdrs = {
            **self._headers_common,
            "User-Agent": user_agent,
        }
        if self._http_keepalive:
            limits = httpx.Limits(max_connections=32, max_keepalive_connections=8)
        else:
            hdrs["Connection"] = "close"
            limits = httpx.Limits(max_connections=32, max_keepalive_connections=0)
        return httpx.AsyncClient(timeout=180.0, headers=hdrs, limits=limits)

    def _cache_key(self, query: str) -> str:
        h = hashlib.sha256(query.encode("utf-8")).hexdigest()
        return h

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"sparql_{key}.json"

    def _read_cache(self, query: str) -> List[Dict] | None:
        key = self._cache_key(query)
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
        except Exception:
            return None

        fetched_at = payload.get("fetched_at_epoch")
        if fetched_at is None:
            return None
        age = time.time() - float(fetched_at)
        if age > self._cache_ttl_s:
            return None
        results = payload.get("results")
        # Never reuse cached empty result sets — WDQS can intermittently return 200 + zero rows
        # while overloaded; caching that poisons loads until TTL expires.
        if isinstance(results, list) and len(results) > 0:
            logger.info(f"SPARQL cache hit: {len(results)} row(s) (age={age:.0f}s)")
            return results
        return None

    def _write_cache(self, query: str, results: List[Dict]) -> None:
        if not results:
            return
        key = self._cache_key(query)
        path = self._cache_path(key)
        payload = {
            "fetched_at_epoch": time.time(),
            "results": results,
        }
        try:
            path.write_text(json.dumps(payload))
        except Exception:
            # Cache is best-effort; never fail the query for cache write issues.
            return
    
    async def execute_sparql(self, query: str) -> List[Dict]:
        """
        Execute a SPARQL query against Wikidata.
        
        Args:
            query: SPARQL query string
            
        Returns:
            List of result dicts
        """
        logger.info(f"Executing SPARQL query...")
        logger.debug(f"Query: {query}")

        cached = self._read_cache(query)
        if cached is not None:
            return cached

        async with self._request_lock:
            now = time.monotonic()
            if self._cooldown_until_monotonic > now:
                sleep_s = self._cooldown_until_monotonic - now
                logger.warning(f"WDQS cooldown active: sleeping {sleep_s:.1f}s before next request")
                await asyncio.sleep(sleep_s)

            min_gap = self._throttle_s + max(0.0, self._burst_throttle_s)
            if min_gap > 0:
                now = time.monotonic()
                if self._last_request_monotonic is not None:
                    elapsed = now - self._last_request_monotonic
                    if elapsed < min_gap:
                        sleep_s = min_gap - elapsed
                        logger.debug(f"Throttling Wikidata request: sleeping {sleep_s:.2f}s")
                        await asyncio.sleep(sleep_s)
                self._last_request_monotonic = time.monotonic()

        max_attempts = max(3, self._sparql_max_attempts)
        base_delay_s = 2.0

        for attempt in range(1, max_attempts + 1):
            user_agent = self._pick_user_agent()
            try:
                async with self._sparql_http_client(user_agent) as client:
                    response = await client.get(
                        self.SPARQL_ENDPOINT,
                        params={
                            "query": query,
                            "format": "json"
                        },
                    )
                    response.raise_for_status()
                    data = response.json()

                    bindings = data.get("results", {}).get("bindings", [])
                    results: List[Dict] = []

                    for binding in bindings:
                        result = {}
                        for key, value in binding.items():
                            result[key] = value.get("value")
                        results.append(result)

                    if len(results) == 0:
                        logger.warning(
                            "WDQS returned HTTP 200 with zero bindings — treating as non-cacheable; "
                            "if this persists, raise WIKIDATA_THROTTLE_SECONDS or retry later."
                        )
                    else:
                        logger.info(f"✅ Query returned {len(results)} results")
                    self._write_cache(query, results)
                    self._record_ua_net(user_agent, "ok")
                    # Ease backoff after successes.
                    self._burst_throttle_s = max(0.0, self._burst_throttle_s * 0.5)
                    return results

            except (asyncio.CancelledError, KeyboardInterrupt):
                raise

            except httpx.HTTPStatusError as e:
                status = e.response.status_code

                if status == 429:
                    self._record_ua_net(user_agent, "429")
                    if attempt == 1:
                        logger.warning(
                            "Wikidata rate limited (429). Raise WIKIDATA_THROTTLE_SECONDS if this persists."
                        )

                    retry_after = e.response.headers.get("Retry-After")
                    wait_s: float = base_delay_s
                    if retry_after:
                        try:
                            wait_s = float(str(retry_after).strip())
                        except ValueError:
                            wait_s = min(base_delay_s * (2 ** (attempt - 1)), self._retry_after_cap_s)
                    else:
                        wait_s = min(base_delay_s * (2 ** (attempt - 1)), 60.0)
                        wait_s = wait_s + random.uniform(0.0, 1.5)

                    # Honor server cooldown but avoid multi-minute stalls unless user raises cap env.
                    if self._retry_after_cap_s > 0:
                        capped = min(wait_s, self._retry_after_cap_s)
                        if capped < wait_s - 1e-3:
                            logger.warning(
                                f"Capping Retry-After {wait_s:.0f}s → {capped:.0f}s "
                                f"(WIKIDATA_RETRY_AFTER_MAX_SECONDS={self._retry_after_cap_s:.0f})"
                            )
                        wait_s = capped

                    wait_s += random.uniform(0.25, 1.25)
                    # Fewer successive 429s: widen spacing for subsequent queries in this process.
                    self._burst_throttle_s = min(120.0, max(self._burst_throttle_s + 8.0, 12.0))
                    # Global cooldown so other queries don't immediately get 429'd too.
                    self._cooldown_until_monotonic = max(self._cooldown_until_monotonic, time.monotonic() + wait_s)

                    logger.warning(
                        f"Wikidata rate limited (429). Sleeping {wait_s:.1f}s then retrying "
                        f"(attempt {attempt}/{max_attempts})"
                    )
                    await asyncio.sleep(wait_s)
                    continue

                if status in (502, 503, 504):
                    self._record_ua_net(user_agent, "5xx")
                    wait_s = min(base_delay_s * (2 ** (attempt - 1)), 60.0) + random.uniform(0.0, 2.0)
                    self._cooldown_until_monotonic = max(self._cooldown_until_monotonic, time.monotonic() + wait_s)
                    logger.warning(
                        f"Wikidata query service error ({status}). Sleeping {wait_s:.1f}s then retrying "
                        f"(attempt {attempt}/{max_attempts})"
                    )
                    await asyncio.sleep(wait_s)
                    continue

                if status == 500:
                    body = ""
                    try:
                        body = e.response.text or ""
                    except Exception:
                        body = ""

                    if (
                        "java.util.concurrent.TimeoutException" in body
                        or "SystemOverloadFilter" in body
                        or "RequestConcurrencyFilter" in body
                    ):
                        self._record_ua_net(user_agent, "5xx")
                        wait_s = min(base_delay_s * (2 ** (attempt - 1)), 90.0) + random.uniform(0.0, 3.0)
                        self._cooldown_until_monotonic = max(self._cooldown_until_monotonic, time.monotonic() + wait_s)
                        logger.warning(
                            "Wikidata query service error (500 timeout/overload). "
                            f"Sleeping {wait_s:.1f}s then retrying (attempt {attempt}/{max_attempts})"
                        )
                        await asyncio.sleep(wait_s)
                        continue

                self._record_ua_net(user_agent, "misc")
                logger.error(f"SPARQL query failed: {status}")
                logger.error(f"Response: {e.response.text}")
                raise

            except httpx.ConnectError as e:
                self._record_ua_net(user_agent, "tx")
                if attempt >= max_attempts:
                    logger.error(f"Error executing SPARQL query: {e}")
                    raise
                wait_s = min(
                    self._connect_retry_base_s * (2 ** (attempt - 1)),
                    max(self._connect_retry_max_s, self._connect_retry_base_s),
                )
                wait_s += random.uniform(0.5, 2.5)
                self._cooldown_until_monotonic = max(self._cooldown_until_monotonic, time.monotonic() + wait_s)
                logger.warning(
                    f"WDQS connect error ({type(e).__name__}): {e}. "
                    f"Sleeping {wait_s:.1f}s then retrying (attempt {attempt}/{max_attempts})"
                )
                await asyncio.sleep(wait_s)
                continue

            except httpx.TimeoutException as e:
                self._record_ua_net(user_agent, "tx")
                if attempt >= max_attempts:
                    logger.error(f"Error executing SPARQL query: {e}")
                    raise
                wait_s = min(base_delay_s * (2 ** (attempt - 1)), 90.0) + random.uniform(0.5, 3.0)
                self._cooldown_until_monotonic = max(self._cooldown_until_monotonic, time.monotonic() + wait_s)
                logger.warning(
                    f"SPARQL query timeout: {e}. Sleeping {wait_s:.1f}s then retrying "
                    f"(attempt {attempt}/{max_attempts})"
                )
                await asyncio.sleep(wait_s)
                continue

            except httpx.RequestError as e:
                self._record_ua_net(user_agent, "tx")
                # Any transport-level issue (DNS, TLS, socket reset, read error, etc.).
                if attempt >= max_attempts:
                    logger.error(f"Error executing SPARQL query: {type(e).__name__}: {e}")
                    raise
                wait_s = min(
                    self._connect_retry_base_s * (2 ** (attempt - 1)),
                    max(self._connect_retry_max_s, self._connect_retry_base_s),
                )
                wait_s += random.uniform(0.5, 2.5)
                self._cooldown_until_monotonic = max(self._cooldown_until_monotonic, time.monotonic() + wait_s)
                logger.warning(
                    f"WDQS request error ({type(e).__name__}): {e}. "
                    f"Sleeping {wait_s:.1f}s then retrying (attempt {attempt}/{max_attempts})"
                )
                await asyncio.sleep(wait_s)
                continue

            except Exception as e:
                self._record_ua_net(user_agent, "misc")
                if attempt < max_attempts:
                    wait_s = min(base_delay_s * (2 ** (attempt - 1)), 45.0) + random.uniform(0.0, 1.5)
                    logger.warning(
                        f"SPARQL query error ({type(e).__name__}): {e}. Sleeping {wait_s:.1f}s then retrying "
                        f"(attempt {attempt}/{max_attempts})"
                    )
                    await asyncio.sleep(wait_s)
                    continue
                logger.error(f"Error executing SPARQL query: {e}")
                raise

        if self._log_ua_stats and self._ua_net:
            self._log_wdqs_user_agent_stats()
        raise RuntimeError("SPARQL query failed after retries")
    
    async def find_school_board_members(
        self,
        state: Optional[str] = None,
        district: Optional[str] = None
    ) -> List[Dict]:
        """
        Find school board members.
        
        Args:
            state: State name (e.g., "Alabama")
            district: School district name (optional)
            
        Returns:
            List of school board member dicts
        """
        # SPARQL query to find school board members
        query = """
        SELECT ?person ?personLabel ?board ?boardLabel ?position ?positionLabel
        WHERE {
          # Person holds a position
          ?person wdt:P39 ?position .
          
          # Position is on a school board
          ?position wdt:P31 wd:Q7430706 .  # instance of school board
          
          # Board is the organization
          ?person wdt:P463 ?board .
          
          # Filter by state if provided
          FILTER_STATE
          
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 100
        """
        
        # Add state filter if provided
        if state:
            state_filter = f'FILTER(CONTAINS(LCASE(?boardLabel), "{state.lower()}")).'
            query = query.replace("FILTER_STATE", state_filter)
        else:
            query = query.replace("FILTER_STATE", "")
        
        results = await self.execute_sparql(query)
        
        # Format results
        members = []
        for result in results:
            members.append({
                "name": result.get("personLabel"),
                "wikidata_id": result.get("person", "").split("/")[-1],
                "board": result.get("boardLabel"),
                "board_id": result.get("board", "").split("/")[-1],
                "position": result.get("positionLabel"),
                "source": "wikidata",
                "fetched_at": datetime.utcnow().isoformat()
            })
        
        logger.info(f"✅ Found {len(members)} school board members")
        return members
    
    async def find_cities_in_county(
        self,
        county: str,
        state: Optional[str] = None
    ) -> List[Dict]:
        """
        Find all cities in a county.
        
        Args:
            county: County name (e.g., "Tuscaloosa County")
            state: State name (e.g., "Alabama")
            
        Returns:
            List of city dicts
        """
        query = f"""
        SELECT ?city ?cityLabel ?population ?website
        WHERE {{
          # City is an instance of city
          ?city wdt:P31 wd:Q515 .
          
          # Located in the county
          ?city wdt:P131 ?county .
          ?county rdfs:label "{county}"@en .
          
          # Optional: population
          OPTIONAL {{ ?city wdt:P1082 ?population . }}
          
          # Optional: official website
          OPTIONAL {{ ?city wdt:P856 ?website . }}
          
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        """
        
        results = await self.execute_sparql(query)
        
        cities = []
        for result in results:
            cities.append({
                "name": result.get("cityLabel"),
                "wikidata_id": result.get("city", "").split("/")[-1],
                "population": result.get("population"),
                "website": result.get("website"),
                "county": county,
                "state": state,
                "source": "wikidata",
                "fetched_at": datetime.utcnow().isoformat()
            })
        
        logger.info(f"✅ Found {len(cities)} cities in {county}")
        return cities
    
    async def find_person_organizations(self, person_name: str) -> List[Dict]:
        """
        Find all organizations a person is affiliated with.
        
        Args:
            person_name: Person's name (e.g., "Walt Maddox")
            
        Returns:
            List of organization dicts
        """
        query = f"""
        SELECT ?person ?personLabel ?org ?orgLabel ?position ?positionLabel
        WHERE {{
          # Find person by name
          ?person rdfs:label "{person_name}"@en .
          ?person wdt:P31 wd:Q5 .  # is a human
          
          # Person is member of organization
          ?person wdt:P463 ?org .
          
          # Optional: position held
          OPTIONAL {{ ?person wdt:P39 ?position . }}
          
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        """
        
        results = await self.execute_sparql(query)
        
        organizations = []
        for result in results:
            organizations.append({
                "person_name": result.get("personLabel"),
                "person_id": result.get("person", "").split("/")[-1],
                "organization": result.get("orgLabel"),
                "organization_id": result.get("org", "").split("/")[-1],
                "position": result.get("positionLabel"),
                "source": "wikidata",
                "fetched_at": datetime.utcnow().isoformat()
            })
        
        logger.info(f"✅ Found {len(organizations)} organizations for {person_name}")
        return organizations
    
    async def find_elected_officials(
        self,
        city: Optional[str] = None,
        state: Optional[str] = None,
        position_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Find elected officials.
        
        Args:
            city: City name
            state: State name
            position_type: Type of position (e.g., "mayor", "council member")
            
        Returns:
            List of official dicts
        """
        # Build SPARQL query dynamically
        filters = []
        if city:
            filters.append(f'FILTER(CONTAINS(LCASE(?cityLabel), "{city.lower()}")).')
        if state:
            filters.append(f'FILTER(CONTAINS(LCASE(?stateLabel), "{state.lower()}")).')
        
        filter_clause = " ".join(filters) if filters else ""
        
        query = f"""
        SELECT ?person ?personLabel ?position ?positionLabel ?location ?locationLabel
        WHERE {{
          # Person holds a position
          ?person wdt:P39 ?position .
          ?person wdt:P31 wd:Q5 .  # is a human
          
          # Position is at a location
          OPTIONAL {{ ?position wdt:P276 ?location . }}
          
          {filter_clause}
          
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 100
        """
        
        results = await self.execute_sparql(query)
        
        officials = []
        for result in results:
            officials.append({
                "name": result.get("personLabel"),
                "wikidata_id": result.get("person", "").split("/")[-1],
                "position": result.get("positionLabel"),
                "location": result.get("locationLabel"),
                "city": city,
                "state": state,
                "source": "wikidata",
                "fetched_at": datetime.utcnow().isoformat()
            })
        
        logger.info(f"✅ Found {len(officials)} elected officials")
        return officials
    
    async def get_jurisdiction_info(
        self,
        name: str,
        state: str,
        jurisdiction_type: str = "city"
    ) -> Optional[Dict]:
        """
        Get jurisdiction information from Wikidata (website, population, etc.).
        
        Args:
            name: Jurisdiction name (e.g., "Alexandria", "Alabaster")
            state: State code or name (e.g., "AL" or "Alabama")
            jurisdiction_type: "city" or "county"
            
        Returns:
            Dict with jurisdiction info or None if not found
        """
        # Map state codes to full names for better Wikidata matching
        state_map = {
            "AL": "Alabama", "GA": "Georgia", "IN": "Indiana",
            "MA": "Massachusetts", "WA": "Washington", "WI": "Wisconsin"
        }
        state_name = state_map.get(state, state)
        
        # Choose Wikidata item type
        item_type = "Q515" if jurisdiction_type == "city" else "Q28575"  # city or county
        
        # Clean up name (remove "city", "CDP", etc.)
        clean_name = name.replace(" city", "").replace(" CDP", "").replace(" town", "").strip()
        
        query = f"""
        SELECT DISTINCT ?place ?placeLabel ?website ?population ?facebook ?twitter ?youtube
        WHERE {{
          # Place is an instance of city/county
          ?place wdt:P31 wd:{item_type} .
          
          # Located in the state
          ?place wdt:P131+ ?state .
          ?state wdt:P31 wd:Q35657 .  # US state
          ?state rdfs:label "{state_name}"@en .
          
          # Name matches (flexible matching)
          ?place rdfs:label ?placeLabel .
          FILTER(LANG(?placeLabel) = "en")
          FILTER(CONTAINS(LCASE(?placeLabel), "{clean_name.lower()}"))
          
          # Optional: official website
          OPTIONAL {{ ?place wdt:P856 ?website . }}
          
          # Optional: population
          OPTIONAL {{ ?place wdt:P1082 ?population . }}
          
          # Optional: social media
          OPTIONAL {{ ?place wdt:P2013 ?facebook . }}  # Facebook username
          OPTIONAL {{ ?place wdt:P2002 ?twitter . }}   # Twitter username
          OPTIONAL {{ ?place wdt:P2397 ?youtube . }}   # YouTube channel ID
          
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 5
        """
        
        try:
            results = await self.execute_sparql(query)
            
            if not results:
                logger.debug(f"No Wikidata entry found for {name}, {state}")
                return None
            
            # Take first result (most likely match)
            result = results[0]
            
            info = {
                "name": result.get("placeLabel", name),
                "wikidata_id": result.get("place", "").split("/")[-1],
                "website": result.get("website"),
                "population": result.get("population"),
                "facebook": result.get("facebook"),
                "twitter": result.get("twitter"),
                "youtube_channel_id": result.get("youtube"),
                "state": state,
                "source": "wikidata",
                "confidence": 0.8,  # Medium confidence for automated matching
                "fetched_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"✅ Found Wikidata entry for {name}, {state}")
            if info.get("website"):
                logger.info(f"   Website: {info['website']}")
            
            return info
            
        except Exception as e:
            logger.error(f"Error querying Wikidata for {name}, {state}: {e}")
            return None
    
    def save_to_json(self, data: List[Dict], filename: str):
        """Save data to JSON cache."""
        import json
        
        filepath = self.cache_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"💾 Saved {len(data)} records to {filepath}")


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example usage of Wikidata integration."""
    
    wikidata = WikidataQuery()
    
    # Example 1: Find school board members in Alabama
    logger.info("\n" + "="*80)
    logger.info("Example 1: Find school board members in Alabama")
    logger.info("="*80)
    
    try:
        members = await wikidata.find_school_board_members(state="Alabama")
        
        print(f"\n✅ Found {len(members)} school board members in Alabama:")
        for member in members[:10]:  # Show first 10
            print(f"   • {member['name']} - {member['board']}")
            if member.get('position'):
                print(f"     Position: {member['position']}")
        
        if members:
            wikidata.save_to_json(members, "alabama_school_board_members.json")
        
    except Exception as e:
        logger.error(f"Error: {e}")
    
    # Example 2: Find cities in Tuscaloosa County
    logger.info("\n" + "="*80)
    logger.info("Example 2: Find cities in Tuscaloosa County")
    logger.info("="*80)
    
    try:
        cities = await wikidata.find_cities_in_county("Tuscaloosa County", "Alabama")
        
        print(f"\n✅ Found {len(cities)} cities in Tuscaloosa County:")
        for city in cities[:10]:
            print(f"   • {city['name']}")
            if city.get('population'):
                print(f"     Population: {city['population']}")
            if city.get('website'):
                print(f"     Website: {city['website']}")
        
        if cities:
            wikidata.save_to_json(cities, "tuscaloosa_county_cities.json")
        
    except Exception as e:
        logger.error(f"Error: {e}")
    
    # Example 3: Find organizations for a person
    logger.info("\n" + "="*80)
    logger.info("Example 3: Find organizations for Walt Maddox")
    logger.info("="*80)
    
    try:
        orgs = await wikidata.find_person_organizations("Walt Maddox")
        
        print(f"\n✅ Found {len(orgs)} organizations:")
        for org in orgs:
            print(f"   • {org['organization']}")
            if org.get('position'):
                print(f"     Position: {org['position']}")
        
        if orgs:
            wikidata.save_to_json(orgs, "walt_maddox_organizations.json")
        
    except Exception as e:
        logger.error(f"Error: {e}")
    
    logger.info("\n✅ Examples complete!")


if __name__ == "__main__":
    asyncio.run(example_usage())
