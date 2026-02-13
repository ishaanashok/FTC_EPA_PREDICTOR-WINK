#!/usr/bin/env python3
"""
Populate the Teams table from FIRST Inspires API
Fetches all team information and stores in DynamoDB
"""

import os
import sys
import json
import boto3
import requests
import argparse
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "services"))
from dynamodb_service import DynamoDBService

# FTC API configuration
FTC_API_BASE_URL = "https://ftc-api.firstinspires.org/v2.0"
CURRENT_SEASON = 2025

class TeamPopulator:
    def __init__(self, environment: str = "stage"):
        self.environment = environment
        self.db_service = DynamoDBService(environment)
        
        # Get FTC API credentials from Secrets Manager
        self.ftc_username = None
        self.ftc_api_key = None
        self._load_credentials()
    
    def _load_credentials(self):
        """Load FTC API credentials from AWS Secrets Manager"""
        try:
            secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
            response = secrets_client.get_secret_value(SecretId='FTC-API-Credentials-stage')
            credentials = json.loads(response['SecretString'])
            self.ftc_username = credentials.get('username')
            self.ftc_api_key = credentials.get('apiKey')
            print(f"✓ Loaded FTC API credentials")
        except Exception as e:
            print(f"✗ Failed to load credentials: {e}")
            raise
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make a request to the FTC API with retry logic"""
        url = f"{FTC_API_BASE_URL}{endpoint}"
        auth = (self.ftc_username, self.ftc_api_key)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, auth=auth, timeout=15)
                
                if response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = 2 ** attempt
                    print(f"  Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    print(f"  Attempt {attempt + 1} failed: {e}, retrying...")
                    time.sleep(1)
                else:
                    print(f"  Error: {e}")
                    return None
        
        return None
    
    def fetch_all_teams(self, season: int) -> List[Dict[str, Any]]:
        """Fetch all teams for a season from FTC API"""
        print(f"\nFetching all teams for season {season}...")
        
        all_teams = []
        page_size = 50
        skip = 0
        
        while True:
            params = {
                'pageSize': page_size,
                'skip': skip
            }
            
            print(f"  Fetching teams {skip} to {skip + page_size}...")
            data = self._make_request(f"/{season}/teams", params)
            
            if not data:
                print(f"  Failed to fetch page at skip={skip}")
                break
            
            teams = data.get('teams', [])
            if not teams:
                print(f"  No more teams found. Total: {len(all_teams)}")
                break
            
            all_teams.extend(teams)
            print(f"  Found {len(teams)} teams this page, total so far: {len(all_teams)}")
            
            # Check if there are more teams
            if len(teams) < page_size:
                print(f"  Reached end of teams. Total: {len(all_teams)}")
                break
            
            skip += page_size
            time.sleep(0.1)  # Small delay between requests
        
        return all_teams
    
    def enrich_team_data(self, team: Dict[str, Any], season: int) -> Dict[str, Any]:
        """Enrich team data with required fields for DynamoDB"""
        
        enriched = {
            'teamNumber': team.get('teamNumber', 0),
            'season': season,
            'teamName': team.get('teamName', ''),
            'schoolName': team.get('schoolName', ''),
            'city': team.get('city', ''),
            'stateProv': team.get('stateProv', ''),
            'country': team.get('country', 'USA'),
            'website': team.get('website', ''),
            'lastUpdated': datetime.now(timezone.utc).isoformat(),
        }
        
        # Determine region/country for GSI
        if enriched['country'] and enriched['country'].upper() not in ['USA', 'UNITED STATES']:
            enriched['homeRegion'] = enriched['country']
        else:
            # For US teams, use state as region
            enriched['homeRegion'] = enriched['stateProv'] if enriched['stateProv'] else 'UNKNOWN'
        
        # Ensure defaults for GSI fields
        if not enriched['country']:
            enriched['country'] = 'USA'
        if not enriched['homeRegion']:
            enriched['homeRegion'] = 'UNKNOWN'
        
        # Initialize EPA tracking
        enriched['epaStats'] = {
            'matchCount': 0,
            'cumulativeEPA': 0.0,
            'averageEPA': 0.0,
            'lastEventCode': None,
            'lastEventDate': None,
        }
        
        return enriched
    
    def populate_teams(self, season: int, batch_size: int = 25) -> Dict[str, int]:
        """Populate all teams for a season"""
        
        print(f"\n{'='*60}")
        print(f"Starting team population for season {season}")
        print(f"{'='*60}")
        
        # Fetch all teams
        api_teams = self.fetch_all_teams(season)
        print(f"\nTotal teams from API: {len(api_teams)}")
        
        if not api_teams:
            print("✗ No teams found!")
            return {'success': 0, 'failed': 0, 'skipped': 0}
        
        # Get existing teams to avoid duplicates
        print(f"\nChecking for existing teams...")
        existing_teams = self.db_service.get_teams_by_season(season, region='UNKNOWN')
        existing_team_numbers = {t.get('teamNumber') for t in existing_teams}
        print(f"Found {len(existing_teams)} existing teams")
        
        # Enrich team data
        print(f"\nEnriching team data...")
        teams_to_save = []
        for team in api_teams:
            enriched = self.enrich_team_data(team, season)
            teams_to_save.append(enriched)
        
        # Save teams in batches
        print(f"\nSaving {len(teams_to_save)} teams to DynamoDB...")
        stats = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
        }
        
        for i in range(0, len(teams_to_save), batch_size):
            batch = teams_to_save[i:i + batch_size]
            
            for team in batch:
                team_number = team.get('teamNumber')
                
                if team_number in existing_team_numbers:
                    stats['skipped'] += 1
                    continue
                
                success = self.db_service.save_team(team)
                if success:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
            
            print(f"  Processed {min(i + batch_size, len(teams_to_save))}/{len(teams_to_save)} teams...")
            time.sleep(0.1)
        
        return stats
    
    def verify_teams(self, season: int) -> int:
        """Verify teams were populated correctly"""
        print(f"\nVerifying team population...")
        
        try:
            teams = self.db_service.get_teams_by_season(season)
            count = len(teams)
            
            print(f"✓ Found {count} teams for season {season}")
            
            # Show sample teams
            if teams:
                print(f"\n  Sample teams:")
                for team in teams[:5]:
                    print(f"    - Team {team.get('teamNumber')}: {team.get('teamName')} ({team.get('city')}, {team.get('stateProv')})")
            
            return count
        except Exception as e:
            print(f"✗ Verification failed: {e}")
            return 0


def main():
    parser = argparse.ArgumentParser(description='Populate teams from FIRST Inspires API')
    parser.add_argument('--season', type=int, default=CURRENT_SEASON, help=f'Season to populate (default: {CURRENT_SEASON})')
    parser.add_argument('--environment', default='stage', help='Environment (stage/dev/prod)')
    parser.add_argument('--batch-size', type=int, default=25, help='Batch size for DynamoDB writes')
    
    args = parser.parse_args()
    
    populator = TeamPopulator(environment=args.environment)
    
    # Populate teams
    stats = populator.populate_teams(args.season, batch_size=args.batch_size)
    
    print(f"\n{'='*60}")
    print(f"Population Complete!")
    print(f"  Saved: {stats['success']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Skipped (existing): {stats['skipped']}")
    print(f"{'='*60}")
    
    # Verify
    total_teams = populator.verify_teams(args.season)
    
    if stats['success'] > 0 or total_teams > 0:
        print(f"\n✓ Team population completed successfully!")
        return 0
    else:
        print(f"\n✗ Team population failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
