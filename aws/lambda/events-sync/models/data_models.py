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
