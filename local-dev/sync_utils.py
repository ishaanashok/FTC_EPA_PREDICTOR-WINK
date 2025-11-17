#!/usr/bin/env python3
"""
FTC Predictor Local Development Sync Utilities

This module provides utilities to sync data between DynamoDB and local PostgreSQL
for development purposes.
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal

import boto3
import psycopg2
import psycopg2.extras
from psycopg2.extras import Json, RealDictCursor
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FTCDataSyncer:
    """Sync data between DynamoDB and PostgreSQL for local development"""
    
    def __init__(self, 
                 postgres_config: Dict[str, str] = None,
                 aws_region: str = 'us-east-1',
                 environment: str = 'stage'):
        """
        Initialize the syncer
        
        Args:
            postgres_config: PostgreSQL connection config
            aws_region: AWS region for DynamoDB
            environment: Environment suffix for DynamoDB tables
        """
        self.environment = environment
        self.aws_region = aws_region
        
        # Default PostgreSQL config
        self.pg_config = postgres_config or {
            'host': 'localhost',
            'port': '5432',
            'database': 'ftc_predictor',
            'user': 'ftc_dev',
            'password': 'ftc_dev_password'
        }
        
        # DynamoDB table names
        self.table_names = {
            'teams': f'FTC_Teams_{environment}',
            'events': f'FTC_Events_{environment}',
            'matches': f'FTC_Matches_{environment}',
            'epa': f'FTC_EPA_{environment}',
            'sync_status': f'FTC_SyncStatus_{environment}'
        }
        
        # Initialize AWS clients
        self.dynamodb = boto3.client('dynamodb', region_name=aws_region)
        self.dynamodb_resource = boto3.resource('dynamodb', region_name=aws_region)
        
    def get_postgres_connection(self):
        """Get PostgreSQL connection"""
        return psycopg2.connect(**self.pg_config)
    
    def convert_dynamodb_to_postgres(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB item format to PostgreSQL format"""
        result = {}
        
        for key, value in item.items():
            if isinstance(value, dict):
                if 'S' in value:  # String
                    result[key.lower()] = value['S']
                elif 'N' in value:  # Number
                    try:
                        # Try integer first
                        result[key.lower()] = int(value['N'])
                    except ValueError:
                        # Fall back to float
                        result[key.lower()] = float(value['N'])
                elif 'BOOL' in value:  # Boolean
                    result[key.lower()] = value['BOOL']
                elif 'NULL' in value:  # Null
                    result[key.lower()] = None
                elif 'L' in value:  # List
                    result[key.lower()] = [self.convert_dynamodb_to_postgres({'item': item})['item'] 
                                         for item in value['L']]
                elif 'M' in value:  # Map
                    result[key.lower()] = self.convert_dynamodb_to_postgres(value['M'])
                elif 'SS' in value:  # String Set
                    result[key.lower()] = value['SS']
                elif 'NS' in value:  # Number Set
                    result[key.lower()] = [int(n) if '.' not in n else float(n) for n in value['NS']]
            else:
                result[key.lower()] = value
                
        return result
    
    def convert_postgres_to_dynamodb(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert PostgreSQL row to DynamoDB item format"""
        result = {}
        
        for key, value in item.items():
            if value is None:
                result[key] = {'NULL': True}
            elif isinstance(value, str):
                result[key] = {'S': value}
            elif isinstance(value, (int, float, Decimal)):
                result[key] = {'N': str(value)}
            elif isinstance(value, bool):
                result[key] = {'BOOL': value}
            elif isinstance(value, list):
                if all(isinstance(x, (int, float)) for x in value):
                    result[key] = {'NS': [str(x) for x in value]}
                elif all(isinstance(x, str) for x in value):
                    result[key] = {'SS': value}
                else:
                    result[key] = {'L': [self.convert_postgres_to_dynamodb({'item': item})['item'] 
                                       for item in value]}
            elif isinstance(value, dict):
                result[key] = {'M': self.convert_postgres_to_dynamodb(value)}
            else:
                result[key] = {'S': str(value)}
                
        return result
    
    async def sync_teams_from_dynamodb(self, limit: int = None) -> Tuple[int, int]:
        """Sync teams from DynamoDB to PostgreSQL"""
        logger.info("Starting teams sync from DynamoDB to PostgreSQL")
        
        table_name = self.table_names['teams']
        inserted = 0
        updated = 0
        
        try:
            with self.get_postgres_connection() as pg_conn:
                with pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Scan DynamoDB table
                    paginator = self.dynamodb.get_paginator('scan')
                    page_iterator = paginator.paginate(
                        TableName=table_name,
                        **({"Limit": limit} if limit else {})
                    )
                    
                    for page in page_iterator:
                        items = page.get('Items', [])
                        
                        for item in items:
                            # Convert DynamoDB item to PostgreSQL format
                            pg_item = self.convert_dynamodb_to_postgres(item)
                            
                            # Check if team exists
                            cursor.execute(
                                "SELECT 1 FROM teams WHERE team_number = %s AND season = %s",
                                (pg_item['teamnumber'], pg_item['season'])
                            )
                            
                            if cursor.fetchone():
                                # Update existing team
                                cursor.execute("""
                                    UPDATE teams SET
                                        team_name = %s,
                                        school_name = %s,
                                        city = %s,
                                        state = %s,
                                        country = %s,
                                        rookie_year = %s,
                                        website = %s,
                                        last_updated = %s,
                                        last_modified = %s,
                                        etag = %s,
                                        api_last_modified = %s,
                                        data_version = %s,
                                        data_hash = %s
                                    WHERE team_number = %s AND season = %s
                                """, (
                                    pg_item.get('teamname', ''),
                                    pg_item.get('schoolname', ''),
                                    pg_item.get('city', ''),
                                    pg_item.get('state', ''),
                                    pg_item.get('country', ''),
                                    pg_item.get('rookieyear'),
                                    pg_item.get('website'),
                                    pg_item.get('lastupdated'),
                                    pg_item.get('lastmodified'),
                                    pg_item.get('etag'),
                                    pg_item.get('apilastmodified'),
                                    pg_item.get('dataversion'),
                                    pg_item.get('datahash'),
                                    pg_item['teamnumber'],
                                    pg_item['season']
                                ))
                                updated += 1
                            else:
                                # Insert new team
                                cursor.execute("""
                                    INSERT INTO teams (
                                        team_number, season, team_name, school_name,
                                        city, state, country, rookie_year, website,
                                        last_updated, last_modified, etag,
                                        api_last_modified, data_version, data_hash
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    pg_item['teamnumber'],
                                    pg_item['season'],
                                    pg_item.get('teamname', ''),
                                    pg_item.get('schoolname', ''),
                                    pg_item.get('city', ''),
                                    pg_item.get('state', ''),
                                    pg_item.get('country', ''),
                                    pg_item.get('rookieyear'),
                                    pg_item.get('website'),
                                    pg_item.get('lastupdated'),
                                    pg_item.get('lastmodified'),
                                    pg_item.get('etag'),
                                    pg_item.get('apilastmodified'),
                                    pg_item.get('dataversion'),
                                    pg_item.get('datahash')
                                ))
                                inserted += 1
                    
                    pg_conn.commit()
                    
        except Exception as e:
            logger.error(f"Error syncing teams: {e}")
            raise
            
        logger.info(f"Teams sync completed: {inserted} inserted, {updated} updated")
        return inserted, updated
    
    async def sync_events_from_dynamodb(self, limit: int = None) -> Tuple[int, int]:
        """Sync events from DynamoDB to PostgreSQL"""
        logger.info("Starting events sync from DynamoDB to PostgreSQL")
        
        table_name = self.table_names['events']
        inserted = 0
        updated = 0
        
        try:
            with self.get_postgres_connection() as pg_conn:
                with pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Scan DynamoDB table
                    paginator = self.dynamodb.get_paginator('scan')
                    page_iterator = paginator.paginate(
                        TableName=table_name,
                        **({"Limit": limit} if limit else {})
                    )
                    
                    for page in page_iterator:
                        items = page.get('Items', [])
                        
                        for item in items:
                            # Convert DynamoDB item to PostgreSQL format
                            pg_item = self.convert_dynamodb_to_postgres(item)
                            
                            # Check if event exists
                            cursor.execute(
                                "SELECT 1 FROM events WHERE event_code = %s AND season = %s",
                                (pg_item['eventcode'], pg_item['season'])
                            )
                            
                            if cursor.fetchone():
                                # Update existing event
                                cursor.execute("""
                                    UPDATE events SET
                                        event_name = %s,
                                        event_type = %s,
                                        date_start = %s,
                                        date_end = %s,
                                        venue = %s,
                                        address = %s,
                                        city = %s,
                                        state = %s,
                                        country = %s,
                                        timezone = %s,
                                        website = %s,
                                        live_stream_url = %s,
                                        team_count = %s,
                                        match_count = %s,
                                        team_numbers = %s,
                                        last_updated = %s,
                                        data_hash = %s
                                    WHERE event_code = %s AND season = %s
                                """, (
                                    pg_item.get('eventname', ''),
                                    pg_item.get('eventtype', ''),
                                    pg_item.get('datestart'),
                                    pg_item.get('dateend'),
                                    pg_item.get('venue'),
                                    pg_item.get('address'),
                                    pg_item.get('city'),
                                    pg_item.get('state'),
                                    pg_item.get('country'),
                                    pg_item.get('timezone'),
                                    pg_item.get('website'),
                                    pg_item.get('livestreamurl'),
                                    pg_item.get('teamcount', 0),
                                    pg_item.get('matchcount', 0),
                                    pg_item.get('teamnumbers'),
                                    pg_item.get('lastupdated'),
                                    pg_item.get('datahash'),
                                    pg_item['eventcode'],
                                    pg_item['season']
                                ))
                                updated += 1
                            else:
                                # Insert new event
                                cursor.execute("""
                                    INSERT INTO events (
                                        event_code, season, event_name, event_type,
                                        date_start, date_end, venue, address, city,
                                        state, country, timezone, website, live_stream_url,
                                        team_count, match_count, team_numbers, last_updated, data_hash
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    pg_item['eventcode'],
                                    pg_item['season'],
                                    pg_item.get('eventname', ''),
                                    pg_item.get('eventtype', ''),
                                    pg_item.get('datestart'),
                                    pg_item.get('dateend'),
                                    pg_item.get('venue'),
                                    pg_item.get('address'),
                                    pg_item.get('city'),
                                    pg_item.get('state'),
                                    pg_item.get('country'),
                                    pg_item.get('timezone'),
                                    pg_item.get('website'),
                                    pg_item.get('livestreamurl'),
                                    pg_item.get('teamcount', 0),
                                    pg_item.get('matchcount', 0),
                                    pg_item.get('teamnumbers'),
                                    pg_item.get('lastupdated'),
                                    pg_item.get('datahash')
                                ))
                                inserted += 1
                    
                    pg_conn.commit()
                    
        except Exception as e:
            logger.error(f"Error syncing events: {e}")
            raise
            
        logger.info(f"Events sync completed: {inserted} inserted, {updated} updated")
        return inserted, updated
    
    async def sync_matches_from_dynamodb(self, limit: int = None) -> Tuple[int, int]:
        """Sync matches from DynamoDB to PostgreSQL (this will be the largest table)"""
        logger.info("Starting matches sync from DynamoDB to PostgreSQL")
        
        table_name = self.table_names['matches']
        inserted = 0
        updated = 0
        
        try:
            with self.get_postgres_connection() as pg_conn:
                with pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Scan DynamoDB table
                    paginator = self.dynamodb.get_paginator('scan')
                    page_iterator = paginator.paginate(
                        TableName=table_name,
                        **({"Limit": limit} if limit else {})
                    )
                    
                    for page in page_iterator:
                        items = page.get('Items', [])
                        
                        for item in items:
                            # Convert DynamoDB item to PostgreSQL format
                            pg_item = self.convert_dynamodb_to_postgres(item)
                            
                            # Check if match exists
                            cursor.execute(
                                "SELECT 1 FROM matches WHERE match_id = %s",
                                (pg_item['matchid'],)
                            )
                            
                            # Convert team arrays and scores to proper format
                            teams_json = Json(pg_item.get('teams', []))
                            red_score_json = Json(pg_item.get('redscore')) if pg_item.get('redscore') else None
                            blue_score_json = Json(pg_item.get('bluescore')) if pg_item.get('bluescore') else None
                            
                            if cursor.fetchone():
                                # Update existing match
                                cursor.execute("""
                                    UPDATE matches SET
                                        season = %s,
                                        event_code = %s,
                                        match_number = %s,
                                        description = %s,
                                        tournament_level = %s,
                                        series = %s,
                                        match_name = %s,
                                        play_number = %s,
                                        field_number = %s,
                                        start_time = %s,
                                        actual_start_time = %s,
                                        post_result_time = %s,
                                        teams = %s,
                                        red_teams = %s,
                                        blue_teams = %s,
                                        all_teams = %s,
                                        red_score = %s,
                                        blue_score = %s,
                                        last_updated = %s,
                                        data_hash = %s
                                    WHERE match_id = %s
                                """, (
                                    pg_item.get('season'),
                                    pg_item.get('eventcode'),
                                    pg_item.get('matchnumber'),
                                    pg_item.get('description', ''),
                                    pg_item.get('tournamentlevel', ''),
                                    pg_item.get('series'),
                                    pg_item.get('matchname'),
                                    pg_item.get('playnumber'),
                                    pg_item.get('fieldnumber'),
                                    pg_item.get('starttime'),
                                    pg_item.get('actualstarttime'),
                                    pg_item.get('postresulttime'),
                                    teams_json,
                                    pg_item.get('redteams', []),
                                    pg_item.get('blueteams', []),
                                    pg_item.get('allteams', []),
                                    red_score_json,
                                    blue_score_json,
                                    pg_item.get('lastupdated'),
                                    pg_item.get('datahash'),
                                    pg_item['matchid']
                                ))
                                updated += 1
                            else:
                                # Insert new match
                                cursor.execute("""
                                    INSERT INTO matches (
                                        match_id, season, event_code, match_number,
                                        description, tournament_level, series, match_name,
                                        play_number, field_number, start_time, actual_start_time,
                                        post_result_time, teams, red_teams, blue_teams,
                                        all_teams, red_score, blue_score, last_updated, data_hash
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    pg_item['matchid'],
                                    pg_item.get('season'),
                                    pg_item.get('eventcode'),
                                    pg_item.get('matchnumber'),
                                    pg_item.get('description', ''),
                                    pg_item.get('tournamentlevel', ''),
                                    pg_item.get('series'),
                                    pg_item.get('matchname'),
                                    pg_item.get('playnumber'),
                                    pg_item.get('fieldnumber'),
                                    pg_item.get('starttime'),
                                    pg_item.get('actualstarttime'),
                                    pg_item.get('postresulttime'),
                                    teams_json,
                                    pg_item.get('redteams', []),
                                    pg_item.get('blueteams', []),
                                    pg_item.get('allteams', []),
                                    red_score_json,
                                    blue_score_json,
                                    pg_item.get('lastupdated'),
                                    pg_item.get('datahash')
                                ))
                                inserted += 1
                    
                    pg_conn.commit()
                    
        except Exception as e:
            logger.error(f"Error syncing matches: {e}")
            raise
            
        logger.info(f"Matches sync completed: {inserted} inserted, {updated} updated")
        return inserted, updated
    
    async def sync_all_from_dynamodb(self, limit_per_table: int = None):
        """Sync all tables from DynamoDB to PostgreSQL"""
        logger.info("Starting full sync from DynamoDB to PostgreSQL")
        
        results = {}
        
        # Sync in order of dependencies
        results['teams'] = await self.sync_teams_from_dynamodb(limit_per_table)
        results['events'] = await self.sync_events_from_dynamodb(limit_per_table)
        results['matches'] = await self.sync_matches_from_dynamodb(limit_per_table)
        
        logger.info("Full sync completed:")
        for table, (inserted, updated) in results.items():
            logger.info(f"  {table}: {inserted} inserted, {updated} updated")
        
        return results
    
    def get_table_counts(self) -> Dict[str, Dict[str, int]]:
        """Get record counts from both DynamoDB and PostgreSQL"""
        counts = {}
        
        # DynamoDB counts
        for table_key, table_name in self.table_names.items():
            try:
                response = self.dynamodb.describe_table(TableName=table_name)
                dynamodb_count = response['Table']['ItemCount']
            except ClientError:
                dynamodb_count = 0
            
            counts[table_key] = {'dynamodb': dynamodb_count}
        
        # PostgreSQL counts
        try:
            with self.get_postgres_connection() as pg_conn:
                with pg_conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM teams")
                    counts['teams']['postgresql'] = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM events")
                    counts['events']['postgresql'] = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM matches")
                    counts['matches']['postgresql'] = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM epa_calculations")
                    counts['epa']['postgresql'] = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM sync_status")
                    counts['sync_status']['postgresql'] = cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting PostgreSQL counts: {e}")
            for table_key in counts:
                counts[table_key]['postgresql'] = 0
        
        return counts


async def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FTC Predictor Data Sync Utility')
    parser.add_argument('--action', choices=['sync-all', 'sync-teams', 'sync-events', 'sync-matches', 'counts'], 
                       default='counts', help='Action to perform')
    parser.add_argument('--limit', type=int, help='Limit number of records per table (for testing)')
    parser.add_argument('--environment', default='stage', help='DynamoDB environment (stage/prod)')
    
    args = parser.parse_args()
    
    syncer = FTCDataSyncer(environment=args.environment)
    
    if args.action == 'counts':
        counts = syncer.get_table_counts()
        print("\nTable Record Counts:")
        print("-" * 50)
        for table, count_data in counts.items():
            dynamo_count = count_data.get('dynamodb', 0)
            pg_count = count_data.get('postgresql', 0)
            print(f"{table:15} | DynamoDB: {dynamo_count:8,} | PostgreSQL: {pg_count:8,}")
    
    elif args.action == 'sync-all':
        await syncer.sync_all_from_dynamodb(args.limit)
    
    elif args.action == 'sync-teams':
        await syncer.sync_teams_from_dynamodb(args.limit)
    
    elif args.action == 'sync-events':
        await syncer.sync_events_from_dynamodb(args.limit)
    
    elif args.action == 'sync-matches':
        await syncer.sync_matches_from_dynamodb(args.limit)


if __name__ == '__main__':
    asyncio.run(main())
