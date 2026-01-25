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

class EventsApiService:
    """Events API service - reads directly from DynamoDB"""
    
    def __init__(self, environment: str = 'dev'):
        self.environment = environment
        self.db_service = DynamoDBService(environment)
    
    def get_events(self, season: int, event_code: Optional[str] = None, 
                        team_number: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """Get events data from DynamoDB"""
        try:
            if event_code:
                # Get specific event
                event = self.db_service.get_event(event_code, season)
                if event:
                    return {
                        "success": True,
                        "events": [event],
                        "total": 1
                    }
                else:
                    return {
                        "success": True,
                        "events": [],
                        "total": 0,
                        "message": f"Event {event_code} not found for season {season}"
                    }
            
            elif team_number:
                # Get events for specific team
                events = self.db_service.get_events_by_team(season, team_number)
                return {
                    "success": True,
                    "events": events,
                    "total": len(events),
                    "teamNumber": team_number
                }
            
            else:
                # Get all events for season
                events = self.db_service.get_events_by_season(season, limit)
                response = {
                    "success": True,
                    "events": events,
                    "total": len(events)
                }
                if limit is not None:
                    response["limit"] = limit
                return response
                
        except Exception as e:
            logger.error(f"Error getting events: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "events": [],
                "total": 0
            }
    
    def get_event_details(self, event_code: str, season: int) -> Dict[str, Any]:
        """Get detailed information about a specific event"""
        try:
            # Get event basic info
            event = self.db_service.get_event(event_code, season)
            
            if not event:
                return {
                    "success": False,
                    "error": f"Event {event_code} not found for season {season}",
                    "event": None
                }
            
            # Try to get matches and teams, but don't fail if they're not available
            matches = []
            teams = []
            
            try:
                matches = self.db_service.get_matches_by_event(event_code, season)
            except Exception as e:
                logger.warning(f"Could not load matches for event {event_code}: {str(e)}")
            
            event_teams = event.get('teams') if event else None
            if isinstance(event_teams, list) and event_teams:
                teams = event_teams
            else:
                try:
                    teams = self.db_service.get_teams_by_event(season, event_code)
                except Exception as e:
                    logger.warning(f"Could not load teams for event {event_code}: {str(e)}")

            # Fallback: build teams from matches if teams list is empty
            if not teams and matches:
                team_numbers = set()
                for match in matches:
                    match_team_numbers = match.get('teamNumbers')
                    if match_team_numbers:
                        if isinstance(match_team_numbers, str):
                            split_numbers = [tn.strip() for tn in match_team_numbers.split(',') if tn.strip()]
                            team_numbers.update(int(tn) for tn in split_numbers)
                        else:
                            team_numbers.update(int(tn) for tn in match_team_numbers)

                    all_teams = match.get('allTeams') or []
                    team_numbers.update(int(tn) for tn in all_teams)

                    red_teams = match.get('redTeams') or []
                    blue_teams = match.get('blueTeams') or []
                    team_numbers.update(int(tn) for tn in red_teams)
                    team_numbers.update(int(tn) for tn in blue_teams)

                    team_entries = match.get('teams') or []
                    for team_entry in team_entries:
                        if isinstance(team_entry, dict):
                            team_number = team_entry.get('teamNumber')
                            if team_number is not None:
                                team_numbers.add(int(team_number))
                        elif team_entry is not None:
                            team_numbers.add(int(team_entry))

                for team_number in team_numbers:
                    team = self.db_service.get_team(int(team_number), season)
                    if team:
                        teams.append(team)
            
            # Separate matches by tournament level
            # Handle various formats: 'qual', 'QUAL', 'qualification', 'QUALIFICATION', etc.
            qual_matches = [m for m in matches if 'qual' in m.get('tournamentLevel', '').lower()]
            playoff_matches = [m for m in matches if 'playoff' in m.get('tournamentLevel', '').lower()]
            
            return {
                "success": True,
                "event": event,
                "matches": {
                    "qualification": qual_matches,
                    "playoff": playoff_matches,
                    "total": len(matches)
                },
                "teams": teams,
                "totalTeams": len(teams)
            }
            
        except Exception as e:
            logger.error(f"Error getting event details for {event_code}: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "event": None
            }


def lambda_handler(event, context):
    """Lambda handler for events API"""
    
    # Initialize service
    api_service = EventsApiService(
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
            # Check if specific event requested
            event_code = path_parameters.get('eventCode')
            if event_code:
                result = api_service.get_event_details(event_code, season)
            else:
                # Get events with optional filters
                event_code_query = query_parameters.get('eventCode')
                team_number_query = query_parameters.get('teamNumber')
                team_number = int(team_number_query) if team_number_query else None
                limit_param = query_parameters.get('limit')
                limit = int(limit_param) if limit_param else None
                
                result = api_service.get_events(
                    season=season,
                    event_code=event_code_query,
                    team_number=team_number,
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
            })
        }


# Main handler is now synchronous - no wrapper needed
handler = lambda_handler 