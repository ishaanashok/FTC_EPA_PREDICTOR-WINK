#!/usr/bin/env python3
"""
Load events data from JSON files into DynamoDB
Reads events_YYYY.json files and loads into FTC_Events table
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

def load_events_from_file(filename: str, season: int) -> List[Dict[str, Any]]:
    """Load events data from JSON file"""
    print(f"Loading events from {filename}...")
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        events = data.get('events', [])
        print(f"  Found {len(events)} events for season {season}")
        
        # Add season to each event record
        for event in events:
            event['season'] = season
        
        return events
    except FileNotFoundError:
        print(f"  ⚠️  File not found: {filename}")
        return []
    except json.JSONDecodeError as e:
        print(f"  ✗ Error parsing JSON: {e}")
        return []
    except Exception as e:
        print(f"  ✗ Error loading file: {e}")
        return []

def prepare_event_item(event: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare event item for DynamoDB"""
    item = {}
    
    # Required fields
    item['eventId'] = event['eventId']
    item['season'] = event['season']
    
    # String fields (not used in GSI)
    string_fields = [
        'divisionCode', 'name', 'type', 'typeName',
        'leagueCode', 'districtCode', 'venue',
        'address', 'city', 'stateprov', 'country', 'website',
        'liveStreamUrl', 'timezone'
    ]
    
    for field in string_fields:
        if field in event and event[field] is not None and str(event[field]).strip():
            item[field] = str(event[field])
    
    # Fields used in GSI - must not be empty strings
    # code is used in CodeSeasonIndex
    if 'code' in event and event['code'] is not None and str(event['code']).strip():
        item['code'] = str(event['code'])
    else:
        item['code'] = 'UNKNOWN'
    
    # dateStart is used in SeasonDateIndex
    if 'dateStart' in event and event['dateStart'] is not None and str(event['dateStart']).strip():
        item['dateStart'] = str(event['dateStart'])
    else:
        item['dateStart'] = '1970-01-01T00:00:00'  # Default date
    
    # dateEnd
    if 'dateEnd' in event and event['dateEnd'] is not None and str(event['dateEnd']).strip():
        item['dateEnd'] = str(event['dateEnd'])
    
    # regionCode is used in RegionSeasonIndex
    if 'regionCode' in event and event['regionCode'] is not None and str(event['regionCode']).strip():
        item['regionCode'] = str(event['regionCode'])
    else:
        item['regionCode'] = 'UNKNOWN'
    
    # Boolean fields
    bool_fields = ['remote', 'hybrid', 'published']
    for field in bool_fields:
        if field in event:
            item[field] = bool(event[field])
    
    # Numeric fields
    if 'fieldCount' in event and event['fieldCount'] is not None:
        item['fieldCount'] = event['fieldCount']
    
    # Complex fields (coordinates, webcasts)
    if 'coordinates' in event and event['coordinates'] is not None:
        item['coordinates'] = event['coordinates']
    
    if 'webcasts' in event and event['webcasts'] is not None:
        item['webcasts'] = event['webcasts']
    
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
        # Query using SeasonDateIndex
        response = table.query(
            IndexName='SeasonDateIndex',
            KeyConditionExpression='season = :season',
            ExpressionAttributeValues={':season': season},
            Select='COUNT'
        )
        
        actual_count = response['Count']
        
        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = table.query(
                IndexName='SeasonDateIndex',
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
    print("FTC Events Data Loader")
    print("=" * 70)
    print()
    
    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table_name = f'FTC_Events_{ENVIRONMENT}'
    
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
        
        filename = f"events_{season}.json"
        
        # Load events from file
        events = load_events_from_file(filename, season)
        
        if not events:
            print(f"  Skipping season {season} (no data)")
            continue
        
        # Prepare items for DynamoDB
        print(f"  Preparing {len(events)} items for DynamoDB...")
        items = []
        for event in events:
            try:
                item = prepare_event_item(event)
                items.append(item)
            except Exception as e:
                print(f"  ⚠️  Error preparing event {event.get('eventId')}: {e}")
        
        print(f"  Prepared {len(items)} items")
        
        # Write to DynamoDB
        print(f"  Writing to DynamoDB...")
        written, failed = batch_write_items(dynamodb, table_name, items)
        
        total_written += written
        total_failed += failed
        
        print(f"  ✓ Written: {written}, Failed: {failed}")
        
        # Verify data
        print(f"  Verifying data...")
        verify_data(dynamodb, table_name, season, len(events))
    
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

