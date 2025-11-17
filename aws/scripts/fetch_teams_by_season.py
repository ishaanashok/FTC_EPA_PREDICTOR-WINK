#!/usr/bin/env python3
"""
FTC Teams Fetcher Script

This script fetches all team details for a given season from the FTC API,
handles pagination automatically, and stores the data in a JSON file.

Usage:
    python fetch_teams_by_season.py <season>
    
Example:
    python fetch_teams_by_season.py 2024

Environment Variables:
    FTC_API_USERNAME: Your FTC API username
    FTC_API_KEY: Your FTC API key
    AWS_ACCESS_KEY_ID: Your AWS Access Key ID
    AWS_SECRET_ACCESS_KEY: Your AWS Secret Access Key
    AWS_DEFAULT_REGION: Your AWS region (default: us-east-1)

The script will create a file named 'teams_<season>.json' with all team data.
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Load environment variables from .env file
try:
    from load_env import load_env_file
    load_env_file()
except ImportError:
    # If load_env.py is not available, try to load manually
    from pathlib import Path
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Import the existing FTC API service
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services'))
from ftc_api_service import FTCApiService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('fetch_teams.log')
    ]
)
logger = logging.getLogger(__name__)


class TeamsFetcher:
    """Fetches all teams for a given season from the FTC API"""
    
    def __init__(self, username: str, api_key: str):
        """Initialize the teams fetcher with FTC API credentials"""
        self.credentials = {
            'username': username,
            'api_key': api_key
        }
        self.api_service = FTCApiService(self.credentials)
    
    async def fetch_all_teams(self, season: int) -> Tuple[List[Dict], Dict[str, Any]]:
        """
        Fetch all teams for a given season with pagination
        
        Args:
            season: The competition season (e.g., 2024)
            
        Returns:
            Tuple of (teams_list, metadata)
        """
        logger.info(f"Starting to fetch all teams for season {season}")
        
        try:
            # Initialize the API service
            await self.api_service.initialize()
            
            # Fetch all teams with pagination
            teams, metadata = await self.api_service.get_teams(season)
            
            if teams is None:
                logger.warning(f"No teams data returned for season {season}")
                return [], metadata
            
            logger.info(f"Successfully fetched {len(teams)} teams for season {season}")
            logger.info(f"Total pages processed: {metadata.get('totalPages', 'unknown')}")
            logger.info(f"Response size: {metadata.get('responseSize', 0)} bytes")
            
            return teams, metadata
            
        except Exception as e:
            logger.error(f"Error fetching teams for season {season}: {str(e)}")
            raise
        finally:
            # Clean up the API service
            await self.api_service.close()
    
    def save_teams_to_json(self, teams: List[Dict], season: int, metadata: Dict[str, Any]) -> str:
        """
        Save teams data to a JSON file
        
        Args:
            teams: List of team dictionaries
            season: The competition season
            metadata: API response metadata
            
        Returns:
            The filename of the saved file
        """
        filename = f"teams_{season}.json"
        
        # Prepare the data structure
        output_data = {
            "season": season,
            "fetchedAt": datetime.now().isoformat(),
            "totalTeams": len(teams),
            "metadata": {
                "totalPages": metadata.get('totalPages', 0),
                "totalRecords": metadata.get('totalRecords', 0),
                "responseSize": metadata.get('responseSize', 0),
                "lastModified": metadata.get('lastModified'),
                "etag": metadata.get('etag')
            },
            "teams": teams
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Successfully saved {len(teams)} teams to {filename}")
            logger.info(f"File size: {os.path.getsize(filename)} bytes")
            
            return filename
            
        except Exception as e:
            logger.error(f"Error saving teams to {filename}: {str(e)}")
            raise
    
    async def fetch_and_save_teams(self, season: int) -> str:
        """
        Fetch all teams for a season and save to JSON file
        
        Args:
            season: The competition season
            
        Returns:
            The filename of the saved file
        """
        logger.info(f"Fetching and saving teams for season {season}")
        
        # Fetch teams
        teams, metadata = await self.fetch_all_teams(season)
        
        if not teams:
            logger.warning(f"No teams found for season {season}")
            # Still save an empty file with metadata
            teams = []
        
        # Save to JSON file
        filename = self.save_teams_to_json(teams, season, metadata)
        
        logger.info(f"Process completed successfully. Data saved to {filename}")
        return filename


def get_credentials() -> Tuple[str, str]:
    """Get FTC API credentials from environment variables"""
    username = os.getenv('FTC_API_USERNAME')
    api_key = os.getenv('FTC_API_KEY')
    
    if not username or not api_key:
        logger.error("FTC API credentials not found in environment variables")
        logger.error("Please set FTC_API_USERNAME and FTC_API_KEY environment variables")
        logger.error("You can also create a .env file with these variables")
        sys.exit(1)
    
    return username, api_key


def setup_aws_credentials():
    """Setup AWS credentials from environment variables"""
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    
    if aws_access_key and aws_secret_key:
        # Set AWS credentials in environment for boto3
        os.environ['AWS_ACCESS_KEY_ID'] = aws_access_key
        os.environ['AWS_SECRET_ACCESS_KEY'] = aws_secret_key
        os.environ['AWS_DEFAULT_REGION'] = aws_region
        logger.info(f"AWS credentials configured for region: {aws_region}")
    else:
        logger.warning("AWS credentials not found in environment variables")
        logger.warning("Some features may not work without AWS access")
        logger.warning("Run 'python setup_teams_fetcher.py' to configure credentials")


def validate_season(season: int) -> bool:
    """Validate that the season is reasonable"""
    current_year = datetime.now().year
    if season < 2010 or season > current_year + 1:
        logger.error(f"Invalid season {season}. Season should be between 2010 and {current_year + 1}")
        return False
    return True


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Fetch all FTC teams for a given season",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python fetch_teams_by_season.py 2024
    python fetch_teams_by_season.py 2023
    
Environment Variables:
    FTC_API_USERNAME: Your FTC API username
    FTC_API_KEY: Your FTC API key
    AWS_ACCESS_KEY_ID: Your AWS Access Key ID
    AWS_SECRET_ACCESS_KEY: Your AWS Secret Access Key
    AWS_DEFAULT_REGION: Your AWS region (default: us-east-1)
    
The script will create a file named 'teams_<season>.json' with all team data.
        """
    )
    
    parser.add_argument(
        'season',
        type=int,
        help='Competition season (e.g., 2024)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='.',
        help='Output directory for the JSON file (default: current directory)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate season
    if not validate_season(args.season):
        sys.exit(1)
    
    # Get credentials
    try:
        username, api_key = get_credentials()
        setup_aws_credentials()
    except SystemExit:
        return
    
    # Change to output directory if specified
    if args.output_dir != '.':
        os.makedirs(args.output_dir, exist_ok=True)
        os.chdir(args.output_dir)
    
    # Create fetcher and run
    fetcher = TeamsFetcher(username, api_key)
    
    try:
        start_time = datetime.now()
        logger.info(f"Starting teams fetch for season {args.season}")
        
        filename = await fetcher.fetch_and_save_teams(args.season)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info(f"✅ Successfully completed in {duration.total_seconds():.2f} seconds")
        logger.info(f"📁 Data saved to: {os.path.abspath(filename)}")
        
        # Print summary
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
                print(f"\n📊 Summary:")
                print(f"   Season: {data['season']}")
                print(f"   Total Teams: {data['totalTeams']}")
                print(f"   File: {os.path.abspath(filename)}")
                print(f"   File Size: {os.path.getsize(filename):,} bytes")
                print(f"   Fetched At: {data['fetchedAt']}")
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # Handle asyncio on different Python versions
    try:
        asyncio.run(main())
    except AttributeError:
        # Python < 3.7
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
