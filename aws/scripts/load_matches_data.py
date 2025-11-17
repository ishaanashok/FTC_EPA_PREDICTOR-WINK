#!/usr/bin/env python3
"""
Load matches data from JSON files into DynamoDB
Reads matches_YYYY.json files and loads into FTC_Matches table
"""
import boto3
import json
import sys
import time
from decimal import Decimal
from typing import Dict, List, Any
from botocore.exceptions import ClientError

# Configuration
#SEASONS = [2022, 2023, 2024, 2025]
SEASONS = [2025]
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

def load_matches_from_file(filename: str, season: int) -> List[Dict[str, Any]]:
    """Load matches data from JSON file"""
    print(f"Loading matches from {filename}...")
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Extract all matches from matchesByEvent
        matches_by_event = data.get('matchesByEvent', {})
        all_matches = []
        
        for event_code, event_data in matches_by_event.items():
            matches = event_data.get('matches', [])
            
            for match in matches:
                # Add season and eventCode to each match
                match['season'] = season
                match['eventCode'] = event_code
                match['eventName'] = event_data.get('eventName', '')
                all_matches.append(match)
        
        print(f"  Found {len(all_matches)} matches across {len(matches_by_event)} events for season {season}")
        
        return all_matches
    except FileNotFoundError:
        print(f"  ⚠️  File not found: {filename}")
        return []
    except json.JSONDecodeError as e:
        print(f"  ✗ Error parsing JSON: {e}")
        return []
    except Exception as e:
        print(f"  ✗ Error loading file: {e}")
        return []

def prepare_match_item(match: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare match item for DynamoDB"""
    item = {}
    
    # Required fields
    season = match['season']
    event_code = match.get('eventCode', 'UNKNOWN')
    tournament_level = match.get('tournamentLevel', 'QUALIFICATION')
    series = match.get('series', 0)
    match_number = match.get('matchNumber', 0)
    
    # Ensure eventCode is not empty (used in GSI)
    if not event_code or not str(event_code).strip():
        event_code = 'UNKNOWN'
    
    # Create matchId (composite key)
    item['matchId'] = f"{season}-{event_code}-{tournament_level}-{series}-{match_number}"
    item['season'] = season
    item['eventCode'] = event_code
    
    # Create composite attribute for quick lookup (used in GSI)
    item['eventCode_matchNumber'] = f"{event_code}-{match_number}"
    
    # String fields
    string_fields = [
        'eventName', 'description', 'tournamentLevel',
        'actualStartTime', 'postResultTime'
    ]
    
    for field in string_fields:
        if field in match and match[field] is not None:
            item[field] = str(match[field])
    
    # Numeric fields
    numeric_fields = [
        'series', 'matchNumber',
        'scoreRedFinal', 'scoreRedFoul', 'scoreRedAuto',
        'scoreBlueFinal', 'scoreBlueFoul', 'scoreBlueAuto'
    ]
    
    for field in numeric_fields:
        if field in match and match[field] is not None:
            item[field] = match[field]
    
    # Teams array
    if 'teams' in match and match['teams']:
        item['teams'] = match['teams']
        
        # Extract team numbers for easier querying
        team_numbers = [team['teamNumber'] for team in match['teams'] if 'teamNumber' in team]
        if team_numbers:
            item['teamNumbers'] = team_numbers
    
    # Convert floats to Decimal
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
            if written % 500 == 0:
                print(f"    Progress: {written}/{total_items} items written", end='\r')
        
        except ClientError as e:
            print(f"\n  ✗ Error writing batch: {e}")
            failed += len(batch)
        
        # Small delay to avoid throttling
        time.sleep(0.05)
    
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
    print("FTC Matches Data Loader")
    print("=" * 70)
    print()
    
    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table_name = f'FTC_Matches_{ENVIRONMENT}'
    
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
        
        filename = f"matches_{season}.json"
        
        # Load matches from file
        matches = load_matches_from_file(filename, season)
        
        if not matches:
            print(f"  Skipping season {season} (no data)")
            continue
        
        # Prepare items for DynamoDB
        print(f"  Preparing {len(matches)} items for DynamoDB...")
        items = []
        for match in matches:
            try:
                item = prepare_match_item(match)
                items.append(item)
            except Exception as e:
                print(f"  ⚠️  Error preparing match: {e}")
        
        print(f"  Prepared {len(items)} items")
        
        # Write to DynamoDB
        print(f"  Writing to DynamoDB...")
        written, failed = batch_write_items(dynamodb, table_name, items)
        
        total_written += written
        total_failed += failed
        
        print(f"  ✓ Written: {written}, Failed: {failed}")
        
        # Verify data
        print(f"  Verifying data...")
        verify_data(dynamodb, table_name, season, len(matches))
    
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

