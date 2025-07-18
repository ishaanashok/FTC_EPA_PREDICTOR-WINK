# FTC Predictor AWS Lambda Infrastructure

## Overview

This directory contains the AWS Lambda infrastructure for the FTC Predictor application, featuring:

- **Data Synchronization**: Automated sync from FTC Events API to DynamoDB every 6 hours
- **HTTP Optimization**: Smart use of HTTP caching headers to minimize data transfer
- **EPA Calculations**: Selective updates only when underlying data changes
- **RESTful APIs**: Direct DynamoDB access for fast response times
- **Event-Driven Architecture**: Scheduled data sync with change detection

## Architecture

### Components

1. **Data Sync Lambda** (`data-sync/`)
   - Syncs teams, events, and matches data from FTC Events API
   - Uses HTTP caching headers (If-Modified-Since, FMS-OnlyModifiedSince, ETag) for bandwidth optimization
   - Only updates EPA calculations when relevant data changes
   - Runs every 6 hours via EventBridge schedule

2. **API Lambda Functions**
   - `teams-api/` - Team data and statistics
   - `events-api/` - Event information and details
   - `matches-api/` - Match data and predictions
   - `epa-api/` - EPA calculations and comparisons
   - `alliance-matchmaker/` - Alliance recommendations

3. **Data Models** (`models/`)
   - Pydantic models for type safety and validation
   - HTTP caching metadata embedded in main data models
   - Automatic data conversion utilities

4. **Services** (`services/`)
   - `ftc_api_service.py` - HTTP-optimized FTC API client
   - `dynamodb_service.py` - DynamoDB operations

5. **Infrastructure** (`infrastructure/`)
   - CloudFormation template for complete AWS setup
   - DynamoDB tables with appropriate indexes
   - Lambda functions with proper IAM permissions
   - API Gateway with CORS configuration

### DynamoDB Tables

- **FTC_Teams**: Team information with HTTP caching metadata
- **FTC_Events**: Event details with HTTP caching metadata  
- **FTC_Matches**: Match data with HTTP caching metadata
- **FTC_EPA**: EPA calculations and historical data

## Performance Optimizations

### HTTP Caching Headers
The system leverages FTC Events API HTTP caching headers for significant bandwidth savings:

- **If-Modified-Since**: Only fetch data if changed since last sync
- **FMS-OnlyModifiedSince**: FTC-specific conditional request header
- **ETag**: Entity tag validation for unchanged resources
- **304 Not Modified**: Responses save bandwidth and processing time

### Selective EPA Updates
EPA calculations are only triggered when:
- Team data changes (new teams, updated information)
- Event data changes (new events, schedule updates)
- Match data changes (new matches, score updates)

This prevents unnecessary computational overhead when data hasn't changed.

### Data Change Detection
Each data model includes a `dataHash` field that tracks content changes:
- SHA256 hash of normalized data content
- Only updates DynamoDB when hash differs
- Enables precise change detection across sync cycles

## API Endpoints

### Teams API
- `GET /api/teams` - List teams for a season
- `GET /api/teams/{teamNumber}` - Get specific team details
- Query parameters: `season`, `eventCode`, `limit`

### Events API  
- `GET /api/events` - List events for a season
- `GET /api/events/{eventCode}` - Get specific event details
- Query parameters: `season`, `limit`

### Matches API
- `GET /api/matches` - List matches (requires `eventCode` or `teamNumber`)
- `GET /api/matches/{matchId}` - Get specific match details
- `GET /api/matches/{matchId}/predictions` - Get match predictions
- Query parameters: `season`, `eventCode`, `teamNumber`, `tournamentLevel`

### EPA API
- `GET /api/epa/{teamNumber}` - Get team EPA data
- `GET /api/epa?teams=1,2,3` - Get multiple team EPAs
- `GET /api/epa?teams=1,2,3&compare=true` - Compare team EPAs
- Query parameters: `historical`, `teams`, `compare`, `top`

### Alliance Matchmaker API
- `GET /api/alliance/{teamNumber}` - Find best alliance partners
- `GET /api/alliance?team1=1&team2=2` - Check team compatibility
- `GET /api/alliance?teams=1,2,3,4` - Suggest alliance combinations
- `GET /api/alliance?eventCode=WABON` - Analyze event alliances
- Query parameters: `season`, `eventCode`, `limit`

## Deployment

### Prerequisites
- AWS CLI configured
- Python 3.11+
- Required Python packages (see requirements.txt)

### Deploy Infrastructure
```bash
# Deploy CloudFormation stack (creates new S3 bucket)
aws cloudformation deploy \
  --template-file infrastructure/cloudformation-template.yaml \
  --stack-name ftc-predictor-dev \
  --parameter-overrides Environment=dev \
  --capabilities CAPABILITY_IAM

# Or use an existing S3 bucket
aws cloudformation deploy \
  --template-file infrastructure/cloudformation-template.yaml \
  --stack-name ftc-predictor-dev \
  --parameter-overrides \
    Environment=dev \
    ExistingLambdaDeploymentBucket=my-existing-bucket \
    CreateLambdaDeploymentBucket=false \
  --capabilities CAPABILITY_IAM

# Package and deploy Lambda functions
./deploy.sh dev
```

**S3 Bucket Options:**
- By default, a new S3 bucket is created for Lambda deployment packages
- Use `ExistingLambdaDeploymentBucket` parameter to specify an existing bucket
- Set `CreateLambdaDeploymentBucket=false` when using an existing bucket
- See [docs/cloudformation-bucket-usage.md](docs/cloudformation-bucket-usage.md) for details

### Environment Variables
Set in CloudFormation template:
- `ENVIRONMENT` - Deployment environment (dev/prod)
- `TEAMS_TABLE` - DynamoDB teams table name
- `EVENTS_TABLE` - DynamoDB events table name  
- `MATCHES_TABLE` - DynamoDB matches table name
- `EPA_TABLE` - DynamoDB EPA table name
- `SECRETS_NAME` - AWS Secrets Manager secret name

## Configuration

### FTC API Credentials
Store in AWS Secrets Manager:
```json
{
  "username": "your-ftc-username",
  "api_key": "your-api-key"
}
```

### Data Sync Schedule
Default: Every 6 hours
Modify in CloudFormation:
```yaml
ScheduleExpression: 'rate(6 hours)'
```

## Monitoring

### CloudWatch Metrics
- Lambda function duration and errors
- DynamoDB read/write capacity utilization
- API Gateway request counts and latency

### Logging
- Structured logging with correlation IDs
- HTTP caching performance metrics
- Data change detection results
- EPA calculation triggers

### Bandwidth Monitoring
Track HTTP caching effectiveness:
- 304 Not Modified response rate
- Data transfer savings
- Conditional request success rate

## Development

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Local development with SAM
sam build
sam local start-api
```

### Data Models
Update `models/data_models.py` for schema changes. Models automatically:
- Convert to DynamoDB format
- Include HTTP caching metadata
- Generate data hashes for change detection

### Adding New Endpoints
1. Create new Lambda function directory
2. Implement handler following existing patterns
3. Update CloudFormation template
4. Add API Gateway resources and methods

## Troubleshooting

### Common Issues

**High DynamoDB Costs**
- Verify change detection is working (check `dataHash` fields)
- Monitor unnecessary writes via CloudWatch metrics
- Ensure HTTP caching is reducing API calls

**Sync Failures**
- Check FTC API credentials in Secrets Manager
- Verify network connectivity and API rate limits
- Review CloudWatch logs for detailed error messages

**Stale Data**
- Verify EventBridge schedule is enabled
- Check last sync timestamps in DynamoDB
- Ensure HTTP headers are being stored correctly

**EPA Not Updating**
- Verify data change detection logic
- Check if underlying team/event/match data has changed
- Review EPA calculation trigger conditions

### Performance Optimization
- Monitor DynamoDB hot partitions
- Optimize query patterns with appropriate indexes
- Use batch operations for bulk data operations
- Implement pagination for large result sets

## Cost Optimization

### HTTP Caching Benefits
- 60-80% reduction in data transfer costs
- Lower Lambda execution time
- Reduced DynamoDB write operations
- Minimal impact on data freshness

### DynamoDB Efficiency
- On-demand billing for variable workloads
- Batch writes reduce request costs
- Proper key design prevents hot partitions
- Change detection minimizes unnecessary writes

### Lambda Optimization
- Right-sized memory allocation
- Efficient cold start handling
- Async operations where possible
- Reuse of HTTP connections 