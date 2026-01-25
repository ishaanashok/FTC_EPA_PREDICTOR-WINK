#!/usr/bin/env python3
"""
Script to delete all DynamoDB tables for FTC-Predictor
"""
import boto3
import sys
import time
from botocore.exceptions import ClientError

def list_ftc_tables():
    """List all FTC-related DynamoDB tables"""
    dynamodb = boto3.client('dynamodb')
    
    try:
        response = dynamodb.list_tables()
        all_tables = response.get('TableNames', [])
        
        # Filter for FTC tables
        ftc_tables = [table for table in all_tables if 'FTC' in table or 'ftc' in table.lower()]
        
        return ftc_tables
    except ClientError as e:
        print(f"Error listing tables: {e}")
        return []

def delete_table(table_name):
    """Delete a specific DynamoDB table"""
    dynamodb = boto3.client('dynamodb')
    
    try:
        print(f"Deleting table: {table_name}...")
        dynamodb.delete_table(TableName=table_name)
        
        # Wait for table to be deleted
        waiter = dynamodb.get_waiter('table_not_exists')
        waiter.wait(TableName=table_name)
        
        print(f"✓ Successfully deleted: {table_name}")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"✗ Table not found: {table_name}")
        else:
            print(f"✗ Error deleting {table_name}: {e}")
        return False

def main():
    print("=" * 60)
    print("FTC-Predictor DynamoDB Table Deletion Script")
    print("=" * 60)
    print()
    
    # List all FTC tables
    print("Scanning for FTC-related tables...")
    tables = list_ftc_tables()
    
    if not tables:
        print("No FTC-related tables found.")
        return
    
    print(f"\nFound {len(tables)} FTC-related table(s):")
    for i, table in enumerate(tables, 1):
        print(f"  {i}. {table}")
    
    print("\n" + "=" * 60)
    print("WARNING: This will DELETE all the tables listed above!")
    print("This action CANNOT be undone!")
    print("=" * 60)
    
    # Confirmation
    response = input("\nType 'DELETE' to confirm deletion: ")
    
    if response != 'DELETE':
        print("\nDeletion cancelled.")
        return
    
    print("\nProceeding with deletion...\n")
    
    # Delete each table
    deleted_count = 0
    for table in tables:
        if delete_table(table):
            deleted_count += 1
        time.sleep(1)  # Small delay between deletions
    
    print("\n" + "=" * 60)
    print(f"Deletion complete: {deleted_count}/{len(tables)} tables deleted")
    print("=" * 60)

if __name__ == "__main__":
    main()


