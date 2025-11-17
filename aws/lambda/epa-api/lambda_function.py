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

class EPAApiService:
    """
    EPA API service for new schema (v2.0)
    
    Supports:
    - Historic EPA (embedded in team records)
    - Per-match EPA (TeamMatchEPA table)
    - Event EPA summaries
    """
    
    def __init__(self, environment: str = 'stage'):
        self.environment = environment
        self.db_service = DynamoDBService(environment)
    
    def get_team_historic_epa(self, team_number: int, season: int = 2025) -> Dict[str, Any]:
        """Get historic EPA for a team (embedded in team record)"""
        try:
            team = self.db_service.get_team(team_number, season)
            
            if not team:
                return {
                    "success": False,
                    "error": f"Team {team_number} not found for season {season}",
                    "teamNumber": team_number,
                    "historicEPA": None
                }
            
            historic_epa = team.get('historicEPA')
            
            if not historic_epa:
                return {
                    "success": True,
                    "teamNumber": team_number,
                    "historicEPA": None,
                    "message": f"No historic EPA data available for team {team_number}"
                }
            
            return {
                "success": True,
                "teamNumber": team_number,
                "historicEPA": historic_epa
            }
                
        except Exception as e:
            logger.error(f"Error getting historic EPA for team {team_number}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "teamNumber": team_number,
                "historicEPA": None
            }
    
    def get_team_season_epa(self, team_number: int, season: int) -> Dict[str, Any]:
        """Get per-match EPA records for a team in a season"""
        try:
            epa_records = self.db_service.get_team_season_epa(team_number, season)
            
            # Calculate summary
            summary = None
            if epa_records:
                latest_record = epa_records[-1]
                summary = {
                    "averageEPA": latest_record.get('averageEPA'),
                    "cumulativeEPA": latest_record.get('cumulativeEPA'),
                    "matchCount": latest_record.get('matchCount'),
                    "latestMatchEPA": latest_record.get('matchEPA')
                }
            
            return {
                "success": True,
                "teamNumber": team_number,
                "season": season,
                "epaRecords": epa_records,
                "summary": summary,
                "totalMatches": len(epa_records)
            }
                
        except Exception as e:
            logger.error(f"Error getting season EPA for team {team_number}, season {season}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "teamNumber": team_number,
                "season": season,
                "epaRecords": [],
                "totalMatches": 0
            }
    
    def get_team_event_epa(self, team_number: int, event_code: str) -> Dict[str, Any]:
        """Get EPA records for a team at a specific event"""
        try:
            epa_records = self.db_service.get_team_event_epa(team_number, event_code)
            
            # Calculate summary
            summary = None
            if epa_records:
                latest_record = epa_records[-1]
                summary = {
                    "averageEPA": latest_record.get('averageEPA'),
                    "matchCount": latest_record.get('matchCount'),
                    "latestMatchEPA": latest_record.get('matchEPA')
                }
            
            return {
                "success": True,
                "teamNumber": team_number,
                "eventCode": event_code,
                "epaRecords": epa_records,
                "summary": summary,
                "totalMatches": len(epa_records)
            }
                
        except Exception as e:
            logger.error(f"Error getting event EPA for team {team_number}, event {event_code}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "teamNumber": team_number,
                "eventCode": event_code,
                "epaRecords": [],
                "totalMatches": 0
            }
    
    def get_event_team_epas(self, event_code: str, season: int = 2025) -> Dict[str, Any]:
        """Get EPA summary for all teams at an event"""
        try:
            # Get all teams at this event
            teams = self.db_service.get_teams_by_event(season, event_code)
            
            # Get EPA for each team
            team_epas = {}
            for team in teams:
                team_number = team.get('teamNumber')
                if team_number:
                    # Convert to int to handle float/Decimal types
                    team_number = int(team_number)
                    
                    # Get historic EPA from team record
                    historic_epa_val = None
                    if 'historicEPA' in team and team['historicEPA']:
                        historic_epa_val = team['historicEPA'].get('historicEPA')
                    
                    # Get latest event EPA from TeamMatchEPA table
                    event_epa_records = self.db_service.get_team_event_epa(team_number, event_code)
                    event_epa_val = None
                    if event_epa_records:
                        event_epa_val = event_epa_records[-1].get('averageEPA')
                    
                    team_epas[str(team_number)] = {
                        "teamNumber": team_number,
                        "historicEPA": historic_epa_val,
                        "eventEPA": event_epa_val,
                        "eventMatches": len(event_epa_records)
                    }
            
            return {
                "success": True,
                "eventCode": event_code,
                "season": season,
                "teamEPAs": team_epas,
                "totalTeams": len(team_epas)
            }
                
        except Exception as e:
            logger.error(f"Error getting event team EPAs for {event_code}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "eventCode": event_code,
                "teamEPAs": {},
                "totalTeams": 0
            }
    
    def compare_team_epas(self, team_numbers: List[int], season: int = 2025) -> Dict[str, Any]:
        """Compare historic EPA between multiple teams"""
        try:
            if len(team_numbers) < 2:
                return {
                    "success": False,
                    "error": "At least 2 teams required for comparison",
                    "comparison": []
                }
            
            comparison_data = []
            for team_number in team_numbers:
                team = self.db_service.get_team(team_number, season)
                if team:
                    historic_epa = team.get('historicEPA', {})
                    comparison_data.append({
                        "teamNumber": team_number,
                        "name": team.get('nameShort', team.get('nameFull', 'Unknown')),
                        "historicEPA": historic_epa.get('historicEPA'),
                        "totalMatches": historic_epa.get('totalHistoricalMatches'),
                        "seasonsWithData": historic_epa.get('seasonsWithData', [])
                    })
            
            # Sort by EPA descending
            comparison_data.sort(key=lambda x: x.get("historicEPA") or 0, reverse=True)
            
            # Calculate statistics
            epa_values = [team.get("historicEPA") or 0 for team in comparison_data]
            max_epa = max(epa_values) if epa_values else 0
            min_epa = min(epa_values) if epa_values else 0
            avg_epa = sum(epa_values) / len(epa_values) if epa_values else 0
            
            return {
                "success": True,
                "comparison": comparison_data,
                "statistics": {
                    "maxEPA": max_epa,
                    "minEPA": min_epa,
                    "averageEPA": avg_epa,
                    "totalTeams": len(comparison_data)
                }
            }
                
        except Exception as e:
            logger.error(f"Error comparing EPAs for teams {team_numbers}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "comparison": []
            }


def lambda_handler(event, context):
    """Lambda handler for EPA API"""
    
    # Initialize service
    api_service = EPAApiService(
        environment=os.environ.get('ENVIRONMENT', 'stage')
    )
    
    try:
        # Extract parameters from event
        http_method = event.get('httpMethod', 'GET')
        path_parameters = event.get('pathParameters') or {}
        query_parameters = event.get('queryStringParameters') or {}
        
        # Default season
        season = int(query_parameters.get('season', 2025))
        
        # Handle different endpoints
        if http_method == 'GET':
            # GET /epa/{teamNumber} - Get historic EPA for a team
            team_number_str = path_parameters.get('teamNumber')
            if team_number_str:
                team_number = int(team_number_str)
                
                # Check if season EPA requested
                if query_parameters.get('type') == 'season':
                    result = api_service.get_team_season_epa(team_number, season)
                # Check if event EPA requested
                elif 'eventCode' in query_parameters:
                    event_code = query_parameters['eventCode']
                    result = api_service.get_team_event_epa(team_number, event_code)
                # Default: historic EPA
                else:
                    result = api_service.get_team_historic_epa(team_number, season)
            
            # GET /epa?eventCode=XXX - Get EPA for all teams at event
            elif 'eventCode' in query_parameters:
                event_code = query_parameters['eventCode']
                result = api_service.get_event_team_epas(event_code, season)
            
            # GET /epa?teams=1,2,3&compare=true - Compare teams
            elif 'teams' in query_parameters:
                team_numbers_str = query_parameters['teams']
                team_numbers = [int(t.strip()) for t in team_numbers_str.split(',')]
                
                if query_parameters.get('compare', '').lower() == 'true':
                    result = api_service.compare_team_epas(team_numbers, season)
                else:
                    # Get individual EPAs
                    results = []
                    for team_number in team_numbers:
                        epa_result = api_service.get_team_historic_epa(team_number, season)
                        results.append(epa_result)
                    result = {
                        "success": True,
                        "teams": results,
                        "total": len(results)
                    }
            
            else:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': 'Missing required parameters. Use teamNumber, eventCode, or teams',
                        'examples': {
                            'teamHistoricEPA': '/epa/{teamNumber}?season=2025',
                            'teamSeasonEPA': '/epa/{teamNumber}?type=season&season=2025',
                            'teamEventEPA': '/epa/{teamNumber}?eventCode=USCASD',
                            'eventTeamEPAs': '/epa?eventCode=USCASD&season=2025',
                            'compareTeams': '/epa?teams=1,2,3&compare=true&season=2025'
                        },
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
    """Main handler for Lambda function"""
    return lambda_handler(event, context)

