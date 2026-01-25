# FTC Events Data Fetcher

A comprehensive Python script to fetch complete FTC events data including event details, team lists, and match results for any given season.

## 🚀 Quick Start

```bash
# Basic usage - fetch everything for 2024 season
python fetch_events_by_season.py 2024

# Events and teams only (no matches)
python fetch_events_by_season.py 2024 --events-only

# Verbose logging with custom concurrency
python fetch_events_by_season.py 2024 --verbose --max-concurrent 10
```

## 📋 Features

- **Comprehensive Data Collection**: Events, team lists, and match results
- **Concurrent Processing**: Fast data fetching with configurable concurrency
- **Progress Tracking**: Real-time progress bars and status updates
- **Error Handling**: Robust retry logic and error reporting
- **Multiple Output Formats**: Separate files for different data types
- **Summary Statistics**: Detailed processing and data statistics
- **Flexible Options**: Events-only mode, custom output directories

## 📁 Output Files

The script creates three JSON files for each season:

### 1. `events_<season>.json` - Main Events Data
Contains event details with complete team lists for each event.

```json
{
  "season": 2024,
  "totalEvents": 1234,
  "fetchedAt": "2025-10-26T22:47:41.059967",
  "metadata": {
    "processingTime": "45.2 seconds",
    "includesTeamLists": true,
    "eventsWithTeams": 1180,
    "totalTeamParticipations": 8500
  },
  "events": [
    {
      "eventCode": "USWAABE",
      "eventName": "FTC Washington State Championship",
      "eventType": "Championship",
      "dateStart": "2024-02-24",
      "dateEnd": "2024-02-25",
      "venue": "ShoWare Center",
      "city": "Kent",
      "state": "WA",
      "country": "USA",
      "teamCount": 48,
      "actualTeamCount": 48,
      "teams": [
        {
          "teamNumber": 1234,
          "teamName": "Team Name",
          "schoolName": "School Name",
          "city": "City",
          "state": "State",
          "country": "Country"
        }
      ]
    }
  ]
}
```

### 2. `matches_<season>.json` - Match Data and Results
Contains all match details, scores, and results organized by event.

```json
{
  "season": 2024,
  "totalMatches": 15000,
  "totalEvents": 1234,
  "fetchedAt": "2025-10-26T22:47:41.059967",
  "metadata": {
    "processingTime": "120.5 seconds",
    "eventsWithMatches": 1180,
    "averageMatchesPerEvent": 12.2
  },
  "matchesByEvent": {
    "USWAABE": {
      "eventCode": "USWAABE",
      "eventName": "FTC Washington State Championship",
      "totalMatches": 120,
      "qualificationMatches": 96,
      "playoffMatches": 24,
      "matches": [
        {
          "matchId": "2024-USWAABE-qual-0-1",
          "season": 2024,
          "eventCode": "USWAABE",
          "matchNumber": 1,
          "description": "Qualification 1",
          "tournamentLevel": "qual",
          "startTime": "2024-02-24T09:00:00",
          "teams": [
            {
              "teamNumber": 1234,
              "station": "Red1",
              "dq": false,
              "onField": true
            }
          ],
          "redTeams": [1234, 5678],
          "blueTeams": [9012, 3456],
          "redScore": {
            "alliance": "Red",
            "totalPoints": 145,
            "autoPoints": 35,
            "teleopPoints": 85,
            "endgamePoints": 25,
            "penaltyPoints": 0
          },
          "blueScore": {
            "alliance": "Blue",
            "totalPoints": 132,
            "autoPoints": 28,
            "teleopPoints": 79,
            "endgamePoints": 25,
            "penaltyPoints": 0
          }
        }
      ]
    }
  }
}
```

### 3. `events_<season>_summary.json` - Processing Summary
Contains statistics and metadata about the data collection process.

```json
{
  "season": 2024,
  "summary": {
    "totalEvents": 1234,
    "totalMatches": 15000,
    "uniqueTeams": 6200,
    "averageTeamsPerEvent": 6.9,
    "eventTypes": {
      "League Meet": 800,
      "Qualifier": 300,
      "Championship": 134
    },
    "countriesRepresented": 45,
    "statesRepresented": 52
  },
  "processingStats": {
    "totalProcessingTime": "165.7 seconds",
    "apiCallsMade": 2468,
    "errorsEncountered": 54,
    "retryAttempts": 127
  },
  "files": {
    "eventsFile": "events_2024.json",
    "matchesFile": "matches_2024.json",
    "eventsFileSize": "25.4 MB",
    "matchesFileSize": "180.2 MB"
  }
}
```

## 🛠️ Installation & Setup

### Prerequisites

- Python 3.7+
- FTC API credentials
- Required Python packages (automatically imported from existing codebase)

### Setup Credentials

1. **Option 1: Use existing setup script**
   ```bash
   python setup_teams_fetcher.py
   ```

2. **Option 2: Manual environment variables**
   ```bash
   export FTC_API_USERNAME="your_username"
   export FTC_API_KEY="your_api_key"
   ```

3. **Option 3: Create `.env` file**
   ```bash
   # Create .env file in aws/scripts/ directory
   FTC_API_USERNAME=your_username
   FTC_API_KEY=your_api_key
   AWS_ACCESS_KEY_ID=your_access_key  # Optional
   AWS_SECRET_ACCESS_KEY=your_secret  # Optional
   AWS_DEFAULT_REGION=us-east-1       # Optional
   ```

### Get FTC API Credentials

1. Visit the [FTC API Documentation](https://ftc-api.firstinspires.org/)
2. Register for an account
3. Generate your API credentials
4. Note your username and API key

## 📖 Usage Examples

### Basic Usage

```bash
# Fetch all data for 2024 season
python fetch_events_by_season.py 2024
```

### Advanced Options

```bash
# Events and teams only (faster, smaller files)
python fetch_events_by_season.py 2024 --events-only

# Custom output directory
python fetch_events_by_season.py 2024 --output-dir /path/to/output

# Verbose logging for debugging
python fetch_events_by_season.py 2024 --verbose

# Increase concurrency for faster processing
python fetch_events_by_season.py 2024 --max-concurrent 10

# Combine options
python fetch_events_by_season.py 2024 -v -c 8 -o ./data/
```

### Command Line Arguments

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `season` | - | FTC season year (required) | - |
| `--verbose` | `-v` | Enable verbose logging | False |
| `--output-dir` | `-o` | Output directory for files | Current directory |
| `--max-concurrent` | `-c` | Max concurrent API requests | 5 |
| `--events-only` | - | Skip match data collection | False |

## 📊 Expected Data Volumes

| Season | Events | Teams | Matches | Events File | Matches File | Processing Time |
|--------|--------|-------|---------|-------------|--------------|-----------------|
| 2022   | ~800   | ~5K   | ~10K    | ~8 MB       | ~120 MB      | ~2 minutes      |
| 2023   | ~1000  | ~6K   | ~12K    | ~15 MB      | ~150 MB      | ~2.5 minutes    |
| 2024   | ~1200  | ~8K   | ~15K    | ~25 MB      | ~180 MB      | ~3 minutes      |

## ⚡ Performance Optimization

### Concurrency Settings

- **Default (5 concurrent)**: Safe for most networks, ~3 minutes for 2024
- **Moderate (8-10 concurrent)**: Faster processing, ~2 minutes for 2024
- **Aggressive (15+ concurrent)**: Risk of rate limiting, may cause errors

### Memory Usage

- **Peak Memory**: ~500MB during processing
- **Events-only mode**: ~200MB peak memory
- **Large seasons**: Consider running on machine with 2GB+ RAM

### Network Requirements

- **Bandwidth**: ~50MB download for complete 2024 season
- **API Calls**: ~2,500 requests for complete 2024 season
- **Rate Limiting**: Built-in retry logic handles FTC API limits

## 🔧 Troubleshooting

### Common Issues

#### 1. Authentication Errors (401)
```
❌ Error 401: Unauthorized
```
**Solution**: Check your FTC API credentials
```bash
# Verify credentials are set
echo $FTC_API_USERNAME
echo $FTC_API_KEY

# Or re-run setup
python setup_teams_fetcher.py
```

#### 2. Network Timeouts
```
⚠️ Event USWAABE: Failed after 3 attempts: timeout
```
**Solution**: Reduce concurrency or check network connection
```bash
# Reduce concurrent requests
python fetch_events_by_season.py 2024 --max-concurrent 3
```

#### 3. SSL Certificate Errors
```
❌ SSL certificate verification failed
```
**Solution**: The script automatically handles SSL certificates using `certifi`. If issues persist, check your Python installation.

#### 4. Memory Errors
```
MemoryError: Unable to allocate memory
```
**Solution**: Use events-only mode or increase system memory
```bash
# Events and teams only (much smaller memory footprint)
python fetch_events_by_season.py 2024 --events-only
```

#### 5. File Permission Errors
```
❌ Error saving events_2024.json: Permission denied
```
**Solution**: Check write permissions or specify different output directory
```bash
# Use custom output directory
python fetch_events_by_season.py 2024 --output-dir ~/ftc_data/
```

### Debug Mode

Enable verbose logging to see detailed information:

```bash
python fetch_events_by_season.py 2024 --verbose
```

This will show:
- Detailed API request/response information
- Progress for each batch of events
- Retry attempts and error details
- Memory usage and performance metrics

### Log Files

The script automatically creates `fetch_events.log` with detailed logging information. Check this file for:
- Complete error messages
- API response details
- Performance metrics
- Debugging information

## 🔄 Integration with Existing Tools

### Use with Teams Fetcher

```bash
# Fetch teams data first
python fetch_teams_by_season.py 2024

# Then fetch events data
python fetch_events_by_season.py 2024

# Now you have complete season data:
# - teams_2024.json (all teams)
# - events_2024.json (events with team lists)
# - matches_2024.json (all matches)
```

### Data Analysis Examples

```python
import json

# Load events data
with open('events_2024.json', 'r') as f:
    events_data = json.load(f)

# Find largest events
large_events = [
    event for event in events_data['events'] 
    if event.get('actualTeamCount', 0) > 50
]

# Load matches data
with open('matches_2024.json', 'r') as f:
    matches_data = json.load(f)

# Calculate average scores
total_red_score = 0
total_blue_score = 0
scored_matches = 0

for event_code, event_matches in matches_data['matchesByEvent'].items():
    for match in event_matches['matches']:
        if match.get('redScore') and match.get('blueScore'):
            total_red_score += match['redScore']['totalPoints']
            total_blue_score += match['blueScore']['totalPoints']
            scored_matches += 1

avg_score = (total_red_score + total_blue_score) / (scored_matches * 2)
print(f"Average match score: {avg_score:.1f}")
```

## 🤝 Contributing

This script is part of the FTC-Predictor project. To contribute:

1. Follow the existing code style and patterns
2. Add appropriate error handling and logging
3. Update documentation for any new features
4. Test with multiple seasons and edge cases

## 📝 Version History

- **v1.0.0**: Initial comprehensive events fetcher
  - Event details and team lists
  - Match data collection
  - Concurrent processing with rate limiting
  - Multiple output formats
  - Comprehensive error handling

## 🆘 Support

If you encounter issues:

1. Check this README for common solutions
2. Review the `fetch_events.log` file for detailed error information
3. Try running with `--verbose` flag for more debugging info
4. Reduce concurrency with `--max-concurrent 3` if experiencing timeouts
5. Use `--events-only` mode if you only need event and team data

For persistent issues, check the FTC API status and ensure your credentials are valid and have appropriate permissions.


