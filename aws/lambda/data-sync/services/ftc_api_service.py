import os
import json
import logging
import asyncio
import aiohttp
import base64
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from email.utils import parsedate_to_datetime, formatdate

logger = logging.getLogger(__name__)

class FTCApiService:
    """Simplified FTC API service with HTTP caching header support"""
    
    def __init__(self, credentials: Dict[str, str]):
        self.base_url = "https://ftc-api.firstinspires.org/v2.0"
        
        # Create authorization token
        username = credentials['username']
        api_key = credentials['api_key']
        auth_string = f"{username}:{api_key}"
        self.auth_token = base64.b64encode(auth_string.encode()).decode()
        
        self.session = None
        
        # Default headers
        self.headers = {
            "Authorization": f"Basic {self.auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "FTC-Predictor-AWS/1.0"
        }
    
    async def initialize(self):
        """Initialize the HTTP session"""
        timeout = aiohttp.ClientTimeout(total=60, connect=15)
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=timeout
        )
        logger.info("FTC API Service initialized")
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            logger.info("FTC API Service closed")
    
    def _parse_last_modified(self, last_modified: str) -> Optional[datetime]:
        """Parse Last-Modified header to datetime"""
        try:
            return parsedate_to_datetime(last_modified)
        except Exception as e:
            logger.warning(f"Error parsing Last-Modified header '{last_modified}': {str(e)}")
            return None
    
    def _format_http_date(self, dt: datetime) -> str:
        """Format datetime for HTTP headers"""
        return formatdate(dt.timestamp(), usegmt=True)
    
    async def make_conditional_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None,
                                     if_modified_since: Optional[str] = None,
                                     if_none_match: Optional[str] = None,
                                     max_retries: int = 3) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Make a conditional HTTP request using caching headers
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            if_modified_since: If-Modified-Since header value
            if_none_match: If-None-Match header value (ETag)
            max_retries: Maximum number of retry attempts
        
        Returns:
            Tuple of (response_data, metadata)
            - response_data: None if 304 Not Modified, otherwise the response JSON
            - metadata: Dict containing response information
        """
        if not self.session:
            raise Exception("Session not initialized. Call initialize() first.")
        
        url = f"{self.base_url}{endpoint}"
        
        # Build conditional headers
        conditional_headers = {}
        
        if if_modified_since:
            conditional_headers['If-Modified-Since'] = if_modified_since
            # Also try FTC-specific header
            conditional_headers['FMS-OnlyModifiedSince'] = if_modified_since
        
        if if_none_match:
            conditional_headers['If-None-Match'] = if_none_match
        
        metadata = {
            'endpoint': endpoint,
            'requestHeaders': conditional_headers,
            'dataChanged': True,  # Assume data changed unless 304
            'responseSize': 0,
            'bandwidthSaved': 0,
            'status': None,
            'lastModified': None,
            'etag': None
        }
        
        for attempt in range(max_retries):
            try:
                logger.info(f"[FTC API] Request {attempt + 1}/{max_retries}: {endpoint}")
                if conditional_headers:
                    logger.info(f"[FTC API] Using conditional headers: {conditional_headers}")
                
                async with self.session.get(
                    url, 
                    params=params,
                    headers=conditional_headers
                ) as response:
                    
                    metadata['status'] = response.status
                    
                    # Handle 304 Not Modified
                    if response.status == 304:
                        logger.info(f"[FTC API] 304 Not Modified: {endpoint}")
                        metadata['dataChanged'] = False
                        metadata['bandwidthSaved'] = 1  # Indicate bandwidth was saved
                        
                        return None, metadata
                    
                    # Handle success response
                    elif response.status == 200:
                        response_data = await response.json()
                        response_text = await response.text()
                        metadata['responseSize'] = len(response_text.encode('utf-8'))
                        
                        # Extract caching headers
                        last_modified = response.headers.get('Last-Modified')
                        etag = response.headers.get('ETag')
                        
                        metadata['lastModified'] = last_modified
                        metadata['etag'] = etag
                        metadata['dataChanged'] = True
                        
                        logger.info(f"[FTC API] 200 OK: {endpoint} ({metadata['responseSize']} bytes)")
                        if last_modified:
                            logger.info(f"[FTC API] Last-Modified: {last_modified}")
                        if etag:
                            logger.info(f"[FTC API] ETag: {etag}")
                        
                        return response_data, metadata
                    
                    # Handle rate limiting
                    elif response.status == 429:
                        retry_after = int(response.headers.get('Retry-After', 60))
                        logger.warning(f"[FTC API] Rate limited, waiting {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    # Handle other errors
                    else:
                        error_text = await response.text()
                        logger.error(f"[FTC API] Error {response.status}: {error_text}")
                        raise Exception(f"HTTP {response.status}: {error_text}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"[FTC API] Timeout for {endpoint}, attempt {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                logger.error(f"[FTC API] Error for {endpoint}, attempt {attempt + 1}/{max_retries}: {str(e)}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        raise Exception(f"Failed to make request to {endpoint} after {max_retries} attempts")
    
    async def get_teams(self, season: int, **params) -> Tuple[Optional[List[Dict]], Dict[str, Any]]:
        """Get teams for a season with conditional request support"""
        endpoint = f"/{season}/teams"
        
        # Extract conditional request parameters
        if_modified_since = params.pop('if_modified_since', None)
        if_none_match = params.pop('if_none_match', None)
        
        response, metadata = await self.make_conditional_request(
            endpoint, 
            params,
            if_modified_since=if_modified_since,
            if_none_match=if_none_match
        )
        
        # Handle response format - FTC API returns {'teams': [...], 'teamCountTotal': ..., ...}
        if response is None:
            return None, metadata
        elif isinstance(response, dict):
            # Extract teams array from the response
            teams = response.get('teams', [])
            if isinstance(teams, list):
                return teams, metadata
            else:
                return None, metadata
        elif isinstance(response, list):
            # Fallback if API returns teams directly as a list
            return response, metadata
        else:
            return None, metadata
    
    async def get_events(self, season: int, **params) -> Tuple[Optional[List[Dict]], Dict[str, Any]]:
        """Get events for a season with conditional request support"""
        endpoint = f"/{season}/events"
        
        # Extract conditional request parameters
        if_modified_since = params.pop('if_modified_since', None)
        if_none_match = params.pop('if_none_match', None)
        
        response, metadata = await self.make_conditional_request(
            endpoint, 
            params,
            if_modified_since=if_modified_since,
            if_none_match=if_none_match
        )
        # Ensure response is a list of dicts or None
        if response is None:
            return None, metadata
        elif isinstance(response, dict):
            return [response], metadata
        elif isinstance(response, list):
            return response, metadata
        else:
            return None, metadata
    
    async def get_event_matches(self, season: int, event_code: str, 
                               tournament_level: str = "qual", **params) -> Tuple[Optional[List[Dict]], Dict[str, Any]]:
        """Get matches for an event with conditional request support"""
        endpoint = f"/{season}/matches/{event_code}"
        if tournament_level:
            params['tournamentLevel'] = tournament_level
            
        # Extract conditional request parameters
        if_modified_since = params.pop('if_modified_since', None)
        if_none_match = params.pop('if_none_match', None)
        
        response, metadata = await self.make_conditional_request(
            endpoint, 
            params,
            if_modified_since=if_modified_since,
            if_none_match=if_none_match
        )
        # Ensure response is a list of dicts or None
        if response is None:
            return None, metadata
        elif isinstance(response, dict):
            return [response], metadata
        elif isinstance(response, list):
            return response, metadata
        else:
            return None, metadata
    
    async def get_event_rankings(self, season: int, event_code: str, **params) -> Tuple[Optional[List[Dict]], Dict[str, Any]]:
        """Get rankings for an event with conditional request support"""
        endpoint = f"/{season}/rankings/{event_code}"
        
        # Extract conditional request parameters
        if_modified_since = params.pop('if_modified_since', None)
        if_none_match = params.pop('if_none_match', None)
        
        response, metadata = await self.make_conditional_request(
            endpoint, 
            params,
            if_modified_since=if_modified_since,
            if_none_match=if_none_match
        )
        # Ensure response is a list of dicts or None
        if response is None:
            return None, metadata
        elif isinstance(response, dict):
            return [response], metadata
        elif isinstance(response, list):
            return response, metadata
        else:
            return None, metadata
    
    async def get_event_teams(self, season: int, event_code: str, **params) -> Tuple[Optional[List[Dict]], Dict[str, Any]]:
        """Get teams for an event with conditional request support"""
        endpoint = f"/{season}/teams"
        params['eventCode'] = event_code
        
        # Extract conditional request parameters
        if_modified_since = params.pop('if_modified_since', None)
        if_none_match = params.pop('if_none_match', None)
        
        response, metadata = await self.make_conditional_request(
            endpoint, 
            params,
            if_modified_since=if_modified_since,
            if_none_match=if_none_match
        )
        # Ensure response is a list of dicts or None
        if response is None:
            return None, metadata
        elif isinstance(response, dict):
            return [response], metadata
        elif isinstance(response, list):
            return response, metadata
        else:
            return None, metadata
    
    async def batch_get_event_data(self, season: int, event_codes: List[str], 
                                  if_modified_since: Optional[str] = None) -> Dict[str, Dict]:
        """
        Batch get event data with optional conditional requests
        
        Args:
            season: Competition season
            event_codes: List of event codes to fetch
            if_modified_since: Optional If-Modified-Since header value
            
        Returns:
            Dict with event_code as key and event data as value
        """
        
        async def fetch_event_data(event_code: str):
            try:
                # Get event matches
                matches_data, matches_meta = await self.get_event_matches(
                    season, event_code, 
                    if_modified_since=if_modified_since
                )
                
                # Get event teams
                teams_data, teams_meta = await self.get_event_teams(
                    season, event_code,
                    if_modified_since=if_modified_since
                )
                
                # Get event rankings
                rankings_data, rankings_meta = await self.get_event_rankings(
                    season, event_code,
                    if_modified_since=if_modified_since
                )
                
                return {
                    'eventCode': event_code,
                    'matches': matches_data,
                    'teams': teams_data,
                    'rankings': rankings_data,
                    'metadata': {
                        'matches': matches_meta,
                        'teams': teams_meta,
                        'rankings': rankings_meta
                    }
                }
                
            except Exception as e:
                logger.error(f"Error fetching data for event {event_code}: {str(e)}")
                return {'eventCode': event_code, 'error': str(e)}
        
        # Limit concurrent requests to avoid rate limiting
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        async def fetch_with_semaphore(event_code: str):
            async with semaphore:
                return await fetch_event_data(event_code)
        
        # Execute all requests concurrently
        tasks = [fetch_with_semaphore(event_code) for event_code in event_codes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        event_data = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in batch fetch: {str(result)}")
                continue

            if isinstance(result, dict):
                event_code = result.get('eventCode')
                if event_code:
                    event_data[event_code] = result

        return event_data 