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
        
        if http_method not in ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'] or not path.startswith('/admin/matches'):
            return {
                'statusCode': 405,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Method not allowed',
                    'message': 'Only GET, POST, PUT and DELETE requests are allowed on this endpoint'
                })
            }
        
        # Handle CORS preflight
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
                },
                'body': ''
            }
        
        # Handle DELETE requests (for deleting individual matches)
        if http_method == 'DELETE':
            return handle_delete_match(event)
        
        # Handle GET requests (for fetching existing matches)
        if http_method == 'GET':
            return handle_get_matches(event)
        
        # Handle PUT requests (for updating existing matches)
        if http_method == 'PUT':
            return handle_update_match(event)
        
        # Handle POST requests (for adding matches)
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
        headers = event.get('headers', {})
        logger.info(f"Available headers: {list(headers.keys())}")
        
        # Try different case variations for the Authorization header
        auth_header = (
            headers.get('Authorization') or 
            headers.get('authorization') or 
            headers.get('AUTHORIZATION') or 
            ''
        )
        
        logger.info(f"Auth header found: {'Yes' if auth_header else 'No'}")
        logger.info(f"Auth header value: {auth_header[:20]}..." if auth_header else "No auth header")
        
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
    logger.info(f"Checking authorization with header: {auth_header[:50]}..." if auth_header else "Empty auth header")
    
    if not auth_header:
        logger.warning("No authorization header provided")
        return False
    
    # For now, accept any token that looks like a Bearer token
    # You should implement proper Cognito JWT validation here
    is_bearer = auth_header.startswith('Bearer ') or auth_header.startswith('bearer ')
    
    if not is_bearer:
        logger.warning(f"Authorization header doesn't start with 'Bearer ': {auth_header[:30]}...")
        return False
    
    # Extract the token part
    token = auth_header.split(' ', 1)[1] if ' ' in auth_header else ''
    
    if len(token) < 10:  # Basic sanity check for token length
        logger.warning(f"Token too short: {len(token)} characters")
        return False
    
    logger.info("Authorization check passed")
    return True

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

def handle_delete_match(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle DELETE requests to remove a match from DynamoDB
    Expected path: /admin/matches/{matchId}
    """
    try:
        # Extract match ID from path
        path = event.get('path', '')
        path_params = event.get('pathParameters', {})
        
        # Try to get match ID from path parameters first (API Gateway)
        match_id = path_params.get('proxy') if path_params else None
        
        # If not found, extract from path manually
        if not match_id:
            # Path should be like /admin/matches/{matchId}
            path_parts = path.strip('/').split('/')
            if len(path_parts) >= 3 and path_parts[0] == 'admin' and path_parts[1] == 'matches':
                match_id = path_parts[2]
        
        logger.info(f"Attempting to delete match with ID: {match_id}")
        
        if not match_id:
            return create_error_response(400, 'Match ID is required in path')
        
        # Validate admin authorization
        headers = event.get('headers', {})
        auth_header = (
            headers.get('Authorization') or 
            headers.get('authorization') or 
            headers.get('AUTHORIZATION') or 
            ''
        )
        
        if not is_admin_authorized(auth_header):
            return create_error_response(403, 'Admin authorization required')
        
        # Parse request body for additional data (season, eventCode)
        body_data = {}
        if event.get('body'):
            try:
                body_data = json.loads(event['body'])
            except json.JSONDecodeError:
                logger.warning("Failed to parse body, proceeding without body data")
        
        # Delete the match
        result = delete_match_from_dynamodb(match_id, body_data.get('season'), body_data.get('eventCode'))
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"Error deleting match: {str(e)}")
        return create_error_response(500, f"Internal server error: {str(e)}")

def delete_match_from_dynamodb(match_id: str, season: int = None, event_code: str = None) -> Dict[str, Any]:
    """
    Delete a match from DynamoDB FTC_Matches table
    """
    environment = os.environ.get('ENVIRONMENT', 'dev')
    table_name = f'FTC_Matches_{environment}'
    
    try:
        table = dynamodb.Table(table_name)
        
        # First check if the match exists
        response = table.get_item(
            Key={
                'matchId': match_id
            }
        )
        
        if 'Item' not in response:
            logger.warning(f"Match {match_id} not found")
            return {
                'success': False,
                'error': 'Match not found',
                'matchId': match_id
            }
        
        # Delete the match
        table.delete_item(
            Key={
                'matchId': match_id
            }
        )
        
        logger.info(f"Successfully deleted match {match_id}")
        
        return {
            'success': True,
            'message': f'Successfully deleted match {match_id}',
            'matchId': match_id,
            'deletedAt': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error deleting match from DynamoDB: {str(e)}")
        raise

def handle_get_matches(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET requests to fetch matches for an event
    Expected path: /admin/matches/{season}/{eventCode}
    """
    try:
        # Extract season and eventCode from path
        path = event.get('path', '')
        path_parts = path.strip('/').split('/')
        
        # Path should be like /admin/matches/{season}/{eventCode}
        if len(path_parts) < 4:
            return create_error_response(400, 'Season and event code are required in path')
        
        season = path_parts[2]
        event_code = path_parts[3]
        
        logger.info(f"Fetching matches for season {season}, event {event_code}")
        
        # Validate admin authorization
        headers = event.get('headers', {})
        auth_header = (
            headers.get('Authorization') or 
            headers.get('authorization') or 
            headers.get('AUTHORIZATION') or 
            ''
        )
        
        if not is_admin_authorized(auth_header):
            return create_error_response(403, 'Admin authorization required')
        
        # Fetch matches from DynamoDB
        result = get_matches_from_dynamodb(season, event_code)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"Error fetching matches: {str(e)}")
        return create_error_response(500, f"Internal server error: {str(e)}")

def handle_update_match(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle PUT requests to update an existing match
    Expected path: /admin/matches/{matchId}
    """
    try:
        # Extract match ID from path
        path = event.get('path', '')
        path_params = event.get('pathParameters', {})
        
        # Try to get match ID from path parameters first (API Gateway)
        match_id = path_params.get('proxy') if path_params else None
        
        # If not found, extract from path manually
        if not match_id:
            # Path should be like /admin/matches/{matchId}
            path_parts = path.strip('/').split('/')
            if len(path_parts) >= 3 and path_parts[0] == 'admin' and path_parts[1] == 'matches':
                match_id = path_parts[2]
        
        logger.info(f"Attempting to update match with ID: {match_id}")
        
        if not match_id:
            return create_error_response(400, 'Match ID is required in path')
        
        # Validate admin authorization
        headers = event.get('headers', {})
        auth_header = (
            headers.get('Authorization') or 
            headers.get('authorization') or 
            headers.get('AUTHORIZATION') or 
            ''
        )
        
        if not is_admin_authorized(auth_header):
            return create_error_response(403, 'Admin authorization required')
        
        # Parse request body
        if not event.get('body'):
            return create_error_response(400, 'Request body is required')
        
        try:
            body = json.loads(event['body'])
        except json.JSONDecodeError:
            return create_error_response(400, 'Invalid JSON in request body')
        
        match_data = body.get('match', {})
        season = body.get('season')
        event_code = body.get('eventCode')
        
        if not match_data:
            return create_error_response(400, 'Match data is required')
        
        # Update the match
        result = update_match_in_dynamodb(match_id, match_data, season, event_code)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"Error updating match: {str(e)}")
        return create_error_response(500, f"Internal server error: {str(e)}")

def get_matches_from_dynamodb(season: str, event_code: str) -> Dict[str, Any]:
    """
    Get matches from DynamoDB for a specific event using EventIndex GSI
    """
    environment = os.environ.get('ENVIRONMENT', 'dev')
    table_name = f'FTC_Matches_{environment}'
    
    try:
        table = dynamodb.Table(table_name)
        
        # Use the EventIndex GSI to efficiently query matches
        response = table.query(
            IndexName='EventIndex',
            KeyConditionExpression='eventCode = :eventCode AND season = :season',
            ExpressionAttributeValues={
                ':eventCode': event_code,
                ':season': int(season)
            }
        )
        
        matches = response.get('Items', [])
        logger.info(f"Found {len(matches)} matches for {event_code} ({season}) using EventIndex")
        
        # Convert DynamoDB format back to frontend format
        converted_matches = []
        for match in matches:
            converted_match = convert_from_dynamodb_types(match)
            converted_matches.append(converted_match)
        
        # Sort by match number for better display
        converted_matches.sort(key=lambda x: x.get('matchNumber', 0))
        
        return {
            'success': True,
            'matches': converted_matches,
            'count': len(converted_matches),
            'season': season,
            'eventCode': event_code
        }
        
    except Exception as e:
        logger.error(f"Error fetching matches from DynamoDB: {str(e)}")
        raise

def update_match_in_dynamodb(match_id: str, match_data: Dict[str, Any], season: int = None, event_code: str = None) -> Dict[str, Any]:
    """
    Update an existing match in DynamoDB
    """
    environment = os.environ.get('ENVIRONMENT', 'dev')
    table_name = f'FTC_Matches_{environment}'
    
    try:
        table = dynamodb.Table(table_name)
        
        # First check if the match exists
        response = table.get_item(
            Key={
                'matchId': match_id
            }
        )
        
        if 'Item' not in response:
            logger.warning(f"Match {match_id} not found")
            return {
                'success': False,
                'error': 'Match not found',
                'matchId': match_id
            }
        
        existing_match = response['Item']
        
        # Update the match data
        updated_match = {**existing_match}
        updated_match.update({
            'matchNumber': match_data.get('matchNumber', existing_match.get('matchNumber')),
            'redTeams': match_data.get('redTeams', existing_match.get('redTeams', [])),
            'blueTeams': match_data.get('blueTeams', existing_match.get('blueTeams', [])),
            'redScore': match_data.get('redScore', existing_match.get('redScore')),
            'blueScore': match_data.get('blueScore', existing_match.get('blueScore')),
            'lastUpdated': datetime.now(timezone.utc).isoformat()
        })
        
        # Update allTeams
        updated_match['allTeams'] = updated_match['redTeams'] + updated_match['blueTeams']
        
        # Convert to DynamoDB format
        dynamo_match = convert_to_dynamodb_types(updated_match)
        
        # Update the item
        table.put_item(Item=dynamo_match)
        
        logger.info(f"Successfully updated match {match_id}")
        
        return {
            'success': True,
            'message': f'Successfully updated match {match_id}',
            'matchId': match_id,
            'match': convert_from_dynamodb_types(dynamo_match),
            'updatedAt': updated_match['lastUpdated']
        }
        
    except Exception as e:
        logger.error(f"Error updating match in DynamoDB: {str(e)}")
        raise

def convert_from_dynamodb_types(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert DynamoDB types back to regular Python types
    """
    def convert_value(value):
        if isinstance(value, Decimal):
            # Convert Decimal to int if it's a whole number, otherwise to float
            if value % 1 == 0:
                return int(value)
            else:
                return float(value)
        elif isinstance(value, dict):
            return {k: convert_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [convert_value(v) for v in value]
        else:
            return value
    
    return {k: convert_value(v) for k, v in item.items()}
