import boto3
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class DynamoDBService:
    """Service layer for DynamoDB operations"""
    
    def __init__(self, environment: str = 'dev'):
        self.dynamodb = boto3.resource('dynamodb')
        self.environment = environment
        
        # Initialize tables
        # Ensure self.dynamodb is a boto3 DynamoDB resource, which has the Table attribute
        self.teams_table = self.dynamodb.Table(f'FTC_Teams_{environment}')
        self.events_table = self.dynamodb.Table(f'FTC_Events_{environment}')
        self.matches_table = self.dynamodb.Table(f'FTC_Matches_{environment}')
        self.epa_table = self.dynamodb.Table(f'FTC_EPA_{environment}')
        # Cache table removed - no longer using caching layer
    
    def convert_to_dynamodb_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert item to DynamoDB compatible format"""
        def convert_value(value):
            if isinstance(value, float):
                return Decimal(str(value))
            elif isinstance(value, dict):
                return {k: convert_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [convert_value(v) for v in value]
            elif isinstance(value, datetime):
                return value.isoformat()
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
    
    # Team operations
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
    
    def get_teams_by_season(self, season: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all teams for a season"""
        try:
            response = self.teams_table.query(
                IndexName='SeasonIndex',
                KeyConditionExpression=Key('season').eq(season),
                Limit=limit
            )
            
            teams = []
            for item in response.get('Items', []):
                teams.append(self.convert_from_dynamodb_item(item))
            
            return teams
            
        except ClientError as e:
            logger.error(f"Error getting teams for season {season}: {str(e)}")
            return []
    
    def get_teams_by_event(self, season: int, event_code: str) -> List[Dict[str, Any]]:
        """Get teams participating in a specific event"""
        try:
            # First try to get teams from event's teamNumbers field
            teams = self.get_teams_by_event_from_roster(season, event_code)
            if teams:
                return teams
            
            # Fallback to old method (get from matches)
            matches = self.get_matches_by_event(season, event_code)
            
            # Extract unique team numbers
            team_numbers = set()
            for match in matches:
                team_numbers.update(match.get('allTeams', []))
            
            # Get team details
            teams = []
            for team_number in team_numbers:
                team = self.get_team(team_number, season)
                if team:
                    teams.append(team)
            
            return teams
            
        except Exception as e:
            logger.error(f"Error getting teams for event {event_code}: {str(e)}")
            return []
    
    def get_teams_by_event_from_roster(self, season: int, event_code: str) -> List[Dict[str, Any]]:
        """Get teams participating in a specific event from event's team roster"""
        try:
            # Get the event to get team numbers
            event = self.get_event(event_code, season)
            
            if not event or not event.get('teamNumbers'):
                logger.info(f"No team numbers found in event roster for {event_code} in season {season}")
                return []
            
            # Parse team numbers from comma-separated string
            team_numbers_str = event.get('teamNumbers', '')
            if not team_numbers_str:
                return []
                
            team_numbers = [int(num.strip()) for num in team_numbers_str.split(',') if num.strip()]
            logger.info(f"Found {len(team_numbers)} team numbers in event {event_code} roster")
            
            # Get team details
            teams = []
            for team_number in team_numbers:
                team = self.get_team(team_number, season)
                if team:
                    teams.append(team)
                else:
                    logger.warning(f"Team {team_number} not found in teams table for season {season}")
            
            logger.info(f"Successfully retrieved {len(teams)} team details for event {event_code}")
            return teams
            
        except Exception as e:
            logger.error(f"Error getting teams from event roster for {event_code}: {str(e)}")
            return []
    
    # Event operations
    def get_event(self, event_code: str, season: int) -> Optional[Dict[str, Any]]:
        """Get a specific event"""
        try:
            response = self.events_table.get_item(
                Key={'eventCode': event_code, 'season': season}
            )
            
            if 'Item' in response:
                return self.convert_from_dynamodb_item(response['Item'])
            return None
            
        except ClientError as e:
            logger.error(f"Error getting event {event_code} for season {season}: {str(e)}")
            return None
    
    def get_events_by_season(self, season: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all events for a season"""
        try:
            query_kwargs = {
                'IndexName': 'SeasonIndex',
                'KeyConditionExpression': Key('season').eq(season)
            }
            
            if limit is not None:
                query_kwargs['Limit'] = limit
            
            response = self.events_table.query(**query_kwargs)
            
            events = []
            for item in response.get('Items', []):
                events.append(self.convert_from_dynamodb_item(item))
            
            return events
            
        except ClientError as e:
            logger.error(f"Error getting events for season {season}: {str(e)}")
            return []
    
    # Match operations
    async def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:
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
    
    async def get_matches_by_event(self, season: int, event_code: str, 
                                  tournament_level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get matches for a specific event"""
        try:
            # Use GSI to query by event
            key_condition = Key('eventCode').eq(event_code) & Key('season').eq(season)
            
            response = self.matches_table.query(
                IndexName='EventIndex',
                KeyConditionExpression=key_condition
            )
            
            matches = []
            for item in response.get('Items', []):
                match = self.convert_from_dynamodb_item(item)
                
                # Filter by tournament level if specified
                if tournament_level is None or match.get('tournamentLevel', '').lower() == tournament_level.lower():
                    matches.append(match)
            
            return matches
            
        except ClientError as e:
            logger.error(f"Error getting matches for event {event_code}: {str(e)}")
            return []
    
    async def get_matches_by_team(self, team_number: int, season: int) -> List[Dict[str, Any]]:
        """Get matches for a specific team"""
        try:
            response = self.matches_table.query(
                IndexName='TeamIndex',
                KeyConditionExpression=Key('teamNumber').eq(team_number) & Key('season').eq(season)
            )
            
            matches = []
            for item in response.get('Items', []):
                match = self.convert_from_dynamodb_item(item)
                # Verify team is actually in the match
                if team_number in match.get('allTeams', []):
                    matches.append(match)
            
            return matches
            
        except ClientError as e:
            logger.error(f"Error getting matches for team {team_number}: {str(e)}")
            return []
    
    # EPA operations
    async def get_latest_epa(self, team_number: int) -> Optional[Dict[str, Any]]:
        """Get the latest EPA calculation for a team"""
        try:
            response = self.epa_table.query(
                KeyConditionExpression=Key('teamNumber').eq(team_number),
                ScanIndexForward=False,  # Sort by calculationDate descending
                Limit=1
            )
            
            if response.get('Items'):
                return self.convert_from_dynamodb_item(response['Items'][0])
            return None
            
        except ClientError as e:
            logger.error(f"Error getting latest EPA for team {team_number}: {str(e)}")
            return None
    
    async def get_historical_epa(self, team_number: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get historical EPA calculations for a team"""
        try:
            response = self.epa_table.query(
                KeyConditionExpression=Key('teamNumber').eq(team_number),
                ScanIndexForward=False,  # Sort by calculationDate descending
                Limit=limit
            )
            
            epa_history = []
            for item in response.get('Items', []):
                epa_history.append(self.convert_from_dynamodb_item(item))
            
            return epa_history
            
        except ClientError as e:
            logger.error(f"Error getting historical EPA for team {team_number}: {str(e)}")
            return []
    
    async def save_epa_calculation(self, team_number: int, epa_data: Dict[str, Any]) -> bool:
        """Save EPA calculation for a team"""
        try:
            # Set the latest flag for this team to False for existing records
            existing_epas = await self.get_historical_epa(team_number, limit=50)
            
            # Update existing records to not be latest
            for epa in existing_epas:
                if epa.get('isLatest', False):
                    update_item = {
                        'teamNumber': team_number,
                        'calculationDate': epa['calculationDate'],
                        'isLatest': False
                    }
                    self.epa_table.put_item(Item=self.convert_to_dynamodb_item(update_item))
            
            # Add new EPA calculation
            epa_item = {
                'teamNumber': team_number,
                'calculationDate': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                'isLatest': True,
                'calculatedAt': datetime.now(timezone.utc).isoformat(),
                **epa_data
            }
            
            self.epa_table.put_item(Item=self.convert_to_dynamodb_item(epa_item))
            return True
            
        except ClientError as e:
            logger.error(f"Error saving EPA calculation for team {team_number}: {str(e)}")
            return False
    
    # Cache operations removed - no longer using caching layer
    
    # Batch operations
    async def batch_get_team_epas(self, team_numbers: List[int]) -> Dict[str, float]:
        """Get EPAs for multiple teams"""
        team_epas = {}
        
        for team_number in team_numbers:
            epa_data = await self.get_latest_epa(team_number)
            if epa_data:
                team_epas[str(team_number)] = epa_data.get('historicalEPA', 0.0)
            else:
                team_epas[str(team_number)] = 0.0
        
        return team_epas
    
    def batch_save_matches(self, matches: List[Dict[str, Any]]) -> bool:
        """Save multiple matches efficiently (expects DynamoDB items)"""
        try:
            with self.matches_table.batch_writer() as batch:
                for match in matches:
                    # Assumes match is already a DynamoDB item
                    batch.put_item(Item=match)
            
            return True
            
        except ClientError as e:
            logger.error(f"Error batch saving matches: {str(e)}")
            return False
    
    def batch_save_teams(self, teams: List[Dict[str, Any]]) -> bool:
        """Save multiple teams efficiently"""
        try:
            with self.teams_table.batch_writer() as batch:
                for team in teams:
                    dynamodb_item = self.convert_to_dynamodb_item(team)
                    batch.put_item(Item=dynamodb_item)
            
            return True
            
        except ClientError as e:
            logger.error(f"Error batch saving teams: {str(e)}")
            return False
    
    def batch_save_events(self, events: List[Dict[str, Any]]) -> bool:
        """Save multiple events efficiently"""
        try:
            with self.events_table.batch_writer() as batch:
                for event in events:
                    dynamodb_item = self.convert_to_dynamodb_item(event)
                    batch.put_item(Item=dynamodb_item)
            
            return True
            
        except ClientError as e:
            logger.error(f"Error batch saving events: {str(e)}")
            return False 