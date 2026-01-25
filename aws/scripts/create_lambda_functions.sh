#!/bin/bash

# Script to create Lambda functions using CloudFormation

set -e

# Configuration
ENVIRONMENT="stage"
REGION="us-east-1"
STACK_NAME="ftc-lambda-functions-${ENVIRONMENT}"
TEMPLATE_FILE="../infrastructure/lambda-functions-template.yaml"

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

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

print_header "Lambda Functions Creation"
echo "Stack Name: $STACK_NAME"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Template: $TEMPLATE_FILE"
echo ""

# Check if template exists
if [ ! -f "$TEMPLATE_FILE" ]; then
    print_error "Template file not found: $TEMPLATE_FILE"
    exit 1
fi

print_success "Template file found"

# Check if stack already exists
print_info "Checking if stack exists..."
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" > /dev/null 2>&1; then
    print_warning "Stack already exists: $STACK_NAME"
    echo ""
    read -p "Do you want to update the existing stack? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Updating stack..."
        aws cloudformation update-stack \
            --stack-name "$STACK_NAME" \
            --template-body "file://$TEMPLATE_FILE" \
            --parameters ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$REGION"
        
        print_info "Waiting for stack update to complete..."
        aws cloudformation wait stack-update-complete \
            --stack-name "$STACK_NAME" \
            --region "$REGION"
        
        print_success "Stack updated successfully!"
    else
        print_info "Skipping stack update"
        exit 0
    fi
else
    print_info "Creating new stack..."
    aws cloudformation create-stack \
        --stack-name "$STACK_NAME" \
        --template-body "file://$TEMPLATE_FILE" \
        --parameters ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION" \
        --tags Key=Environment,Value="$ENVIRONMENT" Key=Application,Value=FTC-Predictor
    
    print_info "Waiting for stack creation to complete..."
    aws cloudformation wait stack-create-complete \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
    
    print_success "Stack created successfully!"
fi

# Get stack outputs
print_header "Stack Outputs"
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

# List created Lambda functions
print_header "Created Lambda Functions"
aws lambda list-functions \
    --region "$REGION" \
    --query "Functions[?starts_with(FunctionName, 'ftc-')].{Name:FunctionName,Runtime:Runtime,Memory:MemorySize,Timeout:Timeout}" \
    --output table

print_header "Next Steps"
echo "1. Deploy Lambda code using the deployment script:"
echo "   cd $SCRIPT_DIR"
echo "   ./deploy_lambdas.sh"
echo ""
echo "2. Or deploy individual functions:"
echo "   cd ../lambda/teams-api"
echo "   zip -r function.zip lambda_function.py services/"
echo "   aws lambda update-function-code --function-name ftc-teams-api-$ENVIRONMENT --zip-file fileb://function.zip --region $REGION"
echo ""
print_success "Lambda functions are ready for code deployment!"

