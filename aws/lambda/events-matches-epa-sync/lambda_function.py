import json
import logging
import os
import asyncio
from datetime import datetime, timezone, timedelta, date, time
from typing import Any, Dict, List, Optional, Tuple

import boto3

from services.events_date_range_service import fetch_events_by_date_range
from services.ftc_api_service import FTCApiService
from services.dynamodb_service import DynamoDBService


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


MATCH_TYPE_MULTIPLIERS = {
    "QUALIFICATION": 1.0,
    "QUAL": 1.0,
    "PLAYOFF": 1.3,
    "ELIMINATION": 1.3,
    "FINAL": 1.3,
}


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


def _event_window_dt(event: Dict[str, Any]) -> Optional[Tuple[datetime, datetime]]:
    event_start = _parse_date(event.get("dateStart"))
    event_end = _parse_date(event.get("dateEnd")) or event_start
    if not event_start:
        return None
    start_dt = datetime.combine(event_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(event_end, time.max, tzinfo=timezone.utc)
    return start_dt, end_dt


def _get_upcoming_window(
    events: List[Dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> Optional[Tuple[datetime, datetime]]:
    windows: List[Tuple[datetime, datetime]] = []
    for event in events:
        window = _event_window_dt(event)
        if not window:
            continue
        event_start, event_end = window
        if event_start <= window_end and event_end >= window_start:
            windows.append((event_start, event_end))

    if not windows:
        return None
    earliest = min(start for start, _ in windows)
    latest = max(end for _, end in windows)
    return earliest, latest


def _parse_match_time(match: Dict[str, Any]) -> str:
    return (
        match.get("actualStartTime")
        or match.get("startTime")
        or match.get("postResultTime")
        or "9999-12-31T00:00:00"
    )


def _match_has_scores(match: Dict[str, Any]) -> bool:
    return (match.get("scoreRedFinal", 0) or 0) > 0 or (match.get("scoreBlueFinal", 0) or 0) > 0


def _score_breakdown(match: Dict[str, Any], alliance: str) -> Dict[str, float]:
    prefix = "Red" if alliance.lower() == "red" else "Blue"
    return {
        "final": float(match.get(f"score{prefix}Final", 0) or 0),
        "auto": float(match.get(f"score{prefix}Auto", 0) or 0),
        "teleop": float(match.get(f"score{prefix}Teleop", 0) or 0),
        "endgame": float(match.get(f"score{prefix}End", 0) or 0),
        "foul": float(match.get(f"score{prefix}Penalty", 0) or 0),
    }


def _calculate_match_epa(
    alliance_score: float,
    opponent_score: float,
    alliance_team_count: int,
    tournament_level: str,
) -> Tuple[float, Dict[str, Any]]:
    if alliance_score == 0 and opponent_score == 0:
        return 0.0, {
            "baseContribution": 0.0,
            "opponentStrengthMultiplier": 1.0,
            "matchTypeMultiplier": 1.0,
        }

    base_contribution = alliance_score / max(alliance_team_count, 1)
    opponent_strength_multiplier = 1 + (opponent_score / max(alliance_score, 1))
    match_type_multiplier = MATCH_TYPE_MULTIPLIERS.get(tournament_level.upper(), 1.0)
    match_epa = base_contribution * opponent_strength_multiplier * match_type_multiplier

    return round(match_epa, 2), {
        "baseContribution": round(base_contribution, 2),
        "opponentStrengthMultiplier": round(opponent_strength_multiplier, 3),
        "matchTypeMultiplier": match_type_multiplier,
    }


def _extract_teams(match: Dict[str, Any]) -> Tuple[List[int], List[int], Dict[int, str]]:
    red_teams: List[int] = []
    blue_teams: List[int] = []
    stations: Dict[int, str] = {}

    for team in match.get("teams", []) or []:
        team_number = team.get("teamNumber")
        if team_number is None:
            continue
        team_number = int(team_number)
        station = team.get("station", "")
        stations[team_number] = station
        if "Red" in station:
            red_teams.append(team_number)
        elif "Blue" in station:
            blue_teams.append(team_number)

    return red_teams, blue_teams, stations


def _pick_latest_epa_record(records: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not records:
        return None

    def sort_key(record: Dict[str, Any]) -> Tuple[str, int]:
        return (record.get("actualStartTime") or "", record.get("matchCount") or 0)

    return sorted(records, key=sort_key, reverse=True)[0]


def _load_team_state(
    db_service: Optional[DynamoDBService],
    team_number: int,
    season: int,
    cache: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    if team_number in cache:
        return cache[team_number]

    latest = None
    if db_service:
        records = db_service.get_team_season_epa(team_number, season)
        latest = _pick_latest_epa_record(records)

    if not latest:
        state = {
            "matchCount": 0,
            "cumulativeEPA": 0.0,
            "totalAuto": 0.0,
            "totalTeleop": 0.0,
            "totalEndgame": 0.0,
            "matchesWithScores": 0,
        }
    else:
        running = latest.get("runningAverages", {}) or {}
        matches_with_scores = int(running.get("matchesWithScores", 0) or 0)
        state = {
            "matchCount": int(latest.get("matchCount", 0) or 0),
            "cumulativeEPA": float(latest.get("cumulativeEPA", 0) or 0),
            "totalAuto": float(running.get("auto", 0) or 0) * matches_with_scores,
            "totalTeleop": float(running.get("teleop", 0) or 0) * matches_with_scores,
            "totalEndgame": float(running.get("endgame", 0) or 0) * matches_with_scores,
            "matchesWithScores": matches_with_scores,
        }

    cache[team_number] = state
    return state


def _convert_ftc_api_match(api_match: Dict[str, Any], season: int, event_code: str) -> Dict[str, Any]:
    tournament_level = api_match.get("tournamentLevel", "UNKNOWN")
    match_number = api_match.get("matchNumber", 0)
    series = api_match.get("series", 0)

    match_id = f"{season}-{event_code}-{tournament_level}-{series}-{match_number}"

    teams = api_match.get("teams", [])
    red_teams: List[int] = []
    blue_teams: List[int] = []
    all_teams: List[int] = []

    for team_data in teams:
        team_number = team_data.get("teamNumber", 0)
        if team_number:
            all_teams.append(team_number)

            station = team_data.get("station", "")
            if "Red" in station:
                red_teams.append(team_number)
            elif "Blue" in station:
                blue_teams.append(team_number)

    red_score = None
    blue_score = None

    if "scoreRedFinal" in api_match:
        red_score = {
            "alliance": "Red",
            "totalPoints": api_match.get("scoreRedFinal", 0),
            "autoPoints": api_match.get("scoreRedAuto", 0),
            "teleopPoints": api_match.get("scoreRedTeleop", 0),
            "endgamePoints": api_match.get("scoreRedEnd", 0),
            "penaltyPoints": api_match.get("scoreRedPenalty", 0),
        }

    if "scoreBlueFinal" in api_match:
        blue_score = {
            "alliance": "Blue",
            "totalPoints": api_match.get("scoreBlueFinal", 0),
            "autoPoints": api_match.get("scoreBlueAuto", 0),
            "teleopPoints": api_match.get("scoreBlueTeleop", 0),
            "endgamePoints": api_match.get("scoreBlueEnd", 0),
            "penaltyPoints": api_match.get("scoreBluePenalty", 0),
        }

    return {
        "matchId": match_id,
        "season": season,
        "eventCode": event_code,
        "matchNumber": api_match.get("matchNumber", 0),
        "description": api_match.get("description", ""),
        "tournamentLevel": api_match.get("tournamentLevel", ""),
        "series": api_match.get("series"),
        "matchName": api_match.get("matchName"),
        "playNumber": api_match.get("playNumber"),
        "fieldNumber": api_match.get("fieldNumber"),
        "startTime": api_match.get("startTime"),
        "actualStartTime": api_match.get("actualStartTime"),
        "postResultTime": api_match.get("postResultTime"),
        "teams": teams,
        "redTeams": red_teams,
        "blueTeams": blue_teams,
        "allTeams": all_teams,
        "redScore": red_score,
        "blueScore": blue_score,
        "lastUpdated": datetime.now(timezone.utc),
        "lastModified": None,
        "etag": None,
        "apiLastModified": None,
        "dataVersion": None,
    }


def _load_credentials_from_env() -> Optional[Dict[str, str]]:
    username = os.environ.get("FTC_API_USERNAME")
    api_key = os.environ.get("FTC_API_KEY") or os.environ.get("FTC_API_TOKEN")
    if username and api_key:
        return {"username": username, "api_key": api_key}
    return None


def _rule_name_from_event(event: Dict[str, Any]) -> Optional[str]:
    resources = event.get("resources") or []
    if not resources:
        return None
    arn = resources[0]
    if ":" in arn and "/" in arn:
        return arn.split("/")[-1]
    return None


class EventsMatchesEpaSyncService:
    def __init__(self, environment: str):
        self.environment = environment
        self.db_service = DynamoDBService(environment)
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

    async def close(self) -> None:
        if self.ftc_api:
            await self.ftc_api.close()
        self.db_service.clear_cache()

    async def sync_range(self, season: int, start_date: str, end_date: str) -> Dict[str, Any]:
        if not self.ftc_api:
            await self.initialize()

        events, _ = await fetch_events_by_date_range(
            season=season,
            start_date=start_date,
            end_date=end_date,
            credentials={"username": "unused", "api_key": "unused"},
            api_service=self.ftc_api,
        )
        logger.info("Fetched %d events for date range.", len(events))

        team_state_cache: Dict[int, Dict[str, Any]] = {}
        total_matches = 0
        total_epa_records = 0
        total_events = 0

        for event in events:
            event_code = event.get("code")
            if not event_code:
                continue
            total_events += 1
            event_name = event.get("name", "")

            logger.info("Fetching matches for event %s", event_code)
            qual_matches, _ = await self.ftc_api.get_event_matches(
                season, event_code, tournament_level="qual"
            )
            playoff_matches, _ = await self.ftc_api.get_event_matches(
                season, event_code, tournament_level="playoff"
            )

            matches = (qual_matches or []) + (playoff_matches or [])
            matches.sort(key=_parse_match_time)

            if not matches:
                continue

            match_items: List[Dict[str, Any]] = []
            epa_records: List[Dict[str, Any]] = []

            for match in matches:
                match_item = _convert_ftc_api_match(match, season, event_code)
                match_items.append(match_item)
                total_matches += 1

                if not _match_has_scores(match):
                    continue

                red_teams, blue_teams, stations = _extract_teams(match)
                if not red_teams and not blue_teams:
                    continue

                red_scores = _score_breakdown(match, "red")
                blue_scores = _score_breakdown(match, "blue")
                match_id = match_item["matchId"]
                tournament_level = match.get("tournamentLevel", "QUALIFICATION")
                match_number = match.get("matchNumber", 0)
                series = match.get("series", 0)
                description = match.get("description", "")
                actual_start_time = match.get("actualStartTime")
                post_result_time = match.get("postResultTime")

                for alliance, teams, alliance_scores, opponent_scores in [
                    ("Red", red_teams, red_scores, blue_scores),
                    ("Blue", blue_teams, blue_scores, red_scores),
                ]:
                    for team_number in teams:
                        existing = self.db_service.get_team_match_epa(team_number, match_id)
                        if existing:
                            # Update cache with existing record to keep cumulative state accurate
                            state = _load_team_state(self.db_service, team_number, season, team_state_cache)
                            match_epa = float(existing.get("matchEPA", 0) or 0)
                            state["matchCount"] = int(existing.get("matchCount", state["matchCount"]))
                            state["cumulativeEPA"] = float(existing.get("cumulativeEPA", state["cumulativeEPA"]) or 0)
                            running = existing.get("runningAverages", {}) or {}
                            matches_scored = int(running.get("matchesWithScores", state["matchesWithScores"]) or 0)
                            state["matchesWithScores"] = matches_scored
                            state["totalAuto"] = float(running.get("auto", 0) or 0) * matches_scored
                            state["totalTeleop"] = float(running.get("teleop", 0) or 0) * matches_scored
                            state["totalEndgame"] = float(running.get("endgame", 0) or 0) * matches_scored
                            continue

                        state = _load_team_state(self.db_service, team_number, season, team_state_cache)
                        match_epa, epa_components = _calculate_match_epa(
                            alliance_scores["final"],
                            opponent_scores["final"],
                            len(teams),
                            tournament_level,
                        )

                        state["matchCount"] += 1
                        state["cumulativeEPA"] += match_epa

                        state["matchesWithScores"] += 1
                        state["totalAuto"] += alliance_scores["auto"] / max(len(teams), 1)
                        state["totalTeleop"] += alliance_scores["teleop"] / max(len(teams), 1)
                        state["totalEndgame"] += alliance_scores["endgame"] / max(len(teams), 1)

                        avg_auto = state["totalAuto"] / state["matchesWithScores"]
                        avg_teleop = state["totalTeleop"] / state["matchesWithScores"]
                        avg_endgame = state["totalEndgame"] / state["matchesWithScores"]

                        team_record = {
                            "season": season,
                            "eventCode": event_code,
                            "eventName": event_name,
                            "matchId": match_id,
                            "matchNumber": match_number,
                            "tournamentLevel": tournament_level,
                            "series": series,
                            "description": description,
                            "teamNumber": team_number,
                            "alliance": alliance,
                            "station": stations.get(team_number, ""),
                            "matchEPA": match_epa,
                            "cumulativeEPA": round(state["cumulativeEPA"], 2),
                            "averageEPA": round(state["cumulativeEPA"] / state["matchCount"], 2),
                            "matchCount": state["matchCount"],
                            "epaComponents": epa_components,
                            "teamScoreContribution": {
                                "auto": round(alliance_scores["auto"] / max(len(teams), 1), 2),
                                "teleop": round(alliance_scores["teleop"] / max(len(teams), 1), 2),
                                "endgame": round(alliance_scores["endgame"] / max(len(teams), 1), 2),
                            },
                            "runningAverages": {
                                "auto": round(avg_auto, 2),
                                "teleop": round(avg_teleop, 2),
                                "endgame": round(avg_endgame, 2),
                                "matchesWithScores": state["matchesWithScores"],
                            },
                            "allianceScore": alliance_scores,
                            "opponentScore": opponent_scores,
                            "allianceTeamCount": len(teams),
                            "allianceTeamNumbers": sorted(teams),
                            "opponentTeamNumbers": sorted(blue_teams if alliance == "Red" else red_teams),
                            "actualStartTime": actual_start_time,
                            "postResultTime": post_result_time,
                            "hasScores": True,
                        }

                        epa_records.append(team_record)
                        total_epa_records += 1
                        self.db_service.increment_team_match_count(team_number, season, 1)

            if match_items:
                self.db_service.batch_save_matches(match_items)
            if epa_records:
                self.db_service.batch_save_team_match_epas(epa_records)

        return {
            "eventsProcessed": total_events,
            "matchesProcessed": total_matches,
            "epaRecordsCreated": total_epa_records,
            "startDate": start_date,
            "endDate": end_date,
        }


def _set_temp_rule_state(rule_name: str, enabled: bool) -> None:
    client = boto3.client("events")
    try:
        if enabled:
            client.enable_rule(Name=rule_name)
        else:
            client.disable_rule(Name=rule_name)
    except Exception as exc:
        logger.warning("Failed to set temp rule %s state to %s: %s", rule_name, enabled, exc)


async def _async_lambda_handler(event, context):
    environment = os.environ.get("ENVIRONMENT", "stage")
    season = int(os.environ.get("SEASON", "2025"))
    upcoming_hours = int(os.environ.get("UPCOMING_WINDOW_HOURS", "24"))
    daily_rule_name = os.environ.get(
        "DAILY_RULE_NAME",
        f"ftc-events-matches-epa-sync-daily-{environment}",
    )
    temp_rule_name = os.environ.get(
        "TEMP_RULE_NAME",
        f"ftc-events-matches-epa-sync-temp-{environment}",
    )

    invoked_rule = _rule_name_from_event(event) if isinstance(event, dict) else None
    now = datetime.now(timezone.utc)

    service = EventsMatchesEpaSyncService(environment)
    await service.initialize()
    try:
        # Determine upcoming window (next 24h)
        upcoming_start = now
        upcoming_end = now + timedelta(hours=upcoming_hours)
        upcoming_events, _ = await fetch_events_by_date_range(
            season=season,
            start_date=upcoming_start.date().isoformat(),
            end_date=upcoming_end.date().isoformat(),
            credentials={"username": "unused", "api_key": "unused"},
            api_service=service.ftc_api,
        )
        upcoming_events = [
            event for event in upcoming_events if _event_overlaps_range(
                event, upcoming_start.date(), upcoming_end.date()
            )
        ]
        upcoming_window = _get_upcoming_window(upcoming_events, upcoming_start, upcoming_end)
        _set_temp_rule_state(temp_rule_name, enabled=bool(upcoming_window))

        if isinstance(event, dict) and event.get("startDate") and event.get("endDate"):
            start_date = event["startDate"]
            end_date = event["endDate"]
            run_reason = "custom-range"
        elif invoked_rule == daily_rule_name:
            yesterday = (now - timedelta(days=1)).date()
            start_date = yesterday.isoformat()
            end_date = yesterday.isoformat()
            run_reason = "daily"
        elif invoked_rule == temp_rule_name and upcoming_window:
            window_start, window_end = upcoming_window
            if now < window_start or now > window_end:
                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "success": True,
                            "skipped": True,
                            "reason": "outside-event-window",
                            "windowStart": window_start.isoformat(),
                            "windowEnd": window_end.isoformat(),
                        }
                    ),
                }
            start_date = window_start.date().isoformat()
            end_date = window_end.date().isoformat()
            run_reason = "temp"
        else:
            yesterday = (now - timedelta(days=1)).date()
            start_date = yesterday.isoformat()
            end_date = yesterday.isoformat()
            run_reason = "default"

        logger.info(
            "Running sync (%s): %s to %s",
            run_reason,
            start_date,
            end_date,
        )

        result = await service.sync_range(season, start_date, end_date)
        result.update(
            {
                "success": True,
                "runReason": run_reason,
                "invokedRule": invoked_rule,
            }
        )
        if upcoming_window:
            result["upcomingWindowStart"] = upcoming_window[0].isoformat()
            result["upcomingWindowEnd"] = upcoming_window[1].isoformat()
        return {"statusCode": 200, "body": json.dumps(result)}
    finally:
        await service.close()


def lambda_handler(event, context):
    return asyncio.run(_async_lambda_handler(event, context))
