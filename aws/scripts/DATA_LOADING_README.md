# Data Loading Scripts - README

## Overview

This directory contains Python scripts to load historical FTC data from JSON files into DynamoDB tables.

## Scripts

| Script | Purpose | Records | Est. Time |
|--------|---------|---------|-----------|
| **load_teams_data.py** | Load teams data | ~30,000 | 2-5 min |
| **load_events_data.py** | Load events data | ~5,000 | 1-2 min |
| **load_matches_data.py** | Load matches data | ~120,000 | 10-15 min |
| **load_team_match_epa_data.py** | Load EPA data | ~500,000 | 30-45 min |
| **load_all_data.py** | Run all loaders | ~655,000 | 45-60 min |

## Prerequisites

### 1. AWS Configuration
```bash
# Configure AWS CLI with credentials
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

### 2. Python Dependencies
```bash
pip install boto3
```

### 3. DynamoDB Tables
Tables must be created before loading data:
```bash
aws cloudformation create-stack \
  --stack-name ftc-predictor-dynamodb-dev \
  --template-body file://new-dynamodb-schema.yaml \
  --parameters ParameterKey=Environment,ParameterValue=dev
```

### 4. Data Files
Ensure these JSON files are in the same directory:
- `teams_2022.json`, `teams_2023.json`, `teams_2024.json`, `teams_2025.json`
- `events_2022.json`, `events_2023.json`, `events_2024.json`, `events_2025.json`
- `matches_2022.json`, `matches_2023.json`, `matches_2024.json`, `matches_2025.json`
- `team_match_epa_2022.json`, `team_match_epa_2023.json`, `team_match_epa_2024.json`, `team_match_epa_2025.json`

## Quick Start

### Option 1: Load All Data (Recommended)
```bash
cd /Users/ashok/other/FTC-Predictor/aws/scripts
python3 load_all_data.py
```

This will:
1. Prompt for confirmation
2. Run all loaders in sequence
3. Show progress for each loader
4. Provide a final summary

### Option 2: Load Individual Data Types
```bash
# Load teams
python3 load_teams_data.py

# Load events
python3 load_events_data.py

# Load matches
python3 load_matches_data.py

# Load EPA data
python3 load_team_match_epa_data.py
```

## Configuration

Each script has configuration variables at the top:

```python
SEASONS = [2022, 2023, 2024, 2025]  # Seasons to load
BATCH_SIZE = 25                      # DynamoDB batch size
ENVIRONMENT = 'dev'                  # Target environment
```

### Change Environment
To load into a different environment (stage/prod):

```python
# Edit the script and change:
ENVIRONMENT = 'stage'  # or 'prod'
```

Or use environment variable:
```bash
export FTC_ENVIRONMENT=stage
python3 load_teams_data.py
```

## Script Details

### 1. load_teams_data.py

**Input Files:** `teams_YYYY.json`

**Data Structure:**
```json
{
  "season": 2022,
  "teams": [
    {
      "teamNumber": 1234,
      "nameFull": "Team Name",
      "city": "City",
      "country": "USA",
      "homeRegion": "USCHS",
      ...
    }
  ]
}
```

**DynamoDB Schema:**
- Primary Key: `teamNumber` (Number)
- Sort Key: `season` (Number)
- Indexes: SeasonIndex, CountrySeasonIndex, RegionSeasonIndex

**Features:**
- Adds `season` field to each team
- Converts null values appropriately
- Handles missing optional fields
- Verifies count after loading

---

### 2. load_events_data.py

**Input Files:** `events_YYYY.json`

**Data Structure:**
```json
{
  "season": 2022,
  "events": [
    {
      "eventId": "abc-123",
      "code": "USCASD",
      "name": "San Diego Qualifier",
      "dateStart": "2024-01-15T00:00:00",
      ...
    }
  ]
}
```

**DynamoDB Schema:**
- Primary Key: `eventId` (String)
- Indexes: CodeSeasonIndex, SeasonDateIndex, RegionSeasonIndex

**Features:**
- Adds `season` field to each event
- Preserves date strings
- Handles complex fields (coordinates, webcasts)
- Verifies count after loading

---

### 3. load_matches_data.py

**Input Files:** `matches_YYYY.json`

**Data Structure:**
```json
{
  "season": 2022,
  "matchesByEvent": {
    "USCASD": {
      "matches": [
        {
          "matchNumber": 1,
          "tournamentLevel": "QUALIFICATION",
          "scoreRedFinal": 125,
          "scoreBlueFinal": 98,
          "teams": [...]
        }
      ]
    }
  }
}
```

**DynamoDB Schema:**
- Primary Key: `matchId` (String) - Format: `YYYY-CODE-LEVEL-SERIES-NUM`
- Composite Attribute: `eventCode_matchNumber` for quick lookups
- Indexes: EventSeasonIndex, EventMatchNumberIndex, SeasonIndex

**Features:**
- Creates composite `matchId` key
- Creates `eventCode_matchNumber` for quick lookups
- Extracts `teamNumbers` array from teams
- Handles nested match data

---

### 4. load_team_match_epa_data.py

**Input Files:** `team_match_epa_YYYY.json`

**Data Structure:**
```json
{
  "season": 2022,
  "teamMatchRecords": [
    {
      "teamNumber": 1234,
      "matchId": "2022-USCASD-QUALIFICATION-0-1",
      "eventCode": "USCASD",
      "matchEPA": 85.5,
      "cumulativeEPA": 1234.5,
      "epaComponents": {...},
      "teamScoreContribution": {...},
      ...
    }
  ]
}
```

**DynamoDB Schema:**
- Primary Key: `teamNumber_matchId` (String) - Format: `TEAM-MATCHID`
- Indexes: TeamSeasonIndex, TeamEventIndex, EventMatchIndex, TeamSeasonTimeIndex, SeasonIndex

**Features:**
- Creates composite `teamNumber_matchId` key
- Preserves all EPA components
- Handles nested objects (epaComponents, scores, etc.)
- Progress indicator for large dataset
- Saves failed items to file for retry

**⚠️ Note:** This is the largest dataset and may take 30-45 minutes to load.

---

## Progress Monitoring

All scripts show progress indicators:

```
Processing Season 2022
----------------------------------------------------------------------
Loading teams from teams_2022.json...
  Found 6960 teams for season 2022
  Preparing 6960 items for DynamoDB...
  Prepared 6960 items
  Writing to DynamoDB...
    Progress: 6960/6960 items written
  ✓ Written: 6960, Failed: 0
  Verifying data...
  Verification: Expected 6960, Found 6960
  ✓ Verification passed for season 2022
```

## Error Handling

### Common Errors

#### 1. Table Not Found
```
✗ Table 'FTC_Teams_dev' not found!
```
**Solution:** Create tables first using CloudFormation template.

#### 2. File Not Found
```
⚠️  File not found: teams_2022.json
```
**Solution:** Ensure JSON files are in the same directory as scripts.

#### 3. AWS Credentials Error
```
botocore.exceptions.NoCredentialsError
```
**Solution:** Configure AWS credentials with `aws configure`.

#### 4. Throttling Error
```
ProvisionedThroughputExceededException
```
**Solution:** Scripts have built-in delays. If still occurring, increase delay in code.

#### 5. Permission Error
```
AccessDeniedException
```
**Solution:** Ensure IAM user/role has these permissions:
- `dynamodb:PutItem`
- `dynamodb:BatchWriteItem`
- `dynamodb:Query`
- `dynamodb:Scan`

### Failed Items

If items fail to load, the EPA loader saves them to:
```
failed_epa_items_dev.json
```

You can retry loading these items manually.

## Verification

After loading, verify data:

### 1. Check Item Counts
```bash
# Teams
aws dynamodb scan --table-name FTC_Teams_dev --select COUNT

# Events
aws dynamodb scan --table-name FTC_Events_dev --select COUNT

# Matches
aws dynamodb scan --table-name FTC_Matches_dev --select COUNT

# EPA
aws dynamodb scan --table-name FTC_TeamMatchEPA_dev --select COUNT
```

### 2. Query Sample Data
```bash
# Get a specific team
aws dynamodb get-item \
  --table-name FTC_Teams_dev \
  --key '{"teamNumber": {"N": "1234"}, "season": {"N": "2024"}}'

# Get events for a season
aws dynamodb query \
  --table-name FTC_Events_dev \
  --index-name SeasonDateIndex \
  --key-condition-expression "season = :season" \
  --expression-attribute-values '{":season": {"N": "2024"}}'
```

### 3. Check DynamoDB Console
1. Go to [DynamoDB Console](https://console.aws.amazon.com/dynamodb/)
2. Select each table
3. Click "Explore table items"
4. Verify data looks correct

## Performance Tips

### 1. Increase Batch Size (Carefully)
```python
BATCH_SIZE = 25  # Max allowed by DynamoDB
```

### 2. Reduce Delay Between Batches
```python
time.sleep(0.05)  # Reduce if not throttling
```

### 3. Use Parallel Loading
Run multiple scripts in parallel (different terminals):
```bash
# Terminal 1
python3 load_teams_data.py

# Terminal 2
python3 load_events_data.py

# Terminal 3
python3 load_matches_data.py
```

**⚠️ Warning:** Don't run the same script twice simultaneously!

### 4. Use On-Demand Billing
The CloudFormation template uses `PAY_PER_REQUEST` billing mode, which automatically scales with load.

## Troubleshooting

### Script Hangs
- Check network connection
- Check AWS credentials
- Check if table exists
- Look for error messages in output

### Slow Performance
- Check internet speed
- Reduce batch size if throttling
- Check DynamoDB metrics in CloudWatch
- Consider using AWS EC2 instance for faster upload

### Data Mismatch
- Check source JSON file format
- Verify season numbers are correct
- Check for duplicate records
- Review preparation logic in script

### Memory Issues
For very large files:
- Process one season at a time
- Increase system memory
- Use streaming JSON parser

## Cleanup

To remove all loaded data:

```bash
# Delete and recreate tables
aws cloudformation delete-stack --stack-name ftc-predictor-dynamodb-dev

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name ftc-predictor-dynamodb-dev

# Recreate tables
aws cloudformation create-stack \
  --stack-name ftc-predictor-dynamodb-dev \
  --template-body file://new-dynamodb-schema.yaml \
  --parameters ParameterKey=Environment,ParameterValue=dev
```

## Next Steps

After loading data:

1. **Verify Data**
   - Check item counts
   - Query sample records
   - Validate data integrity

2. **Update Application**
   - Update Lambda functions
   - Update API endpoints
   - Update frontend queries

3. **Test Queries**
   - Use examples from SCHEMA_SUMMARY.md
   - Test all query patterns
   - Verify performance

4. **Monitor Costs**
   - Check DynamoDB metrics
   - Monitor request costs
   - Set up CloudWatch alarms

## Support

For issues:
1. Check error messages in script output
2. Review AWS CloudWatch logs
3. Check DynamoDB table metrics
4. Verify JSON file formats
5. Review MIGRATION_GUIDE.md

## Summary

| Step | Command | Time |
|------|---------|------|
| 1. Create tables | `aws cloudformation create-stack ...` | 5 min |
| 2. Load all data | `python3 load_all_data.py` | 45-60 min |
| 3. Verify data | `aws dynamodb scan ...` | 2 min |
| **Total** | | **~1 hour** |

---

**Last Updated:** November 10, 2025
**Scripts Version:** 1.0


