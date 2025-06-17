#!/usr/bin/env python3
"""
FTC API Performance Test Script

This script helps test the performance of the API calls in the FTC Predictor app.
It will run a series of API calls and measure the time taken for each call.
"""

import asyncio
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.api_utils import ftc_api_request

async def test_api_performance():
    print("Starting API performance test...")
    
    # Test a variety of API endpoints
    test_endpoints = [
        # Season data
        ("/2024", None, "Season data"),
        
        # Events data
        ("/2024/events", None, "All events"),
        ("/2024/events", {"eventCode": "USMOCHAMP"}, "Single event by code"),
        ("/2024/events", {"teamNumber": 11142}, "Events by team"),
        
        # Team data
        ("/2024/teams", None, "All teams"),
        ("/2024/teams", {"teamNumber": 11142}, "Single team"),
        ("/2024/teams", {"eventCode": "USMOCHAMP"}, "Teams at event"),
        
        # Matches data
        ("/2024/matches/USMOCHAMP", None, "All matches at event"),
        ("/2024/matches/USMOCHAMP", {"teamNumber": 11142}, "Team matches at event"),
        ("/2024/matches/USMOCHAMP", {"tournamentLevel": "qual"}, "Qual matches at event"),
        
        # Rankings data
        ("/2024/rankings/USMOCHAMP", None, "Rankings at event"),
    ]
    
    results = []
    for endpoint, params, description in test_endpoints:
        print(f"\nTesting: {description} - {endpoint} with params {params}")
        try:
            start_time = time.time()
            response = await ftc_api_request(endpoint, params)
            end_time = time.time()
            elapsed = end_time - start_time
            
            # Get response size for analysis
            response_size = sys.getsizeof(str(response))
            
            print(f"✅ Success: {description} in {elapsed:.2f} seconds, size: {response_size/1024:.1f} KB")
            results.append((description, endpoint, params, elapsed, response_size, True))
        except Exception as e:
            print(f"❌ Error: {description} - {str(e)}")
            results.append((description, endpoint, params, 0, 0, False))
    
    # Print summary
    print("\n" + "=" * 80)
    print("API PERFORMANCE TEST RESULTS")
    print("=" * 80)
    
    success_count = sum(1 for r in results if r[5])
    print(f"Total endpoints tested: {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(results) - success_count}")
    
    if success_count > 0:
        avg_time = sum(r[3] for r in results if r[5]) / success_count
        print(f"Average response time: {avg_time:.2f} seconds")
    
    # Sort by time
    sorted_results = sorted(results, key=lambda x: x[3], reverse=True)
    
    print("\nSlowest API calls:")
    for i, (description, endpoint, params, elapsed, size, success) in enumerate(sorted_results[:5], 1):
        if success:
            print(f"{i}. {description} - {endpoint}: {elapsed:.2f}s ({size/1024:.1f} KB)")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(test_api_performance())
