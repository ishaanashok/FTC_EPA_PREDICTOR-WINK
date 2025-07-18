import json
import logging
import os
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import hashlib

# AWS SDK
import boto3
from botocore.exceptions import ClientError

# Local imports
from services.ftc_api_service import FTCApiService
from services.dynamodb_service import DynamoDBService
from models.data_models import (
    Team, Event, Match, EPACalculation, SyncStatus,
    convert_ftc_api_team, convert_ftc_api_event, convert_ftc_api_match
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataSyncService:
    """Data synchronization service with HTTP caching optimization"""
    
    def __init__(self, environment: str = 'dev'):
        self.environment = environment
        self.db_service = DynamoDBService(environment)
        self.ftc_api = None
        self.current_season = 2024
        
    async def initialize(self):
        """Initialize the service with API credentials"""
        try:
            # Get FTC API credentials from AWS Secrets Manager
            secrets_client = boto3.client('secretsmanager')
            secrets_name = os.environ.get('SECRETS_NAME', f'ftc-api-credentials-{self.environment}')
            
            response = secrets_client.get_secret_value(SecretId=secrets_name)
            credentials = json.loads(response['SecretString'])
            
            # Initialize FTC API service
            self.ftc_api = FTCApiService(credentials)
            await self.ftc_api.initialize()
            
            logger.info("Data sync service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize data sync service: {str(e)}")
            raise
    
    async def close(self):
        """Close the service"""
        if self.ftc_api:
            await self.ftc_api.close()
    
    def _calculate_data_hash(self, data: Any) -> str:
        """Calculate a hash of the data for change detection"""
        if isinstance(data, dict):
            # Sort keys for consistent hashing
            sorted_data = json.dumps(data, sort_keys=True)
        else:
            sorted_data = json.dumps(data, sort_keys=True)
        
        return hashlib.sha256(sorted_data.encode()).hexdigest()[:16]
    
    def _should_update_epa(self, team_data_changed: bool, event_data_changed: bool, 
                          match_data_changed: bool) -> bool:
        """Determine if EPA calculations should be updated based on data changes"""
        return team_data_changed or event_data_changed or match_data_changed
    
    async def get_sync_status(self, sync_type: str, season: int) -> Optional[SyncStatus]:
        """Get the last sync status for a specific type"""
        try:
            # This is a simplified version - in a real implementation you'd store sync status
            # in DynamoDB with a composite key of syncType and season
            return None
        except Exception as e:
            logger.error(f"Error getting sync status: {str(e)}")
            return None
    
    async def update_sync_status(self, sync_status: SyncStatus):
        """Update sync status in DynamoDB"""
        try:
            # This is a simplified version - in a real implementation you'd store this in DynamoDB
            logger.info(f"Sync status updated: {sync_status.syncType} - {sync_status.status}")
        except Exception as e:
            logger.error(f"Error updating sync status: {str(e)}")
    
    async def sync_teams(self, season: int = None) -> Dict[str, Any]:
        """Sync teams data with HTTP caching optimization"""
        if season is None:
            season = self.current_season
        
        sync_status = SyncStatus(
            syncType="teams",
            season=season,
            lastSyncTime=datetime.now(timezone.utc),
            nextSyncTime=datetime.now(timezone.utc),
            status="in_progress"
        )
        
        try:
            # Get last sync status to retrieve caching headers
            last_sync = await self.get_sync_status("teams", season)
            
            # Make conditional request using stored headers
            if_modified_since = last_sync.lastModifiedHeader if last_sync else None
            
            teams_data, metadata = await self.ftc_api.get_teams(
                season, 
                if_modified_since=if_modified_since
            )
            
            # Update sync status with HTTP caching info
            sync_status.lastModifiedHeader = metadata.get('lastModified')
            sync_status.etag = metadata.get('etag')
            sync_status.ifModifiedSinceUsed = if_modified_since
            sync_status.dataChanged = metadata.get('dataChanged', True)
            sync_status.bandwidthSaved = metadata.get('bandwidthSaved', 0)
            
            if not metadata.get('dataChanged', True):
                # 304 Not Modified - no changes
                sync_status.status = "completed"
                sync_status.recordsProcessed = 0
                sync_status.recordsUpdated = 0
                
                await self.update_sync_status(sync_status)
                
                logger.info(f"Teams sync completed - no changes (304 Not Modified)")
                return {
                    "success": True,
                    "message": "Teams sync completed - no changes",
                    "recordsProcessed": 0,
                    "recordsUpdated": 0,
                    "dataChanged": False,
                    "bandwidthSaved": metadata.get('bandwidthSaved', 0)
                }
            
            # Process teams data
            teams_list = teams_data.get('teams', []) if teams_data else []
            teams_processed = 0
            teams_updated = 0
            
            for team_data in teams_list:
                try:
                    # Convert API data to model
                    team = convert_ftc_api_team(team_data, season)
                    
                    # Add HTTP caching headers
                    team.lastModified = metadata.get('lastModified')
                    team.etag = metadata.get('etag')
                    team.apiLastModified = datetime.now(timezone.utc) if metadata.get('lastModified') else None
                    team.dataHash = self._calculate_data_hash(team_data)
                    
                    # Check if team exists and needs updating
                    existing_team = await self.db_service.get_team(team.teamNumber, season)
                    
                    should_update = True
                    if existing_team:
                        existing_hash = existing_team.get('dataHash')
                        if existing_hash == team.dataHash:
                            should_update = False
                    
                    if should_update:
                        # Save to DynamoDB
                        await self.db_service.teams_table.put_item(
                            Item=team.to_dynamodb_item()
                        )
                        teams_updated += 1
                    
                    teams_processed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing team {team_data.get('teamNumber', 'unknown')}: {str(e)}")
                    continue
            
            sync_status.status = "completed"
            sync_status.recordsProcessed = teams_processed
            sync_status.recordsUpdated = teams_updated
            
            await self.update_sync_status(sync_status)
            
            logger.info(f"Teams sync completed: {teams_processed} processed, {teams_updated} updated")
            
            return {
                "success": True,
                "message": "Teams sync completed successfully",
                "recordsProcessed": teams_processed,
                "recordsUpdated": teams_updated,
                "dataChanged": True,
                "bandwidthSaved": metadata.get('bandwidthSaved', 0)
            }
            
        except Exception as e:
            sync_status.status = "failed"
            sync_status.errorMessage = str(e)
            await self.update_sync_status(sync_status)
            
            logger.error(f"Teams sync failed: {str(e)}")
            raise
    
    async def sync_events(self, season: int = None) -> Dict[str, Any]:
        """Sync events data with HTTP caching optimization"""
        if season is None:
            season = self.current_season
        
        sync_status = SyncStatus(
            syncType="events",
            season=season,
            lastSyncTime=datetime.now(timezone.utc),
            nextSyncTime=datetime.now(timezone.utc),
            status="in_progress"
        )
        
        try:
            # Get last sync status to retrieve caching headers
            last_sync = await self.get_sync_status("events", season)
            
            # Make conditional request using stored headers
            if_modified_since = last_sync.lastModifiedHeader if last_sync else None
            
            events_data, metadata = await self.ftc_api.get_events(
                season,
                if_modified_since=if_modified_since
            )
            
            # Update sync status with HTTP caching info
            sync_status.lastModifiedHeader = metadata.get('lastModified')
            sync_status.etag = metadata.get('etag')
            sync_status.ifModifiedSinceUsed = if_modified_since
            sync_status.dataChanged = metadata.get('dataChanged', True)
            sync_status.bandwidthSaved = metadata.get('bandwidthSaved', 0)
            
            if not metadata.get('dataChanged', True):
                # 304 Not Modified - no changes
                sync_status.status = "completed"
                sync_status.recordsProcessed = 0
                sync_status.recordsUpdated = 0
                
                await self.update_sync_status(sync_status)
                
                logger.info(f"Events sync completed - no changes (304 Not Modified)")
                return {
                    "success": True,
                    "message": "Events sync completed - no changes",
                    "recordsProcessed": 0,
                    "recordsUpdated": 0,
                    "dataChanged": False,
                    "bandwidthSaved": metadata.get('bandwidthSaved', 0)
                }
            
            # Process events data
            events_list = events_data.get('events', []) if events_data else []
            events_processed = 0
            events_updated = 0
            
            for event_data in events_list:
                try:
                    # Convert API data to model
                    event = convert_ftc_api_event(event_data, season)
                    
                    # Add HTTP caching headers
                    event.lastModified = metadata.get('lastModified')
                    event.etag = metadata.get('etag')
                    event.apiLastModified = datetime.now(timezone.utc) if metadata.get('lastModified') else None
                    event.dataHash = self._calculate_data_hash(event_data)
                    
                    # Check if event exists and needs updating
                    existing_event = await self.db_service.get_event(event.eventCode, season)
                    
                    should_update = True
                    if existing_event:
                        existing_hash = existing_event.get('dataHash')
                        if existing_hash == event.dataHash:
                            should_update = False
                    
                    if should_update:
                        # Save to DynamoDB
                        await self.db_service.events_table.put_item(
                            Item=event.to_dynamodb_item()
                        )
                        events_updated += 1
                    
                    events_processed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing event {event_data.get('code', 'unknown')}: {str(e)}")
                    continue
            
            sync_status.status = "completed"
            sync_status.recordsProcessed = events_processed
            sync_status.recordsUpdated = events_updated
            
            await self.update_sync_status(sync_status)
            
            logger.info(f"Events sync completed: {events_processed} processed, {events_updated} updated")
            
            return {
                "success": True,
                "message": "Events sync completed successfully",
                "recordsProcessed": events_processed,
                "recordsUpdated": events_updated,
                "dataChanged": True,
                "bandwidthSaved": metadata.get('bandwidthSaved', 0)
            }
            
        except Exception as e:
            sync_status.status = "failed"
            sync_status.errorMessage = str(e)
            await self.update_sync_status(sync_status)
            
            logger.error(f"Events sync failed: {str(e)}")
            raise
    
    async def sync_matches_for_event(self, event_code: str, season: int = None) -> Dict[str, Any]:
        """Sync matches for a specific event with HTTP caching optimization"""
        if season is None:
            season = self.current_season
        
        try:
            # Get last sync status to retrieve caching headers
            last_sync = await self.get_sync_status(f"matches_{event_code}", season)
            
            # Make conditional request using stored headers
            if_modified_since = last_sync.lastModifiedHeader if last_sync else None
            
            # Get qualification matches
            qual_matches_data, qual_metadata = await self.ftc_api.get_event_matches(
                season, event_code, "qual",
                if_modified_since=if_modified_since
            )
            
            # Get playoff matches  
            playoff_matches_data, playoff_metadata = await self.ftc_api.get_event_matches(
                season, event_code, "playoff",
                if_modified_since=if_modified_since
            )
            
            matches_processed = 0
            matches_updated = 0
            
            # Process qualification matches
            if qual_matches_data and qual_metadata.get('dataChanged', True):
                qual_matches_list = qual_matches_data.get('matches', [])
                
                for match_data in qual_matches_list:
                    try:
                        # Convert API data to model
                        match = convert_ftc_api_match(match_data, season, event_code)
                        
                        # Add HTTP caching headers
                        match.lastModified = qual_metadata.get('lastModified')
                        match.etag = qual_metadata.get('etag')
                        match.apiLastModified = datetime.now(timezone.utc) if qual_metadata.get('lastModified') else None
                        match.dataHash = self._calculate_data_hash(match_data)
                        
                        # Check if match exists and needs updating
                        existing_match = await self.db_service.get_match(match.matchId)
                        
                        should_update = True
                        if existing_match:
                            existing_hash = existing_match.get('dataHash')
                            if existing_hash == match.dataHash:
                                should_update = False
                        
                        if should_update:
                            # Save to DynamoDB
                            await self.db_service.matches_table.put_item(
                                Item=match.to_dynamodb_item()
                            )
                            matches_updated += 1
                        
                        matches_processed += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing match {match_data.get('matchNumber', 'unknown')}: {str(e)}")
                        continue
            
            # Process playoff matches
            if playoff_matches_data and playoff_metadata.get('dataChanged', True):
                playoff_matches_list = playoff_matches_data.get('matches', [])
                
                for match_data in playoff_matches_list:
                    try:
                        # Convert API data to model
                        match = convert_ftc_api_match(match_data, season, event_code)
                        
                        # Add HTTP caching headers
                        match.lastModified = playoff_metadata.get('lastModified')
                        match.etag = playoff_metadata.get('etag')
                        match.apiLastModified = datetime.now(timezone.utc) if playoff_metadata.get('lastModified') else None
                        match.dataHash = self._calculate_data_hash(match_data)
                        
                        # Check if match exists and needs updating
                        existing_match = await self.db_service.get_match(match.matchId)
                        
                        should_update = True
                        if existing_match:
                            existing_hash = existing_match.get('dataHash')
                            if existing_hash == match.dataHash:
                                should_update = False
                        
                        if should_update:
                            # Save to DynamoDB
                            await self.db_service.matches_table.put_item(
                                Item=match.to_dynamodb_item()
                            )
                            matches_updated += 1
                        
                        matches_processed += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing match {match_data.get('matchNumber', 'unknown')}: {str(e)}")
                        continue
            
            logger.info(f"Matches sync for {event_code}: {matches_processed} processed, {matches_updated} updated")
            
            return {
                "success": True,
                "eventCode": event_code,
                "recordsProcessed": matches_processed,
                "recordsUpdated": matches_updated,
                "dataChanged": matches_updated > 0,
                "bandwidthSaved": qual_metadata.get('bandwidthSaved', 0) + playoff_metadata.get('bandwidthSaved', 0)
            }
            
        except Exception as e:
            logger.error(f"Matches sync failed for event {event_code}: {str(e)}")
            raise
    
    async def sync_all_data(self, season: int = None) -> Dict[str, Any]:
        """Sync all data with change detection for EPA updates"""
        if season is None:
            season = self.current_season
        
        logger.info(f"Starting full data sync for season {season}")
        
        try:
            # Track what data changed
            teams_result = await self.sync_teams(season)
            events_result = await self.sync_events(season)
            
            # Get active events to sync matches
            events_data, _ = await self.ftc_api.get_events(season)
            active_events = events_data.get('events', []) if events_data else []
            
            matches_results = []
            total_matches_processed = 0
            total_matches_updated = 0
            
            for event_data in active_events:
                event_code = event_data.get('code')
                if event_code:
                    try:
                        match_result = await self.sync_matches_for_event(event_code, season)
                        matches_results.append(match_result)
                        total_matches_processed += match_result.get('recordsProcessed', 0)
                        total_matches_updated += match_result.get('recordsUpdated', 0)
                    except Exception as e:
                        logger.error(f"Error syncing matches for event {event_code}: {str(e)}")
            
            # Check if EPA calculations need updating
            teams_changed = teams_result.get('dataChanged', False)
            events_changed = events_result.get('dataChanged', False)
            matches_changed = total_matches_updated > 0
            
            epa_updated = False
            if self._should_update_epa(teams_changed, events_changed, matches_changed):
                logger.info("Data changes detected - updating EPA calculations")
                # This would trigger EPA calculations - placeholder for now
                epa_updated = True
            else:
                logger.info("No significant data changes - skipping EPA calculations")
            
            total_bandwidth_saved = (
                teams_result.get('bandwidthSaved', 0) + 
                events_result.get('bandwidthSaved', 0) + 
                sum(r.get('bandwidthSaved', 0) for r in matches_results)
            )
            
            logger.info(f"Full sync completed for season {season}")
            
            return {
                "success": True,
                "season": season,
                "teams": teams_result,
                "events": events_result,
                "matches": {
                    "totalProcessed": total_matches_processed,
                    "totalUpdated": total_matches_updated,
                    "eventResults": matches_results
                },
                "epaUpdated": epa_updated,
                "totalBandwidthSaved": total_bandwidth_saved,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Full sync failed: {str(e)}")
            raise


async def lambda_handler(event, context):
    """Lambda handler for data synchronization"""
    
    # Initialize service
    sync_service = DataSyncService(
        environment=os.environ.get('ENVIRONMENT', 'dev')
    )
    
    try:
        await sync_service.initialize()
        
        # Extract parameters from event
        sync_type = event.get('syncType', 'all')
        season = event.get('season', 2024)
        
        if sync_type == 'teams':
            result = await sync_service.sync_teams(season)
        elif sync_type == 'events':
            result = await sync_service.sync_events(season)
        elif sync_type == 'all':
            result = await sync_service.sync_all_data(season)
        else:
            raise ValueError(f"Unknown sync type: {sync_type}")
        
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
    try:
        # Try to get the existing event loop
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No event loop in current thread, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        # Use run_until_complete instead of asyncio.run for Lambda compatibility
        return loop.run_until_complete(lambda_handler(event, context))
    finally:
        # Clean up any remaining tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True)) 