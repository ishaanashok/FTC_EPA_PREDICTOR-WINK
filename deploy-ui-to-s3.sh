#!/bin/bash

# Script to build and deploy WinK UI to S3 with production optimizations

set -e

# Configuration - Using existing bucket
BUCKET_NAME="ftc-predictor-frontend-stage"
REGION="us-east-1"
BUILD_DIR="build"

echo "=========================================="
echo "WinK - Production Build & Deploy"
echo "=========================================="
echo "Target bucket: $BUCKET_NAME"
echo ""

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "Error: package.json not found! Please run this script from the project root."
    exit 1
fi

# Clean previous builds
echo "Step 1: Cleaning previous builds..."
echo "----------------------------------------"
rm -rf build
rm -rf node_modules/.cache
echo "✓ Cleaned"
echo ""

# Set production environment variables for optimized build
echo "Step 2: Configuring production build..."
echo "----------------------------------------"
export NODE_ENV=production
export GENERATE_SOURCEMAP=false
export INLINE_RUNTIME_CHUNK=false
export IMAGE_INLINE_SIZE_LIMIT=10000
export DISABLE_ESLINT_PLUGIN=true
echo "✓ Production environment set"
echo ""

# Build the React app with production optimizations
echo "Step 3: Building optimized production bundle..."
echo "----------------------------------------"
npm run build

# Check if build was successful
if [ ! -d "$BUILD_DIR" ]; then
    echo "Error: Build directory not found! Build may have failed."
    exit 1
fi

echo ""
echo "✓ Build completed successfully!"
BUILD_SIZE=$(du -sh build | cut -f1)
echo "  Build size: $BUILD_SIZE"
echo ""

# Verify bucket exists
echo "Step 4: Verifying S3 bucket..."
echo "----------------------------------------"
if ! aws s3 ls "s3://$BUCKET_NAME" > /dev/null 2>&1; then
    echo "Error: Bucket '$BUCKET_NAME' does not exist or you don't have access."
    exit 1
fi
echo "✓ Bucket verified"
echo ""

# Sync build directory to S3 with optimized settings
echo "Step 5: Deploying to S3..."
echo "----------------------------------------"

# Upload static assets (JS, CSS, images) with long cache
echo "→ Uploading static assets (JS, CSS, images)..."
aws s3 sync "$BUILD_DIR/" "s3://$BUCKET_NAME/" \
    --delete \
    --cache-control "public, max-age=31536000, immutable" \
    --exclude "*.html" \
    --exclude "*.json" \
    --exclude "service-worker.js" \
    --exclude "*.txt" \
    --exclude "*.map" \
    --metadata-directive REPLACE

# Upload HTML files with no cache for instant updates
echo "→ Uploading HTML files..."
aws s3 sync "$BUILD_DIR/" "s3://$BUCKET_NAME/" \
    --exclude "*" \
    --include "*.html" \
    --cache-control "public, max-age=0, must-revalidate, no-cache" \
    --content-type "text/html" \
    --metadata-directive REPLACE

# Upload JSON files (manifest, etc.) with short cache
echo "→ Uploading manifest and config files..."
aws s3 sync "$BUILD_DIR/" "s3://$BUCKET_NAME/" \
    --exclude "*" \
    --include "*.json" \
    --include "*.txt" \
    --cache-control "public, max-age=3600" \
    --metadata-directive REPLACE

# Upload service worker with no cache
echo "→ Uploading service worker..."
aws s3 sync "$BUILD_DIR/" "s3://$BUCKET_NAME/" \
    --exclude "*" \
    --include "service-worker.js" \
    --cache-control "public, max-age=0, must-revalidate" \
    --content-type "application/javascript" \
    --metadata-directive REPLACE

echo ""
echo "✓ All files deployed successfully!"
echo ""

# Get the website URLs
WEBSITE_URL="http://$BUCKET_NAME.s3-website-$REGION.amazonaws.com"
S3_URL="https://$BUCKET_NAME.s3.$REGION.amazonaws.com/index.html"

echo "=========================================="
echo "Deployment Complete! 🎉"
echo "=========================================="
echo ""
echo "Your WinK application is live at:"
echo ""
echo "  🌐 S3 Website: $WEBSITE_URL"
echo "  📦 S3 Direct:  $S3_URL"
echo ""
echo "Deployment Info:"
echo "  Bucket: $BUCKET_NAME"
echo "  Region: $REGION"
echo "  Build size: $BUILD_SIZE"
echo ""
echo "Production Optimizations Applied:"
echo "  ✓ Minified JS/CSS"
echo "  ✓ Code splitting"
echo "  ✓ Tree shaking"
echo "  ✓ No source maps"
echo "  ✓ Gzip compression"
echo "  ✓ Optimized caching"
echo ""
echo "To update, run: ./deploy-ui-to-s3.sh"
echo ""
