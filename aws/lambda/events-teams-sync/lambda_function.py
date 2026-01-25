import json
import logging
import os
import asyncio
from datetime import datetime, timezone, timedelta, date
from typing import Any, Dict, List, Optional, Tuple

import boto3

from services.events_date_range_service import fetch_events_by_date_range
from services.ftc_api_service import FTCApiService
from services.dynamodb_service import DynamoDBService


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


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


def _resolve_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
    days_back: int,
) -> Tuple[date, date]:
    range_end = _parse_date(end_date) if end_date else datetime.now(timezone.utc).date()
    if start_date:
        range_start = _parse_date(start_date)
        if not range_start:
            raise ValueError("startDate must be a valid ISO date (YYYY-MM-DD)")
    else:
        range_start = range_end - timedelta(days=max(days_back - 1, 0))
    if not range_start:
        raise ValueError("startDate must be a valid ISO date (YYYY-MM-DD)")
    if range_start > range_end:
        raise ValueError("startDate must be <= endDate")
    return range_start, range_end


def _load_credentials_from_env() -> Optional[Dict[str, str]]:
    username = os.environ.get("FTC_API_USERNAME")
    api_key = os.environ.get("FTC_API_KEY") or os.environ.get("FTC_API_TOKEN")
    if username and api_key:
        return {"username": username, "api_key": api_key}
    return None


class EventsTeamsSyncService:
    def __init__(self, environment: Optional[str] = None):
        self.environment = environment or os.environ.get("ENVIRONMENT", "dev")
        self.db_service = DynamoDBService(self.environment)
        self.ftc_api: Optional[FTCApiService] = None
        self.credentials: Optional[Dict[str, str]] = None

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
        self.credentials = credentials
        self.ftc_api = FTCApiService(credentials)
        await self.ftc_api.initialize()

    async def sync_event_teams(
        self,
        season: int,
        range_start: date,
        range_end: date,
    ) -> Dict[str, Any]:
        if not self.ftc_api:
            await self.initialize()
        if not self.credentials or not self.ftc_api:
            raise RuntimeError("FTC API credentials not initialized")

        events, _ = await fetch_events_by_date_range(
            season=season,
            start_date=range_start.isoformat(),
            end_date=range_end.isoformat(),
            credentials=self.credentials,
            api_service=self.ftc_api,
        )
        events = events or []

        updated = 0
        skipped_missing_code = 0
        skipped_missing_event = 0
        skipped_missing_event_id = 0
        skipped_no_teams_payload = 0

        for event in events:
            event_code = event.get("code") or event.get("eventCode")
            if not event_code:
                skipped_missing_code += 1
                continue

            teams_data, _ = await self.ftc_api.get_event_teams(season, event_code)
            if teams_data is None:
                skipped_no_teams_payload += 1
                continue

            event_record = self.db_service.get_event(event_code, season)
            if not event_record:
                skipped_missing_event += 1
                continue

            event_id = event_record.get("eventId")
            if not event_id:
                skipped_missing_event_id += 1
                continue

            if self.db_service.update_event_teams(event_id, teams_data):
                updated += 1
            else:
                logger.warning("Failed to update teams for event %s", event_code)

        return {
            "success": True,
            "season": season,
            "startDate": range_start.isoformat(),
            "endDate": range_end.isoformat(),
            "eventsFound": len(events),
            "eventsUpdated": updated,
            "skippedMissingEventCode": skipped_missing_code,
            "skippedMissingEventRecord": skipped_missing_event,
            "skippedMissingEventId": skipped_missing_event_id,
            "skippedNoTeamsPayload": skipped_no_teams_payload,
        }

    async def close(self) -> None:
        if self.ftc_api:
            await self.ftc_api.close()


async def _async_lambda_handler(event, context):
    service = EventsTeamsSyncService()
    season = int(os.environ.get("SEASON", "2025"))
    days_back = int(os.environ.get("DAYS_BACK", "7"))

    event_payload = event or {}
    start_date = event_payload.get("startDate") or event_payload.get("start_date")
    end_date = event_payload.get("endDate") or event_payload.get("end_date")

    try:
        range_start, range_end = _resolve_date_range(start_date, end_date, days_back)
        logger.info(
            "Syncing event teams: season=%s, start=%s, end=%s",
            season,
            range_start,
            range_end,
        )

        await service.initialize()
        result = await service.sync_event_teams(season, range_start, range_end)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as exc:
        logger.error("Event teams sync failed: %s", exc, exc_info=True)
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
