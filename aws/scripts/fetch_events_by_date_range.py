#!/usr/bin/env python3
"""
Fetch FTC events for a season, filtered by a date range.

Local usage:
  FTC_API_USERNAME=... FTC_API_KEY=... SEASON=2025 \
  EVENTS_RANGE_START=2025-01-01 EVENTS_RANGE_END=2025-02-01 \
  python3 aws/scripts/fetch_events_by_date_range.py
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Tuple

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "services"))

from events_date_range_service import fetch_events_by_date_range, load_credentials_from_env
from sync_state_store import SyncStateStore
from load_env import load_env_file


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def resolve_date_range(season: int, environment: str, region: str) -> Tuple[str, str, str]:
    start = os.environ.get("EVENTS_RANGE_START")
    end = os.environ.get("EVENTS_RANGE_END")
    if start and end:
        return start, end, "env"

    sync_key = os.environ.get("SYNC_STATE_KEY", f"events-date-range#{season}")
    table_name = os.environ.get("SYNC_STATE_TABLE")
    store = SyncStateStore(environment=environment, table_name=table_name, region=region)
    state = store.get_last_range(sync_key)
    if state and state.get("lastEnd"):
        start = state["lastEnd"]
        end = os.environ.get("EVENTS_RANGE_END") or datetime.now(timezone.utc).date().isoformat()
        return start, end, "dynamodb"

    raise RuntimeError(
        "Provide EVENTS_RANGE_START/END or set up DynamoDB sync state with lastEnd."
    )


async def main() -> None:
    load_env_file()

    season = int(os.environ.get("SEASON", "2025"))
    environment = os.environ.get("ENVIRONMENT", "dev")
    region = os.environ.get("AWS_REGION", "us-east-1")
    save_state = os.environ.get("SAVE_SYNC_STATE", "false").lower() == "true"
    sync_key = os.environ.get("SYNC_STATE_KEY", f"events-date-range#{season}")

    start_date, end_date, source = resolve_date_range(season, environment, region)
    logger.info("Using date range (%s): %s -> %s", source, start_date, end_date)

    credentials = load_credentials_from_env()
    events, metadata = await fetch_events_by_date_range(
        season=season,
        start_date=start_date,
        end_date=end_date,
        credentials=credentials,
    )

    output = {
        "season": season,
        "startDate": start_date,
        "endDate": end_date,
        "eventCount": len(events),
        "events": events,
        "metadata": metadata,
    }
    print(json.dumps(output, indent=2))

    if save_state:
        store = SyncStateStore(environment=environment, region=region)
        saved = store.save_last_range(sync_key, season, start_date, end_date)
        logger.info("Saved sync state: %s", "ok" if saved else "failed")


if __name__ == "__main__":
    asyncio.run(main())
