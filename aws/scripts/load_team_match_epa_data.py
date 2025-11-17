#!/usr/bin/env python3
"""
Load team match EPA data from JSON files into DynamoDB
Reads team_match_epa_YYYY.json files and loads into FTC_TeamMatchEPA table
This is the largest dataset (~500K records)
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

def load_epa_from_file(filename: str, season: int) -> List[Dict[str, Any]]:
    """Load EPA data from JSON file"""
    print(f"Loading EPA data from {filename}...")
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        records = data.get('teamMatchRecords', [])
        print(f"  Found {len(records)} EPA records for season {season}")
        
        # Add season to each record (if not already present)
        for record in records:
            if 'season' not in record:
                record['season'] = season
        
        return records
    except FileNotFoundError:
        print(f"  ⚠️  File not found: {filename}")
        return []
    except json.JSONDecodeError as e:
        print(f"  ✗ Error parsing JSON: {e}")
        return []
    except Exception as e:
        print(f"  ✗ Error loading file: {e}")
        return []

def prepare_epa_item(record: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare EPA item for DynamoDB"""
    item = {}
    
    # Required fields
    team_number = record['teamNumber']
    match_id = record['matchId']
    
    # Create composite primary key
    item['teamNumber_matchId'] = f"{team_number}-{match_id}"
    item['teamNumber'] = team_number
    item['matchId'] = match_id
    item['season'] = record.get('season', 2022)
    
    # eventCode is used in GSI - must not be empty
    if 'eventCode' in record and record['eventCode'] is not None and str(record['eventCode']).strip():
        item['eventCode'] = str(record['eventCode'])
    else:
        item['eventCode'] = 'UNKNOWN'
    
    # actualStartTime is used in GSI - must not be empty
    if 'actualStartTime' in record and record['actualStartTime'] is not None and str(record['actualStartTime']).strip():
        item['actualStartTime'] = str(record['actualStartTime'])
    else:
        item['actualStartTime'] = '1970-01-01T00:00:00'
    
    # Other string fields
    string_fields = [
        'eventName', 'tournamentLevel', 'description',
        'alliance', 'station', 'postResultTime'
    ]
    
    for field in string_fields:
        if field in record and record[field] is not None and str(record[field]).strip():
            item[field] = str(record[field])
    
    # Numeric fields
    numeric_fields = [
        'matchNumber', 'series', 'matchCount', 'allianceTeamCount'
    ]
    
    for field in numeric_fields:
        if field in record and record[field] is not None:
            item[field] = record[field]
    
    # Float/Decimal fields (EPA values)
    decimal_fields = [
        'matchEPA', 'cumulativeEPA', 'averageEPA'
    ]
    
    for field in decimal_fields:
        if field in record and record[field] is not None:
            item[field] = record[field]
    
    # Boolean fields
    if 'hasScores' in record:
        item['hasScores'] = bool(record['hasScores'])
    
    # Complex nested objects
    complex_fields = [
        'epaComponents', 'teamScoreContribution', 'runningAverages',
        'allianceScore', 'opponentScore'
    ]
    
    for field in complex_fields:
        if field in record and record[field] is not None:
            item[field] = record[field]
    
    # Arrays
    array_fields = ['allianceTeamNumbers', 'opponentTeamNumbers']
    
    for field in array_fields:
        if field in record and record[field] is not None:
            item[field] = record[field]
    
    # Convert floats to Decimal
    item = convert_floats_to_decimal(item)
    
    return item

def batch_write_items(dynamodb, table_name: str, items: List[Dict[str, Any]]) -> tuple:
    """Write items to DynamoDB in batches"""
    table = dynamodb.Table(table_name)
    
    total_items = len(items)
    written = 0
    failed = 0
    failed_items = []
    
    # Process in batches of 25 (DynamoDB limit)
    for i in range(0, total_items, BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        
        try:
            with table.batch_writer() as writer:
                for item in batch:
                    writer.put_item(Item=item)
            
            written += len(batch)
            
            # Progress indicator
            if written % 1000 == 0:
                print(f"    Progress: {written}/{total_items} items written ({(written/total_items)*100:.1f}%)", end='\r')
        
        except ClientError as e:
            print(f"\n  ✗ Error writing batch: {e}")
            failed += len(batch)
            failed_items.extend(batch)
        except Exception as e:
            print(f"\n  ✗ Unexpected error: {e}")
            failed += len(batch)
        
        # Small delay to avoid throttling
        time.sleep(0.05)
    
    print(f"    Progress: {written}/{total_items} items written (100.0%)")
    
    return written, failed, failed_items

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
    print("FTC Team Match EPA Data Loader")
    print("=" * 70)
    print()
    print("⚠️  This is the largest dataset (~500K records)")
    print("   Loading may take 30-60 minutes depending on network speed")
    print()
    
    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table_name = f'FTC_TeamMatchEPA_{ENVIRONMENT}'
    
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
    all_failed_items = []
    
    start_time = time.time()
    
    for season in SEASONS:
        print(f"\nProcessing Season {season}")
        print("-" * 70)
        
        filename = f"team_match_epa_{season}.json"
        
        # Load EPA data from file
        records = load_epa_from_file(filename, season)
        
        if not records:
            print(f"  Skipping season {season} (no data)")
            continue
        
        # Prepare items for DynamoDB
        print(f"  Preparing {len(records)} items for DynamoDB...")
        items = []
        prep_errors = 0
        
        for record in records:
            try:
                item = prepare_epa_item(record)
                items.append(item)
            except Exception as e:
                prep_errors += 1
                if prep_errors <= 5:  # Only show first 5 errors
                    print(f"  ⚠️  Error preparing record: {e}")
        
        if prep_errors > 5:
            print(f"  ⚠️  ... and {prep_errors - 5} more preparation errors")
        
        print(f"  Prepared {len(items)} items ({prep_errors} errors)")
        
        # Write to DynamoDB
        print(f"  Writing to DynamoDB (this may take several minutes)...")
        season_start = time.time()
        
        written, failed, failed_items = batch_write_items(dynamodb, table_name, items)
        
        season_elapsed = time.time() - season_start
        
        total_written += written
        total_failed += failed
        all_failed_items.extend(failed_items)
        
        print(f"  ✓ Written: {written}, Failed: {failed}")
        print(f"  ⏱️  Time taken: {season_elapsed:.1f} seconds")
        
        # Verify data
        print(f"  Verifying data...")
        verify_data(dynamodb, table_name, season, len(records) - prep_errors)
    
    total_elapsed = time.time() - start_time
    
    # Final summary
    print()
    print("=" * 70)
    print("Loading Complete")
    print("=" * 70)
    print(f"Total items written: {total_written}")
    print(f"Total items failed: {total_failed}")
    print(f"Total time: {total_elapsed/60:.1f} minutes")
    
    if total_failed == 0:
        print("\n✓ All data loaded successfully!")
    else:
        print(f"\n⚠️  {total_failed} items failed to load")
        
        # Save failed items to file for retry
        if all_failed_items:
            failed_file = f"failed_epa_items_{ENVIRONMENT}.json"
            try:
                with open(failed_file, 'w') as f:
                    json.dump(all_failed_items, f, indent=2, default=str)
                print(f"   Failed items saved to: {failed_file}")
            except Exception as e:
                print(f"   Could not save failed items: {e}")
    
    # Final verification
    print()
    print("Final Verification:")
    print("-" * 70)
    
    try:
        table = dynamodb.Table(table_name)
        response = table.scan(Select='COUNT')
        total_count = response['Count']
        
        print("Scanning table (this may take a while for large tables)...")
        
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                Select='COUNT',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            total_count += response['Count']
            print(f"  Scanned so far: {total_count} items", end='\r')
        
        print(f"\nTotal items in table: {total_count}")
    except ClientError as e:
        print(f"Error getting total count: {e}")

if __name__ == "__main__":
    main()

