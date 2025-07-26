import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

# AWS SDK
import boto3
from botocore.exceptions import ClientError

# Local imports
from services.dynamodb_service import DynamoDBService

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
                teams = self.db_service.get_teams_by_event(season, event_code)
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
            # Get team basic info
            team = self.db_service.get_team(team_number, season)
            
            if not team:
                return {
                    "success": False,
                    "error": f"Team {team_number} not found for season {season}",
                    "team": None
                }
            
            # Get team's matches
            matches = self.db_service.get_matches_by_team(team_number, season)
            
            # Get team's EPA if available
            epa_data = self.db_service.get_latest_epa(team_number)
            
            return {
                "success": True,
                "team": team,
                "matches": matches,
                "epa": epa_data,
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
                })
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
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
            })
        }


def handler(event, context):
    """Main handler for Lambda function"""
    return lambda_handler(event, context) 