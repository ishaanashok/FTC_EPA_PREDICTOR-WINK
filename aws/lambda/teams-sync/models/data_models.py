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
