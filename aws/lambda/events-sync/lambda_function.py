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
    Event, SyncStatus,
    convert_ftc_api_event
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EventsSyncService:
    """
    Events synchronization service
    
    Features:
    - Syncs events from FTC API to DynamoDB
    - Supports season-wide sync or individual event sync
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
        
        logger.info(f"EventsSyncService initialized for environment: {environment}")
        
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
    
    async def create_sync_status(self, sync_type: str, season: int, event_code: Optional[str] = None) -> SyncStatus:
        """Create a new sync status record"""
        if event_code:
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
    
    async def sync_event_by_code(self, event_code: str, season: Optional[int] = None) -> Dict[str, Any]:
        """Sync a specific event by event code"""
        if season is None:
            season = self.current_season
        
        logger.info(f"Starting sync for event {event_code}, season {season}")
        
        # Create sync status
        sync_status = await self.create_sync_status("events", season, event_code)
        await self.update_sync_status(sync_status)
        
        try:
            # Ensure FTC API is initialized
            if self.ftc_api is None:
                await self.initialize()
            
            if self.ftc_api is None:
                raise RuntimeError("FTC API service is not initialized")
            
            # Get specific event from FTC API
            logger.info(f"Fetching event {event_code} from FTC API for season {season}")
            
            # Use the events endpoint with eventCode filter
            events_data, metadata = await self.ftc_api.get_events(
                season, 
                eventCode=event_code
            )
            
            if not events_data or len(events_data) == 0:
                logger.warning(f"No event data received for event {event_code}, season {season}")
                sync_status.status = "completed"
                sync_status.errorMessage = f"No event data found for event {event_code}"
                await self.update_sync_status(sync_status)
                return {
                    "success": False,
                    "message": f"No event data found for event {event_code}",
                    "recordsProcessed": 0,
                    "recordsUpdated": 0
                }
            
            # Process the event
            event_data = events_data[0]  # Should only be one event
            try:
                # Convert API data to model
                event = convert_ftc_api_event(event_data, season)
                
                # Add HTTP caching headers
                event.lastModified = metadata.get('lastModified')
                event.etag = metadata.get('etag')
                event.apiLastModified = datetime.now(timezone.utc) if metadata.get('lastModified') else None
                
                # Save event to DynamoDB
                event_dict = event.model_dump() if hasattr(event, 'model_dump') else event.dict()
                success = self.db_service.save_event(event_dict)
                
                if success:
                    sync_status.status = "completed"
                    sync_status.recordsProcessed = 1
                    sync_status.recordsUpdated = 1
                    
                    await self.update_sync_status(sync_status)
                    
                    logger.info(f"Event {event_code} sync completed successfully")
                    
                    return {
                        "success": True,
                        "message": f"Event {event_code} sync completed for season {season}",
                        "recordsProcessed": 1,
                        "recordsUpdated": 1,
                        "bandwidthSaved": metadata.get('bandwidthSaved', 0),
                        "event": event_dict
                    }
                else:
                    raise Exception(f"Failed to save event {event_code} to DynamoDB")
                    
            except Exception as e:
                logger.error(f"Error processing event {event_code}: {str(e)}")
                raise
                
        except Exception as e:
            sync_status.status = "failed"
            sync_status.errorMessage = str(e)
            await self.update_sync_status(sync_status)
            
            logger.error(f"Event {event_code} sync failed: {str(e)}")
            raise
    
    async def sync_events_by_season(self, season: Optional[int] = None) -> Dict[str, Any]:
        """Sync all events for a specific season with full pagination support"""
        if season is None:
            season = self.current_season
        
        logger.info(f"Starting events sync for season {season}")
        
        # Create sync status
        sync_status = await self.create_sync_status("events", season)
        await self.update_sync_status(sync_status)
        
        try:
            # Ensure FTC API is initialized
            if self.ftc_api is None:
                await self.initialize()
            
            if self.ftc_api is None:
                raise RuntimeError("FTC API service is not initialized")
            
            # Get events with full pagination
            logger.info(f"Fetching events from FTC API for season {season}")
            events_data, metadata = await self.ftc_api.get_events(season)
            
            if not events_data:
                logger.warning(f"No events data received for season {season}")
                sync_status.status = "completed"
                sync_status.errorMessage = "No events data received"
                await self.update_sync_status(sync_status)
                return {
                    "success": False,
                    "message": "No events data received",
                    "recordsProcessed": 0,
                    "recordsUpdated": 0
                }
            
            logger.info(f"Processing {len(events_data)} events for season {season}")
            
            # Process events in batches
            batch_size = 25  # DynamoDB batch write limit
            events_processed = 0
            events_updated = 0
            
            for i in range(0, len(events_data), batch_size):
                batch = events_data[i:i + batch_size]
                batch_events = []
                
                for event_data in batch:
                    try:
                        # Convert API data to model
                        event = convert_ftc_api_event(event_data, season)
                        
                        # Add HTTP caching headers
                        event.lastModified = metadata.get('lastModified')
                        event.etag = metadata.get('etag')
                        event.apiLastModified = datetime.now(timezone.utc) if metadata.get('lastModified') else None
                        
                        # Always update events (overwrite existing records)
                        event_dict = event.model_dump() if hasattr(event, 'model_dump') else event.dict()
                        batch_events.append(event_dict)
                        events_updated += 1
                        
                        events_processed += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing event {event_data.get('code', 'unknown')}: {str(e)}")
                        continue
                
                # Batch save events
                if batch_events:
                    success = self.db_service.batch_save_events(batch_events)
                    if not success:
                        logger.error(f"Failed to save batch of {len(batch_events)} events")
                
                # Update progress
                if events_processed % 50 == 0:
                    logger.info(f"Processed {events_processed}/{len(events_data)} events")
            
            sync_status.status = "completed"
            sync_status.recordsProcessed = events_processed
            sync_status.recordsUpdated = events_updated
            
            await self.update_sync_status(sync_status)
            
            logger.info(f"Events sync completed: {events_processed} processed, {events_updated} updated")
            
            return {
                "success": True,
                "message": f"Events sync completed for season {season}",
                "recordsProcessed": events_processed,
                "recordsUpdated": events_updated,
                "bandwidthSaved": metadata.get('bandwidthSaved', 0)
            }
            
        except Exception as e:
            sync_status.status = "failed"
            sync_status.errorMessage = str(e)
            await self.update_sync_status(sync_status)
            
            logger.error(f"Events sync failed: {str(e)}")
            raise
    
    async def close(self):
        """Clean up resources"""
        if self.ftc_api:
            await self.ftc_api.close()
        self.db_service.clear_cache()


async def lambda_handler(event, context):
    """Lambda handler for events synchronization"""
    
    # Initialize service
    sync_service = EventsSyncService()
    
    try:
        # Ensure FTC API is initialized before any sync calls
        await sync_service.initialize()
        
        # Extract parameters from event
        season = event.get('season', 2024)
        event_code = event.get('eventCode')
        
        logger.info(f"Starting events sync: season={season}, eventCode={event_code}")
        
        if event_code:
            # Sync specific event
            result = await sync_service.sync_event_by_code(event_code, season)
        else:
            # Sync all events for season
            result = await sync_service.sync_events_by_season(season)
        
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
