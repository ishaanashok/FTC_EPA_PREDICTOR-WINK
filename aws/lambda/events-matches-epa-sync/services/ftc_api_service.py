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

        username = credentials["username"]
        api_key = credentials["api_key"]
        auth_string = f"{username}:{api_key}"
        self.auth_token = base64.b64encode(auth_string.encode()).decode()

        self.session = None

        self.headers = {
            "Authorization": f"Basic {self.auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "FTC-Predictor-AWS/1.0",
        }

    async def initialize(self):
        """Initialize the HTTP session"""
        import ssl
        import certifi

        ssl_context = ssl.create_default_context(cafile=certifi.where())

        total_timeout = int(os.environ.get("FTC_API_TIMEOUT_TOTAL", "60"))
        connect_timeout = int(os.environ.get("FTC_API_TIMEOUT_CONNECT", "15"))
        timeout = aiohttp.ClientTimeout(total=total_timeout, connect=connect_timeout)
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=timeout,
            connector=connector,
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
        except Exception as exc:
            logger.warning("Error parsing Last-Modified header '%s': %s", last_modified, exc)
            return None

    def _format_http_date(self, dt: datetime) -> str:
        """Format datetime for HTTP headers"""
        return formatdate(dt.timestamp(), usegmt=True)

    async def make_conditional_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        if_modified_since: Optional[str] = None,
        if_none_match: Optional[str] = None,
        max_retries: int = 3,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        if not self.session:
            raise Exception("Session not initialized. Call initialize() first.")

        url = f"{self.base_url}{endpoint}"
        conditional_headers = {}

        if if_modified_since:
            conditional_headers["If-Modified-Since"] = if_modified_since
            conditional_headers["FMS-OnlyModifiedSince"] = if_modified_since

        if if_none_match:
            conditional_headers["If-None-Match"] = if_none_match

        metadata = {
            "endpoint": endpoint,
            "requestHeaders": conditional_headers,
            "dataChanged": True,
            "responseSize": 0,
            "bandwidthSaved": 0,
            "status": None,
            "lastModified": None,
            "etag": None,
        }

        for attempt in range(max_retries):
            try:
                logger.info("[FTC API] Request %s/%s: %s", attempt + 1, max_retries, endpoint)
                if conditional_headers:
                    logger.info("[FTC API] Using conditional headers: %s", conditional_headers)

                async with self.session.get(url, params=params, headers=conditional_headers) as response:
                    metadata["status"] = response.status

                    if response.status == 304:
                        logger.info("[FTC API] 304 Not Modified: %s", endpoint)
                        metadata["dataChanged"] = False
                        metadata["bandwidthSaved"] = 1
                        return None, metadata

                    if response.status == 200:
                        response_text = await response.text()
                        response_data = json.loads(response_text)

                        metadata["responseSize"] = len(response_text.encode("utf-8"))
                        metadata["lastModified"] = response.headers.get("Last-Modified")
                        metadata["etag"] = response.headers.get("ETag")
                        metadata["dataChanged"] = True

                        logger.info("[FTC API] 200 OK: %s (%s bytes)", endpoint, metadata["responseSize"])
                        if metadata["lastModified"]:
                            logger.info("[FTC API] Last-Modified: %s", metadata["lastModified"])
                        if metadata["etag"]:
                            logger.info("[FTC API] ETag: %s", metadata["etag"])

                        return response_data, metadata

                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning("[FTC API] Rate limited, waiting %s seconds", retry_after)
                        await asyncio.sleep(retry_after)
                        continue

                    error_text = await response.text()
                    logger.error("[FTC API] Error %s: %s", response.status, error_text)
                    raise Exception(f"HTTP {response.status}: {error_text}")

            except asyncio.TimeoutError:
                logger.warning("[FTC API] Timeout for %s, attempt %s/%s", endpoint, attempt + 1, max_retries)
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

            except Exception as exc:
                logger.error("[FTC API] Error for %s, attempt %s/%s: %s", endpoint, attempt + 1, max_retries, exc)
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        raise Exception(f"Failed to make request to {endpoint} after {max_retries} attempts")

    async def get_events(
        self, season: int, if_modified_since: Optional[str] = None, **params
    ) -> Tuple[Optional[List[Dict]], Dict[str, Any]]:
        endpoint = f"/{season}/events"

        all_events: List[Dict[str, Any]] = []
        page = 1
        combined_metadata = {
            "endpoint": endpoint,
            "dataChanged": True,
            "responseSize": 0,
            "totalPages": 0,
            "totalRecords": 0,
            "lastModified": None,
            "etag": None,
        }

        while True:
            page_params = params.copy() if params else {}
            page_params["page"] = page

            logger.info("[FTC API] Fetching events page %s for season %s", page, season)

            response, metadata = await self.make_conditional_request(
                endpoint, page_params, if_modified_since=if_modified_since
            )

            if response is None and page == 1:
                combined_metadata.update(metadata)
                combined_metadata["dataChanged"] = False
                return None, combined_metadata

            if response is None:
                logger.info("[FTC API] No more data at page %s, stopping pagination", page)
                break

            if isinstance(response, dict):
                events_data = response.get("events", [])
                total_count = response.get("totalCount", 0)
                page_count = response.get("pageCount", 1)
                current_page = response.get("pageCurrent", page)

                combined_metadata["totalPages"] = page_count
                combined_metadata["totalRecords"] = total_count

                logger.info(
                    "[FTC API] Page %s/%s: %s events, total: %s",
                    current_page,
                    page_count,
                    len(events_data),
                    total_count,
                )
            elif isinstance(response, list):
                events_data = response
                logger.info("[FTC API] Page %s: %s events (list format)", page, len(events_data))
            else:
                logger.warning("[FTC API] Unexpected response format: %s", type(response))
                events_data = []

            if events_data:
                all_events.extend(events_data)
                combined_metadata["responseSize"] += metadata.get("responseSize", 0)
                if metadata.get("lastModified"):
                    combined_metadata["lastModified"] = metadata["lastModified"]
                if metadata.get("etag"):
                    combined_metadata["etag"] = metadata["etag"]

            if isinstance(response, dict) and "pageCount" in response:
                if page >= response["pageCount"]:
                    logger.info("[FTC API] Reached last page %s/%s", page, response["pageCount"])
                    break
            elif isinstance(response, dict) and "eventCount" in response:
                logger.info(
                    "[FTC API] Events API returned all %s events in single response",
                    response["eventCount"],
                )
                break
            elif len(events_data) == 0:
                logger.info("[FTC API] No events returned on page %s, stopping", page)
                break

            page += 1

            if page > 500:
                logger.warning("[FTC API] Reached page limit (500), stopping pagination")
                break

        logger.info(
            "[FTC API] Events sync complete: %s total events collected across %s pages",
            len(all_events),
            page - 1,
        )
        combined_metadata["totalRecords"] = len(all_events)

        return all_events, combined_metadata

    async def get_event_matches(
        self,
        season: int,
        event_code: str,
        tournament_level: str = "qual",
        if_modified_since: Optional[str] = None,
        **params,
    ) -> Tuple[Optional[List[Dict]], Dict[str, Any]]:
        endpoint = f"/{season}/matches/{event_code}"
        if tournament_level:
            params["tournamentLevel"] = tournament_level
        response, metadata = await self.make_conditional_request(
            endpoint, params, if_modified_since=if_modified_since
        )
        if response is None:
            return None, metadata
        if isinstance(response, dict):
            if "matches" in response:
                return response["matches"], metadata
            return [response], metadata
        if isinstance(response, list):
            return response, metadata
        return None, metadata
