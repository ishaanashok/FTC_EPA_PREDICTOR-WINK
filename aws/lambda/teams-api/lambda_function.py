import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal

# AWS SDK
import boto3
from botocore.exceptions import ClientError

# Local imports
from services.dynamodb_service import DynamoDBService

# Custom JSON encoder for Decimal types
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TeamsApiService:
    """Teams API service - reads directly from DynamoDB"""
    
    def __init__(self, environment: str = 'dev'):
        self.environment = environment
        self.db_service = DynamoDBService(environment)
    
    def get_teams(self, season: int, team_number: Optional[int] = None, 
                       event_code: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """Get teams data from DynamoDB"""
        try:
            if team_number:
                # Get specific team
                team = self.db_service.get_team(team_number, season)
                if team:
                    return {
                        "success": True,
                        "teams": [team],
                        "total": 1
                    }
                else:
                    return {
                        "success": True,
                        "teams": [],
                        "total": 0,
                        "message": f"Team {team_number} not found for season {season}"
                    }
            
            elif event_code:
                # Get teams for specific event
                try:
                    teams = self.db_service.get_teams_by_event(season, event_code)
                except Exception as e:
                    logger.error(f"Error getting teams for event {event_code}: {str(e)}")
                    logger.error(f"Exception type: {type(e).__name__}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    teams = []
                
                return {
                    "success": True,
                    "teams": teams,
                    "total": len(teams),
                    "eventCode": event_code
                }
            
            else:
                # Get all teams for season
                teams = self.db_service.get_teams_by_season(season, limit)
                return {
                    "success": True,
                    "teams": teams,
                    "total": len(teams),
                    "limit": limit
                }
                
        except Exception as e:
            logger.error(f"Error getting teams: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "teams": [],
                "total": 0
            }
    
    def get_team_details(self, team_number: int, season: int) -> Dict[str, Any]:
        """Get detailed information about a specific team"""
        try:
            # Get team basic info (now includes historicEPA embedded)
            team = self.db_service.get_team(team_number, season)
            
            if not team:
                return {
                    "success": False,
                    "error": f"Team {team_number} not found for season {season}",
                    "team": None
                }
            
            # Get team's matches (optional - can be heavy)
            matches = self.db_service.get_matches_by_team(team_number, season)
            
            # Extract historic EPA from team data (NEW - embedded in team record)
            historic_epa = team.get('historicEPA')
            
            # Get per-match EPA for this season (optional - for detailed analysis)
            season_epa_records = self.db_service.get_team_season_epa(team_number, season)
            
            # Calculate current season EPA summary from per-match records
            current_season_epa = None
            if season_epa_records:
                latest_record = season_epa_records[-1]  # Last match has latest averageEPA
                current_season_epa = {
                    "averageEPA": latest_record.get('averageEPA'),
                    "matchCount": latest_record.get('matchCount'),
                    "latestMatchEPA": latest_record.get('matchEPA'),
                    "cumulativeEPA": latest_record.get('cumulativeEPA')
                }
            
            return {
                "success": True,
                "team": team,
                "matches": matches,
                "historicEPA": historic_epa,  # Pre-calculated weighted EPA across seasons
                "currentSeasonEPA": current_season_epa,  # Latest EPA for current season
                "totalMatches": len(matches)
            }
            
        except Exception as e:
            logger.error(f"Error getting team details for {team_number}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "team": None
            }


def lambda_handler(event, context):
    """Lambda handler for teams API"""
    
    # Initialize service
    api_service = TeamsApiService(
        environment=os.environ.get('ENVIRONMENT', 'dev')
    )
    
    try:
        # Extract parameters from event
        http_method = event.get('httpMethod', 'GET')
        path_parameters = event.get('pathParameters') or {}
        query_parameters = event.get('queryStringParameters') or {}
        
        # Default season
        season = int(query_parameters.get('season', 2024))
        
        # Handle different endpoints
        if http_method == 'GET':
            # Check if specific team requested
            team_number = path_parameters.get('teamNumber')
            if team_number:
                team_number = int(team_number)
                result = api_service.get_team_details(team_number, season)
            else:
                # Get teams with optional filters
                team_number_query = query_parameters.get('teamNumber')
                event_code = query_parameters.get('eventCode')
                limit = int(query_parameters.get('limit', 100))
                
                team_number = None
                if team_number_query:
                    team_number = int(team_number_query)
                
                result = api_service.get_teams(
                    season=season,
                    team_number=team_number,
                    event_code=event_code,
                    limit=limit
                )
        else:
            return {
                'statusCode': 405,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Method not allowed',
                    'allowedMethods': ['GET']
                }, cls=DecimalEncoder)
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result, cls=DecimalEncoder)
        }
        
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': str(e),
                'success': False
            }, cls=DecimalEncoder)
        }


def handler(event, context):
    """Main handler for Lambda function"""
    return lambda_handler(event, context) 