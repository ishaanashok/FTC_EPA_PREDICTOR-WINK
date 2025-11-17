# Shared Services

This directory contains shared services used across multiple Lambda functions.

## DynamoDB Service

**Location**: `dynamodb_service.py`

This is the **single source of truth** for DynamoDB operations. All Lambda functions use this shared service.

### How It Works

1. **Development**: Edit `aws/services/dynamodb_service.py` directly
2. **Deployment**: The deployment script automatically copies this file to each Lambda's `services/` directory
3. **Version Control**: Lambda-specific copies are gitignored and regenerated on each deployment

### Benefits

✅ **Single Source of Truth**: One file to maintain  
✅ **Consistency**: All Lambdas use the same logic  
✅ **Easy Updates**: Fix once, deploy everywhere  
✅ **No Manual Sync**: Automatic during deployment  

### Making Changes

1. Edit `aws/services/dynamodb_service.py`
2. Test your changes
3. Deploy Lambda functions using `deploy_lambdas.sh`
4. The script will automatically sync the shared service

### Deployment Process

When you run `deploy_lambdas.sh`, for each Lambda function:

```bash
# 1. Copy shared service
cp aws/services/dynamodb_service.py aws/lambda/{function}/services/

# 2. Create deployment package
zip function.zip lambda_function.py services/ ...

# 3. Deploy to AWS
aws lambda update-function-code ...

# 4. Clean up (remove copied file)
rm aws/lambda/{function}/services/dynamodb_service.py
```

This ensures:
- ✅ Lambda directories stay clean (no generated files in version control)
- ✅ Each deployment uses the latest shared service
- ✅ No confusion about which file is the source of truth

### Key Features

The shared DynamoDB service includes:

- **Type Conversion**: Automatic Decimal ↔ Float conversion
- **Error Handling**: Comprehensive try-catch blocks
- **Caching**: Built-in cache for EPA calculations
- **Schema v2.0**: Updated for new table structure
- **Integer Keys**: Proper handling of team numbers as integers

### Recent Fixes Applied

- ✅ Float to Decimal conversion for all numeric fields
- ✅ Integer conversion for team numbers in queries
- ✅ Proper parameter ordering in method calls
- ✅ Tournament level matching with substring search

### Lambda Functions Using This Service

- `teams-api`
- `events-api`
- `matches-api`
- `epa-api`
- `alliance-matchmaker`
- `teams-sync`
- `events-sync`
- `matches-sync`
- `epa-calculator`

## Other Shared Services

Add other shared services here as needed. Follow the same pattern:

1. Place in `aws/services/`
2. Update `deploy_lambdas.sh` to copy during deployment
3. Add to `.gitignore` in Lambda directories
4. Document in this README

