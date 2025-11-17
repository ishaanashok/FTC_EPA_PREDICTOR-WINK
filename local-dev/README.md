# FTC Predictor Local Development Setup

This directory contains everything you need to set up a local development environment for the FTC Predictor project using PostgreSQL as a local database that mirrors your DynamoDB structure.

## 🚀 Quick Start

### 1. Start the Database

```bash
cd local-dev
docker-compose up -d
```

This will start:
- PostgreSQL database on port 5432
- pgAdmin web interface on port 8080

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

```bash
cp env.example .env
# Edit .env with your actual values
```

### 4. Sync Data from DynamoDB

```bash
# Check current record counts
python sync_utils.py --action counts

# Sync all tables (this may take a while for matches table)
python sync_utils.py --action sync-all

# Or sync individual tables
python sync_utils.py --action sync-teams
python sync_utils.py --action sync-events
python sync_utils.py --action sync-matches --limit 1000  # Limit for testing
```

## 📊 Database Schema

The PostgreSQL schema mirrors your DynamoDB tables:

### Tables Created:
- `teams` - Team information (mirrors FTC_Teams_stage)
- `events` - Event information (mirrors FTC_Events_stage)  
- `matches` - Match data (mirrors FTC_Matches_stage)
- `epa_calculations` - EPA calculations (mirrors FTC_EPA_stage)
- `sync_status` - Sync tracking (mirrors FTC_SyncStatus_stage)
- `alliance_compatibility` - Alliance compatibility data
- `event_predictions` - Event predictions

### Views Created:
- `latest_epa_calculations` - Latest EPA per team
- `current_season_teams` - Teams for current season (2024)
- `current_season_events` - Events for current season (2024)
- `current_season_matches` - Matches for current season (2024)
- `team_match_stats` - Team match statistics

## 🔧 Database Access

### pgAdmin Web Interface
- URL: http://localhost:8080
- Email: admin@ftc-predictor.com
- Password: admin

### Direct PostgreSQL Connection
- Host: localhost
- Port: 5432
- Database: ftc_predictor
- Username: ftc_dev
- Password: ftc_dev_password

### Command Line Access
```bash
# Connect via psql
docker exec -it ftc-predictor-db psql -U ftc_dev -d ftc_predictor

# Or if you have psql installed locally
psql -h localhost -p 5432 -U ftc_dev -d ftc_predictor
```

## 📈 Data Sync Utilities

The `sync_utils.py` script provides several commands:

```bash
# Show record counts comparison
python sync_utils.py --action counts

# Sync all tables from DynamoDB
python sync_utils.py --action sync-all

# Sync specific tables
python sync_utils.py --action sync-teams
python sync_utils.py --action sync-events
python sync_utils.py --action sync-matches

# Limit records for testing
python sync_utils.py --action sync-matches --limit 1000

# Use different environment
python sync_utils.py --action sync-all --environment prod
```

## 🔍 Example Queries

### Get team information
```sql
SELECT * FROM teams WHERE season = 2024 AND team_number = 15886;
```

### Get events for a specific state
```sql
SELECT event_name, city, date_start 
FROM events 
WHERE season = 2024 AND state = 'CA'
ORDER BY date_start;
```

### Get matches for a team
```sql
SELECT m.event_code, m.match_number, m.tournament_level
FROM matches m
WHERE m.season = 2024 
  AND 15886 = ANY(m.all_teams)
ORDER BY m.event_code, m.match_number;
```

### Get latest EPA calculations
```sql
SELECT team_number, current_season_epa, total_matches
FROM latest_epa_calculations
WHERE current_season_epa > 50
ORDER BY current_season_epa DESC
LIMIT 10;
```

### Team performance analysis
```sql
SELECT 
    t.team_number,
    t.team_name,
    tms.matches_played,
    epa.current_season_epa
FROM teams t
JOIN team_match_stats tms ON t.team_number = tms.team_number AND t.season = tms.season
LEFT JOIN latest_epa_calculations epa ON t.team_number = epa.team_number
WHERE t.season = 2024
ORDER BY epa.current_season_epa DESC NULLS LAST
LIMIT 20;
```

## 🔄 Development Workflow

### 1. Local Development
- Use PostgreSQL for fast local queries and development
- Test EPA calculations and predictions locally
- Develop new features with full dataset

### 2. Data Sync
- Periodically sync from DynamoDB to get latest data
- Use `--limit` flag for quick testing
- Monitor sync performance and adjust as needed

### 3. Push to Production
- Test changes locally first
- Deploy Lambda functions with updated code
- Changes automatically sync to DynamoDB via your existing AWS infrastructure

## 🛠️ Advanced Usage

### Custom Sync Scripts
You can extend `sync_utils.py` to add:
- Incremental sync based on timestamps
- Bidirectional sync (PostgreSQL → DynamoDB)
- Data transformation during sync
- Custom filtering and processing

### Performance Optimization
- Use indexes for common query patterns
- Consider partitioning large tables by season
- Use materialized views for complex aggregations
- Monitor query performance with `EXPLAIN ANALYZE`

### Data Analysis
PostgreSQL provides powerful analytics capabilities:
- Window functions for ranking and trends
- JSON operations for flexible schema fields
- Full-text search capabilities
- Statistical functions for EPA analysis

## 🐛 Troubleshooting

### Database Connection Issues
```bash
# Check if containers are running
docker-compose ps

# View logs
docker-compose logs postgres
docker-compose logs pgadmin

# Restart services
docker-compose restart
```

### Sync Issues
```bash
# Check AWS credentials
aws sts get-caller-identity

# Test DynamoDB access
aws dynamodb list-tables --region us-east-1

# Check PostgreSQL connection
python -c "import psycopg2; psycopg2.connect(host='localhost', database='ftc_predictor', user='ftc_dev', password='ftc_dev_password')"
```

### Performance Issues
- Large tables (especially matches) may take time to sync
- Use `--limit` for testing
- Consider running sync during off-peak hours
- Monitor disk space usage

## 📝 Next Steps

1. **Set up automated sync**: Create cron jobs or scheduled tasks for regular data sync
2. **Add local API server**: Create FastAPI endpoints for local development
3. **Implement caching**: Add Redis for frequently accessed data
4. **Create test data**: Generate synthetic data for testing edge cases
5. **Add monitoring**: Set up logging and metrics for sync operations

## 🤝 Contributing

When adding new features:
1. Update the PostgreSQL schema in `init-scripts/01-create-schema.sql`
2. Update the sync utilities in `sync_utils.py`
3. Add appropriate indexes for new query patterns
4. Update this README with new usage examples
