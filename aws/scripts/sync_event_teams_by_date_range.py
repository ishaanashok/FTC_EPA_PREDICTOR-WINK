#!/usr/bin/env python3
"""
Sync event teams into DynamoDB for events in a date range.

Defaults to the last 7 days (inclusive). Uses FTC Inspire API to fetch event teams
and stores the teams array on the existing event records in DynamoDB.

Env vars:
  FTC_API_USERNAME, FTC_API_KEY
  SEASON (default: 2025)
  ENVIRONMENT (default: dev)
  EVENTS_RANGE_START (YYYY-MM-DD) optional
  EVENTS_RANGE_END (YYYY-MM-DD) optional
"""

import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "services"))

from events_date_range_service import fetch_events_by_date_range, load_credentials_from_env
from ftc_api_service import FTCApiService
from dynamodb_service import DynamoDBService


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _parse_date(value: str) -> date:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).date()


def _resolve_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
    days: int,
) -> Tuple[str, str]:
    resolved_end = _parse_date(end_date) if end_date else datetime.utcnow().date()
    resolved_start = _parse_date(start_date) if start_date else resolved_end - timedelta(days=days - 1)
    if resolved_start > resolved_end:
        raise ValueError("start_date must be <= end_date")
    return resolved_start.isoformat(), resolved_end.isoformat()


def _extract_event_code(event: Dict[str, Any]) -> Optional[str]:
    return event.get("code") or event.get("eventCode")


async def _fetch_event_teams(
    api_service: FTCApiService,
    season: int,
    event_code: str,
) -> Optional[List[Dict[str, Any]]]:
    teams_data, _ = await api_service.get_event_teams(season, event_code)
    if teams_data is None:
        return None
    if isinstance(teams_data, list):
        return teams_data
    if isinstance(teams_data, dict):
        return teams_data.get("teams", [])
    return None


async def main() -> None:
    parser = argparse.ArgumentParser(description="Sync event teams to DynamoDB by date range")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=7, help="Number of days in range (default: 7)")
    parser.add_argument("--season", type=int, help="FTC season year (e.g., 2025)")
    parser.add_argument("--environment", help="Target environment (dev/stage/prod)")
    parser.add_argument("--dry-run", action="store_true", help="Log updates without writing to DynamoDB")
    parser.add_argument("--resume-after", help="Resume after this event code")
    args = parser.parse_args()

    season = args.season or int(os.environ.get("SEASON", "2025"))
    environment = args.environment or os.environ.get("ENVIRONMENT", "dev")

    start_env = os.environ.get("EVENTS_RANGE_START")
    end_env = os.environ.get("EVENTS_RANGE_END")
    start_date, end_date = _resolve_date_range(
        args.start_date or start_env,
        args.end_date or end_env,
        args.days,
    )

    credentials = load_credentials_from_env()
    db_service = None if args.dry_run else DynamoDBService(environment)
    api_service = FTCApiService(credentials)

    await api_service.initialize()
    try:
        events, _ = await fetch_events_by_date_range(
            season=season,
            start_date=start_date,
            end_date=end_date,
            credentials=credentials,
            api_service=api_service,
        )
        logger.info("Fetched %d events from %s to %s.", len(events), start_date, end_date)

        resume_after = args.resume_after
        if resume_after:
            event_codes = {(_extract_event_code(event) or "") for event in events}
            if resume_after not in event_codes:
                logger.warning(
                    "Resume event %s not found in range; processing all events.",
                    resume_after,
                )
                resume_after = None

        skipping = True if resume_after else False
        updated = 0
        skipped = 0

        for event in events:
            event_code = _extract_event_code(event)
            if not event_code:
                logger.warning("Skipping event without code: %s", event)
                skipped += 1
                continue

            if skipping:
                if event_code == resume_after:
                    skipping = False
                else:
                    skipped += 1
                    continue

            teams = await _fetch_event_teams(api_service, season, event_code)
            if teams is None:
                logger.warning("No teams payload for event %s; skipping update.", event_code)
                skipped += 1
                continue

            if args.dry_run:
                logger.info("Dry run: would update %s with %d teams.", event_code, len(teams))
                updated += 1
                continue

            event_record = db_service.get_event(event_code, season) if db_service else None
            if not event_record:
                logger.warning("Event %s not found in DynamoDB; skipping.", event_code)
                skipped += 1
                continue

            event_id = event_record.get("eventId")
            if not event_id:
                logger.warning("Event %s missing eventId; skipping.", event_code)
                skipped += 1
                continue

            if db_service.update_event_teams(event_id, teams):
                logger.info("Updated event %s with %d teams.", event_code, len(teams))
                updated += 1
            else:
                logger.warning("Failed to update event %s.", event_code)
                skipped += 1

        logger.info("Done. Updated: %d, skipped: %d.", updated, skipped)
    finally:
        await api_service.close()


if __name__ == "__main__":
    asyncio.run(main())
