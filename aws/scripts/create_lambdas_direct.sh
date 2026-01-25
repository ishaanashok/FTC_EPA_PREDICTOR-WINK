#!/bin/bash

# Script to create Lambda functions directly using AWS CLI
# Simpler approach than CloudFormation

set -e

# Configuration
ENVIRONMENT="stage"
REGION="us-east-1"
RUNTIME="python3.11"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_header "Creating Lambda Functions Directly"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
echo ""

# Check if IAM role exists
ROLE_NAME="ftc-lambda-execution-role-${ENVIRONMENT}"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

print_info "Checking if IAM role exists..."
if aws iam get-role --role-name "$ROLE_NAME" > /dev/null 2>&1; then
    print_success "IAM role already exists: $ROLE_NAME"
else
    print_info "Creating IAM role..."
    
    # Create trust policy
    cat > /tmp/trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
    
    # Create role
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/trust-policy.json \
        --description "Execution role for FTC Lambda functions" \
        --region "$REGION"
    
    # Attach basic execution policy
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    
    # Create and attach DynamoDB policy
    cat > /tmp/dynamodb-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:BatchGetItem",
        "dynamodb:BatchWriteItem",
        "dynamodb:DescribeTable"
      ],
      "Resource": [
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/FTC_Teams_${ENVIRONMENT}",
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/FTC_Teams_${ENVIRONMENT}/index/*",
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/FTC_Events_${ENVIRONMENT}",
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/FTC_Events_${ENVIRONMENT}/index/*",
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/FTC_Matches_${ENVIRONMENT}",
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/FTC_Matches_${ENVIRONMENT}/index/*",
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/FTC_TeamMatchEPA_${ENVIRONMENT}",
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/FTC_TeamMatchEPA_${ENVIRONMENT}/index/*"
      ]
    }
  ]
}
EOF
    
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "DynamoDBAccess" \
        --policy-document file:///tmp/dynamodb-policy.json
    
    print_success "IAM role created: $ROLE_NAME"
    print_info "Waiting 10 seconds for IAM role to propagate..."
    sleep 10
fi

# Function to create a Lambda function
create_lambda() {
    local FUNCTION_NAME=$1
    local DESCRIPTION=$2
    local TIMEOUT=$3
    local MEMORY=$4
    
    print_info "Creating function: $FUNCTION_NAME..."
    
    # Check if function already exists
    if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" > /dev/null 2>&1; then
        print_warning "Function already exists: $FUNCTION_NAME"
        return 0
    fi
    
    # Create placeholder zip
    echo 'def lambda_handler(event, context): return {"statusCode": 200, "body": "Placeholder"}' > /tmp/lambda_function.py
    cd /tmp
    zip -q function.zip lambda_function.py
    
    # Create function
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE_ARN" \
        --handler lambda_function.lambda_handler \
        --zip-file fileb://function.zip \
        --timeout "$TIMEOUT" \
        --memory-size "$MEMORY" \
        --environment Variables={ENVIRONMENT="$ENVIRONMENT"} \
        --description "$DESCRIPTION" \
        --region "$REGION" \
        --no-cli-pager > /dev/null
    
    print_success "Created: $FUNCTION_NAME"
    
    # Clean up
    rm -f /tmp/function.zip /tmp/lambda_function.py
}

# Create all Lambda functions
print_header "Creating Lambda Functions"

create_lambda "ftc-teams-api-${ENVIRONMENT}" "Teams API - Returns team data with embedded historicEPA" 30 512
create_lambda "ftc-epa-api-${ENVIRONMENT}" "EPA API - Comprehensive EPA endpoints" 30 512
create_lambda "ftc-events-api-${ENVIRONMENT}" "Events API - Returns event data" 30 512
create_lambda "ftc-matches-api-${ENVIRONMENT}" "Matches API - Returns match data with win probabilities" 30 512
create_lambda "ftc-alliance-matchmaker-${ENVIRONMENT}" "Alliance Matchmaker - Finds optimal alliance partners" 60 1024
create_lambda "ftc-teams-sync-${ENVIRONMENT}" "Teams Sync - Syncs team data from FTC API" 300 1024
create_lambda "ftc-events-sync-${ENVIRONMENT}" "Events Sync - Syncs event data from FTC API" 300 1024
create_lambda "ftc-matches-sync-${ENVIRONMENT}" "Matches Sync - Syncs match data from FTC API" 300 1024

# List created functions
print_header "Created Lambda Functions"
aws lambda list-functions \
    --region "$REGION" \
    --query "Functions[?starts_with(FunctionName, 'ftc-')].{Name:FunctionName,Runtime:Runtime,Memory:MemorySize,Timeout:Timeout}" \
    --output table

print_header "Next Steps"
echo "1. Deploy Lambda code using the deployment script:"
echo "   cd $(dirname "$0")"
echo "   ./deploy_lambdas.sh"
echo ""
echo "2. The script will deploy the actual code to all functions"
echo ""
print_success "All Lambda functions created successfully!"

