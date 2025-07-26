"""
EPA Calculator Lambda Function

Recent improvements:
- Fixed environment default from 'dev' to 'stage' for production deployment
- Enhanced date parsing with proper string/datetime handling to prevent comparison errors
- Added comprehensive input validation for team numbers and batch requests
- Added performance monitoring with execution timing
- Improved error handling and logging for better debugging
- Validated with TeamIndex GSI for efficient team match lookups

Dependencies:
- Requires DynamoDB service with TeamIndex GSI (teamNumber + season)
- Requires team-match association records for EPA calculations
"""

import json
import boto3
import logging
import os
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
import math

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import the DynamoDB service
from services.dynamodb_service import DynamoDBService

# Environment variables
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'stage')

class EPACalculator:
    """EPA Calculator for FTC teams using DynamoDB data"""
    
    def __init__(self, db_service: DynamoDBService):
        self.db_service = db_service
        self.year_weights = {
            2024: 1.0,
            2023: 0.7,
            2022: 0.5
        }
        self.k = 12  # EPA scaling factor for win probability

    async def calculate_team_epa(self, team_number: int, event_start_date: str = None) -> Dict[str, Any]:
        """Calculate EPA for a team based on their historical matches"""
        start_time = time.time()
        logger.info(f"Calculating EPA for team {team_number}")
        
        try:
            # Get all matches for the team across seasons
            all_matches = {}
            
            # Fetch matches from recent seasons (2022-2024)
            for season in [2022, 2023, 2024]:
                season_matches = await self.db_service.get_matches_by_team(team_number, season)
                if season_matches:
                    # Filter matches before event start date if provided
                    if event_start_date:
                        filtered_matches = []
                        for match in season_matches:
                            match_date = match.get('actualStartTime') or match.get('startTime')
                            if match_date:
                                try:
                                    # Convert string dates to datetime for comparison
                                    if isinstance(match_date, str):
                                        from datetime import datetime
                                        # Handle different date formats that might be stored
                                        if 'T' in match_date:
                                            parsed_date = datetime.fromisoformat(match_date.replace('Z', '+00:00'))
                                        else:
                                            # Assume it's a date string in a standard format
                                            parsed_date = datetime.strptime(match_date, '%Y-%m-%d %H:%M:%S')
                                    else:
                                        parsed_date = match_date
                                    
                                    # Ensure event_start_date is also a datetime
                                    if isinstance(event_start_date, str):
                                        if 'T' in event_start_date:
                                            event_date = datetime.fromisoformat(event_start_date.replace('Z', '+00:00'))
                                        else:
                                            event_date = datetime.strptime(event_start_date, '%Y-%m-%d %H:%M:%S')
                                    else:
                                        event_date = event_start_date
                                    
                                    if parsed_date < event_date:
                                        filtered_matches.append(match)
                                except (ValueError, TypeError) as e:
                                    # If date parsing fails, include the match (safer approach)
                                    logger.warning(f"Could not parse match date {match_date}: {e}")
                                    filtered_matches.append(match)
                        all_matches[season] = filtered_matches
                    else:
                        all_matches[season] = season_matches
            
            # Calculate EPA based on matches
            historical_epa = await self.calculate_historical_epa(all_matches, team_number)
            
            # Calculate current season EPA
            current_season_epa = 0.0
            if 2024 in all_matches:
                current_season_epa = await self.calculate_season_epa(all_matches[2024], team_number)
            
            # Calculate performance metrics
            metrics = await self.calculate_performance_metrics(all_matches, team_number)
            
            epa_data = {
                'historicalEPA': historical_epa,
                'currentSeasonEPA': current_season_epa,
                'seasonEPAs': {
                    season: await self.calculate_season_epa(matches, team_number) 
                    for season, matches in all_matches.items()
                },
                'totalMatches': sum(len(matches) for matches in all_matches.values()),
                'recentMatches': len(all_matches.get(2024, [])),
                'avgAutoPoints': metrics.get('avgAutoPoints', 0.0),
                'avgTeleopPoints': metrics.get('avgTeleopPoints', 0.0),
                'avgEndgamePoints': metrics.get('avgEndgamePoints', 0.0),
                'calculationVersion': '1.0',
                'dataQuality': 'good',
                'lastMatchDate': await self.get_last_match_date(all_matches)
            }
            
            calculation_time = time.time() - start_time
            logger.info(f"EPA calculation completed for team {team_number}: {historical_epa} (took {calculation_time:.2f}s)")
            return epa_data
            
        except Exception as e:
            calculation_time = time.time() - start_time
            logger.error(f"Error calculating EPA for team {team_number}: {str(e)} (took {calculation_time:.2f}s)")
            return {
                'historicalEPA': 0.0,
                'currentSeasonEPA': 0.0,
                'seasonEPAs': {},
                'totalMatches': 0,
                'recentMatches': 0,
                'avgAutoPoints': 0.0,
                'avgTeleopPoints': 0.0,
                'avgEndgamePoints': 0.0,
                'calculationVersion': '1.0',
                'dataQuality': 'poor',
                'lastMatchDate': None
            }

    async def calculate_historical_epa(self, all_matches: Dict[int, List[Dict]], team_number: int) -> float:
        """Calculate historical EPA across all seasons"""
        if not all_matches:
            return 0.0
        
        total_weighted_epa = 0.0
        total_weight = 0.0
        
        for season, matches in all_matches.items():
            if not matches:
                continue
                
            season_epa = await self.calculate_season_epa(matches, team_number)
            weight = self.year_weights.get(season, 0.1)
            
            total_weighted_epa += season_epa * weight
            total_weight += weight
        
        return total_weighted_epa / total_weight if total_weight > 0 else 0.0

    async def calculate_season_epa(self, matches: List[Dict], team_number: int) -> float:
        """Calculate EPA for a specific season"""
        if not matches:
            return 0.0
        
        total_epa = 0.0
        valid_matches = 0
        
        for match in matches:
            match_epa = await self.calculate_match_epa(match, team_number)
            if match_epa > 0:
                total_epa += match_epa
                valid_matches += 1
        
        return total_epa / valid_matches if valid_matches > 0 else 0.0

    async def calculate_match_epa(self, match: Dict, team_number: int) -> float:
        """Calculate EPA contribution from a single match"""
        try:
            # Check for team-match record format first (our current data structure)
            red_teams = match.get('redTeams', [])
            blue_teams = match.get('blueTeams', [])
            
            # Convert team numbers to integers for comparison
            team_number_int = int(team_number)
            red_teams_int = [int(float(t)) for t in red_teams if t is not None]
            blue_teams_int = [int(float(t)) for t in blue_teams if t is not None]
            
            # Find team's alliance using our data structure
            team_alliance = None
            if team_number_int in red_teams_int:
                team_alliance = 'Red'
            elif team_number_int in blue_teams_int:
                team_alliance = 'Blue'
            elif match.get('alliance') == 'red':
                team_alliance = 'Red'
            elif match.get('alliance') == 'blue':
                team_alliance = 'Blue'
            
            if not team_alliance:
                # Fallback to original format for compatibility
                for team_data in match.get('teams', []):
                    if team_data.get('teamNumber') == team_number:
                        team_alliance = 'Red' if 'Red' in team_data.get('station', '') else 'Blue'
                        break
                
                if not team_alliance:
                    return 0.0
            
            # Get scores from our data structure
            red_score = float(match.get('scoreRedFinal', 0))
            blue_score = float(match.get('scoreBlueFinal', 0))
            
            # Fallback to nested format if flat format not available
            if red_score == 0 and blue_score == 0:
                red_score = match.get('redScore', {}).get('totalPoints', 0)
                blue_score = match.get('blueScore', {}).get('totalPoints', 0)
            
            if red_score == 0 and blue_score == 0:
                return 0.0
            
            # Calculate team's alliance and opponent scores
            alliance_score = red_score if team_alliance == 'Red' else blue_score
            opponent_score = blue_score if team_alliance == 'Red' else red_score
            
            # Count teams in alliance (use our data structure)
            if team_alliance == 'Red':
                alliance_teams = len(red_teams_int)
            else:
                alliance_teams = len(blue_teams_int)
            
            # Fallback to original format if needed
            if alliance_teams == 0:
                alliance_teams = len([t for t in match.get('teams', []) 
                                    if ('Red' in t.get('station', '')) == (team_alliance == 'Red')])
            
            # Base contribution (split among alliance members)
            base_contribution = alliance_score / max(alliance_teams, 1)
            
            # Opponent strength adjustment
            opponent_strength = 1 + (opponent_score / max(alliance_score, 1))
            
            # Match type multiplier
            match_level = match.get('matchLevel', match.get('tournamentLevel', '')).lower()
            match_type_multiplier = 1.3 if 'playoff' in match_level or 'elimination' in match_level else 1.0
            
            # Calculate match EPA
            match_epa = base_contribution * opponent_strength * match_type_multiplier
            
            logger.debug(f"Match EPA calculation - Team {team_number} ({team_alliance}): "
                        f"Score {alliance_score} vs {opponent_score}, "
                        f"Teams {alliance_teams}, EPA {match_epa:.2f}")
            
            return match_epa
            
        except Exception as e:
            logger.warning(f"Error calculating match EPA for team {team_number}: {str(e)}")
            return 0.0

    async def calculate_performance_metrics(self, all_matches: Dict[int, List[Dict]], team_number: int) -> Dict[str, float]:
        """Calculate performance metrics across seasons"""
        total_auto = 0.0
        total_teleop = 0.0
        total_endgame = 0.0
        total_matches = 0
        
        for season, matches in all_matches.items():
            weight = self.year_weights.get(season, 0.1)
            
            for match in matches:
                # Find team's alliance using our data structure
                red_teams = match.get('redTeams', [])
                blue_teams = match.get('blueTeams', [])
                
                team_number_int = int(team_number)
                red_teams_int = [int(float(t)) for t in red_teams if t is not None]
                blue_teams_int = [int(float(t)) for t in blue_teams if t is not None]
                
                team_alliance = None
                if team_number_int in red_teams_int:
                    team_alliance = 'Red'
                elif team_number_int in blue_teams_int:
                    team_alliance = 'Blue'
                elif match.get('alliance') == 'red':
                    team_alliance = 'Red'
                elif match.get('alliance') == 'blue':
                    team_alliance = 'Blue'
                
                # Fallback to original format
                if not team_alliance:
                    for team_data in match.get('teams', []):
                        if team_data.get('teamNumber') == team_number:
                            team_alliance = 'Red' if 'Red' in team_data.get('station', '') else 'Blue'
                            break
                
                if not team_alliance:
                    continue
                
                # Get alliance score breakdown from our data structure
                if team_alliance == 'Red':
                    auto_points = float(match.get('scoreRedAuto', 0))
                    teleop_points = float(match.get('scoreRedTeleop', 0))
                    endgame_points = float(match.get('scoreRedEndgame', 0))
                    alliance_teams = len(red_teams_int)
                else:
                    auto_points = float(match.get('scoreBlueAuto', 0))
                    teleop_points = float(match.get('scoreBlueTeleop', 0))
                    endgame_points = float(match.get('scoreBlueEndgame', 0))
                    alliance_teams = len(blue_teams_int)
                
                # Fallback to original nested format if our format not available
                if auto_points == 0 and teleop_points == 0 and endgame_points == 0:
                    alliance_score = match.get('redScore' if team_alliance == 'Red' else 'blueScore', {})
                    auto_points = alliance_score.get('autoPoints', 0)
                    teleop_points = alliance_score.get('teleopPoints', 0)
                    endgame_points = alliance_score.get('endgamePoints', 0)
                
                # Fallback team count if needed
                if alliance_teams == 0:
                    alliance_teams = len([t for t in match.get('teams', []) 
                                        if ('Red' in t.get('station', '')) == (team_alliance == 'Red')])
                
                # Calculate per-team contribution
                if alliance_teams > 0:
                    total_auto += (auto_points / alliance_teams) * weight
                    total_teleop += (teleop_points / alliance_teams) * weight
                    total_endgame += (endgame_points / alliance_teams) * weight
                    total_matches += weight
        
        if total_matches > 0:
            return {
                'avgAutoPoints': total_auto / total_matches,
                'avgTeleopPoints': total_teleop / total_matches,
                'avgEndgamePoints': total_endgame / total_matches
            }
        else:
            return {
                'avgAutoPoints': 0.0,
                'avgTeleopPoints': 0.0,
                'avgEndgamePoints': 0.0
            }

    async def get_last_match_date(self, all_matches: Dict[int, List[Dict]]) -> Optional[str]:
        """Get the date of the last match played"""
        last_date = None
        
        for matches in all_matches.values():
            for match in matches:
                match_date = match.get('actualStartTime') or match.get('startTime')
                if match_date and (not last_date or match_date > last_date):
                    last_date = match_date
        
        return last_date

    async def calculate_match_win_probability(self, red_teams: List[int], blue_teams: List[int], 
                                           team_epas: Dict[str, float]) -> Dict[str, Any]:
        """Calculate win probability for a match"""
        try:
            # Calculate alliance EPAs
            red_epa = sum(team_epas.get(str(team), 0.0) for team in red_teams)
            blue_epa = sum(team_epas.get(str(team), 0.0) for team in blue_teams)
            
            # Calculate win probability using logistic function
            epa_diff = red_epa - blue_epa
            red_win_prob = 1 / (1 + math.exp(-epa_diff / self.k))
            blue_win_prob = 1 - red_win_prob
            
            # Predict scores based on EPAs
            predicted_red_score = max(0, red_epa + 50)  # Base score adjustment
            predicted_blue_score = max(0, blue_epa + 50)
            
            return {
                'redWinProbability': red_win_prob,
                'blueWinProbability': blue_win_prob,
                'predictedRedScore': predicted_red_score,
                'predictedBlueScore': predicted_blue_score,
                'redTotalEPA': red_epa,
                'blueTotalEPA': blue_epa,
                'confidenceLevel': min(0.95, abs(epa_diff) / 50)  # Higher confidence for larger EPA differences
            }
            
        except Exception as e:
            logger.error(f"Error calculating match win probability: {str(e)}")
            return {
                'redWinProbability': 0.5,
                'blueWinProbability': 0.5,
                'predictedRedScore': 0,
                'predictedBlueScore': 0,
                'redTotalEPA': 0,
                'blueTotalEPA': 0,
                'confidenceLevel': 0.0
            }

    async def batch_calculate_team_epas(self, team_numbers: List[int], 
                                      event_start_date: str = None) -> Dict[str, float]:
        """Calculate EPAs for multiple teams efficiently"""
        logger.info(f"Batch calculating EPAs for {len(team_numbers)} teams")
        
        # Check cache first
        cache_key = f"batch_epa:{':'.join(map(str, sorted(team_numbers)))}:{event_start_date or 'latest'}"
        cached_result = await self.db_service.get_cache(cache_key)
        
        if cached_result:
            logger.info("Returning cached EPA results")
            return cached_result
        
        # Calculate EPAs
        team_epas = {}
        
        # Process in batches to avoid memory issues
        batch_size = 10
        for i in range(0, len(team_numbers), batch_size):
            batch = team_numbers[i:i + batch_size]
            
            # Calculate EPAs for this batch
            batch_tasks = []
            for team_number in batch:
                batch_tasks.append(self.calculate_team_epa(team_number, event_start_date))
            
            # Wait for all calculations in this batch
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process results
            for team_number, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error calculating EPA for team {team_number}: {str(result)}")
                    team_epas[str(team_number)] = 0.0
                else:
                    team_epas[str(team_number)] = result.get('historicalEPA', 0.0)
                    
                    # Save individual EPA calculation
                    await self.db_service.save_epa_calculation(team_number, result)
        
        # Cache the results
        await self.db_service.set_cache(cache_key, team_epas, ttl_seconds=3600)  # 1 hour cache
        
        logger.info(f"Batch EPA calculation completed for {len(team_numbers)} teams")
        return team_epas

def lambda_handler(event, context):
    """Lambda handler for EPA calculations"""
    logger.info(f"EPA Calculator Lambda started with event: {json.dumps(event, default=str)}")
    
    try:
        # Initialize services
        logger.info(f"Initializing DynamoDB service with environment: {ENVIRONMENT}")
        db_service = DynamoDBService(ENVIRONMENT)
        epa_calculator = EPACalculator(db_service)
        
        # Parse the request
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '')
        body = event.get('body', '{}')
        
        if isinstance(body, str):
            body = json.loads(body)
        
        # Handle different EPA calculation requests
        if http_method == 'POST':
            if 'team-historical-epa' in path:
                # Single team EPA calculation
                team_number = body.get('teamNumber')
                event_start_date = body.get('eventStartDate')
                
                if not team_number:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({'error': 'teamNumber is required'})
                    }
                
                # Validate team number
                try:
                    team_number = int(team_number)
                    if team_number <= 0 or team_number > 999999:  # Reasonable bounds for FTC team numbers
                        raise ValueError("Team number out of range")
                except (ValueError, TypeError) as e:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({'error': f'Invalid teamNumber: must be a positive integer between 1 and 999999'})
                    }
                
                logger.info(f"Processing EPA calculation for team {team_number}")
                
                # Run the calculation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    epa_data = loop.run_until_complete(
                        epa_calculator.calculate_team_epa(team_number, event_start_date)
                    )
                    
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'teamNumber': team_number,
                            'historicalEPA': epa_data['historicalEPA'],
                            'epaData': epa_data
                        }, default=str)
                    }
                finally:
                    loop.close()
                    
            elif 'batch-historical-epa' in path:
                # Batch EPA calculation
                team_numbers = body.get('teamNumbers', [])
                event_start_date = body.get('eventStartDate')
                
                if not team_numbers:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({'error': 'teamNumbers array is required'})
                    }
                
                # Validate team numbers
                try:
                    validated_team_numbers = []
                    for team_num in team_numbers:
                        team_num = int(team_num)
                        if team_num <= 0 or team_num > 999999:
                            raise ValueError(f"Team number {team_num} out of range")
                        validated_team_numbers.append(team_num)
                    team_numbers = validated_team_numbers
                    
                    if len(team_numbers) > 100:  # Reasonable limit for batch processing
                        return {
                            'statusCode': 400,
                            'headers': {'Content-Type': 'application/json'},
                            'body': json.dumps({'error': 'Too many teams requested (maximum 100)'})
                        }
                        
                except (ValueError, TypeError) as e:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({'error': f'Invalid teamNumbers: all must be positive integers between 1 and 999999'})
                    }
                
                logger.info(f"Processing batch EPA calculation for {len(team_numbers)} teams")
                
                # Run the batch calculation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    team_epas = loop.run_until_complete(
                        epa_calculator.batch_calculate_team_epas(team_numbers, event_start_date)
                    )
                    
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'teamEPAs': team_epas
                        }, default=str)
                    }
                finally:
                    loop.close()
                    
            elif 'match-prediction' in path:
                # Match prediction
                red_teams = body.get('redTeams', [])
                blue_teams = body.get('blueTeams', [])
                team_epas = body.get('teamEpas', {})
                
                if not red_teams or not blue_teams:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({'error': 'redTeams and blueTeams are required'})
                    }
                
                # Run the prediction
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    prediction = loop.run_until_complete(
                        epa_calculator.calculate_match_win_probability(red_teams, blue_teams, team_epas)
                    )
                    
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'prediction': prediction
                        }, default=str)
                    }
                finally:
                    loop.close()
        
        # Handle GET requests for historical EPA
        elif http_method == 'GET':
            path_parts = path.split('/')
            if len(path_parts) >= 3 and path_parts[-1] == 'historical-epa':
                team_number = int(path_parts[-2])
                
                # Get from database
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    epa_data = loop.run_until_complete(
                        db_service.get_latest_epa(team_number)
                    )
                    
                    if epa_data:
                        return {
                            'statusCode': 200,
                            'headers': {'Content-Type': 'application/json'},
                            'body': json.dumps({
                                'teamNumber': team_number,
                                'historicalEPA': epa_data.get('historicalEPA', 0.0),
                                'epaData': epa_data
                            }, default=str)
                        }
                    else:
                        return {
                            'statusCode': 404,
                            'headers': {'Content-Type': 'application/json'},
                            'body': json.dumps({'error': 'EPA data not found for team'})
                        }
                finally:
                    loop.close()
        
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Invalid request'})
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        } 


# Synchronous wrapper for AWS Lambda (required since AWS doesn't support async handlers directly)
def handler(event, context):
    """Synchronous wrapper for the main lambda handler"""
    return lambda_handler(event, context) 