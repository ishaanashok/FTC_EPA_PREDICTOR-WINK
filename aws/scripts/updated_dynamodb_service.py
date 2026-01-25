import boto3
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import time
import os

logger = logging.getLogger(__name__)

class DynamoDBService:
    """
    Updated DynamoDB service for new schema (v2.0)
    
    Key Changes:
    - EPA table renamed to TeamMatchEPA with new composite key structure
    - Events table uses eventId as primary key
    - Updated index names to match new schema
    - Removed SyncStatus table (not in new schema)
    """
    
    def __init__(self, environment: str = None):
        self.dynamodb = boto3.resource('dynamodb')
        
        # Get environment from parameter or environment variable
        if environment is None:
            environment = os.environ.get('ENVIRONMENT', 'stage')
        self.environment = environment
        
        # Initialize simple in-memory cache for EPA calculations
        self._cache = {}
        
        # Initialize tables with environment-specific names (NEW SCHEMA)
        self.teams_table = self.dynamodb.Table(f'FTC_Teams_{environment}')
        self.events_table = self.dynamodb.Table(f'FTC_Events_{environment}')
        self.matches_table = self.dynamodb.Table(f'FTC_Matches_{environment}')
        self.team_match_epa_table = self.dynamodb.Table(f'FTC_TeamMatchEPA_{environment}')
        
        logger.info(f"DynamoDBService initialized for environment: {environment} (Schema v2.0)")
    
    def convert_to_dynamodb_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert item to DynamoDB compatible format"""
        def convert_value(value):
            if isinstance(value, float):
                return Decimal(str(value))
            elif isinstance(value, dict):
                return {k: convert_value(v) for k, v in value.items() if v is not None}
            elif isinstance(value, list):
                return [convert_value(v) for v in value]
            elif isinstance(value, datetime):
                return value.isoformat()
            # Handle empty strings in GSI keys
            elif isinstance(value, str) and not value.strip():
                return None
            return value
        
        result = convert_value(item)
        if not isinstance(result, dict):
            raise TypeError("convert_to_dynamodb_item must return a dictionary")
        return result
    
    def convert_from_dynamodb_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB item to regular Python types"""
        def convert_value(value):
            if isinstance(value, Decimal):
                return float(value)
            elif isinstance(value, dict):
                return {k: convert_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [convert_value(v) for v in value]
            return value
        
        result = convert_value(item)
        if not isinstance(result, dict):
            raise TypeError("convert_from_dynamodb_item must return a dictionary")
        return result
    
    # ========================================================================
    # TEAM OPERATIONS
    # ========================================================================
    
    def get_team(self, team_number: int, season: int) -> Optional[Dict[str, Any]]:
        """Get a specific team"""
        try:
            response = self.teams_table.get_item(
                Key={'teamNumber': team_number, 'season': season}
            )
            
            if 'Item' in response:
                return self.convert_from_dynamodb_item(response['Item'])
            return None
            
        except ClientError as e:
            logger.error(f"Error getting team {team_number} for season {season}: {str(e)}")
            return None
    
    def get_teams_by_season(self, season: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all teams for a season using SeasonIndex"""
        try:
            teams = []
            last_evaluated_key = None
            
            while True:
                query_kwargs = {
                    'IndexName': 'SeasonIndex',
                    'KeyConditionExpression': Key('season').eq(season)
                }
                
                if limit is not None:
                    query_kwargs['Limit'] = limit
                
                if last_evaluated_key:
                    query_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.teams_table.query(**query_kwargs)
                
                for item in response.get('Items', []):
                    teams.append(self.convert_from_dynamodb_item(item))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key or (limit and len(teams) >= limit):
                    break
            
            return teams[:limit] if limit else teams
            
        except ClientError as e:
            logger.error(f"Error getting teams for season {season}: {str(e)}")
            return []
    
    def get_teams_by_country(self, country: str, season: int) -> List[Dict[str, Any]]:
        """Get teams by country using CountrySeasonIndex"""
        try:
            teams = []
            last_evaluated_key = None
            
            while True:
                query_kwargs = {
                    'IndexName': 'CountrySeasonIndex',
                    'KeyConditionExpression': Key('country').eq(country) & Key('season').eq(season)
                }
                
                if last_evaluated_key:
                    query_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.teams_table.query(**query_kwargs)
                
                for item in response.get('Items', []):
                    teams.append(self.convert_from_dynamodb_item(item))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
            
            return teams
            
        except ClientError as e:
            logger.error(f"Error getting teams for country {country}, season {season}: {str(e)}")
            return []
    
    def get_teams_by_region(self, region: str, season: int) -> List[Dict[str, Any]]:
        """Get teams by region using RegionSeasonIndex"""
        try:
            teams = []
            last_evaluated_key = None
            
            while True:
                query_kwargs = {
                    'IndexName': 'RegionSeasonIndex',
                    'KeyConditionExpression': Key('homeRegion').eq(region) & Key('season').eq(season)
                }
                
                if last_evaluated_key:
                    query_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.teams_table.query(**query_kwargs)
                
                for item in response.get('Items', []):
                    teams.append(self.convert_from_dynamodb_item(item))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
            
            return teams
            
        except ClientError as e:
            logger.error(f"Error getting teams for region {region}, season {season}: {str(e)}")
            return []
    
    def save_team(self, team_data: Dict[str, Any]) -> bool:
        """Save a team to DynamoDB"""
        try:
            # Ensure required GSI fields have defaults
            if 'country' not in team_data or not team_data['country']:
                team_data['country'] = 'UNKNOWN'
            if 'homeRegion' not in team_data or not team_data['homeRegion']:
                team_data['homeRegion'] = 'UNKNOWN'
            
            dynamodb_item = self.convert_to_dynamodb_item(team_data)
            self.teams_table.put_item(Item=dynamodb_item)
            return True
        except ClientError as e:
            logger.error(f"Error saving team {team_data.get('teamNumber')}: {str(e)}")
            return False
    
    def batch_save_teams(self, teams: List[Dict[str, Any]]) -> bool:
        """Save multiple teams efficiently"""
        try:
            with self.teams_table.batch_writer() as batch:
                for team in teams:
                    # Ensure required GSI fields have defaults
                    if 'country' not in team or not team['country']:
                        team['country'] = 'UNKNOWN'
                    if 'homeRegion' not in team or not team['homeRegion']:
                        team['homeRegion'] = 'UNKNOWN'
                    
                    dynamodb_item = self.convert_to_dynamodb_item(team)
                    batch.put_item(Item=dynamodb_item)
            return True
        except ClientError as e:
            logger.error(f"Error batch saving teams: {str(e)}")
            return False
    
    # ========================================================================
    # EVENT OPERATIONS (Updated for new schema)
    # ========================================================================
    
    def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific event by eventId (primary key)"""
        try:
            response = self.events_table.get_item(
                Key={'eventId': event_id}
            )
            
            if 'Item' in response:
                return self.convert_from_dynamodb_item(response['Item'])
            return None
            
        except ClientError as e:
            logger.error(f"Error getting event {event_id}: {str(e)}")
            return None
    
    def get_event(self, event_code: str, season: int) -> Optional[Dict[str, Any]]:
        """Get a specific event by code and season using CodeSeasonIndex"""
        try:
            response = self.events_table.query(
                IndexName='CodeSeasonIndex',
                KeyConditionExpression=Key('code').eq(event_code) & Key('season').eq(season),
                Limit=1
            )
            
            if response.get('Items'):
                return self.convert_from_dynamodb_item(response['Items'][0])
            return None
            
        except ClientError as e:
            logger.error(f"Error getting event {event_code} for season {season}: {str(e)}")
            return None
    
    def get_events_by_season(self, season: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all events for a season using SeasonDateIndex (sorted by date)"""
        try:
            events = []
            last_evaluated_key = None
            
            while True:
                query_kwargs = {
                    'IndexName': 'SeasonDateIndex',
                    'KeyConditionExpression': Key('season').eq(season),
                    'ScanIndexForward': True  # Sort by dateStart ascending
                }
                
                if limit is not None:
                    query_kwargs['Limit'] = limit
                
                if last_evaluated_key:
                    query_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.events_table.query(**query_kwargs)
                
                for item in response.get('Items', []):
                    events.append(self.convert_from_dynamodb_item(item))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key or (limit and len(events) >= limit):
                    break
            
            return events[:limit] if limit else events
            
        except ClientError as e:
            logger.error(f"Error getting events for season {season}: {str(e)}")
            return []
    
    def get_events_by_region(self, region_code: str, season: int) -> List[Dict[str, Any]]:
        """Get events by region using RegionSeasonIndex"""
        try:
            events = []
            last_evaluated_key = None
            
            while True:
                query_kwargs = {
                    'IndexName': 'RegionSeasonIndex',
                    'KeyConditionExpression': Key('regionCode').eq(region_code) & Key('season').eq(season)
                }
                
                if last_evaluated_key:
                    query_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.events_table.query(**query_kwargs)
                
                for item in response.get('Items', []):
                    events.append(self.convert_from_dynamodb_item(item))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
            
            return events
            
        except ClientError as e:
            logger.error(f"Error getting events for region {region_code}, season {season}: {str(e)}")
            return []
    
    def save_event(self, event_data: Dict[str, Any]) -> bool:
        """Save an event to DynamoDB"""
        try:
            # Ensure required GSI fields have defaults
            if 'code' not in event_data or not event_data['code']:
                event_data['code'] = 'UNKNOWN'
            if 'dateStart' not in event_data or not event_data['dateStart']:
                event_data['dateStart'] = '1970-01-01T00:00:00'
            if 'regionCode' not in event_data or not event_data['regionCode']:
                event_data['regionCode'] = 'UNKNOWN'
            
            dynamodb_item = self.convert_to_dynamodb_item(event_data)
            self.events_table.put_item(Item=dynamodb_item)
            return True
        except ClientError as e:
            logger.error(f"Error saving event {event_data.get('eventId')}: {str(e)}")
            return False
    
    def batch_save_events(self, events: List[Dict[str, Any]]) -> bool:
        """Save multiple events efficiently"""
        try:
            with self.events_table.batch_writer() as batch:
                for event in events:
                    # Ensure required GSI fields have defaults
                    if 'code' not in event or not event['code']:
                        event['code'] = 'UNKNOWN'
                    if 'dateStart' not in event or not event['dateStart']:
                        event['dateStart'] = '1970-01-01T00:00:00'
                    if 'regionCode' not in event or not event['regionCode']:
                        event['regionCode'] = 'UNKNOWN'
                    
                    dynamodb_item = self.convert_to_dynamodb_item(event)
                    batch.put_item(Item=dynamodb_item)
            return True
        except ClientError as e:
            logger.error(f"Error batch saving events: {str(e)}")
            return False
    
    # ========================================================================
    # MATCH OPERATIONS (Updated index names)
    # ========================================================================
    
    def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific match"""
        try:
            response = self.matches_table.get_item(
                Key={'matchId': match_id}
            )
            
            if 'Item' in response:
                return self.convert_from_dynamodb_item(response['Item'])
            return None
            
        except ClientError as e:
            logger.error(f"Error getting match {match_id}: {str(e)}")
            return None
    
    def get_matches_by_event(self, event_code: str, season: int, 
                            tournament_level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get matches for a specific event using EventSeasonIndex"""
        try:
            key_condition = Key('eventCode').eq(event_code) & Key('season').eq(season)
            
            matches = []
            last_evaluated_key = None
            
            while True:
                query_kwargs = {
                    'IndexName': 'EventSeasonIndex',
                    'KeyConditionExpression': key_condition
                }
                
                if last_evaluated_key:
                    query_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.matches_table.query(**query_kwargs)
                
                for item in response.get('Items', []):
                    match = self.convert_from_dynamodb_item(item)
                    
                    # Filter by tournament level if specified
                    if tournament_level is None or match.get('tournamentLevel', '').lower() == tournament_level.lower():
                        matches.append(match)
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
            
            return matches
            
        except ClientError as e:
            logger.error(f"Error getting matches for event {event_code}: {str(e)}")
            return []
    
    def get_match_by_event_and_number(self, event_code: str, match_number: int) -> Optional[Dict[str, Any]]:
        """Get a specific match by event code and match number using EventMatchNumberIndex"""
        try:
            composite_key = f"{event_code}-{match_number}"
            
            response = self.matches_table.query(
                IndexName='EventMatchNumberIndex',
                KeyConditionExpression=Key('eventCode_matchNumber').eq(composite_key),
                Limit=1
            )
            
            if response.get('Items'):
                return self.convert_from_dynamodb_item(response['Items'][0])
            return None
            
        except ClientError as e:
            logger.error(f"Error getting match {match_number} for event {event_code}: {str(e)}")
            return None
    
    def get_matches_by_season(self, season: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get matches for a season using SeasonIndex"""
        try:
            matches = []
            last_evaluated_key = None
            
            while True:
                query_kwargs = {
                    'IndexName': 'SeasonIndex',
                    'KeyConditionExpression': Key('season').eq(season)
                }
                
                if limit is not None:
                    query_kwargs['Limit'] = limit
                
                if last_evaluated_key:
                    query_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.matches_table.query(**query_kwargs)
                
                for item in response.get('Items', []):
                    matches.append(self.convert_from_dynamodb_item(item))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key or (limit and len(matches) >= limit):
                    break
            
            return matches[:limit] if limit else matches
            
        except ClientError as e:
            logger.error(f"Error getting matches for season {season}: {str(e)}")
            return []
    
    def save_match(self, match_data: Dict[str, Any]) -> bool:
        """Save a match to DynamoDB"""
        try:
            # Ensure eventCode is not empty
            if 'eventCode' not in match_data or not match_data['eventCode']:
                match_data['eventCode'] = 'UNKNOWN'
            
            # Create composite key for EventMatchNumberIndex
            if 'matchNumber' in match_data:
                match_data['eventCode_matchNumber'] = f"{match_data['eventCode']}-{match_data['matchNumber']}"
            
            dynamodb_item = self.convert_to_dynamodb_item(match_data)
            self.matches_table.put_item(Item=dynamodb_item)
            return True
        except ClientError as e:
            logger.error(f"Error saving match {match_data.get('matchId')}: {str(e)}")
            return False
    
    def batch_save_matches(self, matches: List[Dict[str, Any]]) -> bool:
        """Save multiple matches efficiently"""
        try:
            with self.matches_table.batch_writer() as batch:
                for match in matches:
                    # Ensure eventCode is not empty
                    if 'eventCode' not in match or not match['eventCode']:
                        match['eventCode'] = 'UNKNOWN'
                    
                    # Create composite key for EventMatchNumberIndex
                    if 'matchNumber' in match:
                        match['eventCode_matchNumber'] = f"{match['eventCode']}-{match['matchNumber']}"
                    
                    dynamodb_item = self.convert_to_dynamodb_item(match)
                    batch.put_item(Item=dynamodb_item)
            return True
        except ClientError as e:
            logger.error(f"Error batch saving matches: {str(e)}")
            return False
    
    # ========================================================================
    # TEAM MATCH EPA OPERATIONS (NEW - Updated for new schema)
    # ========================================================================
    
    def get_team_match_epa(self, team_number: int, match_id: str) -> Optional[Dict[str, Any]]:
        """Get EPA for a specific team in a specific match"""
        try:
            composite_key = f"{team_number}-{match_id}"
            
            response = self.team_match_epa_table.get_item(
                Key={'teamNumber_matchId': composite_key}
            )
            
            if 'Item' in response:
                return self.convert_from_dynamodb_item(response['Item'])
            return None
            
        except ClientError as e:
            logger.error(f"Error getting EPA for team {team_number}, match {match_id}: {str(e)}")
            return None
    
    def get_team_season_epa(self, team_number: int, season: int) -> List[Dict[str, Any]]:
        """Get all EPA records for a team in a season using TeamSeasonIndex"""
        try:
            epa_records = []
            last_evaluated_key = None
            
            while True:
                query_kwargs = {
                    'IndexName': 'TeamSeasonIndex',
                    'KeyConditionExpression': Key('teamNumber').eq(team_number) & Key('season').eq(season)
                }
                
                if last_evaluated_key:
                    query_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.team_match_epa_table.query(**query_kwargs)
                
                for item in response.get('Items', []):
                    epa_records.append(self.convert_from_dynamodb_item(item))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
            
            return epa_records
            
        except ClientError as e:
            logger.error(f"Error getting EPA for team {team_number}, season {season}: {str(e)}")
            return []
    
    def get_team_event_epa(self, team_number: int, event_code: str) -> List[Dict[str, Any]]:
        """Get all EPA records for a team at an event using TeamEventIndex"""
        try:
            epa_records = []
            last_evaluated_key = None
            
            while True:
                query_kwargs = {
                    'IndexName': 'TeamEventIndex',
                    'KeyConditionExpression': Key('teamNumber').eq(team_number) & Key('eventCode').eq(event_code)
                }
                
                if last_evaluated_key:
                    query_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.team_match_epa_table.query(**query_kwargs)
                
                for item in response.get('Items', []):
                    epa_records.append(self.convert_from_dynamodb_item(item))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
            
            return epa_records
            
        except ClientError as e:
            logger.error(f"Error getting EPA for team {team_number}, event {event_code}: {str(e)}")
            return []
    
    def get_match_team_epas(self, event_code: str, match_id: str) -> List[Dict[str, Any]]:
        """Get EPA records for all teams in a match using EventMatchIndex"""
        try:
            epa_records = []
            last_evaluated_key = None
            
            while True:
                query_kwargs = {
                    'IndexName': 'EventMatchIndex',
                    'KeyConditionExpression': Key('eventCode').eq(event_code) & Key('matchId').eq(match_id)
                }
                
                if last_evaluated_key:
                    query_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.team_match_epa_table.query(**query_kwargs)
                
                for item in response.get('Items', []):
                    epa_records.append(self.convert_from_dynamodb_item(item))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
            
            return epa_records
            
        except ClientError as e:
            logger.error(f"Error getting EPA for match {match_id}, event {event_code}: {str(e)}")
            return []
    
    def get_team_epa_chronological(self, team_number: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get team's EPA records in chronological order using TeamSeasonTimeIndex"""
        try:
            epa_records = []
            last_evaluated_key = None
            
            while True:
                query_kwargs = {
                    'IndexName': 'TeamSeasonTimeIndex',
                    'KeyConditionExpression': Key('teamNumber').eq(team_number),
                    'ScanIndexForward': True  # Ascending order by time
                }
                
                if limit is not None:
                    query_kwargs['Limit'] = limit
                
                if last_evaluated_key:
                    query_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.team_match_epa_table.query(**query_kwargs)
                
                for item in response.get('Items', []):
                    epa_records.append(self.convert_from_dynamodb_item(item))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key or (limit and len(epa_records) >= limit):
                    break
            
            return epa_records[:limit] if limit else epa_records
            
        except ClientError as e:
            logger.error(f"Error getting chronological EPA for team {team_number}: {str(e)}")
            return []
    
    def get_latest_team_epa(self, team_number: int) -> Optional[Dict[str, Any]]:
        """Get the most recent EPA record for a team"""
        try:
            response = self.team_match_epa_table.query(
                IndexName='TeamSeasonTimeIndex',
                KeyConditionExpression=Key('teamNumber').eq(team_number),
                ScanIndexForward=False,  # Descending order by time
                Limit=1
            )
            
            if response.get('Items'):
                return self.convert_from_dynamodb_item(response['Items'][0])
            return None
            
        except ClientError as e:
            logger.error(f"Error getting latest EPA for team {team_number}: {str(e)}")
            return None
    
    def save_team_match_epa(self, epa_data: Dict[str, Any]) -> bool:
        """Save EPA calculation for a team in a match"""
        try:
            # Ensure required fields
            if 'teamNumber' not in epa_data or 'matchId' not in epa_data:
                logger.error("teamNumber and matchId are required for EPA records")
                return False
            
            # Create composite primary key
            epa_data['teamNumber_matchId'] = f"{epa_data['teamNumber']}-{epa_data['matchId']}"
            
            # Ensure GSI fields have defaults
            if 'eventCode' not in epa_data or not epa_data['eventCode']:
                epa_data['eventCode'] = 'UNKNOWN'
            if 'actualStartTime' not in epa_data or not epa_data['actualStartTime']:
                epa_data['actualStartTime'] = '1970-01-01T00:00:00'
            
            dynamodb_item = self.convert_to_dynamodb_item(epa_data)
            self.team_match_epa_table.put_item(Item=dynamodb_item)
            return True
            
        except ClientError as e:
            logger.error(f"Error saving EPA for team {epa_data.get('teamNumber')}: {str(e)}")
            return False
    
    def batch_save_team_match_epas(self, epa_records: List[Dict[str, Any]]) -> bool:
        """Save multiple EPA records efficiently"""
        try:
            with self.team_match_epa_table.batch_writer() as batch:
                for epa_data in epa_records:
                    # Ensure required fields
                    if 'teamNumber' not in epa_data or 'matchId' not in epa_data:
                        logger.warning("Skipping EPA record without teamNumber or matchId")
                        continue
                    
                    # Create composite primary key
                    epa_data['teamNumber_matchId'] = f"{epa_data['teamNumber']}-{epa_data['matchId']}"
                    
                    # Ensure GSI fields have defaults
                    if 'eventCode' not in epa_data or not epa_data['eventCode']:
                        epa_data['eventCode'] = 'UNKNOWN'
                    if 'actualStartTime' not in epa_data or not epa_data['actualStartTime']:
                        epa_data['actualStartTime'] = '1970-01-01T00:00:00'
                    
                    dynamodb_item = self.convert_to_dynamodb_item(epa_data)
                    batch.put_item(Item=dynamodb_item)
            return True
        except ClientError as e:
            logger.error(f"Error batch saving EPA records: {str(e)}")
            return False
    
    # ========================================================================
    # CACHE OPERATIONS
    # ========================================================================
    
    def get_cache(self, key: str) -> Optional[Any]:
        """Get value from cache if it exists and hasn't expired"""
        try:
            if key not in self._cache:
                return None
            
            cache_entry = self._cache[key]
            current_time = time.time()
            
            # Check if cache entry has expired
            if current_time > cache_entry['expires_at']:
                # Remove expired entry
                del self._cache[key]
                return None
            
            logger.debug(f"Cache hit for key: {key}")
            return cache_entry['value']
            
        except Exception as e:
            logger.warning(f"Error getting cache for key {key}: {e}")
            return None
    
    def set_cache(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """Set value in cache with TTL (default 1 hour)"""
        try:
            expires_at = time.time() + ttl_seconds
            
            self._cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': time.time()
            }
            
            # Clean up expired entries periodically (every 100 cache sets)
            if len(self._cache) % 100 == 0:
                self._cleanup_expired_cache()
            
            logger.debug(f"Cache set for key: {key}, TTL: {ttl_seconds}s")
            return True
            
        except Exception as e:
            logger.warning(f"Error setting cache for key {key}: {e}")
            return False
    
    def _cleanup_expired_cache(self):
        """Remove expired cache entries"""
        try:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self._cache.items():
                if current_time > entry['expires_at']:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
                
        except Exception as e:
            logger.warning(f"Error cleaning up cache: {e}")
    
    def clear_cache(self):
        """Clear all cache entries"""
        self._cache.clear()
        logger.debug("Cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        current_time = time.time()
        total_entries = len(self._cache)
        expired_entries = sum(1 for entry in self._cache.values() 
                            if current_time > entry['expires_at'])
        
        return {
            'total_entries': total_entries,
            'active_entries': total_entries - expired_entries,
            'expired_entries': expired_entries
        }
    
    # ========================================================================
    # BATCH OPERATIONS
    # ========================================================================
    
    def batch_get_team_epas(self, team_numbers: List[int], season: Optional[int] = None) -> Dict[str, float]:
        """Get latest EPA for multiple teams"""
        team_epas = {}
        
        for team_number in team_numbers:
            if season:
                # Get average EPA for the season
                epa_records = self.get_team_season_epa(team_number, season)
                if epa_records:
                    avg_epa = sum(r.get('averageEPA', 0) for r in epa_records) / len(epa_records)
                    team_epas[str(team_number)] = avg_epa
                else:
                    team_epas[str(team_number)] = 0.0
            else:
                # Get latest EPA
                latest_epa = self.get_latest_team_epa(team_number)
                if latest_epa:
                    team_epas[str(team_number)] = latest_epa.get('averageEPA', 0.0)
                else:
                    team_epas[str(team_number)] = 0.0
        
        return team_epas
    
    # ========================================================================
    # LEGACY COMPATIBILITY (For backward compatibility with old code)
    # ========================================================================
    
    def get_latest_epa(self, team_number: int) -> Optional[Dict[str, Any]]:
        """Legacy method - redirects to get_latest_team_epa"""
        return self.get_latest_team_epa(team_number)
    
    def get_matches_by_team(self, team_number: int, season: int) -> List[Dict[str, Any]]:
        """Legacy method - get matches for a team (uses EPA table now)"""
        epa_records = self.get_team_season_epa(team_number, season)
        # Extract unique matches from EPA records
        matches = []
        seen_match_ids = set()
        
        for epa_record in epa_records:
            match_id = epa_record.get('matchId')
            if match_id and match_id not in seen_match_ids:
                seen_match_ids.add(match_id)
                # Get full match details
                match = self.get_match(match_id)
                if match:
                    matches.append(match)
        
        return matches
    
    def get_teams_by_event(self, season: int, event_code: str) -> List[Dict[str, Any]]:
        """Legacy method - get teams that participated in an event"""
        # Get all matches for the event
        matches = self.get_matches_by_event(event_code, season)
        
        # Extract unique team numbers
        team_numbers = set()
        for match in matches:
            if 'teamNumbers' in match:
                team_numbers.update(match['teamNumbers'])
        
        # Get team details
        teams = []
        for team_number in team_numbers:
            team = self.get_team(team_number, season)
            if team:
                teams.append(team)
        
        return teams

