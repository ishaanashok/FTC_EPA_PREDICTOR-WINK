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
    Team, SyncStatus,
    convert_ftc_api_team
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TeamsSyncService:
    """
    Teams synchronization service
    
    Features:
    - Syncs teams from FTC API to DynamoDB
    - Supports season-wide sync or individual team sync
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
        
        logger.info(f"TeamsSyncService initialized for environment: {environment}")
        
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
    
    async def create_sync_status(self, sync_type: str, season: int, team_number: Optional[int] = None) -> SyncStatus:
        """Create a new sync status record"""
        if team_number:
            sync_key = f"{sync_type}#{season}#{team_number}"
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
            recordsUpdated=0
        )
    
    async def update_sync_status(self, sync_status: SyncStatus) -> bool:
        """Update sync status in DynamoDB"""
        try:
            sync_status_dict = sync_status.model_dump() if hasattr(sync_status, 'model_dump') else sync_status.dict()
            return self.db_service.save_sync_status(sync_status_dict)
        except Exception as e:
            logger.error(f"Error updating sync status: {str(e)}")
            return False
    
    async def sync_team_by_number(self, team_number: int, season: Optional[int] = None) -> Dict[str, Any]:
        """Sync a specific team by team number"""
        if season is None:
            season = self.current_season
        
        logger.info(f"Starting sync for team {team_number}, season {season}")
        
        # Create sync status
        sync_status = await self.create_sync_status("teams", season, team_number)
        await self.update_sync_status(sync_status)
        
        try:
            # Ensure FTC API is initialized
            if self.ftc_api is None:
                await self.initialize()
            
            if self.ftc_api is None:
                raise RuntimeError("FTC API service is not initialized")
            
            # Get specific team from FTC API
            logger.info(f"Fetching team {team_number} from FTC API for season {season}")
            
            # Use the teams endpoint with teamNumber filter
            teams_data, metadata = await self.ftc_api.get_teams(
                season, 
                teamNumber=team_number
            )
            
            if not teams_data or len(teams_data) == 0:
                logger.warning(f"No team data received for team {team_number}, season {season}")
                sync_status.status = "completed"
                sync_status.errorMessage = f"No team data found for team {team_number}"
                await self.update_sync_status(sync_status)
                return {
                    "success": False,
                    "message": f"No team data found for team {team_number}",
                    "recordsProcessed": 0,
                    "recordsUpdated": 0
                }
            
            # Process the team
            team_data = teams_data[0]  # Should only be one team
            try:
                # Convert API data to model
                team = convert_ftc_api_team(team_data, season)
                
                # Add HTTP caching headers
                team.lastModified = metadata.get('lastModified')
                team.etag = metadata.get('etag')
                team.apiLastModified = datetime.now(timezone.utc) if metadata.get('lastModified') else None
                
                # Save team to DynamoDB
                team_dict = team.model_dump() if hasattr(team, 'model_dump') else team.dict()
                success = self.db_service.save_team(team_dict)
                
                if success:
                    sync_status.status = "completed"
                    sync_status.recordsProcessed = 1
                    sync_status.recordsUpdated = 1
                    
                    await self.update_sync_status(sync_status)
                    
                    logger.info(f"Team {team_number} sync completed successfully")
                    
                    return {
                        "success": True,
                        "message": f"Team {team_number} sync completed for season {season}",
                        "recordsProcessed": 1,
                        "recordsUpdated": 1,
                        "bandwidthSaved": metadata.get('bandwidthSaved', 0),
                        "team": team_dict
                    }
                else:
                    raise Exception(f"Failed to save team {team_number} to DynamoDB")
                    
            except Exception as e:
                logger.error(f"Error processing team {team_number}: {str(e)}")
                raise
                
        except Exception as e:
            sync_status.status = "failed"
            sync_status.errorMessage = str(e)
            await self.update_sync_status(sync_status)
            
            logger.error(f"Team {team_number} sync failed: {str(e)}")
            raise
    
    async def sync_teams_by_season(self, season: Optional[int] = None) -> Dict[str, Any]:
        """Sync all teams for a specific season with full pagination support"""
        if season is None:
            season = self.current_season
        
        logger.info(f"Starting teams sync for season {season}")
        
        # Create sync status
        sync_status = await self.create_sync_status("teams", season)
        await self.update_sync_status(sync_status)
        
        try:
            # Ensure FTC API is initialized
            if self.ftc_api is None:
                await self.initialize()
            
            if self.ftc_api is None:
                raise RuntimeError("FTC API service is not initialized")
            
            # Get teams with full pagination
            logger.info(f"Fetching teams from FTC API for season {season}")
            teams_data, metadata = await self.ftc_api.get_teams(season)
            
            if not teams_data:
                logger.warning(f"No teams data received for season {season}")
                sync_status.status = "completed"
                sync_status.errorMessage = "No teams data received"
                await self.update_sync_status(sync_status)
                return {
                    "success": False,
                    "message": "No teams data received",
                    "recordsProcessed": 0,
                    "recordsUpdated": 0
                }
            
            logger.info(f"Processing {len(teams_data)} teams for season {season}")
            
            # Process teams in batches
            batch_size = 25  # DynamoDB batch write limit
            teams_processed = 0
            teams_updated = 0
            
            for i in range(0, len(teams_data), batch_size):
                batch = teams_data[i:i + batch_size]
                batch_teams = []
                
                for team_data in batch:
                    try:
                        # Convert API data to model
                        team = convert_ftc_api_team(team_data, season)
                        
                        # Add HTTP caching headers
                        team.lastModified = metadata.get('lastModified')
                        team.etag = metadata.get('etag')
                        team.apiLastModified = datetime.now(timezone.utc) if metadata.get('lastModified') else None
                        
                        # Always update teams (overwrite existing records)
                        team_dict = team.model_dump() if hasattr(team, 'model_dump') else team.dict()
                        batch_teams.append(team_dict)
                        teams_updated += 1
                        
                        teams_processed += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing team {team_data.get('teamNumber', 'unknown')}: {str(e)}")
                        continue
                
                # Batch save teams
                if batch_teams:
                    success = self.db_service.batch_save_teams(batch_teams)
                    if not success:
                        logger.error(f"Failed to save batch of {len(batch_teams)} teams")
                
                # Update progress
                if teams_processed % 100 == 0:
                    logger.info(f"Processed {teams_processed}/{len(teams_data)} teams")
            
            sync_status.status = "completed"
            sync_status.recordsProcessed = teams_processed
            sync_status.recordsUpdated = teams_updated
            
            await self.update_sync_status(sync_status)
            
            logger.info(f"Teams sync completed: {teams_processed} processed, {teams_updated} updated")
            
            return {
                "success": True,
                "message": f"Teams sync completed for season {season}",
                "recordsProcessed": teams_processed,
                "recordsUpdated": teams_updated,
                "bandwidthSaved": metadata.get('bandwidthSaved', 0)
            }
            
        except Exception as e:
            sync_status.status = "failed"
            sync_status.errorMessage = str(e)
            await self.update_sync_status(sync_status)
            
            logger.error(f"Teams sync failed: {str(e)}")
            raise
    
    async def close(self):
        """Clean up resources"""
        if self.ftc_api:
            await self.ftc_api.close()
        self.db_service.clear_cache()


async def lambda_handler(event, context):
    """Lambda handler for teams synchronization"""
    
    # Initialize service
    sync_service = TeamsSyncService()
    
    try:
        # Ensure FTC API is initialized before any sync calls
        await sync_service.initialize()
        
        # Extract parameters from event
        season = event.get('season', 2024)
        team_number = event.get('teamNumber')
        
        logger.info(f"Starting teams sync: season={season}, teamNumber={team_number}")
        
        if team_number:
            # Sync specific team
            result = await sync_service.sync_team_by_number(team_number, season)
        else:
            # Sync all teams for season
            result = await sync_service.sync_teams_by_season(season)
        
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
