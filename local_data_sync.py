#!/usr/bin/env python3
"""
Local Data Sync Script for FTC Predictor

This script runs locally on your computer but syncs data to AWS DynamoDB.
Use this as an alternative to the Lambda function when you need more control
or want to avoid AWS timeout issues.

Usage:
    python local_data_sync.py --season 2024 --sync teams
    python local_data_sync.py --season 2024 --sync events
    python local_data_sync.py --season 2024 --sync matches
    python local_data_sync.py --season 2024 --sync all
"""

import asyncio
import argparse
import sys
import os
import logging
from datetime import datetime, timezone
import json
import boto3
from typing import Dict, Any, Optional

# Add the AWS services to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'aws'))

from services.dynamodb_service import DynamoDBService
from services.ftc_api_service import FTCApiService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('local_sync.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class LocalDataSync:
    """Local data synchronization service"""
    
    def __init__(self):
        self.db_service = None
        self.ftc_api = None
        
    async def initialize(self):
        """Initialize AWS and FTC API services"""
        try:
            logger.info("Initializing DynamoDB service...")
            self.db_service = DynamoDBService('stage')
            
            logger.info("Getting FTC API credentials from AWS Secrets Manager...")
            # Get FTC API credentials from AWS Secrets Manager (same as Lambda)
            secrets_client = boto3.client('secretsmanager')
            secrets_name = 'arn:aws:secretsmanager:us-east-1:843578292678:secret:FTC-API-Credentials-stage-0KqPsx'
            
            response = secrets_client.get_secret_value(SecretId=secrets_name)
            credentials = json.loads(response['SecretString'])
            
            logger.info("Initializing FTC API service...")
            self.ftc_api = FTCApiService(credentials)
            await self.ftc_api.initialize()
            
            logger.info("Services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            raise
    
    async def sync_teams(self, season: int) -> Dict[str, Any]:
        """Sync teams data for the specified season"""
        logger.info(f"Starting teams sync for season {season}")
        
        try:
            # Get teams from FTC API (it handles pagination internally)
            logger.info(f"Fetching ALL teams for season {season}")
            teams_data, metadata = await self.ftc_api.get_teams(season)
            
            logger.info(f"Retrieved {len(teams_data) if teams_data else 0} teams total")
            
            if teams_data:
                # Transform raw API data to match our schema
                transformed_teams = []
                for team in teams_data:
                    transformed_team = {
                        'teamNumber': team.get('teamNumber'),
                        'season': season,
                        'teamName': team.get('nameFull', '') or team.get('nameShort', ''),
                        'schoolName': team.get('schoolName', ''),
                        'city': team.get('city', ''),
                        'state': team.get('stateProv', ''),
                        'country': team.get('country', ''),
                        'rookieYear': team.get('rookieYear'),
                        'website': team.get('website'),
                        'lastUpdated': datetime.now(timezone.utc).isoformat()
                    }
                    # Remove None values
                    transformed_team = {k: v for k, v in transformed_team.items() if v is not None}
                    transformed_teams.append(transformed_team)
                
                # Store teams in DynamoDB using batch operations
                batch_size = 25  # DynamoDB batch limit
                teams_updated = 0
                
                for i in range(0, len(transformed_teams), batch_size):
                    batch = transformed_teams[i:i + batch_size]
                    logger.info(f"Storing teams batch {i//batch_size + 1} "
                              f"({len(batch)} teams)")
                    
                    success = await self.db_service.batch_save_teams(batch)
                    if success:
                        teams_updated += len(batch)
                    else:
                        logger.warning(f"Failed to store batch {i//batch_size + 1}")
                
                logger.info(f"Teams sync completed: {teams_updated} teams updated")
                return {
                    'success': True,
                    'teams_processed': len(teams_data),
                    'teams_updated': teams_updated
                }
            else:
                logger.warning("No teams data retrieved")
                return {'success': False, 'error': 'No teams data retrieved'}
                
        except Exception as e:
            logger.error(f"Teams sync failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def sync_events(self, season: int) -> Dict[str, Any]:
        """Sync events data for the specified season"""
        logger.info(f"Starting events sync for season {season}")
        
        try:
            # Get events from FTC API (it handles pagination internally)
            logger.info(f"Fetching ALL events for season {season}")
            events_data, metadata = await self.ftc_api.get_events(season)
            
            logger.info(f"Retrieved {len(events_data) if events_data else 0} events total")
            
            if events_data:
                # Transform raw API data to match our schema
                transformed_events = []
                for event in events_data:
                    transformed_event = {
                        'eventCode': event.get('code', ''),
                        'season': season,
                        'eventName': event.get('name', ''),
                        'eventType': event.get('type', ''),
                        'dateStart': event.get('dateStart'),
                        'dateEnd': event.get('dateEnd'),
                        'venue': event.get('venue'),
                        'address': event.get('address'),
                        'city': event.get('city'),
                        'state': event.get('stateProv'),
                        'country': event.get('country'),
                        'timezone': event.get('timezone'),
                        'website': event.get('website'),
                        'liveStreamUrl': event.get('liveStreamUrl'),
                        'teamCount': event.get('teamCount', 0),
                        'matchCount': event.get('matchCount', 0),
                        'lastUpdated': datetime.now(timezone.utc).isoformat()
                    }
                    # Remove None values
                    transformed_event = {k: v for k, v in transformed_event.items() if v is not None}
                    transformed_events.append(transformed_event)
                
                # Store events in DynamoDB using batch operations
                batch_size = 25  # DynamoDB batch limit
                events_updated = 0
                
                for i in range(0, len(transformed_events), batch_size):
                    batch = transformed_events[i:i + batch_size]
                    logger.info(f"Storing events batch {i//batch_size + 1} "
                              f"({len(batch)} events)")
                    
                    success = await self.db_service.batch_save_events(batch)
                    if success:
                        events_updated += len(batch)
                    else:
                        logger.warning(f"Failed to store batch {i//batch_size + 1}")
                
                logger.info(f"Events sync completed: {events_updated} events updated")
                return {
                    'success': True,
                    'events_processed': len(events_data),
                    'events_updated': events_updated
                }
            else:
                logger.warning("No events data retrieved")
                return {'success': False, 'error': 'No events data retrieved'}
                
        except Exception as e:
            logger.error(f"Events sync failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def sync_matches(self, season: int) -> Dict[str, Any]:
        """Sync matches data for the specified season"""
        logger.info(f"Starting matches sync for season {season}")
        
        try:
            # Get events from DynamoDB (not API - this is the optimization!)
            logger.info(f"Getting events from DynamoDB for season {season}")
            events_from_db = await self.db_service.get_events_by_season(season)
            active_events = events_from_db if events_from_db else []
            
            logger.info(f"Found {len(active_events)} events in DynamoDB")
            
            total_matches_processed = 0
            total_matches_updated = 0
            
            for event_data in active_events:
                event_code = event_data.get('eventCode') or event_data.get('code')
                
                if not event_code:
                    logger.warning(f"Event missing code: {event_data}")
                    continue
                
                logger.info(f"Syncing matches for event: {event_code}")
                
                try:
                    # Get matches for this event (both qual and playoff)
                    all_matches = []
                    
                    # Get qualification matches
                    qual_matches, _ = await self.ftc_api.get_event_matches(season, event_code, "qual")
                    if qual_matches:
                        all_matches.extend(qual_matches)
                    
                    # Get playoff matches
                    playoff_matches, _ = await self.ftc_api.get_event_matches(season, event_code, "playoff")
                    if playoff_matches:
                        all_matches.extend(playoff_matches)
                    
                    if all_matches:
                        total_matches_processed += len(all_matches)
                        
                        # Convert FTC API matches to our Match model format
                        converted_matches = []
                        for match_data in all_matches:
                            try:
                                # Convert using the model conversion function  
                                from models.data_models import convert_ftc_api_match
                                match = convert_ftc_api_match(match_data, season, event_code)
                                converted_matches.append(match.to_dynamodb_item())
                            except Exception as e:
                                logger.error(f"Error converting match {match_data.get('matchNumber', 'unknown')}: {e}")
                                continue
                        
                        # Store converted matches in DynamoDB using batch operations
                        batch_size = 25  # DynamoDB batch limit
                        
                        for i in range(0, len(converted_matches), batch_size):
                            batch = converted_matches[i:i + batch_size]
                            success = await self.db_service.batch_save_matches(batch)
                            if success:
                                total_matches_updated += len(batch)
                        
                        logger.info(f"Event {event_code}: {len(all_matches)} matches processed")
                    else:
                        logger.info(f"Event {event_code}: No matches found")
                        
                except Exception as e:
                    logger.error(f"Failed to sync matches for event {event_code}: {e}")
                    continue
            
            logger.info(f"Matches sync completed: {total_matches_updated} matches updated")
            return {
                'success': True,
                'events_processed': len(active_events),
                'matches_processed': total_matches_processed,
                'matches_updated': total_matches_updated
            }
            
        except Exception as e:
            logger.error(f"Matches sync failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def sync_all(self, season: int) -> Dict[str, Any]:
        """Sync all data (teams, events, matches) for the specified season"""
        logger.info(f"Starting full data sync for season {season}")
        
        results = {}
        
        # Sync teams
        logger.info("=== SYNCING TEAMS ===")
        teams_result = await self.sync_teams(season)
        results['teams'] = teams_result
        
        # Sync events
        logger.info("=== SYNCING EVENTS ===")
        events_result = await self.sync_events(season)
        results['events'] = events_result
        
        # Sync matches (using DynamoDB events)
        logger.info("=== SYNCING MATCHES ===")
        matches_result = await self.sync_matches(season)
        results['matches'] = matches_result
        
        logger.info("Full data sync completed")
        return results

async def main():
    """Main function to handle command line arguments and run sync"""
    parser = argparse.ArgumentParser(description='FTC Data Sync - Local Version')
    parser.add_argument('--season', type=int, required=True, 
                       help='FTC season year (e.g., 2024)')
    parser.add_argument('--sync', choices=['teams', 'events', 'matches', 'all'], 
                       required=True, help='What data to sync')
    
    args = parser.parse_args()
    
    # Create sync instance
    sync = LocalDataSync()
    
    try:
        # Initialize services
        await sync.initialize()
        
        # Run the requested sync operation
        if args.sync == 'teams':
            result = await sync.sync_teams(args.season)
        elif args.sync == 'events':
            result = await sync.sync_events(args.season)
        elif args.sync == 'matches':
            result = await sync.sync_matches(args.season)
        elif args.sync == 'all':
            result = await sync.sync_all(args.season)
        
        # Print results
        print("\n=== SYNC RESULTS ===")
        print(f"Season: {args.season}")
        print(f"Operation: {args.sync}")
        print(f"Results: {result}")
        
        if isinstance(result, dict):
            if result.get('success'):
                print("✅ Sync completed successfully!")
            else:
                print(f"❌ Sync failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
        
    except Exception as e:
        logger.error(f"Sync operation failed: {e}")
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
