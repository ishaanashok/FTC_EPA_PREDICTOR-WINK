# Historic EPA Calculator

Calculate historic EPA for FTC teams based on their performance across multiple seasons and update the teams JSON file with this enriched data.

## Overview

This script analyzes team performance across multiple historical seasons (2022-2024) and calculates a weighted historic EPA that can be used for:
- **Team scouting** - Understand team's historical performance
- **Alliance selection** - Identify consistently strong partners
- **Prediction models** - Use as a feature for match outcome predictions
- **Trend analysis** - Track team improvement over time

## Features

✅ **Multi-Season Analysis**: Analyzes team performance across 2022, 2023, and 2024 seasons  
✅ **Weighted Calculation**: More recent seasons have higher weight (2024: 1.0, 2023: 0.7, 2022: 0.5)  
✅ **Comprehensive Data**: Includes per-season breakdowns and cumulative statistics  
✅ **Safe Updates**: Creates backup before modifying teams file  
✅ **Detailed Reporting**: Generates summary statistics and participation analysis  

## Installation

No additional dependencies beyond Python 3.7+ and standard library.

```bash
cd /Users/ashok/other/FTC-Predictor/aws/scripts
```

## Usage

### Basic Usage

Calculate historic EPA for 2025 teams using 2022-2024 data:
```bash
python3 calculate_historic_epa.py 2025
```

### Advanced Options

Specify custom historical seasons:
```bash
python3 calculate_historic_epa.py 2025 --seasons 2023 2024
```

Custom data directory:
```bash
python3 calculate_historic_epa.py 2025 --data-dir /path/to/data
```

Verbose mode for debugging:
```bash
python3 calculate_historic_epa.py 2025 --verbose
```

### Help

```bash
python3 calculate_historic_epa.py --help
```

## Input Requirements

The script requires the following files in the data directory:

### Required Files
- `teams_<target_season>.json` - Teams to update (e.g., `teams_2025.json`)
- `team_match_epa_<season>.json` - EPA data for each historical season

Example:
```
aws/scripts/
├── teams_2025.json                  # Target teams file
├── team_match_epa_2022.json        # Historical EPA data
├── team_match_epa_2023.json        # Historical EPA data
└── team_match_epa_2024.json        # Historical EPA data
```

## Output Files

### Updated Teams File
The script updates `teams_<season>.json` with a new `historicEPA` field for each team:

```json
{
  "teamNumber": 1,
  "nameShort": "Team Unlimited",
  "historicEPA": {
    "teamNumber": 1,
    "historicEPA": 122.16,
    "weightedCumulativeEPA": 6550.88,
    "totalHistoricalMatches": 65,
    "seasonsWithData": [2022, 2023, 2024],
    "seasonBreakdown": {
      "2022": {
        "averageEPA": 104.93,
        "cumulativeEPA": 2833.06,
        "totalMatches": 27,
        "maxEPA": 205.83,
        "minEPA": 31.0,
        "weight": 0.5
      },
      "2023": {
        "averageEPA": 73.15,
        "cumulativeEPA": 731.5,
        "totalMatches": 10,
        "maxEPA": 149.5,
        "minEPA": 18.0,
        "weight": 0.7
      },
      "2024": {
        "averageEPA": 165.08,
        "cumulativeEPA": 4622.3,
        "totalMatches": 28,
        "maxEPA": 300.3,
        "minEPA": 15.5,
        "weight": 1.0
      }
    },
    "calculatedAt": "2025-11-10T01:16:16.672033+00:00",
    "calculationMethod": "weighted_average",
    "seasonWeights": {
      "2024": 1.0,
      "2023": 0.7,
      "2022": 0.5
    }
  }
}
```

### Backup File
- `teams_<season>_backup.json` - Backup of original file before modification

### Summary Report
- `historic_epa_summary_<season>.json` - Detailed statistics and analysis

## Historic EPA Calculation

### Formula

```python
historic_epa = sum(season_avg_epa × season_weight) / sum(weights)
```

### Season Weights

Default weights (more recent = higher weight):
- **2024**: 1.0 (most recent, full weight)
- **2023**: 0.7 (70% weight)
- **2022**: 0.5 (50% weight)

### Example Calculation

For a team with:
- 2022: Average EPA = 100
- 2023: Average EPA = 120
- 2024: Average EPA = 150

```
historic_epa = (100 × 0.5 + 120 × 0.7 + 150 × 1.0) / (0.5 + 0.7 + 1.0)
             = (50 + 84 + 150) / 2.2
             = 284 / 2.2
             = 129.09
```

## 2025 Season Results

### Summary Statistics

**Teams Processed**: 13,916 total teams

**Coverage**:
- **65.03%** (9,050 teams) have historical data
- **34.97%** (4,866 teams) are new/rookie teams

**Historic EPA Distribution**:
- **Minimum**: 0.9
- **Maximum**: 323.68
- **Mean**: 84.15
- **Median**: 77.28

**Season Participation**:
- **2022**: 4,943 teams (35.52%)
- **2023**: 6,629 teams (47.64%)
- **2024**: 7,577 teams (54.45%)

**Match Count Statistics**:
- **Minimum**: 0 matches
- **Maximum**: 273 matches
- **Average**: 28.8 matches per team

### Top 10 Teams by Historic EPA

| Rank | Team # | Historic EPA | Team Name | Seasons |
|------|--------|--------------|-----------|---------|
| 1 | 28596 | 323.68 | Hypernova | 2024 |
| 2 | 6916 | 307.50 | ASPIRITY | 2024 |
| 3 | 12527 | 280.25 | Prototype | 2024 |
| 4 | 24033 | 278.60 | Alphatronic | 2023, 2024 |
| 5 | 27572 | 276.76 | Dinonaut | 2024 |
| 6 | 24909 | 275.80 | StarLight | 2024 |
| 7 | 17962 | 270.12 | Ro2D2 | 2022, 2023, 2024 |
| 8 | 26914 | 270.03 | ROBOTECH FTC | 2024 |
| 9 | 15972 | 268.48 | TehnoZ | 2022, 2023, 2024 |
| 10 | 26216 | 260.99 | MK II | 2024 |

### Multi-Season Consistency

**Teams with all 3 seasons of data**: 3,894 teams (27.98%)

These teams demonstrate:
- Long-term program sustainability
- Consistent participation
- Reliable historical performance data

## Data Structure

### Team Record with Historic EPA

Each team in `teams_2025.json` now includes:

```json
{
  "teamNumber": <int>,
  "displayTeamNumber": <string>,
  "nameFull": <string>,
  "nameShort": <string>,
  "city": <string>,
  "stateProv": <string>,
  "country": <string>,
  "rookieYear": <int>,
  
  "historicEPA": {
    "teamNumber": <int>,
    "historicEPA": <float>,                    // Weighted average EPA
    "weightedCumulativeEPA": <float>,          // Weighted cumulative EPA
    "totalHistoricalMatches": <int>,           // Total matches across all seasons
    "seasonsWithData": [<int>, ...],           // Seasons with available data
    "seasonBreakdown": {
      "<season>": {
        "averageEPA": <float>,                 // Average EPA for that season
        "cumulativeEPA": <float>,              // Final cumulative EPA
        "totalMatches": <int>,                 // Matches played
        "maxEPA": <float>,                     // Best single match EPA
        "minEPA": <float>,                     // Worst single match EPA
        "weight": <float>                      // Season weight used
      }
    },
    "calculatedAt": <ISO timestamp>,
    "calculationMethod": "weighted_average",
    "seasonWeights": {<season>: <weight>}
  }
}
```

### Metadata

The teams file metadata is updated with:

```json
{
  "metadata": {
    "historicEPACalculated": true,
    "historicEPACalculatedAt": "2025-11-10T01:16:16.766973+00:00",
    "historicEPASeasons": [2022, 2023, 2024],
    "historicEPASeasonWeights": {
      "2024": 1.0,
      "2023": 0.7,
      "2022": 0.5
    }
  }
}
```

## Use Cases

### 1. Team Scouting

Find teams with strong historical performance:

```python
import json

data = json.load(open('teams_2025.json'))

# Get teams with high historic EPA
strong_teams = [
    (t['teamNumber'], t['historicEPA']['historicEPA'], t['nameShort'])
    for t in data['teams']
    if 'historicEPA' in t and t['historicEPA']['historicEPA'] > 150
]

strong_teams.sort(key=lambda x: x[1], reverse=True)
print("Top teams:", strong_teams[:10])
```

### 2. Alliance Selection

Identify consistent performers across multiple seasons:

```python
# Find teams with all 3 seasons of data and high EPA
consistent_teams = [
    t for t in data['teams']
    if 'historicEPA' in t 
    and len(t['historicEPA']['seasonsWithData']) == 3
    and t['historicEPA']['historicEPA'] > 100
]

print(f"Found {len(consistent_teams)} consistent high performers")
```

### 3. Rookie Analysis

Compare rookie teams vs. experienced teams:

```python
rookies = [t for t in data['teams'] 
           if 'historicEPA' in t and t['historicEPA']['historicEPA'] == 0]
experienced = [t for t in data['teams'] 
               if 'historicEPA' in t and t['historicEPA']['historicEPA'] > 0]

print(f"Rookies: {len(rookies)} ({len(rookies)/len(data['teams'])*100:.1f}%)")
print(f"Experienced: {len(experienced)} ({len(experienced)/len(data['teams'])*100:.1f}%)")
```

### 4. Trend Analysis

Analyze team improvement over time:

```python
# Find teams that improved each season
improving_teams = []

for team in data['teams']:
    if 'historicEPA' not in team:
        continue
    
    breakdown = team['historicEPA'].get('seasonBreakdown', {})
    if '2022' in breakdown and '2023' in breakdown and '2024' in breakdown:
        epa_2022 = breakdown['2022']['averageEPA']
        epa_2023 = breakdown['2023']['averageEPA']
        epa_2024 = breakdown['2024']['averageEPA']
        
        if epa_2022 < epa_2023 < epa_2024:
            improvement = epa_2024 - epa_2022
            improving_teams.append((team['teamNumber'], improvement, team['nameShort']))

improving_teams.sort(key=lambda x: x[1], reverse=True)
print("Most improved teams:", improving_teams[:10])
```

### 5. Machine Learning Features

Use historic EPA as a feature for prediction models:

```python
# Extract features for ML
features = []

for team in data['teams']:
    if 'historicEPA' not in team:
        continue
    
    epa_data = team['historicEPA']
    
    features.append({
        'team_number': team['teamNumber'],
        'historic_epa': epa_data['historicEPA'],
        'total_matches': epa_data['totalHistoricalMatches'],
        'seasons_active': len(epa_data['seasonsWithData']),
        'weighted_cumulative': epa_data['weightedCumulativeEPA'],
        'rookie_year': team['rookieYear'],
        'years_active': 2025 - team['rookieYear']
    })
```

## Performance

**Processing Time**: ~4.3 seconds for 13,916 teams

**Breakdown**:
- Loading EPA data: ~3.3 seconds
- Calculating historic EPA: ~0.4 seconds
- Updating teams file: ~0.6 seconds

**File Sizes**:
- Original `teams_2025.json`: 6.3 MB
- Updated `teams_2025.json`: 16.1 MB (+9.8 MB)
- Backup file: 16.1 MB
- Summary report: 701 bytes

## Troubleshooting

### Issue: "EPA file not found"
**Solution**: Ensure you've run `calculate_match_epa.py` for all historical seasons first.

```bash
python3 calculate_match_epa.py 2022 2023 2024
```

### Issue: "Teams file not found"
**Solution**: Ensure you've fetched teams data for the target season.

```bash
python3 fetch_teams_by_season.py 2025
```

### Issue: "No historical data available"
**Solution**: This is expected for rookie teams or teams that didn't compete in historical seasons.

### Issue: Large file size
**Solution**: The increased file size is expected due to the detailed historical data. If needed, you can:
- Compress the file: `gzip teams_2025.json`
- Store only summary statistics (modify the script)

## Technical Details

### Season Weight Rationale

The default weights are designed to:
1. **Prioritize recent performance** (2024 = 1.0)
2. **Consider medium-term trends** (2023 = 0.7)
3. **Include long-term history** (2022 = 0.5)

This weighting scheme:
- Accounts for team evolution and improvement
- Reduces impact of very old data
- Balances recency with historical context

### Calculation Method

The weighted average method:
```python
historic_epa = Σ(season_avg_epa × weight) / Σ(weights)
```

Advantages:
- Simple and interpretable
- Adjustable via weights
- Handles missing seasons gracefully
- Comparable across teams

### Data Quality

**Coverage**: 65.03% of teams have historical data

**Reasons for missing data**:
- Rookie teams (first season in 2025)
- Teams that didn't compete in 2022-2024
- Teams that competed but had no scored matches
- International teams with limited data

## Future Enhancements

Potential improvements:
- [ ] Exponential decay weighting
- [ ] Confidence intervals based on match count
- [ ] Trend indicators (improving/declining)
- [ ] Regional EPA normalization
- [ ] Event difficulty adjustments
- [ ] Playoff performance weighting
- [ ] Custom weight configurations

## Related Scripts

- `calculate_match_epa.py` - Calculate per-match EPA (prerequisite)
- `fetch_teams_by_season.py` - Fetch teams data
- `fetch_events_by_season.py` - Fetch events and matches data

## Examples

### Example 1: Calculate for 2025 Season
```bash
python3 calculate_historic_epa.py 2025
```

### Example 2: Custom Seasons
```bash
python3 calculate_historic_epa.py 2025 --seasons 2023 2024
```

### Example 3: Verbose Mode
```bash
python3 calculate_historic_epa.py 2025 --verbose
```

## Summary Report Example

```json
{
  "targetSeason": 2025,
  "historicalSeasons": [2022, 2023, 2024],
  "seasonWeights": {
    "2024": 1.0,
    "2023": 0.7,
    "2022": 0.5
  },
  "teamsProcessed": 13916,
  "teamsWithHistory": 9050,
  "teamsWithoutHistory": 4866,
  "percentageWithHistory": 65.03,
  "historicEPAStatistics": {
    "min": 0.9,
    "max": 323.68,
    "mean": 84.15,
    "median": 77.28
  },
  "cumulativeEPAStatistics": {
    "min": 4.5,
    "max": 50586.48,
    "mean": 3385.77
  },
  "seasonParticipation": {
    "2022": 4943,
    "2023": 6629,
    "2024": 7577
  },
  "matchCountStatistics": {
    "min": 0,
    "max": 273,
    "mean": 28.8
  }
}
```

---

**Generated**: November 2025  
**Version**: 1.0  
**Author**: FTC-Predictor Team



