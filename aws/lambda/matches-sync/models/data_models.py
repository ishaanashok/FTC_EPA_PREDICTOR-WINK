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
