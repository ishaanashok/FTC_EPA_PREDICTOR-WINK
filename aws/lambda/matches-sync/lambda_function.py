import json
import logging
import os
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import boto3
from botocore.exceptions import ClientError

# Local imports
from services.ftc_api_service import FTCApiService
from services.dynamodb_service import DynamoDBService
from models.data_models import (
    Match, SyncStatus,
    convert_ftc_api_match
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MatchesSyncService:
    """
    Matches synchronization service
    
    Features:
    - Syncs matches from FTC API to DynamoDB
    - Supports event-wide sync or individual match sync
    - Full pagination support for large datasets
    - Robust error handling and retry logic
    - HTTP caching optimization
    """
    
    def __init__(self, environment: str = None):
        if environment is None:
            environment = os.environ.get('ENVIRONMENT', 'dev')
        
        self.environment = environment
        self.db_service = DynamoDBService(environment)
        self.ftc_api = None
        self.current_season = 2024
        
        logger.info(f"MatchesSyncService initialized for environment: {environment}")
        
    async def initialize(self):
        """Initialize FTC API service with credentials from AWS Secrets Manager"""
        try:
            # Get FTC API credentials from Secrets Manager
            secrets_client = boto3.client('secretsmanager')
            secrets_name = os.environ.get('SECRETS_NAME', f'FTC-API-Credentials-{self.environment}')
            
            response = secrets_client.get_secret_value(SecretId=secrets_name)
            credentials = json.loads(response['SecretString'])
            
            # Initialize FTC API service
            self.ftc_api = FTCApiService(credentials)
            
            # Initialize the HTTP session
            await self.ftc_api.initialize()
            
            logger.info("FTC API service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize FTC API service: {str(e)}")
            raise

    def _match_has_scores(self, match_data: Dict[str, Any]) -> bool:
        """Return True when a match has non-zero final scores."""
        if not match_data:
            return False

        def _score_total(score):
            if not score:
                return 0
            if isinstance(score, dict):
                return score.get('totalPoints', 0) or 0
            return getattr(score, 'totalPoints', 0) or 0

        red_score = _score_total(match_data.get('redScore')) or match_data.get('scoreRedFinal', 0) or 0
        blue_score = _score_total(match_data.get('blueScore')) or match_data.get('scoreBlueFinal', 0) or 0

        return (red_score or 0) > 0 or (blue_score or 0) > 0

    def _extract_match_team_numbers(self, match_data: Dict[str, Any]) -> List[int]:
        """Extract team numbers from match data."""
        team_numbers = set()

        for team in match_data.get('allTeams', []) or []:
            team_numbers.add(int(team))

        for team in match_data.get('redTeams', []) or []:
            team_numbers.add(int(team))

        for team in match_data.get('blueTeams', []) or []:
            team_numbers.add(int(team))

        for team_entry in match_data.get('teams', []) or []:
            team_number = team_entry.get('teamNumber')
            if team_number is not None:
                team_numbers.add(int(team_number))

        return sorted(team_numbers)

    def _should_increment_match_count(self, existing_match: Optional[Dict[str, Any]],
                                      new_match: Dict[str, Any]) -> bool:
        """Increment when match transitions from no scores to scored."""
        new_has_scores = self._match_has_scores(new_match)
        old_has_scores = self._match_has_scores(existing_match)
        return new_has_scores and not old_has_scores

    def _increment_match_counts(self, match_data: Dict[str, Any], season: int) -> None:
        """Increment matchCount for all teams in the match."""
        team_numbers = self._extract_match_team_numbers(match_data)
        if not team_numbers:
            return

        for team_number in team_numbers:
            updated = self.db_service.increment_team_match_count(team_number, season, 1)
            if not updated:
                logger.warning(
                    f"Failed to increment matchCount for team {team_number}, season {season}"
                )
    
    async def create_sync_status(self, sync_type: str, season: int, event_code: Optional[str] = None, match_number: Optional[int] = None) -> SyncStatus:
        """Create a new sync status record"""
        if match_number:
            sync_key = f"{sync_type}#{season}#{event_code}#{match_number}"
        elif event_code:
            sync_key = f"{sync_type}#{season}#{event_code}"
        else:
            sync_key = f"{sync_type}#{season}"
        
        current_time = datetime.now(timezone.utc)
        
        return SyncStatus(
            syncKey=sync_key,
            lastSyncTime=current_time.isoformat(),
            syncType=sync_type,
            season=season,
            nextSyncTime=current_time.isoformat(),
            status="in_progress",
            recordsProcessed=0,
            recordsUpdated=0,
            eventCode=event_code
        )
    
    async def update_sync_status(self, sync_status: SyncStatus) -> bool:
        """Update sync status in DynamoDB"""
        try:
            sync_status_dict = sync_status.model_dump() if hasattr(sync_status, 'model_dump') else sync_status.dict()
            return self.db_service.save_sync_status(sync_status_dict)
        except Exception as e:
            logger.error(f"Error updating sync status: {str(e)}")
            return False
    
    async def sync_match_by_number(self, event_code: str, match_number: int, season: Optional[int] = None) -> Dict[str, Any]:
        """Sync a specific match by match number within an event"""
        if season is None:
            season = self.current_season
        
        logger.info(f"Starting sync for match {match_number} in event {event_code}, season {season}")
        
        # Create sync status
        sync_status = await self.create_sync_status("matches", season, event_code, match_number)
        await self.update_sync_status(sync_status)
        
        try:
            # Ensure FTC API is initialized
            if self.ftc_api is None:
                await self.initialize()
            
            if self.ftc_api is None:
                raise RuntimeError("FTC API service is not initialized")
            
            # Get specific match from FTC API
            logger.info(f"Fetching match {match_number} from event {event_code} from FTC API for season {season}")
            
            # Get all matches for the event and filter for the specific match
            matches_data, metadata = await self.ftc_api.get_event_matches(
                season, 
                event_code
            )
            
            if not matches_data:
                logger.warning(f"No matches data received for event {event_code}, season {season}")
                sync_status.status = "completed"
                sync_status.errorMessage = f"No matches data found for event {event_code}"
                await self.update_sync_status(sync_status)
                return {
                    "success": False,
                    "message": f"No matches data found for event {event_code}",
                    "recordsProcessed": 0,
                    "recordsUpdated": 0
                }
            
            # Find the specific match
            target_match = None
            for match_data in matches_data:
                if match_data.get('matchNumber') == match_number:
                    target_match = match_data
                    break
            
            if not target_match:
                logger.warning(f"Match {match_number} not found in event {event_code}")
                sync_status.status = "completed"
                sync_status.errorMessage = f"Match {match_number} not found in event {event_code}"
                await self.update_sync_status(sync_status)
                return {
                    "success": False,
                    "message": f"Match {match_number} not found in event {event_code}",
                    "recordsProcessed": 0,
                    "recordsUpdated": 0
                }
            
            # Process the match
            try:
                # Convert API data to model
                match = convert_ftc_api_match(target_match, season, event_code)
                
                # Add HTTP caching headers
                match.lastModified = metadata.get('lastModified')
                match.etag = metadata.get('etag')
                match.apiLastModified = datetime.now(timezone.utc) if metadata.get('lastModified') else None
                
                # Save match to DynamoDB
                match_dict = match.model_dump() if hasattr(match, 'model_dump') else match.dict()
                existing_match = self.db_service.get_match(match.matchId)
                success = self.db_service.save_match(match_dict)
                
                if success:
                    if self._should_increment_match_count(existing_match, match_dict):
                        self._increment_match_counts(match_dict, season)

                    sync_status.status = "completed"
                    sync_status.recordsProcessed = 1
                    sync_status.recordsUpdated = 1
                    
                    await self.update_sync_status(sync_status)
                    
                    logger.info(f"Match {match_number} in event {event_code} sync completed successfully")
                    
                    return {
                        "success": True,
                        "message": f"Match {match_number} sync completed for event {event_code}, season {season}",
                        "recordsProcessed": 1,
                        "recordsUpdated": 1,
                        "bandwidthSaved": metadata.get('bandwidthSaved', 0),
                        "match": match_dict
                    }
                else:
                    raise Exception(f"Failed to save match {match_number} to DynamoDB")
                    
            except Exception as e:
                logger.error(f"Error processing match {match_number}: {str(e)}")
                raise
                
        except Exception as e:
            sync_status.status = "failed"
            sync_status.errorMessage = str(e)
            await self.update_sync_status(sync_status)
            
            logger.error(f"Match {match_number} sync failed: {str(e)}")
            raise
    
    async def sync_matches_by_event(self, event_code: str, season: Optional[int] = None) -> Dict[str, Any]:
        """Sync all matches for a specific event"""
        if season is None:
            season = self.current_season
        
        logger.info(f"Starting matches sync for event {event_code}, season {season}")
        
        # Create sync status
        sync_status = await self.create_sync_status("matches", season, event_code)
        await self.update_sync_status(sync_status)
        
        try:
            # Ensure FTC API is initialized
            if self.ftc_api is None:
                await self.initialize()
            
            if self.ftc_api is None:
                raise RuntimeError("FTC API service is not initialized")
            
            # Get matches for the event
            logger.info(f"Fetching matches from FTC API for event {event_code}, season {season}")
            matches_data, metadata = await self.ftc_api.get_event_matches(season, event_code)
            
            if not matches_data:
                logger.info(f"No matches data for event {event_code}")
                sync_status.status = "completed"
                sync_status.errorMessage = f"No matches data for event {event_code}"
                await self.update_sync_status(sync_status)
                return {
                    "success": True,
                    "message": f"No matches for event {event_code}",
                    "recordsProcessed": 0,
                    "recordsUpdated": 0
                }
            
            logger.info(f"Processing {len(matches_data)} matches for event {event_code}")
            
            # Process matches in batches
            batch_size = 25  # DynamoDB batch write limit
            matches_processed = 0
            matches_updated = 0
            
            for i in range(0, len(matches_data), batch_size):
                batch = matches_data[i:i + batch_size]
                batch_matches = []
                scored_matches_to_increment = []
                
                for match_data in batch:
                    try:
                        # Convert API data to model
                        match = convert_ftc_api_match(match_data, season, event_code)
                        
                        # Add HTTP caching headers
                        match.lastModified = metadata.get('lastModified')
                        match.etag = metadata.get('etag')
                        match.apiLastModified = datetime.now(timezone.utc) if metadata.get('lastModified') else None
                        
                        # Always update matches (overwrite existing records)
                        match_dict = match.model_dump() if hasattr(match, 'model_dump') else match.dict()
                        existing_match = self.db_service.get_match(match.matchId)
                        if self._should_increment_match_count(existing_match, match_dict):
                            scored_matches_to_increment.append(match_dict)
                        batch_matches.append(match_dict)
                        matches_updated += 1
                        
                        matches_processed += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing match {match_data.get('matchNumber', 'unknown')}: {str(e)}")
                        continue
                
                # Batch save matches
                if batch_matches:
                    success = self.db_service.batch_save_matches(batch_matches)
                    if not success:
                        logger.error(f"Failed to save batch of {len(batch_matches)} matches")
                    else:
                        for scored_match in scored_matches_to_increment:
                            self._increment_match_counts(scored_match, season)
                
                # Update progress
                if matches_processed % 25 == 0:
                    logger.info(f"Processed {matches_processed}/{len(matches_data)} matches")
            
            sync_status.status = "completed"
            sync_status.recordsProcessed = matches_processed
            sync_status.recordsUpdated = matches_updated
            
            await self.update_sync_status(sync_status)
            
            logger.info(f"Matches sync completed for event {event_code}: {matches_processed} processed, {matches_updated} updated")
            
            return {
                "success": True,
                "message": f"Matches sync completed for event {event_code}",
                "recordsProcessed": matches_processed,
                "recordsUpdated": matches_updated,
                "bandwidthSaved": metadata.get('bandwidthSaved', 0)
            }
            
        except Exception as e:
            sync_status.status = "failed"
            sync_status.errorMessage = str(e)
            await self.update_sync_status(sync_status)
            
            logger.error(f"Matches sync failed for event {event_code}: {str(e)}")
            raise
    
    async def close(self):
        """Clean up resources"""
        if self.ftc_api:
            await self.ftc_api.close()
        self.db_service.clear_cache()


async def lambda_handler(event, context):
    """Lambda handler for matches synchronization"""
    
    # Initialize service
    sync_service = MatchesSyncService()
    
    try:
        # Ensure FTC API is initialized before any sync calls
        await sync_service.initialize()
        
        # Extract parameters from event
        season = event.get('season', 2024)
        event_code = event.get('eventCode')
        match_number = event.get('matchNumber')
        
        logger.info(f"Starting matches sync: season={season}, eventCode={event_code}, matchNumber={match_number}")
        
        if not event_code:
            raise ValueError("eventCode is required for matches sync")
        
        if match_number:
            # Sync specific match
            result = await sync_service.sync_match_by_number(event_code, match_number, season)
        else:
            # Sync all matches for event
            result = await sync_service.sync_matches_by_event(event_code, season)
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'success': False
            })
        }
    
    finally:
        await sync_service.close()


def handler(event, context):
    """Synchronous wrapper for async lambda handler"""
    return asyncio.run(lambda_handler(event, context))
