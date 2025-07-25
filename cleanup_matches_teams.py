#!/usr/bin/env python3
"""
Script to remove team information from FTC_Matches_stage table.
Team information should only be stored in FTC_Events_stage.
"""

import boto3
import json
from boto3.dynamodb.conditions import Key
from decimal import Decimal

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
matches_table = dynamodb.Table('FTC_Matches_stage')

def decimal_default(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def clean_match_item(item):
    """Remove team-related fields from a match item"""
    # Fields to remove
    fields_to_remove = ['teams', 'redTeams', 'blueTeams', 'allTeams']
    
    # Create a copy without the team fields
    cleaned_item = {}
    for key, value in item.items():
        if key not in fields_to_remove:
            cleaned_item[key] = value
    
    return cleaned_item

def main():
    print("Starting cleanup of team information from FTC_Matches_stage table...")
    
    try:
        # Scan all items in the matches table
        response = matches_table.scan()
        items = response['Items']
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = matches_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response['Items'])
        
        print(f"Found {len(items)} matches to process")
        
        updated_count = 0
        for item in items:
            # Check if item has team information that needs to be removed
            has_team_info = any(field in item for field in ['teams', 'redTeams', 'blueTeams', 'allTeams'])
            
            if has_team_info:
                print(f"Cleaning match: {item.get('matchId', 'Unknown')}")
                
                # Clean the item
                cleaned_item = clean_match_item(item)
                
                # Update the item in DynamoDB
                matches_table.put_item(Item=cleaned_item)
                updated_count += 1
                
                if updated_count % 10 == 0:
                    print(f"Updated {updated_count} matches...")
        
        print(f"Cleanup completed! Updated {updated_count} matches.")
        print("Team information removed from matches table.")
        print("Team information remains in FTC_Events_stage table only.")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("✅ Cleanup successful!")
    else:
        print("❌ Cleanup failed!")
