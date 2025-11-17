#!/usr/bin/env python3
"""
Master script to load all FTC data into DynamoDB
Runs all data loaders in sequence: teams, events, matches, EPA
"""
import subprocess
import sys
import time
from datetime import datetime

def run_loader(script_name: str, description: str) -> bool:
    """Run a data loader script"""
    print()
    print("=" * 80)
    print(f"Running: {description}")
    print(f"Script: {script_name}")
    print("=" * 80)
    print()
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            ['python3', script_name],
            check=True,
            capture_output=False,
            text=True
        )
        
        elapsed = time.time() - start_time
        
        print()
        print(f"✓ {description} completed successfully")
        print(f"⏱️  Time taken: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        
        return True
    
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        
        print()
        print(f"✗ {description} failed!")
        print(f"⏱️  Time taken: {elapsed:.1f} seconds")
        print(f"Error: {e}")
        
        return False
    
    except KeyboardInterrupt:
        print()
        print("⚠️  Interrupted by user")
        return False
    
    except Exception as e:
        print()
        print(f"✗ Unexpected error: {e}")
        return False

def main():
    print("=" * 80)
    print("FTC-Predictor Data Loading Suite")
    print("=" * 80)
    print()
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("This script will load all historical data into DynamoDB:")
    print("  1. Teams data (~30,000 records)")
    print("  2. Events data (~5,000 records)")
    print("  3. Matches data (~120,000 records)")
    print("  4. Team Match EPA data (~500,000 records)")
    print()
    print("⚠️  Total estimated time: 30-60 minutes")
    print()
    
    # Confirmation
    response = input("Do you want to proceed? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cancelled.")
        sys.exit(0)
    
    overall_start = time.time()
    
    # Define loaders in order
    loaders = [
        ('load_teams_data.py', 'Teams Data Loader'),
        ('load_events_data.py', 'Events Data Loader'),
        ('load_matches_data.py', 'Matches Data Loader'),
        ('load_team_match_epa_data.py', 'Team Match EPA Data Loader'),
    ]
    
    results = {}
    
    # Run each loader
    for script, description in loaders:
        success = run_loader(script, description)
        results[description] = success
        
        if not success:
            print()
            print("⚠️  A loader failed. Do you want to continue with remaining loaders?")
            response = input("Continue? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("Stopping.")
                break
        
        # Brief pause between loaders
        time.sleep(2)
    
    overall_elapsed = time.time() - overall_start
    
    # Final summary
    print()
    print()
    print("=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print()
    
    for description, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"{status:12} - {description}")
    
    print()
    print(f"Total time: {overall_elapsed/60:.1f} minutes")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Overall status
    all_success = all(results.values())
    
    if all_success:
        print("🎉 All data loaded successfully!")
        print()
        print("Next steps:")
        print("  1. Verify data in DynamoDB console")
        print("  2. Test queries using SCHEMA_SUMMARY.md examples")
        print("  3. Update Lambda functions to use new schema")
        print("  4. Update API endpoints")
        print("  5. Test application functionality")
    else:
        failed_count = sum(1 for success in results.values() if not success)
        print(f"⚠️  {failed_count} loader(s) failed")
        print()
        print("Please review the errors above and:")
        print("  1. Check AWS credentials and permissions")
        print("  2. Verify tables exist in DynamoDB")
        print("  3. Check data file formats")
        print("  4. Re-run failed loaders individually")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    main()


