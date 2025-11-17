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
        import ssl
        import certifi
        
        # Create SSL context with proper CA bundle
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        timeout = aiohttp.ClientTimeout(total=60, connect=15)
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=timeout,
            connector=connector
        )
        logger.info("FTC API Service initialized with SSL context")
    
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
                        try:
                            print(f"DEBUG: About to read response text for {endpoint}")
                            response_text = await response.text()
                            print(f"DEBUG: Response text length: {len(response_text)}")
                            print(f"DEBUG: First 200 chars: {response_text[:200]}")
                            
                            print(f"DEBUG: About to parse JSON")
                            response_data = json.loads(response_text)
                            print(f"DEBUG: JSON parsed successfully, type: {type(response_data)}")
                            
                            metadata['responseSize'] = len(response_text.encode('utf-8'))
                        except Exception as e:
                            print(f"DEBUG: Error in response processing: {e}")
                            print(f"DEBUG: Error type: {type(e)}")
                            raise
                        
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
    
    async def get_teams(self, season: int, if_modified_since: Optional[str] = None, **params) -> Tuple[Optional[List[Dict]], Dict[str, Any]]:
        """Get ALL teams for a season with pagination support and conditional request support"""
        endpoint = f"/{season}/teams"
        
        all_teams = []
        page = 1
        total_count = 0
        combined_metadata = {
            'endpoint': endpoint,
            'dataChanged': True,
            'responseSize': 0,
            'totalPages': 0,
            'totalRecords': 0,
            'lastModified': None,
            'etag': None
        }
        
        while True:
            # Add pagination parameters
            page_params = params.copy() if params else {}
            page_params['page'] = page
            
            logger.info(f"[FTC API] Fetching teams page {page} for season {season}")
            
            response, metadata = await self.make_conditional_request(
                endpoint, page_params, if_modified_since=if_modified_since
            )
            
            # If 304 Not Modified on first page, return early
            if response is None and page == 1:
                combined_metadata.update(metadata)
                combined_metadata['dataChanged'] = False
                return None, combined_metadata
            
            # If we get None response on subsequent pages, we might have hit the end
            if response is None:
                logger.info(f"[FTC API] No more data at page {page}, stopping pagination")
                break
            
            # Handle response structure - FTC API returns data in 'teams' field
            if isinstance(response, dict):
                teams_data = response.get('teams', [])
                total_count = response.get('totalCount', 0)
                page_count = response.get('pageCount', 1)
                current_page = response.get('pageCurrent', page)
                
                combined_metadata['totalPages'] = page_count
                combined_metadata['totalRecords'] = total_count
                
                logger.info(f"[FTC API] Page {current_page}/{page_count}: {len(teams_data)} teams, total: {total_count}")
            elif isinstance(response, list):
                # If response is already a list, assume it's the teams data
                teams_data = response
                logger.info(f"[FTC API] Page {page}: {len(teams_data)} teams (list format)")
            else:
                logger.warning(f"[FTC API] Unexpected response format: {type(response)}")
                teams_data = []
            
            # Add teams to our collection
            if teams_data:
                all_teams.extend(teams_data)
                
                # Update combined metadata
                combined_metadata['responseSize'] += metadata.get('responseSize', 0)
                if metadata.get('lastModified'):
                    combined_metadata['lastModified'] = metadata['lastModified']
                if metadata.get('etag'):
                    combined_metadata['etag'] = metadata['etag']
            
            # Check if we have more pages
            if isinstance(response, dict) and 'pageCount' in response:
                if page >= response['pageCount']:
                    logger.info(f"[FTC API] Reached last page {page}/{response['pageCount']}")
                    break
            elif len(teams_data) == 0:
                # If no teams returned, we've reached the end
                logger.info(f"[FTC API] No teams returned on page {page}, stopping")
                break
            
            page += 1
            
            # Safety check to prevent infinite loops
            if page > 500:  # Increased upper limit for large datasets
                logger.warning(f"[FTC API] Reached page limit (500), stopping pagination")
                break
        
        logger.info(f"[FTC API] Teams sync complete: {len(all_teams)} total teams collected across {page-1} pages")
        combined_metadata['totalRecords'] = len(all_teams)
        
        return all_teams, combined_metadata
    
    async def get_events(self, season: int, if_modified_since: Optional[str] = None, **params) -> Tuple[Optional[List[Dict]], Dict[str, Any]]:
        """Get ALL events for a season with pagination support and conditional request support"""
        endpoint = f"/{season}/events"
        
        all_events = []
        page = 1
        total_count = 0
        combined_metadata = {
            'endpoint': endpoint,
            'dataChanged': True,
            'responseSize': 0,
            'totalPages': 0,
            'totalRecords': 0,
            'lastModified': None,
            'etag': None
        }
        
        while True:
            # Add pagination parameters
            page_params = params.copy() if params else {}
            page_params['page'] = page
            
            logger.info(f"[FTC API] Fetching events page {page} for season {season}")
            
            response, metadata = await self.make_conditional_request(
                endpoint, page_params, if_modified_since=if_modified_since
            )
            
            # If 304 Not Modified on first page, return early
            if response is None and page == 1:
                combined_metadata.update(metadata)
                combined_metadata['dataChanged'] = False
                return None, combined_metadata
            
            # If we get None response on subsequent pages, we might have hit the end
            if response is None:
                logger.info(f"[FTC API] No more data at page {page}, stopping pagination")
                break
            
            # Handle response structure - FTC API returns data in 'events' field
            if isinstance(response, dict):
                events_data = response.get('events', [])
                total_count = response.get('totalCount', 0)
                page_count = response.get('pageCount', 1)
                current_page = response.get('pageCurrent', page)
                
                combined_metadata['totalPages'] = page_count
                combined_metadata['totalRecords'] = total_count
                
                logger.info(f"[FTC API] Page {current_page}/{page_count}: {len(events_data)} events, total: {total_count}")
            elif isinstance(response, list):
                # If response is already a list, assume it's the events data
                events_data = response
                logger.info(f"[FTC API] Page {page}: {len(events_data)} events (list format)")
            else:
                logger.warning(f"[FTC API] Unexpected response format: {type(response)}")
                events_data = []
            
            # Add events to our collection
            if events_data:
                all_events.extend(events_data)
                
                # Update combined metadata
                combined_metadata['responseSize'] += metadata.get('responseSize', 0)
                if metadata.get('lastModified'):
                    combined_metadata['lastModified'] = metadata['lastModified']
                if metadata.get('etag'):
                    combined_metadata['etag'] = metadata['etag']
            
            # Check if we have more pages
            if isinstance(response, dict) and 'pageCount' in response:
                if page >= response['pageCount']:
                    logger.info(f"[FTC API] Reached last page {page}/{response['pageCount']}")
                    break
            elif isinstance(response, dict) and 'eventCount' in response:
                # Events API doesn't use pagination - it returns all events in one response
                logger.info(f"[FTC API] Events API returned all {response['eventCount']} events in single response")
                break
            elif len(events_data) == 0:
                # If no events returned, we've reached the end
                logger.info(f"[FTC API] No events returned on page {page}, stopping")
                break
            
            page += 1
            
            # Safety check to prevent infinite loops
            if page > 500:  # Increased upper limit for large datasets
                logger.warning(f"[FTC API] Reached page limit (500), stopping pagination")
                break
        
        logger.info(f"[FTC API] Events sync complete: {len(all_events)} total events collected across {page-1} pages")
        combined_metadata['totalRecords'] = len(all_events)
        
        return all_events, combined_metadata
    
    async def get_event_matches(self, season: int, event_code: str, 
                               tournament_level: str = "qual", 
                               if_modified_since: Optional[str] = None,
                               **params) -> Tuple[Optional[List[Dict]], Dict[str, Any]]:
        """Get matches for an event with conditional request support"""
        endpoint = f"/{season}/matches/{event_code}"
        if tournament_level:
            params['tournamentLevel'] = tournament_level
        response, metadata = await self.make_conditional_request(
            endpoint, params, if_modified_since=if_modified_since
        )
        # Handle the response based on the API structure  
        if response is None:
            return None, metadata
        elif isinstance(response, dict):
            # For matches API, extract the 'matches' list from the response
            if 'matches' in response:
                return response['matches'], metadata
            else:
                # For other APIs that return a single item
                return [response], metadata
        elif isinstance(response, list):
            return response, metadata
        else:
            return None, metadata
    
    async def get_event_rankings(self, season: int, event_code: str, **params) -> Tuple[Optional[List[Dict]], Dict[str, Any]]:
        """Get rankings for an event with conditional request support"""
        endpoint = f"/{season}/rankings/{event_code}"
        response, metadata = await self.make_conditional_request(endpoint, params)
        if response is not None and isinstance(response, dict):
            response = [response]
        return response, metadata
    
    async def get_event_teams(self, season: int, event_code: str, **params) -> Tuple[Optional[List[Dict]], Dict[str, Any]]:
        """Get teams for an event with conditional request support"""
        endpoint = f"/{season}/teams"
        params['eventCode'] = event_code
        response, metadata = await self.make_conditional_request(endpoint, params)
        if response is not None and isinstance(response, dict):
            response = [response]
        return response, metadata
    
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