#!/bin/bash

# FTC Predictor AWS Migration Deployment Script
# This script deploys the complete AWS infrastructure and Lambda functions

set -e

# Configuration
ENVIRONMENT=${1:-dev}
AWS_REGION=${2:-us-east-1}
EXISTING_BUCKET=${3:-""}
STACK_NAME="ftc-predictor-${ENVIRONMENT}"
S3_BUCKET_PREFIX="ftc-lambda-deployment-${ENVIRONMENT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Show usage
show_usage() {
    echo -e "${BLUE}Usage: $0 [ENVIRONMENT] [AWS_REGION] [EXISTING_BUCKET]${NC}"
    echo -e "${BLUE}       $0 --help${NC}"
    echo ""
    echo "Parameters:"
    echo "  ENVIRONMENT     Environment name (default: dev)"
    echo "  AWS_REGION      AWS region (default: us-east-1)"
    echo "  EXISTING_BUCKET Optional existing S3 bucket name to use"
    echo ""
    echo "Examples:"
    echo "  $0 dev us-east-1                           # Create new bucket"
    echo "  $0 prod us-west-2 my-existing-bucket       # Use existing bucket"
    echo "  $0 stage us-east-1 ftc-lambda-stage-123    # Use existing bucket"
    echo ""
    echo "If EXISTING_BUCKET is not provided, a new bucket will be created."
}

# Check if help is requested
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    show_usage
    exit 0
fi

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        error "AWS CLI not found. Please install AWS CLI."
    fi
    
    # Check if AWS credentials are configured
    if ! aws sts get-caller-identity &> /dev/null; then
        error "AWS credentials not configured. Please run 'aws configure'."
    fi
    
    # Check if required files exist
    if [[ ! -f "aws/infrastructure/cloudformation-template.yaml" ]]; then
        error "CloudFormation template not found at aws/infrastructure/cloudformation-template.yaml"
    fi
    
    log "Prerequisites check passed!"
}

# Create S3 bucket for Lambda deployments (if needed)
setup_s3_bucket() {
    if [[ -n "${EXISTING_BUCKET}" ]]; then
        log "Using existing S3 bucket: ${EXISTING_BUCKET}"
        
        # Verify the bucket exists and is accessible
        if ! aws s3api head-bucket --bucket "${EXISTING_BUCKET}" 2>/dev/null; then
            error "Cannot access existing bucket '${EXISTING_BUCKET}'. Please check bucket name and permissions."
        fi
        
        S3_BUCKET="${EXISTING_BUCKET}"
        CREATE_NEW_BUCKET=false
        
    else
        log "Creating new S3 bucket for Lambda deployments..."
        
        S3_BUCKET="${S3_BUCKET_PREFIX}-$(aws sts get-caller-identity --query Account --output text)"
        CREATE_NEW_BUCKET=true
        
        # Check if bucket already exists
        if aws s3api head-bucket --bucket "${S3_BUCKET}" 2>/dev/null; then
            log "S3 bucket ${S3_BUCKET} already exists"
        else
            # Create bucket
            if [[ "${AWS_REGION}" == "us-east-1" ]]; then
                aws s3api create-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}"
            else
                aws s3api create-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}" \
                    --create-bucket-configuration LocationConstraint="${AWS_REGION}"
            fi
            
            # Enable versioning
            aws s3api put-bucket-versioning \
                --bucket "${S3_BUCKET}" \
                --versioning-configuration Status=Enabled
            
            log "S3 bucket ${S3_BUCKET} created successfully"
        fi
    fi
    
    log "S3 bucket configured: ${S3_BUCKET}"
}

# Build and package Lambda functions
build_lambda_functions() {
    log "Building and packaging Lambda functions..."
    
    # Create build directory
    mkdir -p build/lambda
    
    # Build common dependencies layer
    log "Building common dependencies layer..."
    mkdir -p build/layers/common/python
    
    # Copy requirements and install dependencies
    cat > build/layers/common/requirements.txt << EOF
boto3==1.34.0
botocore==1.34.0
pydantic==2.5.0
aiohttp==3.9.0
python-dotenv==1.0.0
numpy==1.24.3
asyncio
typing-extensions
EOF
    
    # Install dependencies
    pip install -r build/layers/common/requirements.txt -t build/layers/common/python/
    
    # Create layer zip
    cd build/layers/common
    zip -r ../../../common-dependencies.zip .
    cd ../../../
    
    # Upload layer to S3
    aws s3 cp common-dependencies.zip s3://${S3_BUCKET}/layers/
    
    # Build Lambda functions
    build_lambda_function "data-sync"
    build_lambda_function "epa-api"
    build_lambda_function "teams-api"
    build_lambda_function "events-api"
    build_lambda_function "matches-api"
    build_lambda_function "alliance-matchmaker"
    
    log "Lambda functions built and uploaded successfully"
}

# Build individual Lambda function
build_lambda_function() {
    local func_name=$1
    log "Building ${func_name} Lambda function..."
    
    mkdir -p "build/lambda/${func_name}"
    
    # Copy Lambda function code
    if [[ -f "aws/lambda/${func_name}/lambda_function.py" ]]; then
        cp "aws/lambda/${func_name}/lambda_function.py" "build/lambda/${func_name}/"
    else
        # Create a basic Lambda function if it doesn't exist
        create_basic_lambda_function "${func_name}"
    fi
    
    # Copy shared services
    mkdir -p "build/lambda/${func_name}/services"
    cp -r aws/services/* "build/lambda/${func_name}/services/" 2>/dev/null || true
    cp -r aws/models/* "build/lambda/${func_name}/" 2>/dev/null || true
    
    # Create deployment package
    cd "build/lambda/${func_name}"
    zip -r "../../../${func_name}.zip" .
    cd ../../../
    
    # Upload to S3
    aws s3 cp "${func_name}.zip" "s3://${S3_BUCKET}/functions/"
    
    log "${func_name} Lambda function packaged and uploaded"
}

# Create basic Lambda function template
create_basic_lambda_function() {
    local func_name=$1
    
    cat > "build/lambda/${func_name}/lambda_function.py" << EOF
import json
import boto3
import logging
import os
from services.dynamodb_service import DynamoDBService

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """Lambda handler for ${func_name}"""
    logger.info(f"${func_name} Lambda started")
    
    try:
        # Initialize services
        db_service = DynamoDBService(os.environ.get('ENVIRONMENT', 'dev'))
        
        # Process the request
        # TODO: Implement specific logic for ${func_name}
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps({'message': '${func_name} Lambda executed successfully'})
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
EOF
}

# Deploy CloudFormation stack
deploy_infrastructure() {
    log "Deploying CloudFormation stack..."
    
    # Get FTC API credentials
    read -sp "Enter FTC API Username: " FTC_USERNAME
    echo
    read -sp "Enter FTC API Key: " FTC_API_KEY
    echo
    
    # Build CloudFormation parameters
    CF_PARAMETERS=(
        "ParameterKey=Environment,ParameterValue=${ENVIRONMENT}"
        "ParameterKey=FTCApiUsername,ParameterValue=${FTC_USERNAME}"
        "ParameterKey=FTCApiKey,ParameterValue=${FTC_API_KEY}"
        "ParameterKey=CreateLambdaDeploymentBucket,ParameterValue=${CREATE_NEW_BUCKET}"
    )
    
    # Add existing bucket parameter if specified
    if [[ -n "${EXISTING_BUCKET}" ]]; then
        CF_PARAMETERS+=("ParameterKey=ExistingLambdaDeploymentBucket,ParameterValue=${EXISTING_BUCKET}")
    fi
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" &>/dev/null; then
        log "Stack ${STACK_NAME} exists, updating..."
        
        aws cloudformation update-stack \
            --stack-name "${STACK_NAME}" \
            --template-body file://aws/infrastructure/cloudformation-template.yaml \
            --parameters "${CF_PARAMETERS[@]}" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "${AWS_REGION}"
            
        # Wait for stack update to complete
        log "Waiting for stack update to complete..."
        aws cloudformation wait stack-update-complete --stack-name "${STACK_NAME}" --region "${AWS_REGION}"
        
    else
        log "Creating new stack ${STACK_NAME}..."
        
        aws cloudformation create-stack \
            --stack-name "${STACK_NAME}" \
            --template-body file://aws/infrastructure/cloudformation-template.yaml \
            --parameters "${CF_PARAMETERS[@]}" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "${AWS_REGION}"
            
        # Wait for stack creation to complete
        log "Waiting for stack creation to complete..."
        aws cloudformation wait stack-create-complete --stack-name "${STACK_NAME}" --region "${AWS_REGION}"
    fi
    
    log "CloudFormation stack deployed successfully"
}

# Get stack outputs
get_stack_outputs() {
    log "Getting stack outputs..."
    
    # Get API Gateway URL
    API_GATEWAY_URL=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
        --output text)
    
    # Get actual bucket used
    DEPLOYMENT_BUCKET=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`LambdaDeploymentBucket`].OutputValue' \
        --output text)
    
    log "API Gateway URL: ${API_GATEWAY_URL}"
    log "Lambda Deployment Bucket: ${DEPLOYMENT_BUCKET}"
    
    # Save outputs to file
    cat > deployment-outputs.json << EOF
{
    "environment": "${ENVIRONMENT}",
    "region": "${AWS_REGION}",
    "stackName": "${STACK_NAME}",
    "apiGatewayUrl": "${API_GATEWAY_URL}",
    "lambdaDeploymentBucket": "${DEPLOYMENT_BUCKET}",
    "existingBucketUsed": $(if [[ -n "${EXISTING_BUCKET}" ]]; then echo "true"; else echo "false"; fi)
}
EOF
    
    log "Deployment outputs saved to deployment-outputs.json"
}

# Run initial data sync
run_initial_sync() {
    log "Running initial data sync..."
    
    # Get the data sync Lambda function name
    DATA_SYNC_FUNCTION=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`DataSyncFunction`].OutputValue' \
        --output text 2>/dev/null || echo "ftc-data-sync-${ENVIRONMENT}")
    
    # Invoke the data sync function
    aws lambda invoke \
        --function-name "${DATA_SYNC_FUNCTION}" \
        --region "${AWS_REGION}" \
        --payload '{"source": "initial-deployment"}' \
        sync-response.json
    
    # Check sync response
    if [[ -f "sync-response.json" ]]; then
        log "Initial data sync response:"
        cat sync-response.json | jq '.' 2>/dev/null || cat sync-response.json
    fi
    
    log "Initial data sync completed"
}

# Test the deployment
test_deployment() {
    log "Testing deployment..."
    
    # Test API Gateway endpoint
    if [[ -n "${API_GATEWAY_URL}" ]]; then
        # Test teams endpoint
        log "Testing teams API endpoint..."
        response=$(curl -s -o /dev/null -w "%{http_code}" "${API_GATEWAY_URL}/teams" || echo "000")
        
        if [[ "${response}" == "200" ]]; then
            log "Teams API endpoint test passed"
        else
            warn "Teams API endpoint test failed (HTTP ${response})"
        fi
        
        # Test events endpoint
        log "Testing events API endpoint..."
        response=$(curl -s -o /dev/null -w "%{http_code}" "${API_GATEWAY_URL}/events" || echo "000")
        
        if [[ "${response}" == "200" ]]; then
            log "Events API endpoint test passed"
        else
            warn "Events API endpoint test failed (HTTP ${response})"
        fi
    fi
    
    log "Deployment testing completed"
}

# Cleanup function
cleanup() {
    log "Cleaning up build artifacts..."
    rm -rf build/
    rm -f *.zip
    rm -f sync-response.json
    log "Cleanup completed"
}

# Main execution
main() {
    log "Starting FTC Predictor AWS Migration Deployment"
    log "Environment: ${ENVIRONMENT}"
    log "Region: ${AWS_REGION}"
    log "Stack Name: ${STACK_NAME}"
    if [[ -n "${EXISTING_BUCKET}" ]]; then
        log "Using existing bucket: ${EXISTING_BUCKET}"
    else
        log "Will create new bucket: ${S3_BUCKET_PREFIX}-<account-id>"
    fi
    
    check_prerequisites
    setup_s3_bucket
    build_lambda_functions
    deploy_infrastructure
    get_stack_outputs
    
    # Optional: Run initial sync and test
    if [[ "${ENVIRONMENT}" == "dev" ]]; then
        run_initial_sync
        test_deployment
    fi
    
    cleanup
    
    log "Deployment completed successfully!"
    log "API Gateway URL: ${API_GATEWAY_URL}"
    log "Lambda Deployment Bucket: ${DEPLOYMENT_BUCKET}"
    log ""
    log "Next steps:"
    log "1. Update your frontend to use the new API Gateway URL"
    log "2. Test all endpoints with the new Lambda functions"
    log "3. Monitor CloudWatch logs for any issues"
    log "4. Set up monitoring and alerts for production"
    log ""
    log "Available API endpoints:"
    log "- GET ${API_GATEWAY_URL}/teams - List all teams"
    log "- GET ${API_GATEWAY_URL}/events - List all events"
    log "- GET ${API_GATEWAY_URL}/matches - List matches"
    log "- GET ${API_GATEWAY_URL}/epa - EPA calculations"
    log "- POST ${API_GATEWAY_URL}/alliance-matchmaker - Alliance recommendations"
}

# Run main function
main "$@" 