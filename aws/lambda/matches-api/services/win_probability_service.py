import boto3
import json
import logging
import math
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class WinProbabilityService:
    """Service for calculating match win probabilities using pre-calculated EPA values"""
    
    def __init__(self, environment: str = 'stage'):
        self.dynamodb = boto3.resource('dynamodb')
        self.environment = environment
        
        # Initialize tables
        self.epa_table = self.dynamodb.Table(f'FTC_EPA_{environment}')
        self.matches_table = self.dynamodb.Table(f'FTC_Matches_{environment}')
        
        # EPA scaling factor for win probability calculation
        self.k = 400  # Standard ELO scaling factor
    
    def convert_from_dynamodb_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB item to regular Python types"""
        def convert_value(value):
            if isinstance(value, Decimal):
                return float(value)
            elif isinstance(value, dict):
                return {k: convert_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [convert_value(v) for v in value]
            return value
        
        return convert_value(item)
    
    async def get_latest_team_epa(self, team_number: int) -> Optional[float]:
        """Get the latest EPA value for a team from the FTC_EPA_stage table"""
        try:
            # Convert to Decimal for DynamoDB query
            team_decimal = Decimal(str(int(team_number)))
            
            # Query for the most recent EPA entry for this team
            response = self.epa_table.query(
                KeyConditionExpression=Key('teamNumber').eq(team_decimal),
                ScanIndexForward=False,  # Sort in descending order by calculationDate
                Limit=1
            )
            
            items = response.get('Items', [])
            if items:
                epa_record = self.convert_from_dynamodb_item(items[0])
                # Try different EPA field names that might exist
                epa_value = (epa_record.get('currentSeasonEPA') or 
                           epa_record.get('historicalEPA') or
                           epa_record.get('epaValue') or
                           epa_record.get('epa', 0.0))
                return float(epa_value)
            
            logger.warning(f"No EPA data found for team {team_number}")
            return 0.0  # Default EPA if no data found
            
        except Exception as e:
            logger.error(f"Error getting EPA for team {team_number}: {str(e)}")
            return 0.0
    
    async def batch_get_team_epas(self, team_numbers: List[int]) -> Dict[str, float]:
        """Get EPA values for multiple teams efficiently"""
        team_epas = {}
        
        try:
            # Use batch_get_item for efficient retrieval
            batch_keys = []
            for team_number in team_numbers:
                # We need to get the latest EPA for each team
                # Since we can't easily do this with batch_get_item, we'll query each individually
                # This could be optimized further if needed
                epa_value = await self.get_latest_team_epa(team_number)
                team_epas[str(team_number)] = epa_value
            
            logger.info(f"Retrieved EPA values for {len(team_epas)} teams")
            return team_epas
            
        except Exception as e:
            logger.error(f"Error in batch EPA retrieval: {str(e)}")
            # Return default EPAs for all teams
            return {str(team): 0.0 for team in team_numbers}
    
    def calculate_win_probability(self, red_teams: List[int], blue_teams: List[int], 
                                 team_epas: Dict[str, float]) -> Dict[str, Any]:
        """Calculate win probability for a match using alliance EPA totals"""
        try:
            # Calculate total EPA for each alliance
            red_total_epa = sum(team_epas.get(str(team), 0.0) for team in red_teams)
            blue_total_epa = sum(team_epas.get(str(team), 0.0) for team in blue_teams)
            
            # Calculate EPA difference
            epa_diff = red_total_epa - blue_total_epa
            
            # Calculate win probability using logistic function: 1 / (1 + 10^(-diff/k))
            # This is the standard ELO win probability formula
            red_win_prob = 1 / (1 + math.pow(10, -epa_diff / self.k))
            blue_win_prob = 1 - red_win_prob
            
            # Calculate confidence level based on EPA difference magnitude
            # Higher EPA differences lead to higher confidence
            max_meaningful_diff = 200  # EPA difference that gives ~95% confidence
            confidence = min(0.95, abs(epa_diff) / max_meaningful_diff * 0.95)
            
            # Predict scores (basic model - can be enhanced)
            # Using alliance EPA as a predictor with some baseline scoring
            baseline_score = 50  # Baseline points teams tend to score
            red_predicted_score = max(0, baseline_score + (red_total_epa / len(red_teams) * 0.5))
            blue_predicted_score = max(0, baseline_score + (blue_total_epa / len(blue_teams) * 0.5))
            
            # Determine predicted winner
            predicted_winner = 'Red' if red_win_prob > 0.5 else 'Blue'
            if abs(red_win_prob - 0.5) < 0.01:  # Very close match
                predicted_winner = 'Toss-up'
            
            return {
                'redWinProbability': round(red_win_prob, 4),
                'blueWinProbability': round(blue_win_prob, 4),
                'predictedRedScore': round(red_predicted_score, 1),
                'predictedBlueScore': round(blue_predicted_score, 1),
                'redTotalEPA': round(red_total_epa, 2),
                'blueTotalEPA': round(blue_total_epa, 2),
                'epaDifference': round(epa_diff, 2),
                'confidenceLevel': round(confidence, 3),
                'predictedWinner': predicted_winner,
                'calculatedAt': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating win probability: {str(e)}")
            return {
                'redWinProbability': 0.5,
                'blueWinProbability': 0.5,
                'predictedRedScore': 0.0,
                'predictedBlueScore': 0.0,
                'redTotalEPA': 0.0,
                'blueTotalEPA': 0.0,
                'epaDifference': 0.0,
                'confidenceLevel': 0.0,
                'predictedWinner': 'Unknown',
                'error': str(e),
                'calculatedAt': datetime.now(timezone.utc).isoformat()
            }
    
    async def add_win_probability_to_match(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """Add win probability data to a single match"""
        try:
            # Extract team information from match
            red_teams = match.get('redTeams', [])
            blue_teams = match.get('blueTeams', [])
            
            if not red_teams or not blue_teams:
                logger.warning(f"Match {match.get('matchId', 'unknown')} missing team data")
                return match
            
            # Get all team numbers involved
            all_teams = red_teams + blue_teams
            
            # Get EPA values for all teams
            team_epas = await self.batch_get_team_epas(all_teams)
            
            # Calculate win probability
            win_prob_data = self.calculate_win_probability(red_teams, blue_teams, team_epas)
            
            # Add win probability data to match
            enhanced_match = match.copy()
            enhanced_match.update({
                'winProbability': win_prob_data,
                'teamEPAs': team_epas
            })
            
            return enhanced_match
            
        except Exception as e:
            logger.error(f"Error adding win probability to match: {str(e)}")
            return match
    
    async def add_win_probability_to_matches(self, matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add win probability data to multiple matches efficiently"""
        try:
            enhanced_matches = []
            
            # Collect all unique team numbers from all matches
            all_team_numbers = set()
            for match in matches:
                red_teams = match.get('redTeams', [])
                blue_teams = match.get('blueTeams', [])
                all_team_numbers.update(red_teams + blue_teams)
            
            # Batch get EPA values for all teams
            logger.info(f"Getting EPA values for {len(all_team_numbers)} unique teams")
            team_epas = await self.batch_get_team_epas(list(all_team_numbers))
            
            # Calculate win probabilities for each match
            for match in matches:
                try:
                    red_teams = match.get('redTeams', [])
                    blue_teams = match.get('blueTeams', [])
                    
                    if red_teams and blue_teams:
                        # Calculate win probability using pre-fetched EPA data
                        win_prob_data = self.calculate_win_probability(red_teams, blue_teams, team_epas)
                        
                        # Add win probability data to match
                        enhanced_match = match.copy()
                        enhanced_match.update({
                            'winProbability': win_prob_data,
                            'teamEPAs': {str(team): team_epas.get(str(team), 0.0) 
                                        for team in red_teams + blue_teams}
                        })
                        enhanced_matches.append(enhanced_match)
                    else:
                        # No team data, add match without win probability
                        enhanced_matches.append(match)
                        
                except Exception as e:
                    logger.error(f"Error processing individual match: {str(e)}")
                    enhanced_matches.append(match)
            
            logger.info(f"Enhanced {len(enhanced_matches)} matches with win probability data")
            return enhanced_matches
            
        except Exception as e:
            logger.error(f"Error adding win probability to matches: {str(e)}")
            return matches
    
    async def calculate_single_match_prediction(self, red_teams: List[int], blue_teams: List[int]) -> Dict[str, Any]:
        """Calculate win probability for a hypothetical match (e.g., for alliance selection)"""
        try:
            # Get EPA values for all teams
            all_teams = red_teams + blue_teams
            team_epas = await self.batch_get_team_epas(all_teams)
            
            # Calculate and return win probability
            return self.calculate_win_probability(red_teams, blue_teams, team_epas)
            
        except Exception as e:
            logger.error(f"Error calculating single match prediction: {str(e)}")
            return {
                'redWinProbability': 0.5,
                'blueWinProbability': 0.5,
                'predictedRedScore': 0.0,
                'predictedBlueScore': 0.0,
                'redTotalEPA': 0.0,
                'blueTotalEPA': 0.0,
                'epaDifference': 0.0,
                'confidenceLevel': 0.0,
                'predictedWinner': 'Unknown',
                'error': str(e),
                'calculatedAt': datetime.now(timezone.utc).isoformat()
            }
