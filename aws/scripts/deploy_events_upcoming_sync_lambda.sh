#!/bin/bash

set -e

ENVIRONMENT="${ENVIRONMENT:-stage}"
REGION="${REGION:-us-east-1}"
FUNCTION_NAME="ftc-events-upcoming-sync-${ENVIRONMENT}"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LAMBDA_DIR="${SCRIPT_DIR}/../lambda/events-upcoming-sync"
BUILD_DIR="/tmp/ftc-events-upcoming-sync-build"
ZIP_PATH="/tmp/ftc-events-upcoming-sync.zip"

echo "=========================================="
echo "Upcoming Events Sync Lambda Deploy"
echo "=========================================="
echo "Function: ${FUNCTION_NAME}"
echo "Region: ${REGION}"
echo "Lambda Dir: ${LAMBDA_DIR}"
echo ""

if [ ! -d "${LAMBDA_DIR}" ]; then
  echo "Lambda directory not found: ${LAMBDA_DIR}"
  exit 1
fi

rm -rf "${BUILD_DIR}" "${ZIP_PATH}"
mkdir -p "${BUILD_DIR}"

echo "Installing dependencies (aiohttp)..."
python3 -m pip install --upgrade --quiet aiohttp \
  -t "${BUILD_DIR}" \
  --trusted-host pypi.org \
  --trusted-host files.pythonhosted.org \
  --trusted-host pypi.python.org

echo "Copying lambda source..."
cp "${LAMBDA_DIR}/lambda_function.py" "${BUILD_DIR}/"
cp -R "${LAMBDA_DIR}/services" "${BUILD_DIR}/"
cp -R "${LAMBDA_DIR}/models" "${BUILD_DIR}/"

echo "Packaging zip..."
cd "${BUILD_DIR}"
zip -r "${ZIP_PATH}" . > /dev/null

echo "Deploying to AWS Lambda..."
aws lambda update-function-code \
  --function-name "${FUNCTION_NAME}" \
  --zip-file "fileb://${ZIP_PATH}" \
  --region "${REGION}" \
  --no-cli-pager > /dev/null

echo "Cleaning up..."
rm -rf "${BUILD_DIR}" "${ZIP_PATH}"

echo "Deployment complete."
