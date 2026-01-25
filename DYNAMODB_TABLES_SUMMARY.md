# DynamoDB Tables Summary

## Overview
The FTC-Predictor application uses 4 DynamoDB tables in the `stage` environment:

1. **FTC_Teams_stage** - Team information with historic EPA
2. **FTC_Events_stage** - Event information
3. **FTC_Matches_stage** - Match results and scores
4. **FTC_TeamMatchEPA_stage** - Per-match EPA calculations

---

## 1. FTC_Teams_stage

### Purpose
Stores team information for each season, including embedded historic EPA data for 2025 teams.

### Primary Key
- **Partition Key**: `teamNumber` (Number)
- **Sort Key**: `season` (Number)

### Key Attributes
- `teamNumber` - Team number (e.g., 1, 12345)
- `season` - Competition season year (e.g., 2022, 2023, 2024, 2025)
- `nameShort` - Short team name
- `nameFull` - Full team name with sponsors
- `city` - City location
- `stateProv` - State/Province code
- `country` - Country code
- `rookieYear` - Year team was founded
- `displayTeamNumber` - Formatted team number
- `displayLocation` - Formatted location string
- `homeRegion` - Home region code
- `website` - Team website URL (optional)
- **`historicEPA`** - Embedded historic EPA data (for 2025 teams only)

### Historic EPA Structure
```json
{
  "historicEPA": {
    "teamNumber": 1,
    "historicEPA": 122.16,
    "calculationMethod": "weighted_average",
    "calculatedAt": "2025-11-10T01:16:16.672033+00:00",
    "seasonsWithData": [2022, 2023, 2024],
    "totalHistoricalMatches": 65,
    "weightedCumulativeEPA": 6550.88,
    "seasonWeights": {
      "2024": 1.0,
      "2023": 0.7,
      "2022": 0.5
    },
    "seasonBreakdown": {
      "2024": {
        "averageEPA": 165.08,
        "cumulativeEPA": 4622.3,
        "totalMatches": 28,
        "minEPA": 15.5,
        "maxEPA": 300.3,
        "weight": 1.0
      },
      "2023": {
        "averageEPA": 73.15,
        "cumulativeEPA": 731.5,
        "totalMatches": 10,
        "minEPA": 18,
        "maxEPA": 149.5,
        "weight": 0.7
      },
      "2022": {
        "averageEPA": 104.93,
        "cumulativeEPA": 2833.06,
        "totalMatches": 27,
        "minEPA": 31,
        "maxEPA": 205.83,
        "weight": 0.5
      }
    }
  }
}
```

### Global Secondary Indexes
- **SeasonIndex**: `season` (Partition Key) - for querying all teams in a season

### Sample Record
```json
{
  "teamNumber": 1,
  "season": 2025,
  "nameShort": "Team Unlimited",
  "nameFull": "&FTC1 Team Unlimited 4-H Club",
  "city": "Sharon",
  "stateProv": "MA",
  "country": "USA",
  "rookieYear": 2007,
  "displayTeamNumber": "1",
  "displayLocation": "Sharon, MA, USA",
  "homeRegion": "USMA",
  "website": "http://www.ftc0001.org/",
  "historicEPA": { ... }
}
```

---

## 2. FTC_Events_stage

### Purpose
Stores event information for each season.

### Primary Key
- **Partition Key**: `code` (String) - Event code (e.g., "USCANONEM1")
- **Sort Key**: `season` (Number)

### Key Attributes
- `code` - Unique event code
- `season` - Competition season year
- `eventId` - UUID for the event
- `name` - Event name
- `typeName` - Event type (e.g., "League Meet", "Qualifier", "Championship")
- `type` - Event type code
- `dateStart` - Start date (ISO 8601 format)
- `dateEnd` - End date (ISO 8601 format)
- `venue` - Venue name
- `address` - Full address
- `city` - City
- `stateprov` - State/Province code
- `country` - Country code
- `regionCode` - Region code
- `leagueCode` - League code (if applicable)
- `timezone` - Timezone string
- `fieldCount` - Number of competition fields
- `published` - Whether event is published
- `remote` - Whether event is remote
- `hybrid` - Whether event is hybrid

### Global Secondary Indexes
- **SeasonIndex**: `season` (Partition Key) - for querying all events in a season

### Sample Record
```json
{
  "code": "USTXNONLM3",
  "season": 2022,
  "eventId": "cb2b2a87-1e42-5445-8cd4-c9858005fdf6",
  "name": "TX-North N-League Meet 3",
  "typeName": "League Meet",
  "type": "1",
  "dateStart": "2022-12-03T00:00:00",
  "dateEnd": "2022-12-03T00:00:00",
  "venue": "McKinney Christian Academy",
  "address": "3601 Bois D Arc Rd, McKinney, TX 75071",
  "city": "McKinney, Texas",
  "stateprov": "TX",
  "country": "USA",
  "regionCode": "USTXNO",
  "leagueCode": "NL",
  "timezone": "America/Chicago",
  "fieldCount": 1,
  "published": true,
  "remote": false,
  "hybrid": false
}
```

---

## 3. FTC_Matches_stage

### Purpose
Stores match results and scores for all events.

### Primary Key
- **Partition Key**: `matchId` (String) - Format: `{season}-{eventCode}-{tournamentLevel}-{series}-{matchNumber}`
- **Sort Key**: None (single-key table)

### Key Attributes
- `matchId` - Unique match identifier
- `season` - Competition season year
- `eventCode` - Event code
- `eventName` - Event name
- `matchNumber` - Match number within the event
- `series` - Series number (0 for qualification)
- `tournamentLevel` - "QUALIFICATION", "SEMIFINAL", or "FINAL"
- `description` - Human-readable description
- `actualStartTime` - Actual start time (ISO 8601)
- `postResultTime` - Time results were posted (ISO 8601)
- `teams` - List of team objects with station assignments
- `teamNumbers` - List of team numbers for easy querying
- `scoreRedFinal` - Red alliance final score
- `scoreBlueFinal` - Blue alliance final score
- `scoreRedAuto` - Red alliance autonomous score
- `scoreBlueAuto` - Blue alliance autonomous score
- `scoreRedFoul` - Red alliance foul points
- `scoreBlueFoul` - Blue alliance foul points
- `eventCode_matchNumber` - Composite key for querying

### Global Secondary Indexes
- **EventCodeIndex**: `eventCode` (Partition Key), `matchNumber` (Sort Key)
- **SeasonIndex**: `season` (Partition Key)

### Sample Record
```json
{
  "matchId": "2024-USMAWAQ-QUALIFICATION-0-4",
  "season": 2024,
  "eventCode": "USMAWAQ",
  "eventName": "",
  "matchNumber": 4,
  "series": 0,
  "tournamentLevel": "QUALIFICATION",
  "description": "Qualification 4",
  "actualStartTime": "2025-02-02T11:16:02.3",
  "postResultTime": "2025-02-02T11:20:04.397",
  "eventCode_matchNumber": "USMAWAQ-4",
  "scoreRedFinal": 141,
  "scoreBlueFinal": 58,
  "scoreRedAuto": 19,
  "scoreBlueAuto": 11,
  "scoreRedFoul": 0,
  "scoreBlueFoul": 0,
  "teams": [
    {
      "teamNumber": 26730,
      "station": "Red1",
      "dq": false,
      "onField": true
    },
    {
      "teamNumber": 4466,
      "station": "Red2",
      "dq": false,
      "onField": true
    },
    {
      "teamNumber": 24357,
      "station": "Blue1",
      "dq": false,
      "onField": true
    },
    {
      "teamNumber": 5710,
      "station": "Blue2",
      "dq": false,
      "onField": true
    }
  ],
  "teamNumbers": [26730, 4466, 24357, 5710]
}
```

---

## 4. FTC_TeamMatchEPA_stage

### Purpose
Stores per-match EPA calculations for each team, including detailed score breakdowns and running averages.

### Primary Key
- **Partition Key**: `teamNumber_matchId` (String) - Format: `{teamNumber}-{matchId}`
- **Sort Key**: None (single-key table)

### Key Attributes
- `teamNumber_matchId` - Composite primary key
- `teamNumber` - Team number
- `matchId` - Match identifier
- `season` - Competition season year
- `eventCode` - Event code
- `matchNumber` - Match number
- `series` - Series number
- `tournamentLevel` - Tournament level
- `description` - Match description
- `actualStartTime` - Match start time
- `postResultTime` - Results posted time
- `alliance` - "Red" or "Blue"
- `station` - Station assignment (e.g., "Red1", "Blue2")
- `allianceTeamCount` - Number of teams on alliance
- `allianceTeamNumbers` - List of teammate numbers
- `opponentTeamNumbers` - List of opponent team numbers
- `hasScores` - Whether match has scores
- **`matchEPA`** - EPA earned in this match
- **`averageEPA`** - Running average EPA
- **`cumulativeEPA`** - Cumulative EPA for the season
- `matchCount` - Number of matches played so far
- **`allianceScore`** - Detailed alliance score breakdown
  - `final` - Final score
  - `auto` - Autonomous score
  - `teleop` - Teleoperated score
  - `endgame` - Endgame score
  - `foul` - Foul points
- **`opponentScore`** - Detailed opponent score breakdown
- **`teamScoreContribution`** - Estimated team contribution
  - `auto` - Autonomous contribution
  - `teleop` - Teleoperated contribution
  - `endgame` - Endgame contribution
- **`runningAverages`** - Running averages for the season
  - `auto` - Average autonomous contribution
  - `teleop` - Average teleoperated contribution
  - `endgame` - Average endgame contribution
  - `matchesWithScores` - Number of matches with scores
- **`epaComponents`** - EPA calculation breakdown
  - `baseContribution` - Base EPA contribution
  - `opponentStrengthMultiplier` - Opponent strength adjustment
  - `matchTypeMultiplier` - Match type adjustment

### Global Secondary Indexes
- **TeamSeasonIndex**: `teamNumber` (Partition Key), `season` (Sort Key)
- **EventCodeIndex**: `eventCode` (Partition Key), `postResultTime` (Sort Key)
- **SeasonIndex**: `season` (Partition Key)

### Sample Record
```json
{
  "teamNumber_matchId": "19389-2022-USUTPRQ-QUALIFICATION-0-6",
  "teamNumber": 19389,
  "matchId": "2022-USUTPRQ-QUALIFICATION-0-6",
  "season": 2022,
  "eventCode": "USUTPRQ",
  "matchNumber": 6,
  "series": 0,
  "tournamentLevel": "QUALIFICATION",
  "description": "Qualification 6",
  "actualStartTime": "2022-12-10T12:31:44.361",
  "postResultTime": "2022-12-10T12:36:45.67",
  "alliance": "Red",
  "station": "Red2",
  "allianceTeamCount": 2,
  "allianceTeamNumbers": [10695, 19389],
  "opponentTeamNumbers": [20515, 21676],
  "hasScores": true,
  "matchEPA": 49,
  "averageEPA": 81.55,
  "cumulativeEPA": 897,
  "matchCount": 11,
  "allianceScore": {
    "final": 63,
    "auto": 20,
    "teleop": 34.4,
    "endgame": 8.6,
    "foul": 0
  },
  "opponentScore": {
    "final": 35,
    "auto": 22,
    "teleop": 10.4,
    "endgame": 2.6,
    "foul": 0
  },
  "teamScoreContribution": {
    "auto": 10,
    "teleop": 17.2,
    "endgame": 4.3
  },
  "runningAverages": {
    "auto": 6,
    "teleop": 19.53,
    "endgame": 4.88,
    "matchesWithScores": 11
  },
  "epaComponents": {
    "baseContribution": 31.5,
    "opponentStrengthMultiplier": 1.556,
    "matchTypeMultiplier": 1
  }
}
```

---

## Data Relationships

### Team → Events
- Query `FTC_TeamMatchEPA_stage` using `TeamSeasonIndex` to find all matches for a team
- Extract unique event codes from matches
- Query `FTC_Events_stage` for each event code

### Event → Teams
- Query `FTC_Matches_stage` using `EventCodeIndex` to get all matches for an event
- Extract unique team numbers from match teams
- Query `FTC_Teams_stage` for each team number

### Team → Matches
- Query `FTC_Matches_stage` using `SeasonIndex` and filter by team number in `teamNumbers`
- Or query `FTC_TeamMatchEPA_stage` using `TeamSeasonIndex` for EPA-enriched match data

### Event → Matches
- Query `FTC_Matches_stage` using `EventCodeIndex` with the event code

---

## Key Design Decisions

1. **Historic EPA Embedded in Teams**: For 2025 teams, historic EPA data is embedded directly in the team record for fast lookups without additional queries.

2. **Composite Keys**: Use composite keys like `teamNumber_matchId` and `eventCode_matchNumber` to enable efficient queries.

3. **Denormalized Data**: Some data is duplicated (e.g., `eventCode` in matches and EPA records) to optimize query performance.

4. **Global Secondary Indexes**: Multiple GSIs enable flexible querying patterns:
   - By season (all tables)
   - By team and season (TeamMatchEPA)
   - By event code (Matches, TeamMatchEPA)

5. **Score Breakdown**: Detailed score breakdowns in `FTC_TeamMatchEPA_stage` enable granular analysis of team performance.

6. **Running Averages**: Pre-calculated running averages in EPA records eliminate the need for real-time aggregation.

---

## Data Loading Status

### Current Data in Tables (as of migration):
- **FTC_Teams_stage**: Teams from seasons 2022-2025
  - 2025 teams include embedded `historicEPA` data
- **FTC_Events_stage**: Events from seasons 2022-2025
- **FTC_Matches_stage**: Matches from seasons 2022-2024
- **FTC_TeamMatchEPA_stage**: Per-match EPA calculations from seasons 2022-2024

### Note on 2025 Data:
- 2025 season is currently in progress
- Team data is loaded with historic EPA from previous seasons
- Event data is loaded as events are scheduled
- Match and EPA data will be populated as matches are played

