import json
import logging
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
import itertools

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

class AllianceMatchmakerService:
    """Alliance Matchmaker service - reads directly from DynamoDB"""
    
    def __init__(self, environment: str = 'dev'):
        self.environment = environment
        self.db_service = DynamoDBService(environment)
    
    async def get_team_compatibility(self, team1: int, team2: int, season: int) -> Dict[str, Any]:
        """Calculate compatibility between two teams"""
        try:
            # Get EPA data for both teams
            team_epas = await self.db_service.batch_get_team_epas([team1, team2])
            
            team1_epa = team_epas.get(str(team1), 0.0)
            team2_epa = team_epas.get(str(team2), 0.0)
            
            # Simple compatibility calculation
            combined_epa = team1_epa + team2_epa
            
            # Basic complementary scoring (this would be more complex in a real system)
            compatibility_score = min(team1_epa, team2_epa) / max(team1_epa, team2_epa) if max(team1_epa, team2_epa) > 0 else 0
            
            return {
                "success": True,
                "team1": team1,
                "team2": team2,
                "team1EPA": team1_epa,
                "team2EPA": team2_epa,
                "combinedEPA": combined_epa,
                "compatibilityScore": compatibility_score
            }
                
        except Exception as e:
            logger.error(f"Error calculating compatibility between teams {team1} and {team2}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "team1": team1,
                "team2": team2
            }
    
    async def find_best_alliance_partners(self, team_number: int, season: int, 
                                        event_code: Optional[str] = None, 
                                        limit: int = 10) -> Dict[str, Any]:
        """Find the best alliance partners for a given team"""
        try:
            # Get available teams (either from event or season)
            if event_code:
                available_teams = await self.db_service.get_teams_by_event(season, event_code)
            else:
                available_teams = await self.db_service.get_teams_by_season(season, limit=200)
            
            # Filter out the requesting team
            partner_teams = [t for t in available_teams if t.get('teamNumber') != team_number]
            
            if not partner_teams:
                return {
                    "success": True,
                    "team": team_number,
                    "partners": [],
                    "message": "No potential partners found"
                }
            
            # Get EPA data for all teams
            all_team_numbers = [team_number] + [t.get('teamNumber') for t in partner_teams]
            team_epas = await self.db_service.batch_get_team_epas(all_team_numbers)
            
            requesting_team_epa = team_epas.get(str(team_number), 0.0)
            
            # Calculate compatibility with each potential partner
            partner_compatibility = []
            for partner_team in partner_teams:
                partner_number = partner_team.get('teamNumber')
                partner_epa = team_epas.get(str(partner_number), 0.0)
                
                combined_epa = requesting_team_epa + partner_epa
                compatibility_score = min(requesting_team_epa, partner_epa) / max(requesting_team_epa, partner_epa) if max(requesting_team_epa, partner_epa) > 0 else 0
                
                partner_compatibility.append({
                    "teamNumber": partner_number,
                    "teamName": partner_team.get('teamName', ''),
                    "epa": partner_epa,
                    "combinedEPA": combined_epa,
                    "compatibilityScore": compatibility_score
                })
            
            # Sort by combined EPA (prioritizing strong alliances)
            partner_compatibility.sort(key=lambda x: x["combinedEPA"], reverse=True)
            
            # Limit results
            best_partners = partner_compatibility[:limit]
            
            return {
                "success": True,
                "team": team_number,
                "teamEPA": requesting_team_epa,
                "partners": best_partners,
                "total": len(best_partners),
                "eventCode": event_code
            }
                
        except Exception as e:
            logger.error(f"Error finding alliance partners for team {team_number}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "team": team_number,
                "partners": []
            }
    
    async def suggest_alliance_combinations(self, team_numbers: List[int], season: int) -> Dict[str, Any]:
        """Suggest best alliance combinations from a list of teams"""
        try:
            if len(team_numbers) < 2:
                return {
                    "success": False,
                    "error": "At least 2 teams required for alliance combinations",
                    "combinations": []
                }
            
            # Get EPA data for all teams
            team_epas = await self.db_service.batch_get_team_epas(team_numbers)
            
            # Generate all possible 2-team combinations
            combinations = []
            for team1, team2 in itertools.combinations(team_numbers, 2):
                team1_epa = team_epas.get(str(team1), 0.0)
                team2_epa = team_epas.get(str(team2), 0.0)
                
                combined_epa = team1_epa + team2_epa
                compatibility_score = min(team1_epa, team2_epa) / max(team1_epa, team2_epa) if max(team1_epa, team2_epa) > 0 else 0
                
                combinations.append({
                    "team1": team1,
                    "team2": team2,
                    "team1EPA": team1_epa,
                    "team2EPA": team2_epa,
                    "combinedEPA": combined_epa,
                    "compatibilityScore": compatibility_score
                })
            
            # Sort by combined EPA
            combinations.sort(key=lambda x: x["combinedEPA"], reverse=True)
            
            return {
                "success": True,
                "combinations": combinations,
                "total": len(combinations)
            }
                
        except Exception as e:
            logger.error(f"Error suggesting alliance combinations: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "combinations": []
            }
    
    async def analyze_event_alliances(self, event_code: str, season: int) -> Dict[str, Any]:
        """Analyze potential alliances for an entire event"""
        try:
            # Get all teams in the event
            event_teams = await self.db_service.get_teams_by_event(season, event_code)
            
            if len(event_teams) < 4:
                return {
                    "success": False,
                    "error": "Not enough teams in event for alliance analysis",
                    "eventCode": event_code,
                    "analysis": None
                }
            
            team_numbers = [t.get('teamNumber') for t in event_teams]
            
            # Get EPA data for all teams
            team_epas = await self.db_service.batch_get_team_epas(team_numbers)
            
            # Create team rankings by EPA
            team_rankings = []
            for team_number in team_numbers:
                epa = team_epas.get(str(team_number), 0.0)
                team_info = next((t for t in event_teams if t.get('teamNumber') == team_number), {})
                
                team_rankings.append({
                    "teamNumber": team_number,
                    "teamName": team_info.get('teamName', ''),
                    "epa": epa
                })
            
            # Sort by EPA
            team_rankings.sort(key=lambda x: x["epa"], reverse=True)
            
            # Generate top alliance combinations (top 8 teams)
            top_teams = team_rankings[:8]
            top_team_numbers = [t["teamNumber"] for t in top_teams]
            
            # Get best combinations among top teams
            combinations_result = await self.suggest_alliance_combinations(top_team_numbers, season)
            top_combinations = combinations_result.get("combinations", [])[:10]  # Top 10 combinations
            
            return {
                "success": True,
                "eventCode": event_code,
                "analysis": {
                    "totalTeams": len(event_teams),
                    "teamRankings": team_rankings,
                    "topCombinations": top_combinations,
                    "averageEPA": sum(team_epas.values()) / len(team_epas) if team_epas else 0
                }
            }
                
        except Exception as e:
            logger.error(f"Error analyzing event alliances for {event_code}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "eventCode": event_code,
                "analysis": None
            }


async def lambda_handler(event, context):
    """Lambda handler for Alliance Matchmaker API"""
    
    # Initialize service
    api_service = AllianceMatchmakerService(
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
            # Check if specific team partners requested
            team_number_str = path_parameters.get('teamNumber')
            if team_number_str:
                team_number = int(team_number_str)
                event_code = query_parameters.get('eventCode')
                limit = int(query_parameters.get('limit', 10))
                
                result = await api_service.find_best_alliance_partners(
                    team_number, season, event_code, limit
                )
            
            # Check if team compatibility requested
            elif 'team1' in query_parameters and 'team2' in query_parameters:
                team1 = int(query_parameters['team1'])
                team2 = int(query_parameters['team2'])
                
                result = await api_service.get_team_compatibility(team1, team2, season)
            
            # Check if alliance combinations requested
            elif 'teams' in query_parameters:
                team_numbers_str = query_parameters['teams']
                team_numbers = [int(t.strip()) for t in team_numbers_str.split(',')]
                
                result = await api_service.suggest_alliance_combinations(team_numbers, season)
            
            # Check if event analysis requested
            elif 'eventCode' in query_parameters:
                event_code = query_parameters['eventCode']
                result = await api_service.analyze_event_alliances(event_code, season)
            
            else:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': 'Missing required parameters. Use teamNumber, team1&team2, teams, or eventCode',
                        'success': False
                    })
                }
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