#!/bin/bash

# FTC Predictor Lambda Functions Deployment Script
# Deploys Lambda functions with optimized dependencies (no CloudFormation)

set -e

# Configuration
ENVIRONMENT=${1:-stage}
AWS_REGION=${2:-us-east-1}
LAMBDA_NAME=${3:-"all"}  # Specific lambda name or "all"
S3_BUCKET="ftc-lambda-deployment-${ENVIRONMENT}-843578292678"

# Available Lambda functions
LAMBDA_FUNCTIONS=(
    "data-sync"
    "epa-api" 
    "epa-calculator"
    "teams-api"
    "events-api"
    "matches-api"
    "alliance-matchmaker"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Show usage
show_usage() {
    echo -e "${BLUE}Usage: $0 [ENVIRONMENT] [AWS_REGION] [LAMBDA_NAME]${NC}"
    echo ""
    echo "Parameters:"
    echo "  ENVIRONMENT  Environment name (default: stage)"
    echo "  AWS_REGION   AWS region (default: us-east-1)"
    echo "  LAMBDA_NAME  Specific lambda to deploy or 'all' (default: all)"
    echo ""
    echo "Available Lambda functions:"
    for func in "${LAMBDA_FUNCTIONS[@]}"; do
        echo "  - $func"
    done
    echo ""
    echo "Examples:"
    echo "  $0                                    # Deploy all lambdas to stage"
    echo "  $0 stage us-east-1 matches-api       # Deploy only matches-api"
    echo "  $0 prod us-west-2 all                # Deploy all to prod"
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
    
    # Check if S3 bucket exists
    if ! aws s3api head-bucket --bucket "${S3_BUCKET}" 2>/dev/null; then
        error "S3 bucket '${S3_BUCKET}' not found or not accessible."
    fi
    
    log "Prerequisites check passed!"
}

# Build optimized dependencies layer
build_dependencies_layer() {
    log "Building optimized dependencies layer..."
    
    # Create build directory
    mkdir -p build/layers/optimized/python
    
    # Create optimized requirements.txt (excluding runtime-provided dependencies)
    cat > build/layers/optimized/requirements.txt << EOF
# Optimized dependencies - excluding runtime-provided packages
# Runtime already includes: boto3, botocore, urllib3, jmespath, s3transfer, six, python-dateutil, simplejson
pydantic>=1.10.0,<2.0.0
aiohttp>=3.9.1
python-dotenv>=1.0.0
typing-extensions>=4.8.0
EOF
    
    # Install dependencies
    log "Installing optimized dependencies..."
    pip install -r build/layers/optimized/requirements.txt -t build/layers/optimized/python/ --upgrade --no-deps
    
    # Create layer zip
    cd build/layers/optimized
    zip -r ../../../optimized-dependencies.zip .
    cd ../../../
    
    # Upload layer to S3
    aws s3 cp optimized-dependencies.zip s3://${S3_BUCKET}/layers/
    log "Optimized dependencies layer uploaded successfully"
}

# Get or create Lambda layer
get_lambda_layer() {
    local layer_name="ftc-optimized-deps-${ENVIRONMENT}"
    
    # Check if layer exists
    local layer_arn=$(aws lambda list-layer-versions \
        --layer-name "$layer_name" \
        --query 'LayerVersions[0].LayerVersionArn' \
        --output text 2>/dev/null || echo "None")
    
    if [[ "$layer_arn" == "None" || "$layer_arn" == "" ]]; then
        log "Creating new Lambda layer: $layer_name" >&2
        layer_arn=$(aws lambda publish-layer-version \
            --layer-name "$layer_name" \
            --description "Optimized dependencies for FTC Predictor (${ENVIRONMENT})" \
            --content S3Bucket=${S3_BUCKET},S3Key=layers/optimized-dependencies.zip \
            --compatible-runtimes python3.11 python3.12 \
            --query 'LayerVersionArn' \
            --output text)
        log "Created layer: $layer_arn" >&2
    else
        log "Using existing layer: $layer_arn" >&2
    fi
    
    # Return only the ARN (strip any potential whitespace/newlines)
    echo "$layer_arn" | tr -d '\n\r'
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
        error "Lambda function file not found: aws/lambda/${func_name}/lambda_function.py"
    fi
    
    # Copy shared services and models (only if they exist)
    if [[ -d "aws/services" ]]; then
        mkdir -p "build/lambda/${func_name}/services"
        cp -r aws/services/* "build/lambda/${func_name}/services/" 2>/dev/null || true
    fi
    
    if [[ -d "aws/models" ]]; then
        mkdir -p "build/lambda/${func_name}/models"
        cp -r aws/models/* "build/lambda/${func_name}/models/" 2>/dev/null || true
    fi
    
    # Copy function-specific services if they exist
    if [[ -d "aws/lambda/${func_name}/services" ]]; then
        mkdir -p "build/lambda/${func_name}/services"
        cp -r "aws/lambda/${func_name}/services"/* "build/lambda/${func_name}/services/" 2>/dev/null || true
    fi
    
    if [[ -d "aws/lambda/${func_name}/models" ]]; then
        mkdir -p "build/lambda/${func_name}/models"
        cp -r "aws/lambda/${func_name}/models"/* "build/lambda/${func_name}/models/" 2>/dev/null || true
    fi
    
    # Create deployment package
    cd "build/lambda/${func_name}"
    zip -r "../../../${func_name}.zip" .
    cd ../../../
    
    # Upload to S3
    aws s3 cp "${func_name}.zip" "s3://${S3_BUCKET}/functions/"
    
    log "${func_name} Lambda function packaged and uploaded"
}

# Deploy individual Lambda function
deploy_lambda_function() {
    local func_name=$1
    local layer_arn=$2
    local function_name="ftc-${func_name}-${ENVIRONMENT}"
    
    log "Deploying ${func_name} Lambda function..."
    
    # Check if function exists
    if aws lambda get-function --function-name "$function_name" &>/dev/null; then
        log "Updating existing function: $function_name"
        
        # Update function code
        aws lambda update-function-code \
            --function-name "$function_name" \
            --s3-bucket "$S3_BUCKET" \
            --s3-key "functions/${func_name}.zip"
        
        # Update function configuration with correct handler
        aws lambda update-function-configuration \
            --function-name "$function_name" \
            --handler "lambda_function.handler" \
            --runtime "python3.11" \
            --layers "$layer_arn" \
            --timeout 30 \
            --memory-size 512 \
            --environment Variables="{ENVIRONMENT=${ENVIRONMENT}}"
            
    else
        log "Creating new function: $function_name"
        
        # Get Lambda execution role ARN (assumes it exists from CloudFormation)
        local role_arn="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ftc-lambda-execution-role-${ENVIRONMENT}"
        
        # Create function
        aws lambda create-function \
            --function-name "$function_name" \
            --runtime "python3.11" \
            --role "$role_arn" \
            --handler "lambda_function.handler" \
            --code "S3Bucket=${S3_BUCKET},S3Key=functions/${func_name}.zip" \
            --layers "$layer_arn" \
            --timeout 30 \
            --memory-size 512 \
            --environment Variables="{ENVIRONMENT=${ENVIRONMENT}}" \
            --description "FTC Predictor ${func_name} function (${ENVIRONMENT})"
    fi
    
    log "${func_name} Lambda function deployed successfully"
}

# Validate lambda name
validate_lambda_name() {
    local lambda_name=$1
    
    if [[ "$lambda_name" == "all" ]]; then
        return 0
    fi
    
    for func in "${LAMBDA_FUNCTIONS[@]}"; do
        if [[ "$func" == "$lambda_name" ]]; then
            return 0
        fi
    done
    
    error "Invalid lambda name: $lambda_name. Use 'all' or one of: ${LAMBDA_FUNCTIONS[*]}"
}

# Deploy specific or all lambdas
deploy_lambdas() {
    local layer_arn=$1
    
    if [[ "$LAMBDA_NAME" == "all" ]]; then
        log "Deploying all Lambda functions..."
        for func in "${LAMBDA_FUNCTIONS[@]}"; do
            build_lambda_function "$func"
            deploy_lambda_function "$func" "$layer_arn"
        done
    else
        log "Deploying specific Lambda function: $LAMBDA_NAME"
        build_lambda_function "$LAMBDA_NAME"
        deploy_lambda_function "$LAMBDA_NAME" "$layer_arn"
    fi
}

# Cleanup function
cleanup() {
    log "Cleaning up build artifacts..."
    rm -rf build/
    rm -f *.zip
    log "Cleanup completed"
}

# Main execution
main() {
    log "Starting FTC Predictor Lambda Deployment"
    log "Environment: ${ENVIRONMENT}"
    log "Region: ${AWS_REGION}"
    log "Target: ${LAMBDA_NAME}"
    log "S3 Bucket: ${S3_BUCKET}"
    
    # Validate inputs
    validate_lambda_name "$LAMBDA_NAME"
    
    check_prerequisites
    build_dependencies_layer
    
    # Get or create optimized layer
    log "Getting Lambda layer ARN..."
    layer_arn=$(get_lambda_layer)
    log "Using layer ARN: $layer_arn"
    
    # Deploy lambda functions
    deploy_lambdas "$layer_arn"
    
    cleanup
    
    log "Lambda deployment completed successfully!"
    log ""
    log "Deployed functions:"
    if [[ "$LAMBDA_NAME" == "all" ]]; then
        for func in "${LAMBDA_FUNCTIONS[@]}"; do
            log "  - ftc-${func}-${ENVIRONMENT}"
        done
    else
        log "  - ftc-${LAMBDA_NAME}-${ENVIRONMENT}"
    fi
    log ""
    log "Layer used: $layer_arn"
    log ""
    log "Next steps:"
    log "1. Test the deployed functions using AWS Console or CLI"
    log "2. Monitor CloudWatch logs for any issues"
    log "3. Update API Gateway endpoints if needed"
}

# Run main function
main "$@" 