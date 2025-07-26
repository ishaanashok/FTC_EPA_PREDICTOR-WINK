import json
import boto3
import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any
from decimal import Decimal

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    AWS Lambda function to handle admin match additions
    
    Expected API Gateway event structure:
    - POST /admin/matches
    - Authorization header with admin token
    - Body with matches data
    """
    
    try:
        # Parse the request
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        
        logger.info(f"Request: {http_method} {path}")
        
        if http_method != 'POST' or not path.endswith('/admin/matches'):
            return {
                'statusCode': 405,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Method not allowed',
                    'message': 'Only POST requests are allowed on this endpoint'
                })
            }
        
        # Handle CORS preflight
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS'
                },
                'body': ''
            }
        
        # Parse request body
        if not event.get('body'):
            return create_error_response(400, 'Request body is required')
        
        try:
            body = json.loads(event['body'])
        except json.JSONDecodeError:
            return create_error_response(400, 'Invalid JSON in request body')
        
        # Validate required fields
        matches = body.get('matches', [])
        season = body.get('season')
        event_code = body.get('eventCode')
        
        logger.info(f"Received request: {len(matches)} matches for season {season}, event {event_code}")
        logger.info(f"Matches type: {type(matches)}")
        
        if not matches:
            return create_error_response(400, 'No matches provided')
        if not season:
            return create_error_response(400, 'Season is required')
        if not event_code:
            return create_error_response(400, 'Event code is required')
        
        # Ensure matches is a list
        if not isinstance(matches, list):
            return create_error_response(400, 'Matches must be an array')
        
        logger.info(f"Processing {len(matches)} matches")
        
        # Validate admin authorization (simplified - you might want more robust auth)
        auth_header = event.get('headers', {}).get('Authorization', '')
        if not is_admin_authorized(auth_header):
            return create_error_response(403, 'Admin authorization required')
        
        # Process matches
        result = add_matches_to_dynamodb(matches, season, event_code)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
        
    except TypeError as e:
        if "await" in str(e) or "async" in str(e):
            logger.error(f"Async/await error: {str(e)}")
            return create_error_response(500, f"Internal async error: {str(e)}")
        else:
            logger.error(f"Type error: {str(e)}")
            return create_error_response(500, f"Type error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return create_error_response(500, f"Internal server error: {str(e)}")

def is_admin_authorized(auth_header: str) -> bool:
    """
    Validate admin authorization
    In a real implementation, this would validate against Cognito or similar
    """
    # For now, just check if there's an authorization header
    # You should implement proper Cognito JWT validation here
    return bool(auth_header and auth_header.startswith('Bearer '))

def add_matches_to_dynamodb(matches: List[Dict[str, Any]], season: int, event_code: str) -> Dict[str, Any]:
    """
    Add matches to DynamoDB FTC_Matches table
    """
    environment = os.environ.get('ENVIRONMENT', 'dev')
    table_name = f'FTC_Matches_{environment}'
    
    try:
        table = dynamodb.Table(table_name)
        
        # Validate and convert matches
        validated_matches = []
        for i, match in enumerate(matches):
            try:
                logger.info(f"Validating match {i+1}: {match.get('matchNumber', 'unknown')}")
                validated_match = validate_and_convert_match(match, season, event_code)
                validated_matches.append(validated_match)
            except Exception as e:
                logger.error(f"Error validating match {i+1}: {str(e)}")
                return {
                    'success': False,
                    'error': f"Invalid match data at index {i}: {str(e)}"
                }
        
        logger.info(f"Successfully validated {len(validated_matches)} matches")
        
        # Check for existing matches to prevent duplicates
        existing_matches = check_existing_matches(table, validated_matches, season, event_code)
        if existing_matches:
            return {
                'success': False,
                'error': 'Duplicate matches found',
                'existing_matches': existing_matches,
                'message': 'Some matches already exist in the database'
            }
        
        # Insert matches in batches
        inserted_count = 0
        batch_size = 25  # DynamoDB batch write limit
        
        for i in range(0, len(validated_matches), batch_size):
            batch = validated_matches[i:i + batch_size]
            
            try:
                with table.batch_writer() as batch_writer:
                    for match in batch:
                        # Convert to DynamoDB format (handle Decimal types)
                        dynamo_match = convert_to_dynamodb_types(match)
                        batch_writer.put_item(Item=dynamo_match)
                        inserted_count += 1
                        
            except Exception as e:
                logger.error(f"Error writing batch: {str(e)}")
                raise
        
        logger.info(f"Successfully inserted {inserted_count} matches for {event_code} ({season})")
        
        return {
            'success': True,
            'message': f'Successfully added {inserted_count} matches',
            'matches_added': inserted_count,
            'season': season,
            'eventCode': event_code,
            'matchIds': [match['matchId'] for match in validated_matches]
        }
        
    except Exception as e:
        logger.error(f"Error adding matches to DynamoDB: {str(e)}")
        raise

def validate_and_convert_match(match: Dict[str, Any], season: int, event_code: str) -> Dict[str, Any]:
    """
    Validate and ensure match data is in correct format
    """
    # Extract required fields
    match_number = match.get('matchNumber')
    if not match_number or not isinstance(match_number, int) or match_number <= 0:
        raise ValueError(f"Invalid match number: {match_number}")
    
    # Ensure teams data exists
    teams = match.get('teams', [])
    red_teams = match.get('redTeams', [])
    blue_teams = match.get('blueTeams', [])
    
    if not teams and not (red_teams and blue_teams):
        raise ValueError(f"Match {match_number} missing team assignments")
    
    # Create match ID if not present
    tournament_level = match.get('tournamentLevel', 'QUALIFICATION')
    series = match.get('series', 1)
    match_id = match.get('matchId', f"{season}-{event_code}-{tournament_level}-{series}-{match_number}")
    
    # Ensure timestamps
    current_time = datetime.now(timezone.utc).isoformat()
    
    validated_match = {
        'matchId': match_id,
        'season': season,
        'eventCode': event_code,
        'matchNumber': match_number,
        'description': match.get('description', f"{tournament_level} {match_number}"),
        'tournamentLevel': tournament_level,
        'series': series,
        'teams': teams,
        'redTeams': red_teams,
        'blueTeams': blue_teams,
        'allTeams': match.get('allTeams', red_teams + blue_teams),
        'redScore': match.get('redScore'),
        'blueScore': match.get('blueScore'),
        'startTime': match.get('startTime', current_time),
        'actualStartTime': match.get('actualStartTime'),
        'postResultTime': match.get('postResultTime'),
        'lastUpdated': current_time
    }
    
    return validated_match

def check_existing_matches(table, matches: List[Dict[str, Any]], season: int, event_code: str) -> List[str]:
    """
    Check if any matches already exist in the database
    """
    existing_matches = []
    
    for match in matches:
        try:
            response = table.get_item(
                Key={
                    'matchId': match['matchId']
                }
            )
            if 'Item' in response:
                existing_matches.append(match['matchId'])
        except Exception as e:
            logger.warning(f"Error checking for existing match {match['matchId']}: {str(e)}")
    
    return existing_matches

def convert_to_dynamodb_types(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert Python types to DynamoDB-compatible types
    """
    def convert_value(value):
        if isinstance(value, float):
            return Decimal(str(value))
        elif isinstance(value, dict):
            return {k: convert_value(v) for k, v in value.items() if v is not None}
        elif isinstance(value, list):
            return [convert_value(v) for v in value]
        elif value is None:
            return None
        else:
            return value
    
    return {k: convert_value(v) for k, v in item.items() if v is not None}

def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Create standardized error response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': True,
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    }
