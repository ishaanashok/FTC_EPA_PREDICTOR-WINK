#!/usr/bin/env python3
"""
Backfill matchCount on FTC_Teams table from FTC_TeamMatchEPA records.

Counts team-match records per (teamNumber, season) and updates all team
items with the derived matchCount. Teams without EPA records are set to 0.
"""
import argparse
import logging
import time
from collections import defaultdict
from typing import Dict, Iterable, Tuple, Optional

import boto3
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)


def _scan_table_keys(table, key_attrs) -> Iterable[Dict]:
    expression_names = {f"#{attr}": attr for attr in key_attrs}
    projection = ", ".join(expression_names.keys())
    last_key = None

    while True:
        scan_kwargs = {
            "ProjectionExpression": projection,
            "ExpressionAttributeNames": expression_names
        }
        if last_key:
            scan_kwargs["ExclusiveStartKey"] = last_key

        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            yield item

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break


def _query_teams_by_season(table, season: int, projection: Optional[str] = None,
                           expression_names: Optional[Dict[str, str]] = None) -> Iterable[Dict]:
    expression_names = {
        "#season": "season",
        "#tn": "teamNumber"
    } if expression_names is None else expression_names
    last_key = None

    while True:
        query_kwargs = {
            "IndexName": "SeasonIndex",
            "KeyConditionExpression": "#season = :season",
            "ExpressionAttributeNames": expression_names,
            "ExpressionAttributeValues": {":season": int(season)}
        }
        if projection:
            query_kwargs["ProjectionExpression"] = projection
        if last_key:
            query_kwargs["ExclusiveStartKey"] = last_key

        response = table.query(**query_kwargs)
        for item in response.get("Items", []):
            yield item

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break


def _extract_team_season(item: Dict) -> Tuple[int, int]:
    team_number = int(item.get("teamNumber"))
    season = int(item.get("season"))
    return team_number, season


def build_match_counts(team_match_epa_table, scores_only: bool,
                       seasons: Optional[set] = None) -> Dict[Tuple[int, int], int]:
    counts = defaultdict(int)
    expression_names = {
        "#tn": "teamNumber",
        "#season": "season"
    }
    projection = "#tn, #season"
    last_key = None

    logger.info("Scanning TeamMatchEPA table for match counts...")
    while True:
        scan_kwargs = {
            "ProjectionExpression": projection,
            "ExpressionAttributeNames": expression_names
        }
        filter_expressions = []
        expression_values = {}
        if scores_only:
            expression_names["#hasScores"] = "hasScores"
            filter_expressions.append("#hasScores = :true")
            expression_values[":true"] = True
        if seasons:
            filter_expressions.append("#season IN (" + ", ".join(f":s{i}" for i, _ in enumerate(seasons)) + ")")
            for i, season in enumerate(sorted(seasons)):
                expression_values[f":s{i}"] = int(season)
        if filter_expressions:
            scan_kwargs["FilterExpression"] = " AND ".join(filter_expressions)
            scan_kwargs["ExpressionAttributeValues"] = expression_values
        if last_key:
            scan_kwargs["ExclusiveStartKey"] = last_key

        response = team_match_epa_table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            key = _extract_team_season(item)
            counts[key] += 1

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break

    logger.info("Match counts computed for %s team-season pairs.", len(counts))
    return counts


def update_team_match_counts(teams_table, match_counts: Dict[Tuple[int, int], int],
                             dry_run: bool, sleep_seconds: float,
                             seasons: Optional[set] = None) -> None:
    updated = 0
    total = 0

    logger.info("Scanning Teams table to apply matchCount updates...")
    if seasons:
        for season in sorted(seasons):
            season_total = 0
            season_updated = 0
            logger.info("Processing teams for season %s...", season)

            projection = "#tn, #season, #mc"
            expression_names = {"#season": "season", "#tn": "teamNumber", "#mc": "matchCount"}

            team_items = _query_teams_by_season(
                teams_table,
                season,
                projection=projection,
                expression_names=expression_names
            )

            for item in team_items:
                season_total += 1
                total += 1
                if "matchCount" in item and item["matchCount"] is not None:
                    if season_total % 500 == 0 and dry_run:
                        logger.info("Dry run progress: %s teams scanned...", season_total)
                    continue

                team_number, season_value = _extract_team_season(item)
                match_count = match_counts.get((team_number, season_value), 0)

                if dry_run:
                    if season_total % 500 == 0:
                        logger.info("Dry run progress: %s teams scanned...", season_total)
                    continue

                try:
                    teams_table.update_item(
                        Key={"teamNumber": team_number, "season": season_value},
                        UpdateExpression="SET matchCount = :c",
                        ExpressionAttributeValues={":c": match_count},
                        ConditionExpression="attribute_not_exists(matchCount)"
                    )
                    season_updated += 1
                    updated += 1
                except ClientError as error:
                    if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                        logger.error(
                            "Failed to update team %s season %s: %s",
                            team_number,
                            season_value,
                            error
                        )

                if season_updated and season_updated % 500 == 0:
                    logger.info("Update progress: %s/%s teams updated", season_updated, season_total)
                if sleep_seconds:
                    time.sleep(sleep_seconds)

            logger.info("Season %s complete. Updated %s teams.", season, season_updated)
    else:
        team_items = list(_scan_table_keys(teams_table, ["teamNumber", "season"]))

        for item in team_items:
            team_number, season = _extract_team_season(item)
            match_count = match_counts.get((team_number, season), 0)
            total += 1

            if dry_run:
                if total % 500 == 0:
                    logger.info("Dry run progress: %s teams scanned...", total)
                continue

            try:
                teams_table.update_item(
                    Key={"teamNumber": team_number, "season": season},
                    UpdateExpression="SET matchCount = :c",
                    ExpressionAttributeValues={":c": match_count},
                    ConditionExpression="attribute_not_exists(matchCount)"
                )
                updated += 1
            except ClientError as error:
                if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                    logger.error(
                        "Failed to update team %s season %s: %s",
                        team_number,
                        season,
                        error
                    )

            if sleep_seconds:
                time.sleep(sleep_seconds)

            if updated and updated % 500 == 0:
                logger.info("Update progress: %s/%s teams updated", updated, total)

    logger.info("Update complete. Updated %s teams.", updated)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill matchCount on FTC_Teams from FTC_TeamMatchEPA data."
    )
    parser.add_argument(
        "--environment",
        default="stage",
        help="Environment name (dev, stage, prod). Default: stage"
    )
    parser.add_argument(
        "--scores-only",
        action="store_true",
        help="Only count matches with hasScores=true."
    )
    parser.add_argument(
        "--season",
        action="append",
        type=int,
        default=[],
        help="Season(s) to backfill (repeatable)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and compute counts without updating DynamoDB."
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Sleep between updates to reduce throttling (seconds)."
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    dynamodb = boto3.resource("dynamodb")
    teams_table = dynamodb.Table(f"FTC_Teams_{args.environment}")
    team_match_epa_table = dynamodb.Table(f"FTC_TeamMatchEPA_{args.environment}")

    seasons = set(args.season) if args.season else None
    match_counts = build_match_counts(team_match_epa_table, args.scores_only, seasons)
    update_team_match_counts(
        teams_table,
        match_counts,
        dry_run=args.dry_run,
        sleep_seconds=args.sleep,
        seasons=seasons
    )


if __name__ == "__main__":
    main()
