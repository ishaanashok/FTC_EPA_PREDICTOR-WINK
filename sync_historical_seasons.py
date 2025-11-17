#!/usr/bin/env python3
"""
Synchronous Local Data Sync Script for FTC Predictor

This script runs locally and syncs data to AWS DynamoDB for seasons 2022 and 2023.
Uses synchronous operations to match our fixed Lambda functions.

Usage:
    python sync_historical_seasons.py --season 2023 --sync all
    python sync_historical_seasons.py --season 2022 --sync all
    python sync_historical_seasons.py --season 2023 --sync teams
    python sync_historical_seasons.py --season 2023 --sync events
"""

import argparse
import sys
import os
import logging
import json
import boto3
import requests
import base64
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

# Add the AWS services to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'aws'))

from services.dynamodb_service import DynamoDBService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync_historical.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SyncFTCApi:
    """Synchronous FTC API client for data sync"""
    
    def __init__(self, credentials: Dict[str, str]):
        self.base_url = "https://ftc-api.firstinspires.org/v2.0"
        
        # Create authorization token
        username = credentials['username']
        api_key = credentials['api_key']
        auth_string = f"{username}:{api_key}"
        auth_token = base64.b64encode(auth_string.encode()).decode()
        
        self.headers = {
            "Authorization": f"Basic {auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "FTC-Predictor-Sync/1.0"
        }
    
    def make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a synchronous HTTP request to FTC API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {endpoint}: {e}")
            raise
    
    def get_teams(self, season: int, page: int = 1, per_page: int = 10000) -> Tuple[List[Dict], Dict]:
        """Get teams for a season with pagination"""
        endpoint = f"/{season}/teams"
        params = {
            'page': page,
            'per_page': per_page
        }
        
        logger.info(f"Fetching teams for season {season}, page {page}")
        response = self.make_request(endpoint, params)
        
        teams = response.get('teams', [])
        
        # Build metadata
        metadata = {
            'page': page,
            'per_page': per_page,
            'total_pages': response.get('pageTotal', 1),
            'total_count': response.get('teamCountTotal', len(teams))
        }
        
        return teams, metadata
    
    def get_all_teams(self, season: int) -> List[Dict]:
        """Get all teams for a season (handles pagination)"""
        all_teams = []
        page = 1
        
        while True:
            teams, metadata = self.get_teams(season, page=page)
            all_teams.extend(teams)
            
            logger.info(f"Retrieved {len(teams)} teams from page {page}/{metadata['total_pages']}")
            
            if page >= metadata['total_pages']:
                break
            
            page += 1
            time.sleep(0.5)  # Rate limiting
        
        logger.info(f"Retrieved {len(all_teams)} total teams for season {season}")
        return all_teams
    
    def get_events(self, season: int, page: int = 1, per_page: int = 10000) -> Tuple[List[Dict], Dict]:
        """Get events for a season with pagination"""
        endpoint = f"/{season}/events"
        params = {
            'page': page,
            'per_page': per_page
        }
        
        logger.info(f"Fetching events for season {season}, page {page}")
        response = self.make_request(endpoint, params)
        
        # Debug: log the response structure
        logger.info(f"Events API response keys: {list(response.keys())}")
        
        # Try different possible field names
        events = None
        if 'Events' in response:
            events = response['Events']
        elif 'events' in response:
            events = response['events']
        else:
            logger.warning(f"No 'Events' or 'events' field found. Response: {response}")
            events = []
        
        # Build metadata
        metadata = {
            'page': page,
            'per_page': per_page,
            'total_pages': response.get('pageTotal', 1),
            'total_count': response.get('eventCountTotal', len(events))
        }
        
        return events, metadata
    
    def get_all_events(self, season: int) -> List[Dict]:
        """Get all events for a season (no pagination needed)"""
        endpoint = f"/{season}/events"
        
        logger.info(f"Fetching all events for season {season}")
        response = self.make_request(endpoint)
        
        # Response uses lowercase 'events' 
        events = response.get('events', [])
        event_count = response.get('eventCount', len(events))
        
        logger.info(f"Retrieved {len(events)} total events for season {season} (API reported {event_count})")
        return events
    
    def get_event_matches(self, season: int, event_code: str) -> List[Dict]:
        """Get all matches for an event"""
        endpoint = f"/{season}/matches/{event_code}"
        
        try:
            logger.info(f"Fetching all matches for event {event_code}")
            response = self.make_request(endpoint)
            
            matches = response.get('Matches', response.get('matches', []))
            logger.info(f"Retrieved {len(matches)} matches for {event_code}")
            
            return matches
        except Exception as e:
            # Log warning instead of error for missing matches (common for historical data)
            logger.warning(f"Could not get matches for {event_code}: {e}")
            return []

class HistoricalDataSync:
    """Synchronous data synchronization service for historical seasons"""
    
    def __init__(self):
        self.db_service = None
        self.ftc_api = None
        
    def initialize(self):
        """Initialize AWS and FTC API services"""
        try:
            logger.info("Initializing DynamoDB service...")
            self.db_service = DynamoDBService('stage')
            
            logger.info("Using provided FTC API credentials...")
            # Use provided credentials directly
            credentials = {
                'username': 'ishaanashok',
                'api_key': '62C6B474-AE61-46FF-BBA7-DC513DC8E012'
            }
            
            logger.info("Initializing FTC API service...")
            self.ftc_api = SyncFTCApi(credentials)
            
            logger.info("Services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            raise
    
    def sync_teams(self, season: int) -> Dict[str, Any]:
        """Sync teams data for the specified season"""
        logger.info(f"Starting teams sync for season {season}")
        
        try:
            # Get all teams from FTC API
            teams_data = self.ftc_api.get_all_teams(season)
            
            if teams_data:
                # Transform raw API data to match our schema
                transformed_teams = []
                teams_to_store = []
                teams_skipped = 0
                
                for team in teams_data:
                    team_number = team.get('teamNumber')
                    if not team_number:
                        continue
                    
                    
                    transformed_team = {
                        'teamNumber': team_number,
                        'season': season,
                        'teamName': team.get('nameFull', '') or team.get('nameShort', ''),
                        'schoolName': team.get('schoolName', ''),
                        'city': team.get('city', ''),
                        'state': team.get('stateProv', ''),
                        'country': team.get('country', ''),
                        'rookieYear': team.get('rookieYear'),
                        'website': team.get('website'),
                        'lastUpdated': datetime.now(timezone.utc).isoformat(),
                        'dataHash': current_hash
                    }
                    # Remove None values
                    transformed_team = {k: v for k, v in transformed_team.items() if v is not None}
                    transformed_teams.append(transformed_team)
                    
                    # Check if team already exists with same data
                    existing_team = self.db_service.get_team(team_number, season)
                    if existing_team:
                        existing_hash = existing_team.get('dataHash', '')
                        if existing_hash == current_hash:
                            # Data hasn't changed, skip this team
                            teams_skipped += 1
                            continue
                        else:
                            logger.info(f"Team {team_number} data changed, will update")
                    else:
                        logger.info(f"Team {team_number} is new for season {season}")
                    
                    # Team needs to be stored (new or changed)
                    teams_to_store.append(transformed_team)
                
                logger.info(f"Teams analysis: {len(transformed_teams)} total, {len(teams_to_store)} to store, {teams_skipped} skipped (no changes)")
                
                if teams_to_store:
                    # Store only teams that need updating in DynamoDB using batch operations
                    batch_size = 25  # DynamoDB batch limit
                    teams_updated = 0
                    
                    for i in range(0, len(teams_to_store), batch_size):
                        batch = teams_to_store[i:i + batch_size]
                        logger.info(f"Storing teams batch {i//batch_size + 1} "
                                  f"({len(batch)} teams)")
                        
                        success = self.db_service.batch_save_teams(batch)
                        if success:
                            teams_updated += len(batch)
                        else:
                            logger.warning(f"Failed to store batch {i//batch_size + 1}")
                    
                    logger.info(f"Teams sync completed: {teams_updated} teams updated, {teams_skipped} teams skipped")
                else:
                    logger.info(f"Teams sync completed: No teams needed updating, {teams_skipped} teams skipped")
                
                return {
                    'success': True,
                    'teams_processed': len(teams_data),
                    'teams_updated': len(teams_to_store),
                    'teams_skipped': teams_skipped
                }
            else:
                logger.warning("No teams data retrieved")
                return {'success': False, 'error': 'No teams data retrieved'}
                
        except Exception as e:
            logger.error(f"Teams sync failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def sync_events(self, season: int) -> Dict[str, Any]:
        """Sync events data for the specified season"""
        logger.info(f"Starting events sync for season {season}")
        
        try:
            # Get all events from FTC API
            events_data = self.ftc_api.get_all_events(season)
            
            if events_data:
                # Transform raw API data to match our schema
                transformed_events = []
                events_to_store = []
                events_skipped = 0
                
                for event in events_data:
                    event_code = event.get('code', '')
                    if not event_code:
                        continue
                    
                    
                    transformed_event = {
                        'eventCode': event_code,
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
                        'lastUpdated': datetime.now(timezone.utc).isoformat(),
                        'dataHash': current_hash
                    }
                    # Remove None values
                    transformed_event = {k: v for k, v in transformed_event.items() if v is not None}
                    transformed_events.append(transformed_event)
                    
                    # Check if event already exists with same data
                    existing_event = self.db_service.get_event(event_code, season)
                    if existing_event:
                        existing_hash = existing_event.get('dataHash', '')
                        if existing_hash == current_hash:
                            # Data hasn't changed, skip this event
                            events_skipped += 1
                            continue
                        else:
                            logger.info(f"Event {event_code} data changed, will update")
                    else:
                        logger.info(f"Event {event_code} is new for season {season}")
                    
                    # Event needs to be stored (new or changed)
                    events_to_store.append(transformed_event)
                
                logger.info(f"Events analysis: {len(transformed_events)} total, {len(events_to_store)} to store, {events_skipped} skipped (no changes)")
                
                if events_to_store:
                    # Store only events that need updating in DynamoDB using batch operations
                    batch_size = 25  # DynamoDB batch limit
                    events_updated = 0
                    
                    for i in range(0, len(events_to_store), batch_size):
                        batch = events_to_store[i:i + batch_size]
                        logger.info(f"Storing events batch {i//batch_size + 1} "
                                  f"({len(batch)} events)")
                        
                        success = self.db_service.batch_save_events(batch)
                        if success:
                            events_updated += len(batch)
                        else:
                            logger.warning(f"Failed to store batch {i//batch_size + 1}")
                    
                    logger.info(f"Events sync completed: {events_updated} events updated, {events_skipped} events skipped")
                else:
                    logger.info(f"Events sync completed: No events needed updating, {events_skipped} events skipped")
                
                return {
                    'success': True,
                    'events_processed': len(events_data),
                    'events_updated': len(events_to_store),
                    'events_skipped': events_skipped
                }
            else:
                logger.warning("No events data retrieved")
                return {'success': False, 'error': 'No events data retrieved'}
                
        except Exception as e:
            logger.error(f"Events sync failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def sync_matches(self, season: int) -> Dict[str, Any]:
        """Sync matches data for the specified season"""
        logger.info(f"Starting matches sync for season {season}")
        
        try:
            # Get events from DynamoDB
            logger.info(f"Getting events from DynamoDB for season {season}")
            events_from_db = self.db_service.get_events_by_season(season)
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
                    # Get all matches for this event (qualification, playoff, etc.)
                    all_matches = self.ftc_api.get_event_matches(season, event_code)
                    
                    if all_matches:
                        total_matches_processed += len(all_matches)
                        
                        # Convert FTC API matches to our format
                        converted_matches = []
                        for match_data in all_matches:
                            try:
                                match = self._convert_match(match_data, season, event_code)
                                converted_matches.append(match)
                            except Exception as e:
                                logger.error(f"Error converting match {match_data.get('matchNumber', 'unknown')}: {e}")
                                continue
                        
                        # Store converted matches in DynamoDB using batch operations
                        batch_size = 25  # DynamoDB batch limit
                        
                        for i in range(0, len(converted_matches), batch_size):
                            batch = converted_matches[i:i + batch_size]
                            success = self.db_service.batch_save_matches(batch)
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
    
    def sync_all(self, season: int) -> Dict[str, Any]:
        """Sync all data (teams, events, matches) for the specified season"""
        logger.info(f"Starting full data sync for season {season}")
        
        results = {}
        
        # Sync teams
        logger.info("=== SYNCING TEAMS ===")
        teams_result = self.sync_teams(season)
        results['teams'] = teams_result
        
        # Sync events
        logger.info("=== SYNCING EVENTS ===")
        events_result = self.sync_events(season)
        results['events'] = events_result
        
        # Sync matches (using DynamoDB events)
        logger.info("=== SYNCING MATCHES ===")
        matches_result = self.sync_matches(season)
        results['matches'] = matches_result
        
        logger.info("Full data sync completed")
        return results
    
    
    def _convert_match(self, match_data: Dict, season: int, event_code: str) -> Dict:
        """Convert FTC API match to our DynamoDB format"""
        # Extract teams from alliances
        red_teams = []
        blue_teams = []
        
        if 'alliances' in match_data:
            if 'red' in match_data['alliances'] and 'teams' in match_data['alliances']['red']:
                red_teams = [team.get('teamNumber') for team in match_data['alliances']['red']['teams']]
            if 'blue' in match_data['alliances'] and 'teams' in match_data['alliances']['blue']:
                blue_teams = [team.get('teamNumber') for team in match_data['alliances']['blue']['teams']]
        
        # Create teams array for DynamoDB
        teams = []
        for i, team_num in enumerate(red_teams):
            teams.append({
                'teamNumber': team_num,
                'station': f'Red{i+1}'
            })
        for i, team_num in enumerate(blue_teams):
            teams.append({
                'teamNumber': team_num,
                'station': f'Blue{i+1}'
            })
        
        return {
            'matchId': f"{season}-{event_code}-{match_data.get('tournamentLevel', 'QUAL')}-{match_data.get('series', 1)}-{match_data.get('matchNumber', 1)}",
            'season': season,
            'eventCode': event_code,
            'tournamentLevel': match_data.get('tournamentLevel', 'QUALIFICATION'),
            'series': match_data.get('series', 1),
            'matchNumber': match_data.get('matchNumber', 1),
            'description': match_data.get('description', ''),
            'startTime': match_data.get('startTime', ''),
            'actualStartTime': match_data.get('actualStartTime', ''),
            'postResultTime': match_data.get('postResultTime', ''),
            'scoreRedFinal': match_data.get('scoreRedFinal', 0),
            'scoreRedFoul': match_data.get('scoreRedFoul', 0),
            'scoreRedAuto': match_data.get('scoreRedAuto', 0),
            'scoreBlueFinal': match_data.get('scoreBlueFinal', 0),
            'scoreBlueFoul': match_data.get('scoreBlueFoul', 0),
            'scoreBlueAuto': match_data.get('scoreBlueAuto', 0),
            'teams': teams,
            'lastUpdated': datetime.now(timezone.utc).isoformat(),
        }

def main():
    """Main function to handle command line arguments and run sync"""
    parser = argparse.ArgumentParser(description='Historical FTC Data Sync - Synchronous Version')
    parser.add_argument('--season', type=int, required=True, 
                       help='FTC season year (e.g., 2023, 2022)')
    parser.add_argument('--sync', choices=['teams', 'events', 'matches', 'all'], 
                       required=True, help='What data to sync')
    
    args = parser.parse_args()
    
    # Validate season
    if args.season not in [2022, 2023]:
        print("❌ This script is for historical seasons 2022 and 2023 only")
        sys.exit(1)
    
    # Create sync instance
    sync = HistoricalDataSync()
    
    try:
        # Initialize services
        sync.initialize()
        
        # Run the requested sync operation
        if args.sync == 'teams':
            result = sync.sync_teams(args.season)
        elif args.sync == 'events':
            result = sync.sync_events(args.season)
        elif args.sync == 'matches':
            result = sync.sync_matches(args.season)
        elif args.sync == 'all':
            result = sync.sync_all(args.season)
        
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
    main()
