#!/usr/bin/env python3
"""
FTC Events Data Fetcher

Comprehensive script to fetch all events, team lists, and match data for a given FTC season.
Creates multiple output files:
- events_<season>.json: Event details with team lists
- matches_<season>.json: All match data and results
- events_<season>_summary.json: Processing summary and statistics

Author: FTC-Predictor Team
Version: 1.0.0
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
import time

# Add the parent directory to the path to import our services
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services'))
sys.path.append(os.path.join(os.path.dirname(__file__)))

from ftc_api_service import FTCApiService
from load_env import load_env_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('fetch_events.log')
    ]
)
logger = logging.getLogger(__name__)

class EventsDataFetcher:
    """Main class for fetching comprehensive FTC events data"""
    
    def __init__(self, season: int, max_concurrent: int = 5, verbose: bool = False):
        self.season = season
        self.max_concurrent = max_concurrent
        self.verbose = verbose
        self.api_service = None
        
        # Statistics tracking
        self.stats = {
            'start_time': time.time(),
            'events_found': 0,
            'events_processed': 0,
            'teams_collected': 0,
            'matches_collected': 0,
            'api_calls_made': 0,
            'errors_encountered': 0,
            'retry_attempts': 0
        }
        
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
    
    async def initialize(self):
        """Initialize the API service"""
        try:
            username, api_key = get_credentials()
            credentials = {'username': username, 'api_key': api_key}
            
            self.api_service = FTCApiService(credentials)
            await self.api_service.initialize()
            
            # Setup AWS credentials
            setup_aws_credentials()
            
            logger.info(f"🚀 Starting events data fetch for season {self.season}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            return False
    
    async def fetch_all_events(self) -> List[Dict[str, Any]]:
        """Stage 1: Fetch all events for the season"""
        logger.info("🔄 Stage 1/2: Fetching events list...")
        
        try:
            events_data, metadata = await self.api_service.get_events(self.season)
            self.stats['api_calls_made'] += 1
            
            if events_data is None:
                logger.error("❌ No events data received from API")
                return []
            
            self.stats['events_found'] = len(events_data)
            logger.info(f"✅ Found {len(events_data):,} events for season {self.season}")
            
            if self.verbose:
                logger.debug(f"Events metadata: {metadata}")
            
            return events_data
            
        except Exception as e:
            logger.error(f"❌ Error fetching events: {e}")
            self.stats['errors_encountered'] += 1
            return []
    
    
    async def fetch_event_matches_with_retry(self, event_code: str, max_retries: int = 3) -> Tuple[str, List[Dict], Optional[str]]:
        """Fetch matches for a single event with retry logic"""
        all_matches = []
        
        for attempt in range(max_retries):
            try:
                # Fetch both qualification and playoff matches
                qual_matches, qual_meta = await self.api_service.get_event_matches(
                    self.season, event_code, tournament_level="qual"
                )
                self.stats['api_calls_made'] += 1
                
                playoff_matches, playoff_meta = await self.api_service.get_event_matches(
                    self.season, event_code, tournament_level="playoff"
                )
                self.stats['api_calls_made'] += 1
                
                # Combine matches
                if qual_matches:
                    all_matches.extend(qual_matches)
                if playoff_matches:
                    all_matches.extend(playoff_matches)
                
                return event_code, all_matches, None
                
            except Exception as e:
                self.stats['retry_attempts'] += 1
                if attempt == max_retries - 1:
                    error_msg = f"Failed after {max_retries} attempts: {str(e)}"
                    logger.warning(f"⚠️  Event {event_code} matches: {error_msg}")
                    return event_code, [], error_msg
                
                wait_time = 2 ** attempt
                logger.debug(f"Retry {attempt + 1} for event {event_code} matches in {wait_time}s")
                await asyncio.sleep(wait_time)
        
        return event_code, [], "Max retries exceeded"
    
    
    async def fetch_matches_for_events(self, events: List[Dict]) -> Dict[str, Any]:
        """Stage 2: Fetch match data for all events concurrently"""
        logger.info("🔄 Stage 2/2: Fetching match data for events...")
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def fetch_with_semaphore(event):
            async with semaphore:
                # Handle different event data structures
                event_code = event.get('eventCode') or event.get('code')
                if not event_code:
                    logger.warning(f"⚠️  Event missing eventCode: {event}")
                    return event.get('code', 'UNKNOWN'), [], "Missing event code"
                return await self.fetch_event_matches_with_retry(event_code)
        
        # Create progress tracking
        total_events = len(events)
        completed = 0
        
        # Process events in batches to show progress
        batch_size = 25  # Smaller batches for matches (more data per request)
        matches_by_event = {}
        errors = {}
        
        for i in range(0, total_events, batch_size):
            batch = events[i:i + batch_size]
            tasks = [fetch_with_semaphore(event) for event in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"❌ Batch processing error: {result}")
                    self.stats['errors_encountered'] += 1
                    continue
                
                event_code, matches_list, error = result
                completed += 1
                
                if error:
                    errors[event_code] = error
                    self.stats['errors_encountered'] += 1
                else:
                    matches_by_event[event_code] = matches_list
                    self.stats['matches_collected'] += len(matches_list)
                
                # Show progress
                progress = (completed / total_events) * 100
                print(f"\rProgress: [{('█' * int(progress // 2.5)).ljust(40)}] {completed}/{total_events} ({progress:.1f}%)", end='', flush=True)
        
        print()  # New line after progress bar
        
        logger.info(f"✅ Collected {self.stats['matches_collected']:,} matches from {len(matches_by_event):,} events")
        
        return {
            'matches_by_event': matches_by_event,
            'errors': errors
        }
    
    def create_events_data(self, events: List[Dict]) -> Dict[str, Any]:
        """Create the main events data structure"""
        return {
            'season': self.season,
            'totalEvents': len(events),
            'fetchedAt': datetime.now(timezone.utc).isoformat(),
            'metadata': {
                'processingTime': f"{time.time() - self.stats['start_time']:.1f} seconds",
                'includesTeamLists': False,
                'includesMatches': False,
                'apiCallsMade': self.stats['api_calls_made'],
                'errorsEncountered': self.stats['errors_encountered']
            },
            'events': events
        }
    
    def create_matches_data(self, events: List[Dict], matches_data: Dict) -> Dict[str, Any]:
        """Create the matches data structure"""
        matches_by_event = {}
        
        for event in events:
            event_code = event.get('eventCode') or event.get('code', '')
            event_matches = matches_data['matches_by_event'].get(event_code, [])
            
            if event_matches:
                # Categorize matches
                qual_matches = [m for m in event_matches if m.get('tournamentLevel', '').lower() == 'qual']
                playoff_matches = [m for m in event_matches if m.get('tournamentLevel', '').lower() == 'playoff']
                
                matches_by_event[event_code] = {
                    'eventCode': event_code,
                    'eventName': event.get('eventName', ''),
                    'totalMatches': len(event_matches),
                    'qualificationMatches': len(qual_matches),
                    'playoffMatches': len(playoff_matches),
                    'matches': event_matches
                }
        
        return {
            'season': self.season,
            'totalMatches': self.stats['matches_collected'],
            'totalEvents': len(events),
            'fetchedAt': datetime.now(timezone.utc).isoformat(),
            'metadata': {
                'processingTime': f"{time.time() - self.stats['start_time']:.1f} seconds",
                'eventsProcessed': len(events),
                'eventsWithMatches': len(matches_by_event),
                'eventsWithErrors': len(matches_data['errors']),
                'averageMatchesPerEvent': round(self.stats['matches_collected'] / max(len(matches_by_event), 1), 1),
                'apiCallsMade': self.stats['api_calls_made'],
                'errorsEncountered': self.stats['errors_encountered']
            },
            'matchesByEvent': matches_by_event,
            'errors': matches_data['errors']
        }
    
    def create_summary_data(self, events_data: Dict, matches_data: Dict, file_sizes: Dict) -> Dict[str, Any]:
        """Create summary statistics"""
        events = events_data['events']
        
        # Calculate statistics
        event_types = {}
        countries = set()
        states = set()
        
        for event in events:
            # Event types
            event_type = event.get('typeName', event.get('type', 'Unknown'))
            event_types[event_type] = event_types.get(event_type, 0) + 1
            
            # Geographic data
            if event.get('country'):
                countries.add(event['country'])
            if event.get('stateprov'):
                states.add(event['stateprov'])
        
        processing_time = time.time() - self.stats['start_time']
        
        return {
            'season': self.season,
            'summary': {
                'totalEvents': len(events),
                'totalMatches': self.stats['matches_collected'],
                'averageMatchesPerEvent': round(self.stats['matches_collected'] / max(len(events), 1), 1),
                'eventTypes': dict(sorted(event_types.items(), key=lambda x: x[1], reverse=True)),
                'countriesRepresented': len(countries),
                'statesRepresented': len(states)
            },
            'processingStats': {
                'totalProcessingTime': f"{processing_time:.1f} seconds",
                'eventsProcessed': len(events),
                'matchesProcessed': self.stats['matches_collected'],
                'apiCallsMade': self.stats['api_calls_made'],
                'errorsEncountered': self.stats['errors_encountered'],
                'retryAttempts': self.stats['retry_attempts']
            },
            'files': file_sizes
        }
    
    async def close(self):
        """Clean up resources"""
        if self.api_service:
            await self.api_service.close()

def get_credentials() -> Tuple[str, str]:
    """Get FTC API credentials from environment variables"""
    # Try to load from .env file first
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        load_env_file(env_file)
    
    username = os.getenv('FTC_API_USERNAME')
    api_key = os.getenv('FTC_API_KEY')
    
    if not username or not api_key:
        logger.error("❌ FTC API credentials not found!")
        logger.error("Please set FTC_API_USERNAME and FTC_API_KEY environment variables")
        logger.error("Or run 'python setup_teams_fetcher.py' to configure credentials")
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

def save_json_file(data: Dict[str, Any], filepath: str) -> int:
    """Save data to JSON file and return file size"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        file_size = os.path.getsize(filepath)
        logger.info(f"✅ Saved {filepath} ({file_size:,} bytes, {file_size/1024/1024:.1f} MB)")
        return file_size
        
    except Exception as e:
        logger.error(f"❌ Error saving {filepath}: {e}")
        return 0

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Fetch comprehensive FTC events data for a given season",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python fetch_events_by_season.py 2024
    python fetch_events_by_season.py 2024 --verbose
    python fetch_events_by_season.py 2024 --events-only
    python fetch_events_by_season.py 2024 -o /path/to/output -c 10

Environment Variables:
    FTC_API_USERNAME: Your FTC API username
    FTC_API_KEY: Your FTC API key
    AWS_ACCESS_KEY_ID: Your AWS Access Key ID (optional)
    AWS_SECRET_ACCESS_KEY: Your AWS Secret Access Key (optional)
    AWS_DEFAULT_REGION: Your AWS region (default: us-east-1)

Output Files:
    events_<season>.json: Event details with team lists
    matches_<season>.json: All match data and results
    events_<season>_summary.json: Processing summary and statistics
        """
    )
    
    parser.add_argument('season', type=int, help='FTC season year (e.g., 2024)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--output-dir', '-o', default='.', help='Output directory for JSON files')
    parser.add_argument('--max-concurrent', '-c', type=int, default=5, help='Max concurrent API requests (default: 5)')
    parser.add_argument('--events-only', action='store_true', help='Fetch only event details and teams (no matches)')
    
    args = parser.parse_args()
    
    # Validate season
    current_year = datetime.now().year
    if args.season < 2007 or args.season > current_year + 1:
        logger.error(f"❌ Invalid season: {args.season}. Must be between 2007 and {current_year + 1}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize fetcher
    fetcher = EventsDataFetcher(args.season, args.max_concurrent, args.verbose)
    
    try:
        # Initialize API service
        if not await fetcher.initialize():
            sys.exit(1)
        
        # Stage 1: Fetch all events
        events = await fetcher.fetch_all_events()
        if not events:
            logger.error("❌ No events found. Exiting.")
            sys.exit(1)
        
        # Stage 2: Fetch matches (unless events-only mode)
        if args.events_only:
            logger.info("📋 Events-only mode: Skipping match data collection")
            matches_data = {'matches_by_event': {}, 'errors': {}}
        else:
            matches_data = await fetcher.fetch_matches_for_events(events)
        
        # Create data structures (no team fetching)
        events_json = fetcher.create_events_data(events)
        matches_json = fetcher.create_matches_data(events, matches_data)
        
        # Save files
        events_file = output_dir / f"events_{args.season}.json"
        matches_file = output_dir / f"matches_{args.season}.json"
        summary_file = output_dir / f"events_{args.season}_summary.json"
        
        file_sizes = {}
        
        # Save events file
        events_size = save_json_file(events_json, str(events_file))
        file_sizes['eventsFile'] = events_file.name
        file_sizes['eventsFileSize'] = f"{events_size/1024/1024:.1f} MB"
        
        # Save matches file (unless events-only)
        if not args.events_only:
            matches_size = save_json_file(matches_json, str(matches_file))
            file_sizes['matchesFile'] = matches_file.name
            file_sizes['matchesFileSize'] = f"{matches_size/1024/1024:.1f} MB"
        else:
            file_sizes['matchesFile'] = "Not created (events-only mode)"
            file_sizes['matchesFileSize'] = "0 MB"
        
        # Create and save summary
        summary_json = fetcher.create_summary_data(events_json, matches_json, file_sizes)
        summary_size = save_json_file(summary_json, str(summary_file))
        file_sizes['summaryFile'] = summary_file.name
        file_sizes['summaryFileSize'] = f"{summary_size/1024:.1f} KB"
        
        # Final summary
        processing_time = time.time() - fetcher.stats['start_time']
        
        logger.info("🎉 Processing completed successfully!")
        logger.info("📊 Final Summary:")
        logger.info(f"   • Events: {len(events):,} total")
        if not args.events_only:
            logger.info(f"   • Matches: {fetcher.stats['matches_collected']:,} total matches")
        logger.info(f"   • Processing time: {processing_time:.1f} seconds")
        logger.info(f"   • API calls made: {fetcher.stats['api_calls_made']:,}")
        logger.info(f"   • Files created: {len([f for f in file_sizes.values() if 'Not created' not in str(f)])}")
        logger.info(f"📁 Output files saved to: {output_dir.absolute()}")
        
    except KeyboardInterrupt:
        logger.info("⏹️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        await fetcher.close()

if __name__ == "__main__":
    asyncio.run(main())
