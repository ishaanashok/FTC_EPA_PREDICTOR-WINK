from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
import json
from decimal import Decimal

class DynamoDBBaseModel(BaseModel):
    """Base model for DynamoDB items with common utilities"""
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert Pydantic model to DynamoDB item format"""
        try:
            # Use model_dump for Pydantic v2
            item = self.model_dump()
        except AttributeError:
            # Fallback to dict() for Pydantic v1
            item = self.dict()
        return self._convert_to_dynamodb_types(item)
    
    def _convert_to_dynamodb_types(self, obj: Any) -> Any:
        """Convert Python types to DynamoDB compatible types"""
        if obj is None:
            return None
        elif isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            # Filter out None values in dictionaries
            return {k: self._convert_to_dynamodb_types(v) for k, v in obj.items() if v is not None}
        elif isinstance(obj, list):
            return [self._convert_to_dynamodb_types(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return obj
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class Team(DynamoDBBaseModel):
    """Team model for FTC_Teams table"""
    # Primary Key
    teamNumber: int = Field(..., description="Team number")
    season: int = Field(..., description="Competition season")
    
    # Team Information
    teamName: str = Field("", description="Team name")
    schoolName: str = Field("", description="School name")
    city: str = Field("", description="City")
    state: str = Field("", description="State")
    country: str = Field("", description="Country")
    rookieYear: Optional[int] = Field(None, description="Rookie year")
    website: Optional[str] = Field(None, description="Team website")
    matchCount: int = Field(0, description="Matches played in season")
    
    # Metadata
    lastUpdated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # HTTP Caching Support
    lastModified: Optional[str] = Field(None, description="Last-Modified header from FTC API")
    etag: Optional[str] = Field(None, description="ETag from FTC API response")
    apiLastModified: Optional[datetime] = Field(None, description="Parsed Last-Modified timestamp")
    dataVersion: Optional[str] = Field(None, description="Data version for change tracking")

class Event(DynamoDBBaseModel):
    """Event model for FTC_Events table"""
    # Primary Key
    eventCode: str = Field(..., description="Event code")
    season: int = Field(..., description="Competition season")
    
    # Event Information
    eventName: str = Field("", description="Event name")
    eventType: str = Field("", description="Event type")
    dateStart: Optional[str] = Field(None, description="Event start date")
    dateEnd: Optional[str] = Field(None, description="Event end date")
    venue: Optional[str] = Field(None, description="Event venue")
    address: Optional[str] = Field(None, description="Event address")
    city: Optional[str] = Field(None, description="Event city")
    state: Optional[str] = Field(None, description="Event state")
    country: Optional[str] = Field(None, description="Event country")
    timezone: Optional[str] = Field(None, description="Event timezone")
    website: Optional[str] = Field(None, description="Event website")
    liveStreamUrl: Optional[str] = Field(None, description="Live stream URL")
    
    # Statistics
    teamCount: int = Field(0, description="Number of teams")
    matchCount: int = Field(0, description="Number of matches")
    teamNumbers: Optional[str] = Field(None, description="Comma-separated list of team numbers attending the event")
    
    # Metadata
    lastUpdated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # HTTP Caching Support
    lastModified: Optional[str] = Field(None, description="Last-Modified header from FTC API")
    etag: Optional[str] = Field(None, description="ETag from FTC API response")
    apiLastModified: Optional[datetime] = Field(None, description="Parsed Last-Modified timestamp")
    dataVersion: Optional[str] = Field(None, description="Data version for change tracking")
    matchesLastModified: Optional[str] = Field(None, description="Last-Modified for matches endpoint")
    rankingsLastModified: Optional[str] = Field(None, description="Last-Modified for rankings endpoint")

class MatchScore(DynamoDBBaseModel):
    """Match score breakdown"""
    alliance: str = Field(..., description="Alliance color (Red/Blue)")
    totalPoints: int = Field(0, description="Total points")
    autoPoints: int = Field(0, description="Autonomous points")
    teleopPoints: int = Field(0, description="Teleop points")
    endgamePoints: int = Field(0, description="Endgame points")
    penaltyPoints: int = Field(0, description="Penalty points")

class Match(DynamoDBBaseModel):
    """Match model for FTC_Matches table"""
    # Primary Key
    matchId: str = Field(..., description="Unique match ID: season-eventCode-tournamentLevel-series-matchNumber")
    
    # Match Information
    season: int = Field(..., description="Competition season")
    eventCode: str = Field(..., description="Event code")
    matchNumber: int = Field(..., description="Match number")
    description: str = Field("", description="Match description")
    tournamentLevel: str = Field("", description="Tournament level (qual, playoff)")
    series: Optional[int] = Field(None, description="Series number for playoffs")
    matchName: Optional[str] = Field(None, description="Match name")
    playNumber: Optional[int] = Field(None, description="Play number")
    fieldNumber: Optional[int] = Field(None, description="Field number")
    startTime: Optional[str] = Field(None, description="Scheduled start time")
    actualStartTime: Optional[str] = Field(None, description="Actual start time")
    postResultTime: Optional[str] = Field(None, description="Result post time")
    
    # Team information
    teams: Optional[List[Dict[str, Any]]] = Field(None, description="All teams with station assignments")
    redTeams: Optional[List[int]] = Field(None, description="Red alliance team numbers")
    blueTeams: Optional[List[int]] = Field(None, description="Blue alliance team numbers") 
    allTeams: Optional[List[int]] = Field(None, description="All team numbers in match")
    
    # Scores
    redScore: Optional[MatchScore] = Field(None, description="Red alliance score")
    blueScore: Optional[MatchScore] = Field(None, description="Blue alliance score")
    
    # Metadata
    lastUpdated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # HTTP Caching Support
    lastModified: Optional[str] = Field(None, description="Last-Modified header from FTC API")
    etag: Optional[str] = Field(None, description="ETag from FTC API response")
    apiLastModified: Optional[datetime] = Field(None, description="Parsed Last-Modified timestamp")
    dataVersion: Optional[str] = Field(None, description="Data version for change tracking")

class EPACalculation(DynamoDBBaseModel):
    """EPA calculation model for FTC_EPA table"""
    # Primary Key
    teamNumber: int = Field(..., description="Team number")
    calculationDate: str = Field(..., description="Calculation date (YYYY-MM-DD)")
    
    # EPA Values
    historicalEPA: float = Field(0.0, description="Historical EPA value")
    currentSeasonEPA: float = Field(0.0, description="Current season EPA")
    
    # Season-specific EPAs
    seasonEPAs: Dict[int, float] = Field(default_factory=dict, description="EPA by season")
    
    # Match statistics
    totalMatches: int = Field(0, description="Total matches played")
    recentMatches: int = Field(0, description="Recent matches (last 10)")
    
    # Performance metrics
    avgAutoPoints: float = Field(0.0, description="Average auto points contribution")
    avgTeleopPoints: float = Field(0.0, description="Average teleop points contribution")
    avgEndgamePoints: float = Field(0.0, description="Average endgame points contribution")
    
    # Calculation metadata
    calculationVersion: str = Field("1.0", description="EPA calculation version")
    dataQuality: str = Field("good", description="Data quality assessment")
    lastMatchDate: Optional[str] = Field(None, description="Last match date used")
    
    # Timestamps
    calculatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    isLatest: bool = Field(True, description="Is this the latest calculation")

class SyncStatus(DynamoDBBaseModel):
    """Sync status tracking with HTTP caching optimization"""
    # Primary Key
    syncKey: str = Field(..., description="Composite key: {syncType}#{season}")
    lastSyncTime: str = Field(..., description="Last successful sync time (ISO format)")
    
    # Sync metadata
    syncType: str = Field(..., description="Type of sync (teams, events, matches)")
    season: int = Field(..., description="Season")
    nextSyncTime: str = Field(..., description="Next scheduled sync time (ISO format)")
    status: str = Field("pending", description="Sync status (pending, in_progress, completed, failed)")
    errorMessage: Optional[str] = Field(None, description="Error message if failed")
    recordsProcessed: int = Field(0, description="Number of records processed")
    recordsUpdated: int = Field(0, description="Number of records updated")
    
    # HTTP Caching Support for FTC API optimization
    lastModifiedHeader: Optional[str] = Field(None, description="Last-Modified from API response")
    ifModifiedSinceUsed: Optional[str] = Field(None, description="If-Modified-Since sent in request")
    fmsOnlyModifiedSinceUsed: Optional[str] = Field(None, description="FMS-OnlyModifiedSince sent in request")
    etag: Optional[str] = Field(None, description="ETag from API response")
    dataChanged: bool = Field(True, description="Whether data was modified (not 304)")
    bandwidthSaved: int = Field(0, description="Bytes saved due to conditional requests")
    responseSize: int = Field(0, description="Response size in bytes")
    
    # FTC API specific fields
    apiEndpoint: Optional[str] = Field(None, description="FTC API endpoint called")
    eventCode: Optional[str] = Field(None, description="Event code for match-specific syncs")
    totalPages: Optional[int] = Field(None, description="Total pages in paginated response")
    currentPage: Optional[int] = Field(None, description="Current page processed")

# Utility functions for data conversion
def convert_ftc_api_team(api_team: Dict[str, Any], season: int) -> Team:
    """Convert FTC API team response to Team model with comprehensive None handling"""
    
    # Validate season parameter
    if season is None:
        raise ValueError("Invalid season parameter: season is None")
    
    try:
        season_int = int(season)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid season parameter: season '{season}' cannot be converted to int: {e}")
    
    # Validate and convert teamNumber
    team_number = api_team.get('teamNumber')
    if team_number is None:
        raise ValueError(f"Invalid team data: teamNumber is None in {api_team}")
    
    try:
        team_number_int = int(team_number)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid team data: teamNumber '{team_number}' cannot be converted to int: {e}")
    
    # Handle rookieYear safely - convert to int if possible, None otherwise
    rookie_year = api_team.get('rookieYear')
    rookie_year_int = None
    if rookie_year is not None:
        try:
            rookie_year_str = str(rookie_year).strip()
            if rookie_year_str and rookie_year_str.lower() not in ['null', 'none', '']:
                rookie_year_int = int(rookie_year_str)
        except (ValueError, TypeError):
            # Silently continue with None for invalid rookie years
            pass
    
    # Safely get string fields with empty string fallback
    def safe_string(value):
        if value is None:
            return ''
        return str(value).strip()
    
    # Create team with proper field mapping
    team_data = {
        'teamNumber': team_number_int,
        'season': season_int,
        'teamName': safe_string(api_team.get('nameShort')),
        'schoolName': safe_string(api_team.get('nameFull')),
        'city': safe_string(api_team.get('city')),
        'state': safe_string(api_team.get('state')),
        'country': safe_string(api_team.get('country')),
        'rookieYear': rookie_year_int,
        'website': safe_string(api_team.get('website')) if api_team.get('website') else None,
        'matchCount': 0,
        'lastUpdated': datetime.now(timezone.utc),
        # Set all optional caching fields to None explicitly
        'lastModified': None,
        'etag': None,
        'apiLastModified': None,
        'dataVersion': None
    }
    
    try:
        team = Team(**team_data)
        return team
    except Exception as e:
        raise ValueError(f"Team creation failed for team {team_number_int}: {e}")

def convert_ftc_api_event(api_event: Dict[str, Any], season: int) -> Event:
    """Convert FTC API event response to Event model with comprehensive None handling"""
    
    # Validate season parameter
    if season is None:
        raise ValueError("Invalid season parameter: season is None")
    
    try:
        season_int = int(season)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid season parameter: season '{season}' cannot be converted to int: {e}")
    
    # Validate event code
    event_code = api_event.get('code')
    if not event_code:
        raise ValueError(f"Invalid event data: code is missing in {api_event}")
    
    # Safely convert integer fields
    def safe_int(value, default=0):
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    # Safely get string fields
    def safe_string(value):
        if value is None:
            return ''
        return str(value).strip()
    
    return Event(
        eventCode=str(event_code),
        season=season_int,
        eventName=safe_string(api_event.get('name')),
        eventType=safe_string(api_event.get('type')),
        dateStart=api_event.get('dateStart'),
        dateEnd=api_event.get('dateEnd'),
        venue=safe_string(api_event.get('venue')) if api_event.get('venue') else None,
        address=safe_string(api_event.get('address')) if api_event.get('address') else None,
        city=safe_string(api_event.get('city')) if api_event.get('city') else None,
        state=safe_string(api_event.get('state')) if api_event.get('state') else None,
        country=safe_string(api_event.get('country')) if api_event.get('country') else None,
        timezone=safe_string(api_event.get('timezone')) if api_event.get('timezone') else None,
        website=safe_string(api_event.get('website')) if api_event.get('website') else None,
        liveStreamUrl=safe_string(api_event.get('liveStreamUrl')) if api_event.get('liveStreamUrl') else None,
        teamCount=safe_int(api_event.get('teamCount')),
        matchCount=safe_int(api_event.get('matchCount')),
        lastModified=None,
        etag=None,
        apiLastModified=None,
        dataVersion=None,
        matchesLastModified=None,
        rankingsLastModified=None
    )

def convert_ftc_api_match(api_match: Dict[str, Any], season: int, event_code: str) -> Match:
    """Convert FTC API match response to Match model with team data"""
    tournament_level = api_match.get('tournamentLevel', 'UNKNOWN')
    match_number = api_match.get('matchNumber', 0)
    series = api_match.get('series', 0)
    
    # Create unique match ID including tournament level and series to avoid duplicates
    match_id = f"{season}-{event_code}-{tournament_level}-{series}-{match_number}"
    
    # Extract team data from teams field
    teams = api_match.get('teams', [])
    red_teams = []
    blue_teams = []
    all_teams = []
    
    for team_data in teams:
        team_number = team_data.get('teamNumber', 0)
        if team_number:
            all_teams.append(team_number)
            
            station = team_data.get('station', '')
            if 'Red' in station:
                red_teams.append(team_number)
            elif 'Blue' in station:
                blue_teams.append(team_number)
    
    # Extract scores
    red_score = None
    blue_score = None
    
    if 'scoreRedFinal' in api_match:
        red_score = MatchScore(
            alliance='Red',
            totalPoints=api_match.get('scoreRedFinal', 0),
            autoPoints=api_match.get('scoreRedAuto', 0),
            teleopPoints=api_match.get('scoreRedTeleop', 0),
            endgamePoints=api_match.get('scoreRedEnd', 0),
            penaltyPoints=api_match.get('scoreRedPenalty', 0)
        )
    
    if 'scoreBlueFinal' in api_match:
        blue_score = MatchScore(
            alliance='Blue',
            totalPoints=api_match.get('scoreBlueFinal', 0),
            autoPoints=api_match.get('scoreBlueAuto', 0),
            teleopPoints=api_match.get('scoreBlueTeleop', 0),
            endgamePoints=api_match.get('scoreBlueEnd', 0),
            penaltyPoints=api_match.get('scoreBluePenalty', 0)
        )
    
    return Match(
        matchId=match_id,
        season=season,
        eventCode=event_code,
        matchNumber=api_match.get('matchNumber', 0),
        description=api_match.get('description', ''),
        tournamentLevel=api_match.get('tournamentLevel', ''),
        series=api_match.get('series'),
        matchName=api_match.get('matchName'),
        playNumber=api_match.get('playNumber'),
        fieldNumber=api_match.get('fieldNumber'),
        startTime=api_match.get('startTime'),
        actualStartTime=api_match.get('actualStartTime'),
        postResultTime=api_match.get('postResultTime'),
        teams=teams,
        redTeams=red_teams,
        blueTeams=blue_teams,
        allTeams=all_teams,
        redScore=red_score,
        blueScore=blue_score,
        lastModified=None,
        etag=None,
        apiLastModified=None,
        dataVersion=None
    )