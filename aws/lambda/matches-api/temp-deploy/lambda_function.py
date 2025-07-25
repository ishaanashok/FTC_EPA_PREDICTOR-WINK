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
# Note: FTC API service requires additional dependencies not in current layer
# from services.ftc_api_service import FTCApiService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MatchesApiService:
    """Matches API service - reads directly from DynamoDB"""
    
    def __init__(self, environment: str = 'dev'):
        self.environment = environment
        self.db_service = DynamoDBService(environment)
        # self.ftc_api_service = FTCApiService()  # Disabled due to missing dependencies
    
    def transform_match_scores(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """Transform DynamoDB score structure to expected format"""
        transformed_match = match.copy()
        
        # Extract red score
        red_score = match.get('redScore', {})
        if isinstance(red_score, dict) and 'totalPoints' in red_score:
            transformed_match['scoreRedFinal'] = int(red_score.get('totalPoints', 0))
        else:
            transformed_match['scoreRedFinal'] = int(red_score) if red_score else 0
        
        # Extract blue score  
        blue_score = match.get('blueScore', {})
        if isinstance(blue_score, dict) and 'totalPoints' in blue_score:
            transformed_match['scoreBlueFinal'] = int(blue_score.get('totalPoints', 0))
        else:
            transformed_match['scoreBlueFinal'] = int(blue_score) if blue_score else 0
        
        # Add score breakdown if available
        if isinstance(red_score, dict):
            transformed_match['redScoreBreakdown'] = {
                'auto': int(red_score.get('autoPoints', 0)),
                'teleop': int(red_score.get('teleopPoints', 0)),
                'endgame': int(red_score.get('endgamePoints', 0)),
                'penalty': int(red_score.get('penaltyPoints', 0)),
                'total': int(red_score.get('totalPoints', 0))
            }
        
        if isinstance(blue_score, dict):
            transformed_match['blueScoreBreakdown'] = {
                'auto': int(blue_score.get('autoPoints', 0)),
                'teleop': int(blue_score.get('teleopPoints', 0)),
                'endgame': int(blue_score.get('endgamePoints', 0)),
                'penalty': int(blue_score.get('penaltyPoints', 0)),
                'total': int(blue_score.get('totalPoints', 0))
            }
        
        return transformed_match
    
    async def enrich_matches_with_teams(self, matches: List[Dict[str, Any]], season: int, event_code: str) -> List[Dict[str, Any]]:
        """Add empty team structure to matches for frontend compatibility"""
        try:
            # For now, just add empty team arrays to prevent frontend errors
            # TODO: Implement team assignment lookup once FTC API dependencies are resolved
            enriched_matches = []
            for match in matches:
                enriched_match = match.copy()
                # Add empty team structure for frontend compatibility
                enriched_match['teams'] = []
                enriched_match['redTeams'] = []
                enriched_match['blueTeams'] = []
                if 'allTeams' not in enriched_match:
                    enriched_match['allTeams'] = []
                enriched_matches.append(enriched_match)
            
            logger.info(f"Added empty team structure to {len(enriched_matches)} matches")
            return enriched_matches
            
        except Exception as e:
            logger.error(f"Error adding team structure to matches: {str(e)}")
            # Return original matches if enrichment fails
            return matches
    
    async def get_matches(self, season: int, event_code: Optional[str] = None,
                         team_number: Optional[int] = None, 
                         tournament_level: Optional[str] = None,
                         limit: int = 100) -> Dict[str, Any]:
        """Get matches data from DynamoDB"""
        try:
            if event_code:
                # Get matches for specific event
                matches = await self.db_service.get_matches_by_event(
                    season, event_code, tournament_level
                )
                
                # Transform score structures
                transformed_matches = [self.transform_match_scores(match) for match in matches]
                
                # Enrich with team assignment data
                enriched_matches = await self.enrich_matches_with_teams(transformed_matches, season, event_code)
                
                return {
                    "success": True,
                    "matches": enriched_matches,
                    "total": len(enriched_matches),
                    "eventCode": event_code,
                    "tournamentLevel": tournament_level
                }
            
            elif team_number:
                # Get matches for specific team
                matches = await self.db_service.get_matches_by_team(team_number, season)
                
                # Filter by tournament level if specified
                if tournament_level:
                    matches = [m for m in matches if m.get('tournamentLevel', '').lower() == tournament_level.lower()]
                
                # Transform score structures
                transformed_matches = [self.transform_match_scores(match) for match in matches]
                
                return {
                    "success": True,
                    "matches": transformed_matches,
                    "total": len(transformed_matches),
                    "teamNumber": team_number,
                    "tournamentLevel": tournament_level
                }
            
            else:
                return {
                    "success": False,
                    "error": "Either eventCode or teamNumber must be specified",
                    "matches": [],
                    "total": 0
                }
                
        except Exception as e:
            logger.error(f"Error getting matches: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "matches": [],
                "total": 0
            }
    
    async def get_match_details(self, match_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific match"""
        try:
            # Get match basic info
            match = await self.db_service.get_match(match_id)
            
            if not match:
                return {
                    "success": False,
                    "error": f"Match {match_id} not found",
                    "match": None
                }
            
            # Transform score structure
            transformed_match = self.transform_match_scores(match)
            
            # Get EPA data for teams in this match if available
            team_epas = {}
            all_teams = match.get('allTeams', [])
            
            if all_teams:
                team_epas = await self.db_service.batch_get_team_epas(all_teams)
            
            return {
                "success": True,
                "match": transformed_match,
                "teamEPAs": team_epas
            }
            
        except Exception as e:
            logger.error(f"Error getting match details for {match_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "match": None
            }
    
    async def get_match_predictions(self, match_id: str) -> Dict[str, Any]:
        """Get predictions for a specific match"""
        try:
            # Get match details
            match = await self.db_service.get_match(match_id)
            
            if not match:
                return {
                    "success": False,
                    "error": f"Match {match_id} not found",
                    "predictions": None
                }
            
            # Get EPA data for teams
            all_teams = match.get('allTeams', [])
            team_epas = await self.db_service.batch_get_team_epas(all_teams)
            
            # Simple prediction based on EPA
            red_teams = match.get('redTeams', [])
            blue_teams = match.get('blueTeams', [])
            
            red_epa_sum = sum(team_epas.get(str(team), 0.0) for team in red_teams)
            blue_epa_sum = sum(team_epas.get(str(team), 0.0) for team in blue_teams)
            
            total_epa = red_epa_sum + blue_epa_sum
            
            if total_epa > 0:
                red_win_prob = red_epa_sum / total_epa
                blue_win_prob = blue_epa_sum / total_epa
            else:
                red_win_prob = 0.5
                blue_win_prob = 0.5
            
            return {
                "success": True,
                "match": match,
                "predictions": {
                    "redWinProbability": red_win_prob,
                    "blueWinProbability": blue_win_prob,
                    "redEPA": red_epa_sum,
                    "blueEPA": blue_epa_sum,
                    "teamEPAs": team_epas
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting match predictions for {match_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "predictions": None
            }


async def lambda_handler(event, context):
    """Lambda handler for matches API"""
    
    # Initialize service
    api_service = MatchesApiService(
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
            # Check if specific match requested
            match_id = path_parameters.get('matchId')
            if match_id:
                # Check if predictions requested
                if 'predictions' in event.get('path', ''):
                    result = await api_service.get_match_predictions(match_id)
                else:
                    result = await api_service.get_match_details(match_id)
            else:
                # Get matches with filters
                # Check path parameters first, then query parameters
                event_code = path_parameters.get('eventCode') or query_parameters.get('eventCode')
                season_param = path_parameters.get('season')
                if season_param:
                    season = int(season_param.split('-')[0])  # Handle "2024-25" format
                
                team_number_str = query_parameters.get('teamNumber')
                team_number = int(team_number_str) if team_number_str else None
                tournament_level = query_parameters.get('tournamentLevel')
                limit = int(query_parameters.get('limit', 100))
                
                result = await api_service.get_matches(
                    season=season,
                    event_code=event_code,
                    team_number=team_number,
                    tournament_level=tournament_level,
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