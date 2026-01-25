#!/usr/bin/env python3
"""
Load teams data from JSON files into DynamoDB
Reads teams_YYYY.json files and loads into FTC_Teams table
"""
import boto3
import json
import sys
import time
from decimal import Decimal
from typing import Dict, List, Any
from botocore.exceptions import ClientError

# Configuration
SEASONS = [2025]  # Only load 2025 data
BATCH_SIZE = 25  # DynamoDB batch write limit
ENVIRONMENT = 'stage'  # Change to 'dev' or 'prod' as needed

def convert_floats_to_decimal(obj):
    """Convert float values to Decimal for DynamoDB"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    return obj

def load_teams_from_file(filename: str, season: int) -> List[Dict[str, Any]]:
    """Load teams data from JSON file"""
    print(f"Loading teams from {filename}...")
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        teams = data.get('teams', [])
        print(f"  Found {len(teams)} teams for season {season}")
        
        # Add season to each team record
        for team in teams:
            team['season'] = season
        
        return teams
    except FileNotFoundError:
        print(f"  ⚠️  File not found: {filename}")
        return []
    except json.JSONDecodeError as e:
        print(f"  ✗ Error parsing JSON: {e}")
        return []
    except Exception as e:
        print(f"  ✗ Error loading file: {e}")
        return []

def prepare_team_item(team: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare team item for DynamoDB"""
    # Convert None values to empty strings or remove them
    item = {}
    
    # Required fields
    item['teamNumber'] = team['teamNumber']
    item['season'] = team['season']
    
    # Optional string fields
    string_fields = [
        'displayTeamNumber', 'nameFull', 'nameShort', 'schoolName',
        'city', 'stateProv', 'website', 'robotName',
        'districtCode', 'homeCMP', 'displayLocation'
    ]
    
    for field in string_fields:
        if field in team and team[field] is not None and str(team[field]).strip():
            item[field] = str(team[field])
    
    # Fields used in GSI - must not be empty strings
    # country is used in CountrySeasonIndex
    if 'country' in team and team['country'] is not None and str(team['country']).strip():
        item['country'] = str(team['country'])
    else:
        item['country'] = 'UNKNOWN'  # Default value for empty countries
    
    # homeRegion is used in RegionSeasonIndex
    if 'homeRegion' in team and team['homeRegion'] is not None and str(team['homeRegion']).strip():
        item['homeRegion'] = str(team['homeRegion'])
    else:
        item['homeRegion'] = 'UNKNOWN'  # Default value for empty regions
    
    # Numeric fields
    if 'rookieYear' in team and team['rookieYear'] is not None:
        item['rookieYear'] = team['rookieYear']
    if 'matchCount' in team and team['matchCount'] is not None:
        item['matchCount'] = team['matchCount']
    else:
        item['matchCount'] = 0
    
    # Historic EPA (NEW - embedded from teams_YYYY.json)
    # This is a pre-calculated aggregated EPA with season breakdown
    if 'historicEPA' in team and team['historicEPA']:
        item['historicEPA'] = team['historicEPA']
    
    # Convert floats to Decimal (including nested historicEPA)
    item = convert_floats_to_decimal(item)
    
    return item

def batch_write_items(dynamodb, table_name: str, items: List[Dict[str, Any]]) -> tuple:
    """Write items to DynamoDB in batches"""
    table = dynamodb.Table(table_name)
    
    total_items = len(items)
    written = 0
    failed = 0
    
    # Process in batches of 25 (DynamoDB limit)
    for i in range(0, total_items, BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        
        try:
            with table.batch_writer() as writer:
                for item in batch:
                    writer.put_item(Item=item)
            
            written += len(batch)
            
            # Progress indicator
            if written % 100 == 0:
                print(f"    Progress: {written}/{total_items} items written", end='\r')
        
        except ClientError as e:
            print(f"\n  ✗ Error writing batch: {e}")
            failed += len(batch)
        
        # Small delay to avoid throttling
        time.sleep(0.1)
    
    print(f"    Progress: {written}/{total_items} items written")
    
    return written, failed

def verify_data(dynamodb, table_name: str, season: int, expected_count: int):
    """Verify data was loaded correctly"""
    table = dynamodb.Table(table_name)
    
    try:
        # Query using SeasonIndex
        response = table.query(
            IndexName='SeasonIndex',
            KeyConditionExpression='season = :season',
            ExpressionAttributeValues={':season': season},
            Select='COUNT'
        )
        
        actual_count = response['Count']
        
        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = table.query(
                IndexName='SeasonIndex',
                KeyConditionExpression='season = :season',
                ExpressionAttributeValues={':season': season},
                Select='COUNT',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            actual_count += response['Count']
        
        print(f"  Verification: Expected {expected_count}, Found {actual_count}")
        
        if actual_count == expected_count:
            print(f"  ✓ Verification passed for season {season}")
            return True
        else:
            print(f"  ⚠️  Count mismatch for season {season}")
            return False
    
    except ClientError as e:
        print(f"  ✗ Error verifying data: {e}")
        return False

def main():
    print("=" * 70)
    print("FTC Teams Data Loader")
    print("=" * 70)
    print()
    
    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table_name = f'FTC_Teams_{ENVIRONMENT}'
    
    print(f"Target table: {table_name}")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Seasons to load: {SEASONS}")
    print()
    
    # Verify table exists
    try:
        table = dynamodb.Table(table_name)
        table.load()
        print(f"✓ Table '{table_name}' found")
    except ClientError:
        print(f"✗ Table '{table_name}' not found!")
        print("Please create the table first using the CloudFormation template.")
        sys.exit(1)
    
    print()
    print("-" * 70)
    
    # Load data for each season
    total_written = 0
    total_failed = 0
    
    for season in SEASONS:
        print(f"\nProcessing Season {season}")
        print("-" * 70)
        
        filename = f"teams_{season}.json"
        
        # Load teams from file
        teams = load_teams_from_file(filename, season)
        
        if not teams:
            print(f"  Skipping season {season} (no data)")
            continue
        
        # Prepare items for DynamoDB
        print(f"  Preparing {len(teams)} items for DynamoDB...")
        items = []
        for team in teams:
            try:
                item = prepare_team_item(team)
                items.append(item)
            except Exception as e:
                print(f"  ⚠️  Error preparing team {team.get('teamNumber')}: {e}")
        
        print(f"  Prepared {len(items)} items")
        
        # Write to DynamoDB
        print(f"  Writing to DynamoDB...")
        written, failed = batch_write_items(dynamodb, table_name, items)
        
        total_written += written
        total_failed += failed
        
        print(f"  ✓ Written: {written}, Failed: {failed}")
        
        # Verify data
        print(f"  Verifying data...")
        verify_data(dynamodb, table_name, season, len(teams))
    
    # Final summary
    print()
    print("=" * 70)
    print("Loading Complete")
    print("=" * 70)
    print(f"Total items written: {total_written}")
    print(f"Total items failed: {total_failed}")
    
    if total_failed == 0:
        print("\n✓ All data loaded successfully!")
    else:
        print(f"\n⚠️  {total_failed} items failed to load")
    
    # Final verification
    print()
    print("Final Verification:")
    print("-" * 70)
    
    try:
        table = dynamodb.Table(table_name)
        response = table.scan(Select='COUNT')
        total_count = response['Count']
        
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                Select='COUNT',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            total_count += response['Count']
        
        print(f"Total items in table: {total_count}")
    except ClientError as e:
        print(f"Error getting total count: {e}")

if __name__ == "__main__":
    main()

