import json
import logging
import os
import asyncio
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Any, Optional, List, Tuple

import boto3

from services.ftc_api_service import FTCApiService
from services.dynamodb_service import DynamoDBService
from models.data_models import convert_ftc_api_event


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

FIELD_MAP: List[Tuple[str, str, str]] = [
    ("name", "eventName", "string"),
    ("type", "eventType", "string"),
    ("dateStart", "dateStart", "date"),
    ("dateEnd", "dateEnd", "date"),
    ("venue", "venue", "string"),
    ("address", "address", "string"),
    ("city", "city", "string"),
    ("state", "state", "string"),
    ("country", "country", "string"),
    ("timezone", "timezone", "string"),
    ("website", "website", "string"),
    ("liveStreamUrl", "liveStreamUrl", "string"),
    ("teamCount", "teamCount", "int"),
]


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


def _normalize(value: Any, value_type: str) -> Any:
    if value_type == "string":
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized if normalized else None
    if value_type == "int":
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    if value_type == "date":
        parsed = _parse_date(value)
        return parsed.isoformat() if parsed else None
    return value


def _diff_event(api_event: Dict[str, Any], db_event: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    diffs: Dict[str, Dict[str, Any]] = {}
    for api_key, db_key, value_type in FIELD_MAP:
        api_value = _normalize(api_event.get(api_key), value_type)
        db_value = _normalize(db_event.get(db_key), value_type)
        if api_value != db_value:
            diffs[db_key] = {"api": api_value, "db": db_value}
    return diffs


def _resolve_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
    lookahead_days: int,
) -> Tuple[date, date]:
    range_start = _parse_date(start_date) if start_date else None
    range_end = _parse_date(end_date) if end_date else None

    if range_start and range_end:
        if range_start > range_end:
            raise ValueError("startDate must be <= endDate")
        return range_start, range_end

    if range_start and not range_end:
        return range_start, range_start + timedelta(days=lookahead_days)

    today = datetime.now(timezone.utc).date()
    if lookahead_days < 0:
        return today + timedelta(days=lookahead_days), today
    return today, today + timedelta(days=lookahead_days)


def _load_credentials_from_env() -> Optional[Dict[str, str]]:
    username = os.environ.get("FTC_API_USERNAME")
    api_key = os.environ.get("FTC_API_KEY") or os.environ.get("FTC_API_TOKEN")
    if username and api_key:
        return {"username": username, "api_key": api_key}
    return None


class UpcomingEventsSyncService:
    def __init__(self, environment: Optional[str] = None):
        self.environment = environment or os.environ.get("ENVIRONMENT", "dev")
        self.db_service = DynamoDBService(self.environment)
        self.ftc_api: Optional[FTCApiService] = None

    async def initialize(self) -> None:
        credentials = _load_credentials_from_env()
        if not credentials:
            secrets_client = boto3.client("secretsmanager")
            secrets_name = os.environ.get(
                "SECRETS_NAME",
                f"FTC-API-Credentials-{self.environment}",
            )
            response = secrets_client.get_secret_value(SecretId=secrets_name)
            credentials = json.loads(response["SecretString"])

        self.ftc_api = FTCApiService(credentials)
        await self.ftc_api.initialize()

    async def sync_upcoming_events(
        self,
        season: int,
        range_start: date,
        range_end: date,
    ) -> Dict[str, Any]:
        if not self.ftc_api:
            await self.initialize()

        events_data, metadata = await self.ftc_api.get_events(season)
        events_data = events_data or []

        filtered_events = [
            event
            for event in events_data
            if _event_overlaps_range(event, range_start, range_end)
        ]

        created_events: List[str] = []
        updated_events: List[str] = []
        skipped_existing = 0
        skipped_missing_code = 0

        for event in filtered_events:
            event_code = event.get("code") or event.get("eventCode")
            if not event_code:
                skipped_missing_code += 1
                continue

            existing = self.db_service.get_event(event_code, season)
            diffs = _diff_event(event, existing) if existing else {}

            if existing and not diffs:
                skipped_existing += 1
                continue

            event_dict = convert_ftc_api_event(event, season)
            event_dict["lastModified"] = metadata.get("lastModified")
            event_dict["etag"] = metadata.get("etag")
            event_dict["apiLastModified"] = (
                datetime.now(timezone.utc) if metadata.get("lastModified") else None
            )
            saved = self.db_service.save_event(event_dict)
            if existing:
                if saved:
                    updated_events.append(event_code)
                else:
                    logger.warning("Failed to update event %s", event_code)
            else:
                if saved:
                    created_events.append(event_code)
                else:
                    logger.warning("Failed to save new event %s", event_code)

        return {
            "success": True,
            "season": season,
            "startDate": range_start.isoformat(),
            "endDate": range_end.isoformat(),
            "eventsFound": len(filtered_events),
            "eventsCreated": len(created_events),
            "eventsUpdated": len(updated_events),
            "eventsSkippedExisting": skipped_existing,
            "eventsSkippedMissingCode": skipped_missing_code,
            "createdEventCodes": created_events,
            "updatedEventCodes": updated_events,
            "bandwidthSaved": metadata.get("bandwidthSaved", 0),
        }

    async def close(self) -> None:
        if self.ftc_api:
            await self.ftc_api.close()
        self.db_service.clear_cache()


async def _async_lambda_handler(event, context):
    service = UpcomingEventsSyncService()

    try:
        env_season = os.environ.get("SEASON")
        lookahead_days = int(os.environ.get("LOOKAHEAD_DAYS", "30"))

        season = int(event.get("season") or env_season or 2025)
        lookahead_days = int(event.get("lookaheadDays") or lookahead_days)

        range_start, range_end = _resolve_date_range(
            event.get("startDate"),
            event.get("endDate"),
            lookahead_days,
        )

        logger.info(
            "Syncing upcoming events: season=%s, start=%s, end=%s",
            season,
            range_start,
            range_end,
        )

        result = await service.sync_upcoming_events(season, range_start, range_end)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as exc:
        logger.error("Upcoming events sync failed: %s", exc, exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"success": False, "error": str(exc)}),
        }
    finally:
        await service.close()


def lambda_handler(event, context):
    return asyncio.run(_async_lambda_handler(event, context))


def handler(event, context):
    return lambda_handler(event, context)
