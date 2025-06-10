import os
from dotenv import load_dotenv
import base64
import asyncio
import httpx
import math
import time
import traceback
from typing import Optional
from fastapi import HTTPException
from utils.api_utils import ftc_api_request

class EPACalculator:
    def __init__(self):
        self.year_weights = {
            2024: 1.0,
            2023: 0.7,
            2022: 0.5
        }
        self.k = 12  # EPA scaling factor for win probability

    async def get_team_matches(self, team_number: int, start_date: Optional[str] = None) -> dict:
        print(f"[EPA DEBUG] Fetching matches for team {team_number}")
        all_matches = {}
        
        # Only fetch from 2022 onwards as older data seems unreliable
        for season in range(2022, 2025):
            try:
                # Fetch events for the season with increased limit
                events_response = await ftc_api_request(f"/{season}/events", {
                    "teamNumber": team_number,
                    "limit": 50  # Increase limit to reduce pagination
                })
                
                if not events_response or not isinstance(events_response, dict):
                    print(f"Invalid or empty response for season {season}")
                    continue

                events = events_response.get("events", [])
                if not events:
                    print(f"No events found for team {team_number} in season {season}")
                    continue

                # Prepare parallel requests for qualification matches only
                match_tasks = []
                for event in events:
                    if not event or not isinstance(event, dict):
                        print(f"Skipping invalid event data in season {season}")
                        continue

                    event_code = event.get('code')
                    if not event_code:
                        print(f"Skipping event with missing code in season {season}")
                        continue
                        
                    event_date = event.get('dateStart', '')
                    if not event_date:
                        print(f"No start date for event {event_code}, using default future date")
                        event_date = '9999-99-99'
                    else:
                        event_date = event_date[:10]
                    
                    try:
                        event_year = int(event_date[:4])
                    except (ValueError, TypeError):
                        print(f"Invalid date format for event {event_code}: {event_date}")
                        continue

                    if event_year < season:
                        print(f"Skipping event {event_code} as event year {event_year} is less than season {season}")
                        continue

                    if start_date and event_date > start_date[:10]:
                        print(f"Skipping event {event_code} as event date {event_date} is after start_date {start_date[:10]}")
                        continue
                        
                    print(f"Requesting matches for team {team_number} at event {event_code} in season {season}")
                    start_time = time.time()
                    
                    match_tasks.append({
                        'event': event,
                        'task': ftc_api_request(
                            f"/{season}/matches/{event_code}", 
                            {
                                "tournamentLevel": "qual",
                                "teamNumber": team_number,
                                "limit": 100  # Increase limit to reduce pagination
                            }
                        ),
                        'start_time': start_time
                    })
                
                if not match_tasks:
                    print(f"No valid events found for team {team_number} in season {season}")
                    continue
                
                print(f"Processing {len(match_tasks)} events for team {team_number} in season {season}")
                # Lower concurrency limit to avoid API timeouts
                concurrency_limit = 10  # Lowered from 10000 for reliability
                
                # Group tasks into chunks of concurrency_limit size
                async def process_chunk(chunk):
                    return await asyncio.gather(*[task['task'] for task in chunk], return_exceptions=True)
                
                chunks = [match_tasks[i:i + concurrency_limit] for i in range(0, len(match_tasks), concurrency_limit)]
                all_results = []
                
                for chunk in chunks:
                    chunk_results = await process_chunk(chunk)
                    all_results.extend(chunk_results)
                
                match_results = all_results
                
                # Process results and filter for Qualification matches
                season_matches = []
                for result, task_info in zip(match_results, match_tasks):
                    end_time = time.time()
                    response_time = end_time - task_info['start_time']
                    event_code = task_info['event'].get('code', 'unknown')
                    
                    if isinstance(result, Exception) or not isinstance(result, dict):
                        print(f"Error fetching matches for event {event_code}: {str(result)}")
                        continue
                    
                    print(f"Received response for event {event_code} in {response_time:.2f} seconds")
                    
                    matches = result.get("matches", [])
                    if not matches:
                        print(f"No matches found for event {event_code}")
                        continue

                    match_count = 0
                    for match in matches:
                        if not match or not isinstance(match, dict):
                            continue
                        if match.get('tournamentLevel', '').upper() == "QUALIFICATION":
                            match["eventCode"] = task_info['event'].get('code')
                            match["eventName"] = task_info['event'].get('name')
                            season_matches.append(match)
                            match_count += 1
                    
                    print(f"Added {match_count} qualification matches from event {event_code}")
                
                if season_matches:
                    print(f"Total {len(season_matches)} matches found for season {season}")
                    all_matches[season] = season_matches
                else:
                    print(f"No qualification matches found for season {season}")
                
            except Exception as e:
                import traceback
                print(f"Error processing season {season}: {str(e)}")
                traceback.print_exc()
                continue
        
        return all_matches

    def calculate_match_epa(self, match: dict, team_number: int) -> float:
        try:
            # Find team's alliance from the teams array
            team_data = next(
                (team for team in match.get('teams', []) 
                if str(team.get('teamNumber')) == str(team_number)),
                None
            )
            
            if not team_data:
                return 0.0

            # Determine alliance color from station
            is_red = 'Red' in team_data['station']
            
            # Get alliance and opponent scores
            alliance_score = match.get('scoreRedFinal', 0) if is_red else match.get('scoreBlueFinal', 0)
            opponent_score = match.get('scoreBlueFinal', 0) if is_red else match.get('scoreRedFinal', 0)

            if alliance_score == 0 and opponent_score == 0:
                return 0.0

            # Count teams in alliance
            alliance_teams = len([t for t in match.get('teams', []) if ('Red' in t['station']) == is_red])
            
            # Base contribution (split among alliance members)
            base_contribution = alliance_score / alliance_teams

            # Opponent strength adjustment (normalized to typical match scores)
            opponent_strength = 1 + (opponent_score / max(alliance_score, 1))

            # Match type multiplier
            match_type = 1.3 if match.get('tournamentLevel', '').lower() == 'playoff' else 1.0

            # Calculate match EPA
            match_epa = base_contribution * opponent_strength * match_type

            return match_epa

        except Exception as e:
            print(f"Error calculating match EPA: {e}")
            return 0.0

    def calculate_season_epa(self, matches: list, team_number: int) -> float:
        if not matches:
            return 0.0

        match_epas = []
        for match in matches:
            match_epa = self.calculate_match_epa(match, team_number)
            if match_epa > 0:
                match_epas.append(match_epa)

        if not match_epas:
            return 0.0

        # Calculate average EPA for the season
        # More recent matches within a season are weighted slightly higher
        weights = [1.0 + (i / len(match_epas) * 0.2) for i in range(len(match_epas))]
        weighted_sum = sum(epa * weight for epa, weight in zip(match_epas, weights))
        total_weight = sum(weights)

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def calculate_historical_epa(self, all_matches: dict, team_number) -> float:
        print(f"[EPA DEBUG] Calculating historical EPA for team {team_number}")
        if not all_matches:
            return 0.0

        weighted_sum = 0.0
        total_weight = 0.0

        for season, matches in all_matches.items():
            try:
                season_year = int(season)
                if season_year in self.year_weights:
                    season_epa = self.calculate_season_epa(matches, team_number)
                    year_weight = self.year_weights[season_year]
                    weighted_sum += season_epa * year_weight
                    total_weight += year_weight
            except ValueError:
                continue

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def calculate_match_win_probability(self, red_alliance: list, blue_alliance: list, team_epas: dict) -> dict:
        try:
            # Sum EPA scores for each alliance
            red_epa = sum(team_epas.get(str(team), 0.0) for team in red_alliance)
            blue_epa = sum(team_epas.get(str(team), 0.0) for team in blue_alliance)
            print(f"Red EPA: {red_epa}, Blue EPA: {blue_epa}")
            
            # Calculate EPA difference (ΔEPA)
            epa_diff = red_epa - blue_epa
            
            # Calculate win probability using the formula: 1/(1 + 10^(-ΔEPA/400))
            red_win_prob = 1 / (1 + math.pow(10, -epa_diff/400))
            blue_win_prob = 1 - red_win_prob
            
            # Determine winner and color styling
            predicted_winner = 'Red' if red_win_prob > 0.5 else 'Blue'
            winner_color = '#fee2e2' if predicted_winner == 'Red' else '#dbeafe'  # Light red or light blue from theme
            
            return {
                'red_win_probability': round(red_win_prob, 3),
                'blue_win_probability': round(blue_win_prob, 3),
                'predicted_winner': predicted_winner,
                'winner_color': winner_color,
                'win_margin': abs(epa_diff)
            }
        except Exception as e:
            print(f"Error calculating match win probability: {e}")
            return {
                'red_win_probability': 0.5,
                'blue_win_probability': 0.5,
                'predicted_winner': 'Tie',
                'winner_color': '#ffffff',  # White for tie
                'win_margin': 0
            }
