#!/usr/bin/env python3
"""
Sync matches and per-team EPA records for events within a date range.

Env vars:
  FTC_API_USERNAME, FTC_API_KEY
  SEASON (default: 2025)
  EVENTS_RANGE_START (YYYY-MM-DD)
  EVENTS_RANGE_END (YYYY-MM-DD)
  ENVIRONMENT (default: dev)
  DRY_RUN (default: false)
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lambda", "matches-sync", "models"))

from events_date_range_service import fetch_events_by_date_range, load_credentials_from_env
from ftc_api_service import FTCApiService
from dynamodb_service import DynamoDBService
from data_models import convert_ftc_api_match


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


MATCH_TYPE_MULTIPLIERS = {
    "QUALIFICATION": 1.0,
    "QUAL": 1.0,
    "PLAYOFF": 1.3,
    "ELIMINATION": 1.3,
    "FINAL": 1.3,
}


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


async def main() -> None:
    season = int(os.environ.get("SEASON", "2025"))
    environment = os.environ.get("ENVIRONMENT", "dev")
    start_date = os.environ.get("EVENTS_RANGE_START")
    end_date = os.environ.get("EVENTS_RANGE_END")
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    resume_after = os.environ.get("RESUME_AFTER_EVENT")

    if not start_date or not end_date:
        raise RuntimeError("EVENTS_RANGE_START and EVENTS_RANGE_END must be set")

    credentials = load_credentials_from_env()
    db_service = None if dry_run else DynamoDBService(environment)
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
        logger.info("Fetched %d events for date range.", len(events))
        if resume_after:
            event_codes = {event.get("code") for event in events}
            if resume_after not in event_codes:
                logger.warning(
                    "Resume event %s not found in range; processing all events.",
                    resume_after,
                )
                resume_after = None

        team_state_cache: Dict[int, Dict[str, Any]] = {}
        total_matches = 0
        total_epa_records = 0

        skipping = True if resume_after else False
        for event in events:
            event_code = event.get("code")
            if not event_code:
                continue
            if skipping:
                if event_code == resume_after:
                    skipping = False
                continue
            event_name = event.get("name", "")

            logger.info("Fetching matches for event %s", event_code)
            qual_matches, _ = await api_service.get_event_matches(season, event_code, tournament_level="qual")
            playoff_matches, _ = await api_service.get_event_matches(season, event_code, tournament_level="playoff")

            matches = (qual_matches or []) + (playoff_matches or [])
            matches.sort(key=_parse_match_time)

            if not matches:
                continue

            match_items: List[Dict[str, Any]] = []
            epa_records: List[Dict[str, Any]] = []

            for match in matches:
                match_model = convert_ftc_api_match(match, season, event_code)
                match_item = match_model.model_dump() if hasattr(match_model, "model_dump") else match_model.dict()
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
                        if db_service:
                            existing = db_service.get_team_match_epa(team_number, match_id)
                            if existing:
                                continue

                        state = _load_team_state(db_service, team_number, season, team_state_cache)
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

                        if db_service:
                            db_service.increment_team_match_count(team_number, season, 1)

            if db_service:
                if match_items:
                    db_service.batch_save_matches(match_items)
                if epa_records:
                    db_service.batch_save_team_match_epas(epa_records)

        logger.info("Completed: %d matches, %d EPA records", total_matches, total_epa_records)
    finally:
        await api_service.close()


if __name__ == "__main__":
    asyncio.run(main())
