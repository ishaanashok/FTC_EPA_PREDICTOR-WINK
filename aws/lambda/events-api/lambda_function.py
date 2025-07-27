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

class EventsApiService:
    """Events API service - reads directly from DynamoDB"""
    
    def __init__(self, environment: str = 'dev'):
        self.environment = environment
        self.db_service = DynamoDBService(environment)
    
    async def get_events(self, season: int, event_code: Optional[str] = None, 
                        team_number: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """Get events data from DynamoDB"""
        try:
            if event_code:
                # Get specific event
                event = await self.db_service.get_event(event_code, season)
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
                events = await self.db_service.get_events_by_team(season, team_number)
                return {
                    "success": True,
                    "events": events,
                    "total": len(events),
                    "teamNumber": team_number
                }
            
            else:
                # Get all events for season
                events = await self.db_service.get_events_by_season(season, limit)
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
    
    async def get_event_details(self, event_code: str, season: int) -> Dict[str, Any]:
        """Get detailed information about a specific event"""
        try:
            # Get event basic info
            event = await self.db_service.get_event(event_code, season)
            
            if not event:
                return {
                    "success": False,
                    "error": f"Event {event_code} not found for season {season}",
                    "event": None
                }
            
            # Get event's matches
            matches = await self.db_service.get_matches_by_event(season, event_code)
            
            # Get event's teams
            teams = await self.db_service.get_teams_by_event(season, event_code)
            
            # Separate matches by tournament level
            qual_matches = [m for m in matches if m.get('tournamentLevel', '').lower() == 'qual']
            playoff_matches = [m for m in matches if m.get('tournamentLevel', '').lower() == 'playoff']
            
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
            return {
                "success": False,
                "error": str(e),
                "event": None
            }


async def lambda_handler(event, context):
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
                result = await api_service.get_event_details(event_code, season)
            else:
                # Get events with optional filters
                event_code_query = query_parameters.get('eventCode')
                team_number_query = query_parameters.get('teamNumber')
                team_number = int(team_number_query) if team_number_query else None
                limit_param = query_parameters.get('limit')
                limit = int(limit_param) if limit_param else None
                
                result = await api_service.get_events(
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
    """Synchronous wrapper for async lambda handler"""
    import asyncio
    try:
        # Try to get the existing event loop
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No event loop in current thread, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        # Use run_until_complete instead of asyncio.run for Lambda compatibility
        return loop.run_until_complete(lambda_handler(event, context))
    finally:
        # Clean up any remaining tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True)) 