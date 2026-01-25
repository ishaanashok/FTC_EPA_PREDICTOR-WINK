#!/bin/bash

set -e

ENVIRONMENT="${ENVIRONMENT:-stage}"
REGION="${REGION:-us-east-1}"
STACK_NAME="ftc-events-matches-epa-sync-${ENVIRONMENT}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TEMPLATE_FILE="${SCRIPT_DIR}/../infrastructure/events-matches-epa-sync-template.yaml"
SECRETS_NAME="${SECRETS_NAME:-FTC-API-Credentials-${ENVIRONMENT}}"
ROLE_NAME="${ROLE_NAME:-FTC-Lambda-Role-${ENVIRONMENT}}"
UPCOMING_WINDOW_HOURS="${UPCOMING_WINDOW_HOURS:-24}"
SEASON="${SEASON:-2025}"

echo "=========================================="
echo "Events Matches/EPA Sync Stack Deployment"
echo "=========================================="
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${REGION}"
echo "Stack: ${STACK_NAME}"
echo "Template: ${TEMPLATE_FILE}"
echo "Secrets Name: ${SECRETS_NAME}"
echo "Role Name: ${ROLE_NAME}"
echo "Upcoming Window Hours: ${UPCOMING_WINDOW_HOURS}"
echo "Season: ${SEASON}"
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
    RoleName="${ROLE_NAME}" \
    UpcomingWindowHours="${UPCOMING_WINDOW_HOURS}" \
    Season="${SEASON}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "${REGION}" \
  --no-cli-pager

echo ""
echo "Stack deployment complete."
echo "Next: deploy lambda code with:"
echo "  bash /Users/ashok/other/FTC-Predictor/aws/scripts/deploy_events_matches_epa_sync_lambda.sh"
