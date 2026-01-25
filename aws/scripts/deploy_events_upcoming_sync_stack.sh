#!/bin/bash

set -e

ENVIRONMENT="${ENVIRONMENT:-stage}"
REGION="${REGION:-us-east-1}"
STACK_NAME="ftc-events-upcoming-sync-${ENVIRONMENT}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TEMPLATE_FILE="${SCRIPT_DIR}/../infrastructure/events-upcoming-sync-template.yaml"
SECRETS_NAME="${SECRETS_NAME:-FTC-API-Credentials-${ENVIRONMENT}}"
LOOKAHEAD_DAYS="${LOOKAHEAD_DAYS:-30}"
ROLE_NAME="${ROLE_NAME:-FTC-Lambda-Role-${ENVIRONMENT}}"

echo "=========================================="
echo "Upcoming Events Sync Stack Deployment"
echo "=========================================="
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${REGION}"
echo "Stack: ${STACK_NAME}"
echo "Template: ${TEMPLATE_FILE}"
echo "Secrets Name: ${SECRETS_NAME}"
echo "Lookahead Days: ${LOOKAHEAD_DAYS}"
echo "Role Name: ${ROLE_NAME}"
echo ""

if [ ! -f "${TEMPLATE_FILE}" ]; then
  echo "Template file not found: ${TEMPLATE_FILE}"
  exit 1
fi

echo "Deploying CloudFormation stack..."
aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE_FILE}" \
  --parameter-overrides \
    Environment="${ENVIRONMENT}" \
    SecretsName="${SECRETS_NAME}" \
    LookaheadDays="${LOOKAHEAD_DAYS}" \
    RoleName="${ROLE_NAME}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "${REGION}" \
  --no-cli-pager

echo ""
echo "Stack deployment complete."
echo "Next: deploy lambda code with:"
echo "  cd /Users/ashok/other/FTC-Predictor/aws/lambda/events-upcoming-sync"
echo "  zip -r function.zip lambda_function.py services models"
echo "  aws lambda update-function-code --function-name ftc-events-upcoming-sync-${ENVIRONMENT} --zip-file fileb://function.zip --region ${REGION}"
echo "  rm -f function.zip"
