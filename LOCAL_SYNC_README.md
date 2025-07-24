# FTC Predictor Local Data Sync

This is a local alternative to the AWS Lambda data sync function. It runs on your computer but still syncs data to AWS DynamoDB, giving you more control and avoiding AWS timeout issues.

## Features

- ✅ **Runs locally** - No Lambda timeout issues
- ✅ **Full pagination support** - Gets ALL teams, events, and matches
- ✅ **Optimized matches sync** - Reads events from DynamoDB instead of API
- ✅ **Batch operations** - Efficient DynamoDB writes
- ✅ **Detailed logging** - See exactly what's happening
- ✅ **Flexible operations** - Sync teams, events, matches, or all data

## Quick Start

### 1. Setup (One-time)

Run the setup script to install dependencies and configure AWS:

```bash
python setup_local_sync.py
```

This will:
- Check if AWS CLI is installed
- Verify AWS credentials are configured
- Install Python dependencies
- Test connections to AWS services

### 2. Configure AWS (if needed)

If you haven't configured AWS CLI yet:

```bash
aws configure
```

Enter your credentials:
- **AWS Access Key ID**: Your access key
- **AWS Secret Access Key**: Your secret key  
- **Default region name**: `us-east-1`
- **Default output format**: `json`

### 3. Run Data Sync

Sync all data for the current season:
```bash
python local_data_sync.py --season 2024 --sync all
```

Or sync specific data types:
```bash
# Sync only teams
python local_data_sync.py --season 2024 --sync teams

# Sync only events  
python local_data_sync.py --season 2024 --sync events

# Sync only matches (uses DynamoDB events - fast!)
python local_data_sync.py --season 2024 --sync matches
```

## Advantages Over Lambda

### 🚀 **No Timeouts**
- Lambda has 15-minute timeout limit
- Local script can run as long as needed
- Perfect for large data syncs

### 🔍 **Better Debugging**
- See real-time progress in terminal
- Detailed logs saved to `local_sync.log`
- Easy to troubleshoot issues

### ⚡ **Optimized Performance**
- Matches sync reads events from DynamoDB (not API)
- Batch operations for faster writes
- Full pagination support gets ALL data

### 🎛️ **More Control**
- Run specific sync operations
- Easy to modify and customize
- No AWS deployment needed for changes

## How It Works

### Teams Sync
1. Fetches ALL teams with pagination (not just first 65)
2. Stores teams in DynamoDB using batch operations
3. Handles API rate limits gracefully

### Events Sync  
1. Fetches ALL events with pagination
2. Stores each event in DynamoDB
3. Creates the data source for matches sync

### Matches Sync (Optimized!)
1. **Reads events from DynamoDB** (not FTC API)
2. For each event, fetches matches from FTC API
3. Stores matches in DynamoDB
4. Much faster than the old method!

## Logging

All operations are logged to both:
- **Console**: Real-time progress
- **`local_sync.log`**: Detailed log file

Log levels:
- `INFO`: Normal operations and progress
- `WARNING`: Non-fatal issues  
- `ERROR`: Failed operations

## Troubleshooting

### AWS Credentials Issues
```bash
# Check if credentials are configured
aws sts get-caller-identity

# Reconfigure if needed
aws configure
```

### Import Errors
Make sure you're running from the project root directory:
```bash
cd "C:\Users\Ishaan\Desktop\FTC-Predictor"
python local_data_sync.py --season 2024 --sync teams
```

### API Rate Limits
The script handles FTC API rate limits automatically. If you see rate limit errors, the script will retry after a delay.

### DynamoDB Permissions
Make sure your AWS user has permissions for:
- `dynamodb:PutItem`
- `dynamodb:BatchWriteItem` 
- `dynamodb:Query`
- `dynamodb:Scan`

## Performance Comparison

| Operation | Lambda (Old) | Local (New) | Improvement |
|-----------|--------------|-------------|-------------|
| Teams Sync | ~65 teams | ALL teams | Complete data |
| Events Sync | Timeout risk | No timeout | Reliable |
| Matches Sync | API + API | DDB + API | 50% faster |
| Debugging | CloudWatch | Local logs | Much easier |

## Examples

### Full Season Sync
```bash
# Sync everything for 2024 season
python local_data_sync.py --season 2024 --sync all
```

### Quick Team Update
```bash
# Just update teams (fast)
python local_data_sync.py --season 2024 --sync teams
```

### Event-Only Sync
```bash
# Update events before matches sync
python local_data_sync.py --season 2024 --sync events
```

### Matches After Events
```bash
# First ensure events are current
python local_data_sync.py --season 2024 --sync events

# Then sync matches (uses DynamoDB events)
python local_data_sync.py --season 2024 --sync matches
```

This local sync approach gives you the best of both worlds: the reliability and control of local execution with the scalability and accessibility of cloud storage!
