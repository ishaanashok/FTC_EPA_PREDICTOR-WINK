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
    
    def calculate_compatibility_from_data(self, team1: int, team2: int, 
                                         team1_data: Dict[str, Any], team2_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate compatibility between two teams using pre-fetched EPA data"""
        try:
            team1_epa = team1_data.get('historicalEPA', 0.0)
            team2_epa = team2_data.get('historicalEPA', 0.0)
            
            # Calculate combined EPA
            combined_epa = team1_epa + team2_epa
            
            # Enhanced compatibility scoring using EPA breakdown
            # Handle cases where teams have no EPA data
            if team1_epa == 0 and team2_epa == 0:
                # Both teams have no data - use a neutral compatibility score
                basic_compatibility = 0.5
            elif team1_epa == 0 or team2_epa == 0:
                # One team has no data - penalize heavily but not completely
                basic_compatibility = 0.1
            else:
                # Both teams have data - calculate normal compatibility
                basic_compatibility = min(team1_epa, team2_epa) / max(team1_epa, team2_epa)
            
            # 2. Complementary skills scoring (how well they complement each other)
            team1_auto = team1_data.get('avgAutoPoints', 0.0)
            team1_teleop = team1_data.get('avgTeleopPoints', 0.0)
            team1_endgame = team1_data.get('avgEndgamePoints', 0.0)
            
            team2_auto = team2_data.get('avgAutoPoints', 0.0)
            team2_teleop = team2_data.get('avgTeleopPoints', 0.0)
            team2_endgame = team2_data.get('avgEndgamePoints', 0.0)
            
            # Calculate strength balance across game phases
            combined_auto = team1_auto + team2_auto
            combined_teleop = team1_teleop + team2_teleop
            combined_endgame = team1_endgame + team2_endgame
            
            # Calculate match count factor (prefer teams with more match data)
            team1_matches = team1_data.get('totalMatches', 0)
            team2_matches = team2_data.get('totalMatches', 0)
            avg_matches = (team1_matches + team2_matches) / 2
            match_confidence = min(1.0, avg_matches / 10.0)  # Full confidence at 10+ matches
            
            # Complementary scoring: reward balanced alliances
            total_combined = combined_auto + combined_teleop + combined_endgame
            if total_combined > 0 and (team1_matches > 0 or team2_matches > 0):
                # Calculate variance to penalize unbalanced alliances
                phase_scores = [combined_auto, combined_teleop, combined_endgame]
                avg_phase = total_combined / 3
                variance = sum((score - avg_phase) ** 2 for score in phase_scores) / 3
                balance_score = 1.0 / (1.0 + variance / (avg_phase ** 2 + 0.1))  # Normalize variance
            else:
                # No detailed performance data available
                balance_score = 0.3  # Neutral score for unknown teams
            
            # Final compatibility score: weighted combination with match confidence
            compatibility_score = (0.4 * basic_compatibility + 0.3 * balance_score + 0.3 * match_confidence)
            
            return {
                "success": True,
                "team1": team1,
                "team2": team2,
                "team1EPA": team1_epa,
                "team2EPA": team2_epa,
                "combinedEPA": combined_epa,
                "compatibilityScore": compatibility_score,
                "breakdown": {
                    "team1": {
                        "auto": team1_auto,
                        "teleop": team1_teleop,
                        "endgame": team1_endgame,
                        "matches": team1_data.get('totalMatches', 0)
                    },
                    "team2": {
                        "auto": team2_auto,
                        "teleop": team2_teleop,
                        "endgame": team2_endgame,
                        "matches": team2_data.get('totalMatches', 0)
                    },
                    "combined": {
                        "auto": combined_auto,
                        "teleop": combined_teleop,
                        "endgame": combined_endgame,
                        "balanceScore": balance_score
                    }
                }
            }
                
        except Exception as e:
            logger.error(f"Error calculating compatibility between teams {team1} and {team2}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "team1": team1,
                "team2": team2
            }

    async def get_team_compatibility(self, team1: int, team2: int, season: int) -> Dict[str, Any]:
        """Calculate compatibility between two teams using detailed EPA breakdown"""
        try:
            # Get detailed EPA data for both teams
            detailed_epas = self.db_service.batch_get_detailed_team_epas([team1, team2])
            
            team1_data = detailed_epas.get(str(team1), {})
            team2_data = detailed_epas.get(str(team2), {})
            
            team1_epa = team1_data.get('historicalEPA', 0.0)
            team2_epa = team2_data.get('historicalEPA', 0.0)
            
            # Calculate combined EPA
            combined_epa = team1_epa + team2_epa
            
            # Enhanced compatibility scoring using EPA breakdown
            # Handle cases where teams have no EPA data
            if team1_epa == 0 and team2_epa == 0:
                # Both teams have no data - use a neutral compatibility score
                basic_compatibility = 0.5
            elif team1_epa == 0 or team2_epa == 0:
                # One team has no data - penalize heavily but not completely
                basic_compatibility = 0.1
            else:
                # Both teams have data - calculate normal compatibility
                basic_compatibility = min(team1_epa, team2_epa) / max(team1_epa, team2_epa)
            
            # 2. Complementary skills scoring (how well they complement each other)
            team1_auto = team1_data.get('avgAutoPoints', 0.0)
            team1_teleop = team1_data.get('avgTeleopPoints', 0.0)
            team1_endgame = team1_data.get('avgEndgamePoints', 0.0)
            
            team2_auto = team2_data.get('avgAutoPoints', 0.0)
            team2_teleop = team2_data.get('avgTeleopPoints', 0.0)
            team2_endgame = team2_data.get('avgEndgamePoints', 0.0)
            
            # Calculate strength balance across game phases
            combined_auto = team1_auto + team2_auto
            combined_teleop = team1_teleop + team2_teleop
            combined_endgame = team1_endgame + team2_endgame
            
            # Calculate match count factor (prefer teams with more match data)
            team1_matches = team1_data.get('totalMatches', 0)
            team2_matches = team2_data.get('totalMatches', 0)
            avg_matches = (team1_matches + team2_matches) / 2
            match_confidence = min(1.0, avg_matches / 10.0)  # Full confidence at 10+ matches
            
            # Complementary scoring: reward balanced alliances
            total_combined = combined_auto + combined_teleop + combined_endgame
            if total_combined > 0 and (team1_matches > 0 or team2_matches > 0):
                # Calculate variance to penalize unbalanced alliances
                phase_scores = [combined_auto, combined_teleop, combined_endgame]
                avg_phase = total_combined / 3
                variance = sum((score - avg_phase) ** 2 for score in phase_scores) / 3
                balance_score = 1.0 / (1.0 + variance / (avg_phase ** 2 + 0.1))  # Normalize variance
            else:
                # No detailed performance data available
                balance_score = 0.3  # Neutral score for unknown teams
            
            # Final compatibility score: weighted combination with match confidence
            compatibility_score = (0.4 * basic_compatibility + 0.3 * balance_score + 0.3 * match_confidence)
            
            return {
                "success": True,
                "team1": team1,
                "team2": team2,
                "team1EPA": team1_epa,
                "team2EPA": team2_epa,
                "combinedEPA": combined_epa,
                "compatibilityScore": compatibility_score,
                "breakdown": {
                    "team1": {
                        "auto": team1_auto,
                        "teleop": team1_teleop,
                        "endgame": team1_endgame,
                        "matches": team1_data.get('totalMatches', 0)
                    },
                    "team2": {
                        "auto": team2_auto,
                        "teleop": team2_teleop,
                        "endgame": team2_endgame,
                        "matches": team2_data.get('totalMatches', 0)
                    },
                    "combined": {
                        "auto": combined_auto,
                        "teleop": combined_teleop,
                        "endgame": combined_endgame,
                        "balanceScore": balance_score
                    }
                }
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
        """Find the best alliance partners for a given team using detailed EPA analysis"""
        try:
            # Get available teams (either from event or season)
            if event_code:
                available_teams = self.db_service.get_teams_by_event(season, event_code)
            else:
                available_teams = self.db_service.get_teams_by_season(season, limit=200)
            
            # Filter out the requesting team
            partner_teams = [t for t in available_teams if t.get('teamNumber') != team_number]
            
            if not partner_teams:
                return {
                    "success": True,
                    "team": team_number,
                    "partners": [],
                    "message": "No potential partners found"
                }
            
            # Get detailed EPA data for all teams - ensure all team numbers are integers
            all_team_numbers = [team_number] + [int(t.get('teamNumber')) if isinstance(t.get('teamNumber'), float) else t.get('teamNumber') for t in partner_teams]
            detailed_epas = self.db_service.batch_get_detailed_team_epas(all_team_numbers)
            
            requesting_team_data = detailed_epas.get(str(team_number), {})
            requesting_team_epa = requesting_team_data.get('historicalEPA', 0.0)
            
            # Calculate compatibility with each potential partner using pre-fetched data
            partner_compatibility = []
            for partner_team in partner_teams:
                partner_number = partner_team.get('teamNumber')
                # Ensure partner number is an integer
                partner_number = int(partner_number) if isinstance(partner_number, float) else partner_number
                partner_data = detailed_epas.get(str(partner_number), {})
                partner_epa = partner_data.get('historicalEPA', 0.0)
                
                # Calculate detailed compatibility using the pre-fetched EPA data
                compatibility_result = self.calculate_compatibility_from_data(
                    team_number, partner_number, requesting_team_data, partner_data
                )
                
                partner_compatibility.append({
                    "teamNumber": partner_number,
                    "teamName": partner_team.get('teamName', ''),
                    "epa": float(partner_epa),
                    "combinedEPA": float(compatibility_result.get('combinedEPA', requesting_team_epa + partner_epa)),
                    "compatibilityScore": float(compatibility_result.get('compatibilityScore', 0.0)),
                    "breakdown": compatibility_result.get('breakdown', {}).get('team2', {}),
                    "totalMatches": int(partner_data.get('totalMatches', 0)),
                    "dataQuality": partner_data.get('dataQuality', 'no_data')
                })
            
            # Sort by multiple criteria for better ranking:
            # 1. Teams with EPA data first
            # 2. Higher compatibility score
            # 3. Higher combined EPA
            # 4. More matches (data reliability)
            partner_compatibility.sort(key=lambda x: (
                x["epa"] > 0,  # Teams with EPA data first
                x["compatibilityScore"],  # Higher compatibility score
                x["combinedEPA"],  # Higher combined EPA
                x["totalMatches"]  # More matches for reliability
            ), reverse=True)
            
            # Limit results
            best_partners = partner_compatibility[:limit]
            
            return {
                "success": True,
                "team": team_number,
                "teamEPA": requesting_team_epa,
                "teamBreakdown": requesting_team_data,
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
        """Suggest best alliance combinations from a list of teams using detailed analysis"""
        try:
            if len(team_numbers) < 2:
                return {
                    "success": False,
                    "error": "At least 2 teams required for alliance combinations",
                    "combinations": []
                }
            
            # Get detailed EPA data for all teams
            detailed_epas = self.db_service.batch_get_detailed_team_epas(team_numbers)
            
            # Generate all possible 2-team combinations
            combinations = []
            for team1, team2 in itertools.combinations(team_numbers, 2):
                # Calculate detailed compatibility
                compatibility_result = await self.get_team_compatibility(team1, team2, season)
                
                if compatibility_result.get('success', False):
                    combinations.append({
                        "team1": team1,
                        "team2": team2,
                        "team1EPA": compatibility_result.get('team1EPA', 0.0),
                        "team2EPA": compatibility_result.get('team2EPA', 0.0),
                        "combinedEPA": compatibility_result.get('combinedEPA', 0.0),
                        "compatibilityScore": compatibility_result.get('compatibilityScore', 0.0),
                        "breakdown": compatibility_result.get('breakdown', {})
                    })
            
            # Sort by compatibility score first, then by combined EPA
            combinations.sort(key=lambda x: (x["compatibilityScore"], x["combinedEPA"]), reverse=True)
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
        """Analyze potential alliances for an entire event using detailed EPA analysis"""
        try:
            # Get all teams in the event
            event_teams = self.db_service.get_teams_by_event(season, event_code)
            
            if len(event_teams) < 4:
                return {
                    "success": False,
                    "error": "Not enough teams in event for alliance analysis",
                    "eventCode": event_code,
                    "analysis": None
                }
            
            team_numbers = [t.get('teamNumber') for t in event_teams]
            
            # Get detailed EPA data for all teams
            detailed_epas = await self.db_service.batch_get_detailed_team_epas(team_numbers)
            
            # Create team rankings by EPA with breakdown
            team_rankings = []
            for team_number in team_numbers:
                team_data = detailed_epas.get(str(team_number), {})
                epa = team_data.get('historicalEPA', 0.0)
                team_info = next((t for t in event_teams if t.get('teamNumber') == team_number), {})
                
                team_rankings.append({
                    "teamNumber": team_number,
                    "teamName": team_info.get('teamName', ''),
                    "epa": epa,
                    "breakdown": {
                        "auto": team_data.get('avgAutoPoints', 0.0),
                        "teleop": team_data.get('avgTeleopPoints', 0.0),
                        "endgame": team_data.get('avgEndgamePoints', 0.0),
                        "matches": team_data.get('totalMatches', 0)
                    }
                })
            
            # Sort by EPA
            team_rankings.sort(key=lambda x: x["epa"], reverse=True)
            
            # Generate top alliance combinations (top 8 teams)
            top_teams = team_rankings[:8]
            top_team_numbers = [t["teamNumber"] for t in top_teams]
            
            # Get best combinations among top teams
            combinations_result = await self.suggest_alliance_combinations(top_team_numbers, season)
            top_combinations = combinations_result.get("combinations", [])[:10]  # Top 10 combinations
            
            # Calculate event statistics
            all_epas = [team_data.get('historicalEPA', 0.0) for team_data in detailed_epas.values()]
            avg_epa = sum(all_epas) / len(all_epas) if all_epas else 0
            
            return {
                "success": True,
                "eventCode": event_code,
                "analysis": {
                    "totalTeams": len(event_teams),
                    "teamRankings": team_rankings,
                    "topCombinations": top_combinations,
                    "averageEPA": avg_epa
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
        
        # Handle CORS preflight
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
                    'Content-Type': 'application/json'
                },
                'body': ''
            }
        
        # Default season
        season = int(query_parameters.get('season', 2024))
        
        # Handle POST requests (from frontend)
        if http_method == 'POST':
            import json
            body = json.loads(event.get('body', '{}'))
            season = body.get('season', 2024)
            event_code = body.get('eventCode')
            
            # Check if this is a batch request
            path = event.get('path', '')
            if 'batch' in path or 'teamNumbers' in body:
                # Handle batch alliance matchmaker request
                team_numbers = body.get('teamNumbers', [])
                team_epas = body.get('teamEPAs', {})
                
                if not team_numbers or not event_code:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                        },
                        'body': json.dumps({
                            'error': 'Missing required parameters: teamNumbers and eventCode',
                            'success': False
                        })
                    }
                
                # Process batch alliance suggestions
                result = await api_service.suggest_alliance_combinations(team_numbers, season)
            else:
                # Handle single team alliance matchmaker request
                team_number = body.get('teamNumber')
                
                if team_number and event_code:
                    limit = body.get('limit', 10)
                    result = await api_service.find_best_alliance_partners(
                        team_number, season, event_code, limit
                    )
                else:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                        },
                        'body': json.dumps({
                            'error': 'Missing required parameters: teamNumber and eventCode',
                            'success': False
                        })
                    }
        
        # Handle different GET endpoints
        elif http_method == 'GET':
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
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
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
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Method not allowed',
                    'allowedMethods': ['GET', 'POST']
                })
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
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