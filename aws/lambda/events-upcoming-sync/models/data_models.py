from datetime import datetime, timezone
from typing import Dict, Optional, Any


def convert_ftc_api_event(api_event: Dict[str, Any], season: int) -> Dict[str, Any]:
    """Convert FTC API event response to Event dict with None handling"""

    if season is None:
        raise ValueError("Invalid season parameter: season is None")

    try:
        season_int = int(season)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Invalid season parameter: season '{season}' cannot be converted to int: {exc}"
        )

    event_code = api_event.get("code")
    if not event_code:
        raise ValueError(f"Invalid event data: code is missing in {api_event}")

    event_id = api_event.get("eventId") or api_event.get("id") or f"{season_int}-{event_code}"
    region_code = api_event.get("regionCode") or api_event.get("region")

    def safe_int(value, default=0):
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def safe_string(value):
        if value is None:
            return ""
        return str(value).strip()

    return {
        "eventId": str(event_id),
        "code": str(event_code),
        "eventCode": str(event_code),
        "season": season_int,
        "eventName": safe_string(api_event.get("name")),
        "eventType": safe_string(api_event.get("type")),
        "dateStart": api_event.get("dateStart"),
        "dateEnd": api_event.get("dateEnd"),
        "venue": safe_string(api_event.get("venue")) if api_event.get("venue") else None,
        "address": safe_string(api_event.get("address")) if api_event.get("address") else None,
        "city": safe_string(api_event.get("city")) if api_event.get("city") else None,
        "state": safe_string(api_event.get("state")) if api_event.get("state") else None,
        "country": safe_string(api_event.get("country")) if api_event.get("country") else None,
        "timezone": safe_string(api_event.get("timezone")) if api_event.get("timezone") else None,
        "website": safe_string(api_event.get("website")) if api_event.get("website") else None,
        "liveStreamUrl": safe_string(api_event.get("liveStreamUrl"))
        if api_event.get("liveStreamUrl")
        else None,
        "teamCount": safe_int(api_event.get("teamCount")),
        "matchCount": safe_int(api_event.get("matchCount")),
        "teamNumbers": None,
        "lastUpdated": datetime.now(timezone.utc),
        "regionCode": safe_string(region_code) if region_code else None,
        "lastModified": None,
        "etag": None,
        "apiLastModified": None,
        "dataVersion": None,
        "matchesLastModified": None,
        "rankingsLastModified": None,
    }
