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
    """Service layer for DynamoDB operations for Matches API"""
    
    def __init__(self, environment: str = 'stage'):
        self.dynamodb = boto3.resource('dynamodb')
        self.environment = environment
        
        # Initialize tables
        self.teams_table = self.dynamodb.Table(f'FTC_Teams_{environment}')
        self.events_table = self.dynamodb.Table(f'FTC_Events_{environment}')
        self.matches_table = self.dynamodb.Table(f'FTC_Matches_{environment}')
        self.epa_table = self.dynamodb.Table(f'FTC_EPA_{environment}')
    
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
        
        return convert_value(item)
    
    async def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific match by ID"""
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
                                 tournament_level: Optional[str] = None,
                                 limit: int = 100) -> List[Dict[str, Any]]:
        """Get matches for a specific event"""
        try:
            # Build key condition
            key_condition = Key('season').eq(season) & Key('eventCode').eq(event_code)
            
            query_params = {
                'IndexName': 'EventIndex',
                'KeyConditionExpression': key_condition,
                'Limit': limit
            }
            
            # Add tournament level filter if specified
            if tournament_level:
                query_params['FilterExpression'] = Attr('tournamentLevel').eq(tournament_level)
            
            response = self.matches_table.query(**query_params)
            
            matches = []
            for item in response.get('Items', []):
                matches.append(self.convert_from_dynamodb_item(item))
            
            return matches
            
        except ClientError as e:
            logger.error(f"Error getting matches for event {event_code}: {str(e)}")
            return []
    
    async def get_matches_by_team(self, team_number: int, season: Optional[int] = None,
                                limit: int = 100) -> List[Dict[str, Any]]:
        """Get matches for a specific team"""
        try:
            if season:
                # Query using TeamIndex with season
                key_condition = Key('teamNumber').eq(team_number) & Key('season').eq(season)
                index_name = 'TeamIndex'
            else:
                # Query all seasons for the team
                key_condition = Key('teamNumber').eq(team_number)
                index_name = 'TeamIndex'
            
            # Only get team records (denormalized records)
            response = self.matches_table.query(
                IndexName=index_name,
                KeyConditionExpression=key_condition,
                FilterExpression=Attr('isTeamRecord').eq(True),
                Limit=limit
            )
            
            matches = []
            for item in response.get('Items', []):
                matches.append(self.convert_from_dynamodb_item(item))
            
            return matches
            
        except ClientError as e:
            logger.error(f"Error getting matches for team {team_number}: {str(e)}")
            return []
    
    async def batch_get_team_epas(self, team_numbers: List[int]) -> Dict[str, float]:
        """Get latest EPA values for multiple teams"""
        team_epas = {}
        
        try:
            for team_number in team_numbers:
                # Convert to Decimal for DynamoDB query
                team_decimal = Decimal(str(int(team_number)))
                
                # Get latest EPA for each team
                response = self.epa_table.query(
                    KeyConditionExpression=Key('teamNumber').eq(team_decimal),
                    ScanIndexForward=False,  # Get most recent first
                    Limit=1
                )
                
                items = response.get('Items', [])
                if items:
                    epa_record = self.convert_from_dynamodb_item(items[0])
                    # Get EPA value from various possible field names
                    epa_value = (epa_record.get('currentSeasonEPA') or 
                               epa_record.get('historicalEPA') or
                               epa_record.get('epaValue') or
                               epa_record.get('epa', 0.0))
                    team_epas[str(team_number)] = float(epa_value)
                else:
                    team_epas[str(team_number)] = 0.0
            
            return team_epas
            
        except Exception as e:
            logger.error(f"Error in batch EPA retrieval: {str(e)}")
            return {str(team): 0.0 for team in team_numbers}
