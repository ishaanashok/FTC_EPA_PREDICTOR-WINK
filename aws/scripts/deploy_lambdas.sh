#!/bin/bash

# Lambda Deployment Script
# Deploys updated Lambda functions to AWS

set -e  # Exit on error

# Configuration
ENVIRONMENT="stage"
REGION="us-east-1"
PYTHON_VERSION="python3.11"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
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

# Function to deploy a Lambda function
deploy_lambda() {
    local LAMBDA_DIR=$1
    local FUNCTION_NAME=$2
    local DESCRIPTION=$3
    
    print_header "Deploying: $FUNCTION_NAME"
    
    # Check if directory exists
    if [ ! -d "$LAMBDA_DIR" ]; then
        print_error "Directory not found: $LAMBDA_DIR"
        return 1
    fi
    
    cd "$LAMBDA_DIR"
    
    # Sync shared DynamoDB service if services directory exists
    if [ -d "services" ]; then
        SHARED_SERVICE="$SCRIPT_DIR/../services/dynamodb_service.py"
        if [ -f "$SHARED_SERVICE" ]; then
            print_info "Syncing shared DynamoDB service..."
            cp "$SHARED_SERVICE" "services/dynamodb_service.py"
            print_success "Synced shared DynamoDB service"
        fi
    fi
    
    # Create deployment package
    print_info "Creating deployment package..."
    
    # Remove old zip if exists
    rm -f function.zip
    
    # Create zip with lambda_function.py and services directory
    if [ -f "lambda_function.py" ]; then
        zip -r function.zip lambda_function.py
        print_success "Added lambda_function.py"
    else
        print_error "lambda_function.py not found"
        return 1
    fi
    
    if [ -d "services" ]; then
        zip -r function.zip services/
        print_success "Added services/"
    fi
    
    if [ -d "models" ]; then
        zip -r function.zip models/
        print_success "Added models/"
    fi
    
    # Check if function exists
    print_info "Checking if function exists..."
    if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" > /dev/null 2>&1; then
        # Update existing function
        print_info "Updating existing function..."
        aws lambda update-function-code \
            --function-name "$FUNCTION_NAME" \
            --zip-file fileb://function.zip \
            --region "$REGION" \
            --no-cli-pager > /dev/null
        
        print_success "Function updated: $FUNCTION_NAME"
    else
        print_warning "Function does not exist: $FUNCTION_NAME"
        print_info "You may need to create it first via CloudFormation or AWS Console"
    fi
    
    # Clean up deployment artifacts
    rm -f function.zip
    
    # Remove copied shared service (keep Lambda directories clean)
    if [ -f "services/dynamodb_service.py" ]; then
        rm -f services/dynamodb_service.py
        print_info "Cleaned up copied shared service"
    fi
    
    cd - > /dev/null
}

# Main deployment script
main() {
    print_header "Lambda Deployment Script"
    echo "Environment: $ENVIRONMENT"
    echo "Region: $REGION"
    echo ""
    
    # Get the script directory
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    LAMBDA_BASE_DIR="$SCRIPT_DIR/../lambda"
    
    # Check if we're in the right directory
    if [ ! -d "$LAMBDA_BASE_DIR" ]; then
        print_error "Lambda directory not found: $LAMBDA_BASE_DIR"
        exit 1
    fi
    
    print_info "Lambda base directory: $LAMBDA_BASE_DIR"
    echo ""
    
    # Ask user which functions to deploy
    echo "Which Lambda functions do you want to deploy?"
    echo ""
    echo "1. Teams API (Updated - returns historicEPA)"
    echo "2. EPA API (NEW - comprehensive EPA endpoints)"
    echo "3. Events API"
    echo "4. Matches API"
    echo "5. Alliance Matchmaker"
    echo "6. Teams Sync"
    echo "7. Events Sync"
    echo "8. Matches Sync"
    echo "9. EPA Calculator"
    echo "10. All functions"
    echo "0. Cancel"
    echo ""
    read -p "Enter your choice (0-10): " choice
    
    case $choice in
        1)
            deploy_lambda "$LAMBDA_BASE_DIR/teams-api" "ftc-teams-api-$ENVIRONMENT" "Teams API"
            ;;
        2)
            deploy_lambda "$LAMBDA_BASE_DIR/epa-api" "ftc-epa-api-$ENVIRONMENT" "EPA API"
            ;;
        3)
            deploy_lambda "$LAMBDA_BASE_DIR/events-api" "ftc-events-api-$ENVIRONMENT" "Events API"
            ;;
        4)
            deploy_lambda "$LAMBDA_BASE_DIR/matches-api" "ftc-matches-api-$ENVIRONMENT" "Matches API"
            ;;
        5)
            deploy_lambda "$LAMBDA_BASE_DIR/alliance-matchmaker" "ftc-alliance-matchmaker-$ENVIRONMENT" "Alliance Matchmaker"
            ;;
        6)
            deploy_lambda "$LAMBDA_BASE_DIR/teams-sync" "ftc-teams-sync-$ENVIRONMENT" "Teams Sync"
            ;;
        7)
            deploy_lambda "$LAMBDA_BASE_DIR/events-sync" "ftc-events-sync-$ENVIRONMENT" "Events Sync"
            ;;
        8)
            deploy_lambda "$LAMBDA_BASE_DIR/matches-sync" "ftc-matches-sync-$ENVIRONMENT" "Matches Sync"
            ;;
        9)
            deploy_lambda "$LAMBDA_BASE_DIR/epa-calculator" "ftc-epa-calculator-$ENVIRONMENT" "EPA Calculator"
            ;;
        10)
            print_info "Deploying all functions..."
            
            deploy_lambda "$LAMBDA_BASE_DIR/teams-api" "ftc-teams-api-$ENVIRONMENT" "Teams API"
            deploy_lambda "$LAMBDA_BASE_DIR/epa-api" "ftc-epa-api-$ENVIRONMENT" "EPA API"
            deploy_lambda "$LAMBDA_BASE_DIR/events-api" "ftc-events-api-$ENVIRONMENT" "Events API"
            deploy_lambda "$LAMBDA_BASE_DIR/matches-api" "ftc-matches-api-$ENVIRONMENT" "Matches API"
            deploy_lambda "$LAMBDA_BASE_DIR/alliance-matchmaker" "ftc-alliance-matchmaker-$ENVIRONMENT" "Alliance Matchmaker"
            deploy_lambda "$LAMBDA_BASE_DIR/teams-sync" "ftc-teams-sync-$ENVIRONMENT" "Teams Sync"
            deploy_lambda "$LAMBDA_BASE_DIR/events-sync" "ftc-events-sync-$ENVIRONMENT" "Events Sync"
            deploy_lambda "$LAMBDA_BASE_DIR/matches-sync" "ftc-matches-sync-$ENVIRONMENT" "Matches Sync"
            deploy_lambda "$LAMBDA_BASE_DIR/epa-calculator" "ftc-epa-calculator-$ENVIRONMENT" "EPA Calculator"
            ;;
        0)
            print_info "Deployment cancelled"
            exit 0
            ;;
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
    
    print_header "Deployment Complete"
    print_success "All selected Lambda functions have been deployed!"
    echo ""
    print_info "Next steps:"
    echo "  1. Test the deployed functions"
    echo "  2. Check CloudWatch logs for any errors"
    echo "  3. Update API Gateway if needed"
    echo ""
}

# Run main function
main

