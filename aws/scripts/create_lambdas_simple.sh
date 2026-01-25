#!/bin/bash

# Simple script to create Lambda functions using existing IAM role

set -e

ENVIRONMENT="stage"
REGION="us-east-1"
RUNTIME="python3.11"
ROLE_ARN="arn:aws:iam::843578292678:role/FTC-Lambda-Role-stage"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Creating Lambda Functions${NC}"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Role: $ROLE_ARN"
echo ""

# Create placeholder zip
echo 'def lambda_handler(event, context): return {"statusCode": 200, "body": "Placeholder"}' > /tmp/lambda_function.py
cd /tmp && zip -q function.zip lambda_function.py

create_lambda() {
    local NAME=$1
    local DESC=$2
    local TIMEOUT=$3
    local MEMORY=$4
    
    if aws lambda get-function --function-name "$NAME" --region "$REGION" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠${NC} Already exists: $NAME"
    else
        echo -e "${BLUE}Creating: $NAME${NC}"
        aws lambda create-function \
            --function-name "$NAME" \
            --runtime "$RUNTIME" \
            --role "$ROLE_ARN" \
            --handler lambda_function.lambda_handler \
            --zip-file fileb:///tmp/function.zip \
            --timeout "$TIMEOUT" \
            --memory-size "$MEMORY" \
            --environment Variables={ENVIRONMENT="$ENVIRONMENT"} \
            --description "$DESC" \
            --region "$REGION" \
            --no-cli-pager > /dev/null
        echo -e "${GREEN}✓${NC} Created: $NAME"
    fi
}

create_lambda "ftc-teams-api-${ENVIRONMENT}" "Teams API" 30 512
create_lambda "ftc-epa-api-${ENVIRONMENT}" "EPA API" 30 512
create_lambda "ftc-events-api-${ENVIRONMENT}" "Events API" 30 512
create_lambda "ftc-matches-api-${ENVIRONMENT}" "Matches API" 30 512
create_lambda "ftc-alliance-matchmaker-${ENVIRONMENT}" "Alliance Matchmaker" 60 1024
create_lambda "ftc-teams-sync-${ENVIRONMENT}" "Teams Sync" 300 1024
create_lambda "ftc-events-sync-${ENVIRONMENT}" "Events Sync" 300 1024
create_lambda "ftc-matches-sync-${ENVIRONMENT}" "Matches Sync" 300 1024

rm -f /tmp/function.zip /tmp/lambda_function.py

echo ""
echo -e "${GREEN}✓ All functions created!${NC}"
echo ""
echo "Next: Deploy code with ./deploy_lambdas.sh"
