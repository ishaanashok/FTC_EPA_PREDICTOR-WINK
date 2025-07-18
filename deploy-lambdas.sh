#!/bin/bash

# FTC Predictor Lambda Deployment Script
# This script builds and deploys only the Lambda functions

set -e

# Configuration
ENVIRONMENT=${1:-dev}
AWS_REGION=${2:-us-east-1}
STACK_NAME="ftc-predictor-${ENVIRONMENT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Show usage
show_usage() {
    echo -e "${BLUE}Usage: $0 [ENVIRONMENT] [AWS_REGION]${NC}"
    echo -e "${BLUE}       $0 --help${NC}"
    echo ""
    echo "Parameters:"
    echo "  ENVIRONMENT     Environment name (default: dev)"
    echo "  AWS_REGION      AWS region (default: us-east-1)"
    echo ""
    echo "Examples:"
    echo "  $0 dev us-east-1       # Deploy to dev environment"
    echo "  $0 prod us-west-2      # Deploy to prod environment"
    echo ""
    echo "This script will:"
    echo "  1. Build lambda deployment packages"
    echo "  2. Upload to S3 deployment bucket"
    echo "  3. Update lambda function code"
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

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        error "AWS CLI not found. Please install AWS CLI first."
    fi
    
    # Check if AWS credentials are configured
    if ! aws sts get-caller-identity &> /dev/null; then
        error "AWS credentials not configured. Please run 'aws configure' first."
    fi
    
    # Check if required files exist
    if [[ ! -f "aws/infrastructure/cloudformation-template.yaml" ]]; then
        error "CloudFormation template not found. Please ensure you're in the project root."
    fi
    
    # Check if lambda directories exist
    if [[ ! -d "aws/lambda" ]]; then
        error "Lambda functions directory not found."
    fi
    
    log "Prerequisites check passed"
}

# Get the S3 bucket from CloudFormation stack
get_deployment_bucket() {
    log "Getting deployment bucket from CloudFormation stack..."
    
    # Check if stack exists
    if ! aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" &>/dev/null; then
        error "CloudFormation stack '${STACK_NAME}' not found. Please deploy infrastructure first."
    fi
    
    # Get the bucket name from stack outputs
    DEPLOYMENT_BUCKET=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`LambdaDeploymentBucket`].OutputValue' \
        --output text)
    
    if [[ -z "${DEPLOYMENT_BUCKET}" || "${DEPLOYMENT_BUCKET}" == "None" ]]; then
        error "Could not find deployment bucket in CloudFormation stack outputs."
    fi
    
    log "Using deployment bucket: ${DEPLOYMENT_BUCKET}"
}

# Build common dependencies layer
build_dependencies_layer() {
    log "Building common dependencies layer..."
    
    # Create build directory
    mkdir -p build/layers/common/python
    
    # Create an empty layer (use only AWS Lambda runtime dependencies)
    echo "# Empty layer - using only AWS Lambda runtime dependencies" > build/layers/common/requirements.txt
    
    # Create layer zip with minimal content
    cd build/layers/common
    zip -r ../../../common-dependencies.zip . -q
    cd ../../../
    
    # Upload layer to S3
    log "Uploading minimal dependencies layer to S3..."
    aws s3 cp common-dependencies.zip s3://${DEPLOYMENT_BUCKET}/layers/ --region "${AWS_REGION}"
    
    log "Minimal dependencies layer built and uploaded successfully"
}

# Build individual Lambda function
build_lambda_function() {
    local func_name=$1
    log "Building ${func_name} Lambda function..."
    
    # Create function build directory
    mkdir -p "build/lambda/${func_name}"
    
    # Copy Lambda function code
    if [[ -f "aws/lambda/${func_name}/lambda_function.py" ]]; then
        cp "aws/lambda/${func_name}/lambda_function.py" "build/lambda/${func_name}/"
    else
        error "Lambda function ${func_name}/lambda_function.py not found"
    fi
    
    # Copy shared services
    if [[ -d "aws/services" ]]; then
        mkdir -p "build/lambda/${func_name}/services"
        cp -r aws/services/* "build/lambda/${func_name}/services/"
    fi
    
    # Copy models
    if [[ -d "aws/models" ]]; then
        cp -r aws/models/* "build/lambda/${func_name}/"
    fi
    
    # Install dependencies directly in the function package
    log "Installing dependencies for ${func_name}..."
    cat > "build/lambda/${func_name}/requirements.txt" << EOF
pydantic==2.5.0
aiohttp==3.9.0
python-dotenv==1.0.0
typing-extensions
EOF
    
    # Install dependencies directly in the function directory
    pip install -r "build/lambda/${func_name}/requirements.txt" -t "build/lambda/${func_name}/" --quiet --upgrade
    
    # Remove the requirements file from the package
    rm "build/lambda/${func_name}/requirements.txt"
    
    # Create deployment package
    cd "build/lambda/${func_name}"
    zip -r "../../../${func_name}.zip" . -q
    cd ../../../
    
    # Upload to S3
    log "Uploading ${func_name} to S3..."
    aws s3 cp "${func_name}.zip" "s3://${DEPLOYMENT_BUCKET}/functions/" --region "${AWS_REGION}"
    
    log "${func_name} Lambda function packaged and uploaded"
}

# Update Lambda function code
update_lambda_function() {
    local func_name=$1
    local lambda_function_name="ftc-${func_name}-${ENVIRONMENT}"
    
    log "Updating ${func_name} Lambda function code..."
    
    # Get the S3 key for the function
    S3_KEY="functions/${func_name}.zip"
    
    # Update the function code
    aws lambda update-function-code \
        --function-name "${lambda_function_name}" \
        --s3-bucket "${DEPLOYMENT_BUCKET}" \
        --s3-key "${S3_KEY}" \
        --region "${AWS_REGION}" \
        --output table
    
    # Wait for update to complete
    log "Waiting for ${func_name} update to complete..."
    aws lambda wait function-updated \
        --function-name "${lambda_function_name}" \
        --region "${AWS_REGION}"
    
    log "${func_name} Lambda function updated successfully"
}

# Update Lambda layer
update_lambda_layer() {
    log "Updating Lambda layer..."
    
    # Get layer ARN from CloudFormation
    LAYER_ARN=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`CommonDependenciesLayer`].OutputValue' \
        --output text)
    
    if [[ -n "${LAYER_ARN}" && "${LAYER_ARN}" != "None" ]]; then
        # Extract layer name from ARN
        LAYER_NAME=$(echo "${LAYER_ARN}" | cut -d':' -f7)
        
        # Publish new layer version
        aws lambda publish-layer-version \
            --layer-name "${LAYER_NAME}" \
            --content S3Bucket="${DEPLOYMENT_BUCKET}",S3Key="layers/common-dependencies.zip" \
            --compatible-runtimes python3.11 \
            --region "${AWS_REGION}" \
            --output table
        
        log "Lambda layer updated successfully"
    else
        warn "Could not find Lambda layer ARN, skipping layer update"
    fi
}

# Build and deploy all Lambda functions
deploy_lambda_functions() {
    log "Building and deploying Lambda functions..."
    
    # List of Lambda functions to deploy
    LAMBDA_FUNCTIONS=(
        "data-sync"
        "epa-api"
        "teams-api"
        "events-api"
        "matches-api"
        "alliance-matchmaker"
    )
    
    # Build each function
    for func_name in "${LAMBDA_FUNCTIONS[@]}"; do
        if [[ -d "aws/lambda/${func_name}" ]]; then
            build_lambda_function "${func_name}"
        else
            warn "Lambda function directory ${func_name} not found, skipping"
        fi
    done
    
    # Update each function
    for func_name in "${LAMBDA_FUNCTIONS[@]}"; do
        if [[ -f "${func_name}.zip" ]]; then
            update_lambda_function "${func_name}"
        else
            warn "Lambda function package ${func_name}.zip not found, skipping update"
        fi
    done
    
    log "All Lambda functions deployed successfully"
}

# Test Lambda functions
test_lambda_functions() {
    log "Testing Lambda functions..."
    
    # Test data-sync function
    log "Testing data-sync function..."
    aws lambda invoke \
        --function-name "ftc-data-sync-${ENVIRONMENT}" \
        --region "${AWS_REGION}" \
        --payload '{"syncType": "teams", "season": 2024}' \
        test-response.json
    
    if [[ -f "test-response.json" ]]; then
        log "Data-sync test response:"
        cat test-response.json | jq '.' 2>/dev/null || cat test-response.json
        rm -f test-response.json
    fi
    
    log "Lambda function testing completed"
}

# Cleanup function
cleanup() {
    log "Cleaning up build artifacts..."
    rm -rf build/
    rm -f *.zip
    rm -f test-response.json
    log "Cleanup completed"
}

# Main execution
main() {
    log "Starting FTC Predictor Lambda Deployment"
    log "Environment: ${ENVIRONMENT}"
    log "Region: ${AWS_REGION}"
    log "Stack Name: ${STACK_NAME}"
    
    check_prerequisites
    get_deployment_bucket
    
    # Build dependencies layer
    build_dependencies_layer
    
    # Deploy Lambda functions
    deploy_lambda_functions
    
    # Update the layer (optional)
    update_lambda_layer
    
    # Test deployment in dev environment
    if [[ "${ENVIRONMENT}" == "dev" ]]; then
        test_lambda_functions
    fi
    
    cleanup
    
    log "Lambda deployment completed successfully!"
    log ""
    log "Updated Lambda functions:"
    log "- ftc-data-sync-${ENVIRONMENT}"
    log "- ftc-epa-api-${ENVIRONMENT}"
    log "- ftc-teams-api-${ENVIRONMENT}"
    log "- ftc-events-api-${ENVIRONMENT}"
    log "- ftc-matches-api-${ENVIRONMENT}"
    log "- ftc-alliance-matchmaker-${ENVIRONMENT}"
    log ""
    log "Next steps:"
    log "1. Test your API endpoints"
    log "2. Monitor CloudWatch logs for any issues"
    log "3. Run data sync if needed: aws lambda invoke --function-name ftc-data-sync-${ENVIRONMENT} --payload '{\"syncType\": \"all\", \"season\": 2024}' response.json"
}

# Run main function
main "$@" 