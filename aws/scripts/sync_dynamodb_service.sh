#!/bin/bash

# Script to sync the shared DynamoDB service to all Lambda functions
# This ensures all Lambdas use the same, up-to-date DynamoDB service

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Syncing Shared DynamoDB Service to Lambda Functions${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SHARED_SERVICE="$SCRIPT_DIR/../services/dynamodb_service.py"
LAMBDA_BASE_DIR="$SCRIPT_DIR/../lambda"

# Check if shared service exists
if [ ! -f "$SHARED_SERVICE" ]; then
    echo "Error: Shared DynamoDB service not found at $SHARED_SERVICE"
    exit 1
fi

echo "Source: $SHARED_SERVICE"
echo ""

# List of Lambda functions that use DynamoDB service
LAMBDA_FUNCTIONS=(
    "teams-api"
    "events-api"
    "matches-api"
    "epa-api"
    "alliance-matchmaker"
    "teams-sync"
    "events-sync"
    "matches-sync"
    "epa-calculator"
)

# Copy to each Lambda function
for lambda_func in "${LAMBDA_FUNCTIONS[@]}"; do
    target_dir="$LAMBDA_BASE_DIR/$lambda_func/services"
    target_file="$target_dir/dynamodb_service.py"
    
    if [ -d "$target_dir" ]; then
        # Create backup if file exists
        if [ -f "$target_file" ]; then
            backup_file="$target_file.backup.$(date +%Y%m%d_%H%M%S)"
            cp "$target_file" "$backup_file"
            echo -e "${GREEN}✓${NC} Backed up $lambda_func/services/dynamodb_service.py"
        fi
        
        # Copy shared service
        cp "$SHARED_SERVICE" "$target_file"
        echo -e "${GREEN}✓${NC} Updated $lambda_func/services/dynamodb_service.py"
    else
        echo "⚠  Skipping $lambda_func (services directory not found)"
    fi
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓${NC} Sync complete!"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Next steps:"
echo "  1. Review the changes"
echo "  2. Deploy the updated Lambda functions"
echo "  3. Test the APIs"
echo ""

