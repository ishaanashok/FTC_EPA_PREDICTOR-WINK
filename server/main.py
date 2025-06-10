# Remove the EPA-related imports and endpoint
from fastapi import FastAPI, HTTPException
import asyncio
import time

from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from dotenv import load_dotenv
import base64
from epa_calculator import EPACalculator
from epa_parallel import ParallelEPAProcessor
from alliance_matchmaker_fixed import AllianceMatchmaker
from utils.api_utils import ftc_api_request
from batch_epa_endpoint import process_batch_historical_epa

load_dotenv()

app = FastAPI(debug=True)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FTC API Configuration
FTC_API_BASE_URL = "https://ftc-api.firstinspires.org/v2.0"
FTC_USERNAME = os.getenv("FTC_API_USERNAME")
FTC_AUTH_KEY = os.getenv("FTC_API_KEY")

# Create authorization token
auth_string = f"{FTC_USERNAME}:{FTC_AUTH_KEY}"
AUTH_TOKEN = base64.b64encode(auth_string.encode()).decode()

# Remove the ftc_api_request function from main.py
# async def ftc_api_request(endpoint: str, params: dict | None = None):
#     headers = {
#         "Authorization": f"Basic {AUTH_TOKEN}",
#         "Content-Type": "application/json"
#     }
#     
#     async with httpx.AsyncClient() as client:
#         try:
#             response = await client.get(
#                 f"{FTC_API_BASE_URL}{endpoint}",
#                 headers=headers,
#                 params=params
#             )
#             response.raise_for_status()
#             return response.json()
#         except httpx.HTTPError as e:
#             if isinstance(e, httpx.HTTPStatusError):
#                 raise HTTPException(status_code=e.response.status_code, detail=str(e))
#             raise HTTPException(status_code=500, detail=str(e))

# Advancement endpoints
@app.get("/api/advancement/{season}/{eventCode}")
async def get_event_advancement(season: int, eventCode: str, excludeSkipped: bool = False):
    return await ftc_api_request(f"/{season}/advancement/{eventCode}", {"excludeSkipped": excludeSkipped})

@app.get("/api/advancement/{season}/{eventCode}/source")
async def get_advancement_source(season: int, eventCode: str, includeDeclines: bool = False):
    return await ftc_api_request(f"/{season}/advancement/{eventCode}/source", {"includeDeclines": includeDeclines})

# League endpoints
@app.get("/api/leagues/{season}")
async def get_leagues(season: int, regionCode: str | None = None, leagueCode: str | None = None):
    params = {"regionCode": regionCode, "leagueCode": leagueCode}
    return await ftc_api_request(f"/{season}/leagues", params)

@app.get("/api/leagues/{season}/members/{regionCode}/{leagueCode}")
async def get_league_members(season: int, regionCode: str, leagueCode: str):
    return await ftc_api_request(f"/{season}/leagues/members/{regionCode}/{leagueCode}")

@app.get("/api/leagues/{season}/rankings/{regionCode}/{leagueCode}")
async def get_league_rankings(season: int, regionCode: str, leagueCode: str):
    return await ftc_api_request(f"/{season}/leagues/rankings/{regionCode}/{leagueCode}")

# Season Data endpoints
@app.get("/api/season/{season}")
async def get_season_summary(season: int):
    return await ftc_api_request(f"/{season}")

@app.get("/api/events/{season}")
async def get_events(season: int, eventCode: str | None = None, teamNumber: int | None = None):
    params = {"eventCode": eventCode, "teamNumber": teamNumber}
    return await ftc_api_request(f"/{season}/events", params)

@app.get("/api/events/{season}/{eventCode}/rankings")
async def get_event_rankings(season: int, eventCode: str):
    return await ftc_api_request(f"/{season}/rankings/{eventCode}")

@app.get("/api/teams/{season}")
async def get_teams(
    season: int,
    teamNumber: int | None = None,
    eventCode: str | None = None,
    state: str | None = None,
    country: str | None = None,  # Added missing parameter
    page: int = 1
):
    params = {
        "teamNumber": teamNumber,
        "eventCode": eventCode,
        "state": state,
        "country": country,
        "page": page
    }
    return await ftc_api_request(f"/{season}/teams", params)

# Schedule endpoints
@app.get("/api/schedule/{season}/{eventCode}/{tournamentLevel}/hybrid")
async def get_hybrid_schedule(
    season: int,
    eventCode: str,
    tournamentLevel: str,
    start: int = 0,
    end: int = 999
):
    params = {"start": start, "end": end}
    return await ftc_api_request(
        f"/{season}/schedule/{eventCode}/{tournamentLevel}/hybrid",
        params
    )

@app.get("/api/schedule/{season}/{eventCode}")
async def get_event_schedule_v1(
    season: int,
    eventCode: str,
    tournamentLevel: str | None = None,
    teamNumber: int | None = None,
    start: int = 0,
    end: int = 999
):
    params = {
        "tournamentLevel": tournamentLevel,
        "teamNumber": teamNumber,
        "start": start,
        "end": end
    }
    return await ftc_api_request(f"/{season}/schedule/{eventCode}", params)

# Update path to match official API
from typing import Optional

@app.get("/api/matches/{season}/{eventCode}")
async def get_event_matches(
    season: int,
    eventCode: str,
    tournamentLevel: Optional[str] = None,
    teamNumber: Optional[int] = None,
    start: int = 0,
    end: int = 999
):
    params = {
        "tournamentLevel": tournamentLevel,
        "teamNumber": teamNumber,
        "start": start,
        "end": end
    }
    return await ftc_api_request(f"/{season}/matches/{eventCode}", params)

# Update schedule endpoint to match API
@app.get("/api/schedule/{season}/{eventCode}")
async def get_event_schedule(
    season: int,
    eventCode: str,
    tournamentLevel: str = "qual",
    teamNumber: Optional[int] = None,
    start: int = 0,
    end: int = 999
):
    params = {
        "tournamentLevel": tournamentLevel,
        "teamNumber": teamNumber,
        "start": start,
        "end": end
    }
    return await ftc_api_request(f"/{season}/schedule/{eventCode}", params)

@app.get("/api/teams/{teamNumber}/matches/{season}")
async def get_team_season_matches(season: int, teamNumber: int):
    try:
        # Get all events for the team in the season
        events_response = await ftc_api_request(f"/{season}/events", {"teamNumber": teamNumber})
        
        all_matches = []
        events_list = events_response.get("events", []) if events_response else []
        for event in events_list:
            # Get both qual and playoff matches for each event
            for tournament_level in ["qual", "playoff"]:
                try:
                    matches_response = await ftc_api_request(
                        f"/{season}/matches/{event['code']}", 
                        {
                            "tournamentLevel": tournament_level,
                            "teamNumber": teamNumber
                        }
                    )
                    
                    if matches_response is not None and matches_response.get("matches"):
                        # Add event context to each match
                        for match in matches_response["matches"]:
                            match["eventCode"] = event["code"]
                            match["eventName"] = event["name"]
                            match["tournamentLevel"] = tournament_level
                            all_matches.append(match)
                except Exception as e:
                    print(f"Error fetching {tournament_level} matches for event {event['code']}: {str(e)}")
                    continue

        return {"matches": all_matches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/teams/{teamNumber}/historical-matches")
async def get_team_historical_matches_v1(teamNumber: int):
    all_seasons_matches = {}
    current_season = 2024
    
    # Fetch data for recent seasons
    for season in range(2020, current_season + 1):
        try:
            season_matches = await get_team_season_matches(season, teamNumber)
            all_seasons_matches[season] = season_matches["matches"]
        except HTTPException as e:
            if e.status_code != 404:  # Ignore 404s for seasons without data
                raise e
            all_seasons_matches[season] = []
    
    return {"matches": all_seasons_matches}

@app.post("/api/event-predictions-epa")
async def get_event_predictions_epa(data: dict):
    try:
        season = data['season']
        event_code = data['eventCode']
        
        print(f"Processing request for season {season}, event {event_code}")
        
        # Get all initial data in parallel
        try:
            event_info, teams_data, matches_data = await asyncio.gather(
                ftc_api_request(f"/{season}/events", {"eventCode": event_code}),
                ftc_api_request(f"/{season}/teams", {"eventCode": event_code}),
                ftc_api_request(f"/{season}/matches/{event_code}"),
                return_exceptions=True
            )
            
            # Check for exceptions in gathered results
            for result in [event_info, teams_data, matches_data]:
                if isinstance(result, Exception):
                    raise result
                    
        except Exception as e:
            print(f"Error fetching initial data: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error fetching event data: {str(e)}")
        
        if teams_data is None or isinstance(teams_data, Exception):
            raise HTTPException(status_code=500, detail="Failed to fetch teams data")
        
        # Ensure teams_data is a dict before accessing 'get'
        if not isinstance(teams_data, dict):
            raise HTTPException(status_code=500, detail="Teams data is not a valid response")
        teams_list = teams_data.get('teams', [])
        print(f"Found {len(teams_list)} teams")
        
        try:
            # Get event start date
            if isinstance(event_info, dict) and event_info.get('events'):
                event_start_date = event_info['events'][0].get('dateStart')
            else:
                event_start_date = None
            
            # Initialize the parallel EPA processor
            epa_processor = ParallelEPAProcessor(concurrency_limit=50)
            
            # Extract team numbers from the teams list
            team_numbers = [team['teamNumber'] for team in teams_list]
            
            # Process all teams in parallel
            start_time = time.time()
            epa_results = await epa_processor.calculate_multiple_team_epas(team_numbers, event_start_date)
            total_time = time.time() - start_time
            print(f"Completed EPA calculations for all teams in {total_time:.2f} seconds")
            
            # Create EPA mapping
            team_epas = epa_processor.get_epa_mapping(epa_results)
            print(f"Calculated EPAs for {len(team_epas)} teams")
            
            # Calculate predictions for all matches in parallel
            matches_list = []
            if isinstance(matches_data, dict):
                matches_list = matches_data.get('matches', [])
            else:
                matches_list = []
            predictions = await epa_processor.calculate_match_predictions(
                matches_list,
                team_epas
            )
                
        except Exception as e:
            print(f"Error processing team EPAs or predictions: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error calculating team EPAs or match predictions: {str(e)}")
        
        return {
            'eventDetails': event_info,
            'teams': teams_data.get('teams', []),
            'matches': matches_data.get('matches', []) if isinstance(matches_data, dict) else [],
            'teamEPAs': team_epas,
            'predictions': predictions
        }
        
    except Exception as e:
        print(f"Unexpected error in get_event_predictions_epa: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/teams/{teamNumber}/historical-matches")
async def get_team_historical_matches(teamNumber: int):
    all_seasons_matches = {}
    
    # Fetch data from 2020 to 2024
    for season in range(2020, 2025):
        try:
            season_matches = await get_team_season_matches(season, teamNumber)
            all_seasons_matches[season] = season_matches["matches"]
        except HTTPException as e:
            if e.status_code != 404:  # Ignore 404s for seasons without data
                raise e
            all_seasons_matches[season] = []
    
    return {"matches": all_seasons_matches}

@app.get("/api/teams/{teamNumber}/historical-epa")
async def get_team_historical_epa(teamNumber: int):
    try:
        # Use the parallel processor for individual team calculations as well
        epa_processor = ParallelEPAProcessor()
        result = await epa_processor.calculate_team_epa(teamNumber)
        return {"teamNumber": teamNumber, "historicalEPA": result["historicalEPA"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/match-prediction")
async def get_match_prediction(data: dict):
    try:
        calculator = EPACalculator()
        prediction = calculator.calculate_match_win_probability(
            data['redTeams'], 
            data['blueTeams'], 
            data['teamEpas']
        )
        
        return {
            "season": data['season'],
            "eventCode": data['eventCode'],
            "matchNumber": data['matchNumber'],
            "redTeams": data['redTeams'],
            "blueTeams": data['blueTeams'],
            "prediction": prediction
        }
    except Exception as e:
        print(f"Error in match prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/teams/batch-historical-epa")
async def get_batch_historical_epa(data: dict):
    """
    Process multiple team EPAs in a single batch request.
    
    Expects a JSON with the following structure:
    {
        "teamNumbers": [team1, team2, team3, ...]
    }
    
    Returns a dictionary mapping team numbers to their EPA values.
    """
    try:
        team_numbers = data.get('teamNumbers', [])
        if not team_numbers:
            raise HTTPException(status_code=400, detail="No team numbers provided")
        
        print(f"Processing batch EPA request for {len(team_numbers)} teams")
        
        # Use our parallel processor to efficiently calculate all team EPAs
        epa_processor = ParallelEPAProcessor(concurrency_limit=50)
        
        start_time = time.time()
        epa_results = await epa_processor.calculate_multiple_team_epas(team_numbers)
        total_time = time.time() - start_time
        print(f"Completed batch EPA calculations for {len(team_numbers)} teams in {total_time:.2f} seconds")
        
        # Create EPA mapping
        team_epas = epa_processor.get_epa_mapping(epa_results)
        
        return {"teamEPAs": team_epas}
    except Exception as e:
        print(f"Error in batch EPA calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Alliance matchmaking endpoint
@app.post("/api/alliance-matchup")
async def create_alliance_matchup(data: dict):
    """
    Create an alliance matchup for a given event and season.
    
    Expects a JSON with the following structure:
    {
        "season": 2024,
        "eventCode": "exampleEventCode",
        "teams": [
            {"teamNumber": 1234, "allianceColor": "red"},
            {"teamNumber": 5678, "allianceColor": "blue"}
        ]
    }
    
    Returns the created matchup details.
    """
    try:
        matchmaker = AllianceMatchmaker()
        # If create_matchup does not exist, use find_best_alliance_partner or another appropriate method
        # Example using find_best_alliance_partner (update arguments as needed):
        result = await matchmaker.find_best_alliance_partner(
            data['teams'][0]['teamNumber'],  # Example: use the first team's number
            [team['teamNumber'] for team in data['teams']],
            {},  # Provide team_epas if available
            {}   # Provide team_matches if available
        )
        return result
    except Exception as e:
        print(f"Error in alliance matchup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/alliance-matchmaker")
async def find_alliance_match(data: dict):
    """
    Find the best alliance partner for a team at an event based on complementary strengths and EPAs.
    
    Expected request body:
    {
        "season": 2024,
        "eventCode": "USMACMP",
        "teamNumber": 12345
    }
    """
    try:
        season = data.get('season')
        event_code = data.get('eventCode')
        team_number = data.get('teamNumber')
        
        if not all([season, event_code, team_number]):
            raise HTTPException(status_code=400, detail="Missing required parameters")
        
        # Get event data including teams and EPAs
        event_data = None
        try:
            # First check if we can use the existing event predictions endpoint
            event_data = await get_event_predictions_epa({"season": season, "eventCode": event_code})
            teams_list = event_data.get('teams', [])
            team_epas = event_data.get('teamEPAs', {})
        except Exception as e:
            # If we can't get event predictions, fetch teams directly
            print(f"Could not use event predictions: {e}")
            event_response = await ftc_api_request(f"/{season}/teams", {"eventCode": event_code})
            if event_response is not None and isinstance(event_response, dict):
                teams_list = event_response.get('teams', [])
            else:
                teams_list = []
            
            # We need EPAs for these teams
            epa_processor = ParallelEPAProcessor(concurrency_limit=50)
            team_numbers = [team['teamNumber'] for team in teams_list]
            epa_results = await epa_processor.calculate_multiple_team_epas(team_numbers)
            team_epas = epa_processor.get_epa_mapping(epa_results)
        
        # Get historical matches for all teams
        matchmaker = AllianceMatchmaker()
        team_matches = {}

        # Use ParallelEPAProcessor directly for EPA calculations
        epa_processor = ParallelEPAProcessor(concurrency_limit=50)
        
        # First get matches for the input team
        try:
            if team_number is None or not isinstance(team_number, int):
                raise HTTPException(status_code=400, detail="Invalid team number provided")
            input_team_matches_response = await epa_processor.calculate_team_epa(team_number)
            team_matches[team_number] = input_team_matches_response.get('matches', {})
        except Exception as e:
            print(f"Error fetching matches for team {team_number}: {str(e)}")
            team_matches[team_number] = {}
        
        # Get matches for other teams in the event
        team_numbers = [team['teamNumber'] for team in teams_list]
        for other_team in team_numbers[:20]:  # Limit to 20 teams to avoid overloading
            if other_team != team_number:
                try:
                    team_response = await epa_processor.calculate_team_epa(other_team)
                    team_matches[other_team] = team_response.get('matches', {})
                except Exception as e:
                    print(f"Error fetching matches for team {other_team}: {str(e)}")
                    team_matches[other_team] = {}
        
        # Ensure team_number is a valid int before calling find_best_alliance_partner
        if team_number is None or not isinstance(team_number, int):
            raise HTTPException(status_code=400, detail="Invalid team number provided")
        # Find the best alliance match
        result = await matchmaker.find_best_alliance_partner(
            team_number, 
            team_numbers,
            team_epas,
            team_matches
        )
        
        return result
        
    except Exception as e:
        print(f"Error in alliance matchmaker: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/alliance-matchmaker/batch")
async def find_alliance_matches_batch(data: dict):
    """
    Find the best alliance partners for multiple teams at an event in parallel
    based on complementary strengths and EPAs.
    """
    try:
        season = data.get('season')
        event_code = data.get('eventCode')
        team_numbers = data.get('teamNumbers')
        provided_team_epas = data.get('teamEPAs')  # Accept precomputed EPAs from frontend
        if not all([season, event_code, team_numbers]) or not isinstance(team_numbers, list):
            raise HTTPException(status_code=400, detail="Missing required parameters or teamNumbers is not a list")
        # Get event data including teams and EPAs
        try:
            event_data = await get_event_predictions_epa({"season": season, "eventCode": event_code})
            teams_list = event_data.get('teams', [])
            team_epas = event_data.get('teamEPAs', {})
            event_start_date = event_data.get('eventDetails', {}).get('events', [{}])[0].get('dateStart', None)
        except Exception as e:
            print(f"Could not use event predictions: {e}")
            event_response = await ftc_api_request(f"/{season}/teams", {"eventCode": event_code})
            if event_response is not None and isinstance(event_response, dict):
                teams_list = event_response.get('teams', [])
            else:
                teams_list = []
            epa_processor = ParallelEPAProcessor(concurrency_limit=50)
            all_team_numbers = [team['teamNumber'] for team in teams_list]
            epa_results = await epa_processor.calculate_multiple_team_epas(all_team_numbers)
            team_epas = epa_processor.get_epa_mapping(epa_results)
            event_start_date = None
        # Merge provided EPAs with backend-calculated ones, prefer provided
        if provided_team_epas:
            team_epas.update({str(k): v for k, v in provided_team_epas.items()})
        matchmaker = AllianceMatchmaker()
        epa_processor = ParallelEPAProcessor(concurrency_limit=50)
        all_event_team_numbers = [team['teamNumber'] for team in teams_list]
        # Only calculate matches for all teams, not EPA again
        all_needed_teams = list(set(team_numbers) | set(all_event_team_numbers))
        all_team_results = await epa_processor.calculate_multiple_team_epas(all_needed_teams, event_start_date)
        team_matches = {result['teamNumber']: result.get('matches', {}) for result in all_team_results}
        results = {}
        partner_tasks = [matchmaker.find_best_alliance_partner(
            team_num,
            all_event_team_numbers,
            team_epas,
            team_matches
        ) for team_num in team_numbers]
        partner_results = await asyncio.gather(*partner_tasks)
        for i, team_num in enumerate(team_numbers):
            results[team_num] = partner_results[i]
        return results
    except Exception as e:
        print(f"Error in batch alliance matchmaker: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
