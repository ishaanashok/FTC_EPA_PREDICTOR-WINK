import os
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

from ftc_api_service import FTCApiService


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def _event_overlaps_range(event: Dict[str, Any], start: date, end: date) -> bool:
    event_start = _parse_date(event.get("dateStart"))
    event_end = _parse_date(event.get("dateEnd")) or event_start
    if not event_start:
        return False
    if not event_end:
        event_end = event_start
    return event_start <= end and event_end >= start


async def fetch_events_by_date_range(
    season: int,
    start_date: str,
    end_date: str,
    credentials: Dict[str, str],
    api_service: Optional[FTCApiService] = None,
    **params: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetch all events for a season from the FTC API and filter by date range.

    Args:
        season: FTC season year (e.g., 2025)
        start_date: ISO date string (YYYY-MM-DD) inclusive
        end_date: ISO date string (YYYY-MM-DD) inclusive
        credentials: Dict with username and api_key
        api_service: Optional initialized FTCApiService for reuse/testing
        params: Additional query params for the events endpoint
    """
    range_start = _parse_date(start_date)
    range_end = _parse_date(end_date)
    if not range_start or not range_end:
        raise ValueError("start_date and end_date must be valid ISO dates (YYYY-MM-DD)")
    if range_start > range_end:
        raise ValueError("start_date must be <= end_date")

    close_client = False
    if api_service is None:
        api_service = FTCApiService(credentials)
        await api_service.initialize()
        close_client = True

    try:
        events, metadata = await api_service.get_events(season, **params)
        if not events:
            return [], metadata

        filtered = [
            event for event in events if _event_overlaps_range(event, range_start, range_end)
        ]
        return filtered, metadata
    finally:
        if close_client:
            await api_service.close()


def load_credentials_from_env() -> Dict[str, str]:
    username = os.environ.get("FTC_API_USERNAME")
    api_key = os.environ.get("FTC_API_KEY")
    if not username or not api_key:
        raise RuntimeError("FTC_API_USERNAME and FTC_API_KEY must be set")
    return {"username": username, "api_key": api_key}
