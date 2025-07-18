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
    """EPA API service - reads directly from DynamoDB"""
    
    def __init__(self, environment: str = 'dev'):
        self.environment = environment
        self.db_service = DynamoDBService(environment)
    
    async def get_team_epa(self, team_number: int, historical: bool = False) -> Dict[str, Any]:
        """Get EPA data for a specific team"""
        try:
            if historical:
                # Get historical EPA data
                epa_history = await self.db_service.get_historical_epa(team_number, limit=10)
                return {
                    "success": True,
                    "teamNumber": team_number,
                    "epaHistory": epa_history,
                    "total": len(epa_history)
                }
            else:
                # Get latest EPA data
                epa_data = await self.db_service.get_latest_epa(team_number)
                if epa_data:
                    return {
                        "success": True,
                        "teamNumber": team_number,
                        "epa": epa_data
                    }
                else:
                    return {
                        "success": True,
                        "teamNumber": team_number,
                        "epa": None,
                        "message": f"No EPA data found for team {team_number}"
                    }
                
        except Exception as e:
            logger.error(f"Error getting EPA for team {team_number}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "teamNumber": team_number,
                "epa": None
            }
    
    async def get_multiple_team_epas(self, team_numbers: List[int]) -> Dict[str, Any]:
        """Get EPA data for multiple teams"""
        try:
            team_epas = await self.db_service.batch_get_team_epas(team_numbers)
            
            # Convert to more structured format
            epa_results = []
            for team_number in team_numbers:
                epa_value = team_epas.get(str(team_number), 0.0)
                epa_results.append({
                    "teamNumber": team_number,
                    "epa": epa_value
                })
            
            return {
                "success": True,
                "teams": epa_results,
                "total": len(epa_results)
            }
                
        except Exception as e:
            logger.error(f"Error getting EPAs for teams {team_numbers}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "teams": [],
                "total": 0
            }
    
    async def get_top_teams_by_epa(self, limit: int = 20) -> Dict[str, Any]:
        """Get top teams by EPA (simplified implementation)"""
        try:
            # This is a simplified implementation
            # In a real system, you'd have a GSI to query by EPA value
            logger.warning("get_top_teams_by_epa is a simplified implementation")
            
            return {
                "success": True,
                "message": "Top teams by EPA - feature not yet implemented",
                "teams": [],
                "total": 0
            }
                
        except Exception as e:
            logger.error(f"Error getting top teams by EPA: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "teams": [],
                "total": 0
            }
    
    async def get_team_epa_comparison(self, team_numbers: List[int]) -> Dict[str, Any]:
        """Compare EPA values between teams"""
        try:
            if len(team_numbers) < 2:
                return {
                    "success": False,
                    "error": "At least 2 teams required for comparison",
                    "comparison": None
                }
            
            # Get EPA data for all teams
            team_epas = await self.db_service.batch_get_team_epas(team_numbers)
            
            # Build comparison data
            comparison_data = []
            for team_number in team_numbers:
                epa_value = team_epas.get(str(team_number), 0.0)
                comparison_data.append({
                    "teamNumber": team_number,
                    "epa": epa_value
                })
            
            # Sort by EPA descending
            comparison_data.sort(key=lambda x: x["epa"], reverse=True)
            
            # Calculate statistics
            epa_values = [team["epa"] for team in comparison_data]
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
                "comparison": None
            }


async def lambda_handler(event, context):
    """Lambda handler for EPA API"""
    
    # Initialize service
    api_service = EPAApiService(
        environment=os.environ.get('ENVIRONMENT', 'dev')
    )
    
    try:
        # Extract parameters from event
        http_method = event.get('httpMethod', 'GET')
        path_parameters = event.get('pathParameters') or {}
        query_parameters = event.get('queryStringParameters') or {}
        
        # Handle different endpoints
        if http_method == 'GET':
            # Check if specific team requested
            team_number_str = path_parameters.get('teamNumber')
            if team_number_str:
                team_number = int(team_number_str)
                historical = query_parameters.get('historical', '').lower() == 'true'
                result = await api_service.get_team_epa(team_number, historical)
            
            # Check if multiple teams requested
            elif 'teams' in query_parameters:
                team_numbers_str = query_parameters['teams']
                team_numbers = [int(t.strip()) for t in team_numbers_str.split(',')]
                
                # Check if comparison requested
                if query_parameters.get('compare', '').lower() == 'true':
                    result = await api_service.get_team_epa_comparison(team_numbers)
                else:
                    result = await api_service.get_multiple_team_epas(team_numbers)
            
            # Check if top teams requested
            elif query_parameters.get('top', '').lower() == 'true':
                limit = int(query_parameters.get('limit', 20))
                result = await api_service.get_top_teams_by_epa(limit)
            
            else:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': 'Missing required parameters. Use teamNumber, teams, or top=true',
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