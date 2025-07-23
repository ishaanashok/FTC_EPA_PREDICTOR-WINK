# PowerShell script to deploy the data-sync Lambda function
$ErrorActionPreference = "Stop"

Write-Host "Creating Lambda deployment package..." -ForegroundColor Yellow

# Navigate to the data-sync function directory
$functionDir = "aws\lambda\data-sync"
$buildDir = "build\lambda\data-sync"

# Create build directory
if (Test-Path $buildDir) {
    Remove-Item $buildDir -Recurse -Force
}
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null

# Copy source files
Write-Host "Copying source files..." -ForegroundColor Green
Copy-Item "$functionDir\lambda_function.py" "$buildDir\"
Copy-Item "$functionDir\services" "$buildDir\services" -Recurse
Copy-Item "$functionDir\models" "$buildDir\models" -Recurse

# Copy shared dependencies
Write-Host "Copying shared dependencies..." -ForegroundColor Green
Copy-Item "aws\services\*.py" "$buildDir\services\" -Force
Copy-Item "aws\models\*.py" "$buildDir\models\" -Force

# Create deployment package
Write-Host "Creating ZIP package..." -ForegroundColor Green
$zipPath = "deployment-package.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

# Use PowerShell's built-in compression
Compress-Archive -Path "$buildDir\*" -DestinationPath $zipPath -Force

# Update Lambda function
Write-Host "Updating Lambda function..." -ForegroundColor Green
try {
    $result = aws lambda update-function-code --function-name "ftc-data-sync-stage" --zip-file "fileb://$zipPath"
    Write-Host "Lambda function updated successfully!" -ForegroundColor Green
    
    # Parse the JSON result to get function info
    $functionInfo = $result | ConvertFrom-Json
    Write-Host "Function: $($functionInfo.FunctionName)" -ForegroundColor Cyan
    Write-Host "Runtime: $($functionInfo.Runtime)" -ForegroundColor Cyan
    Write-Host "Last Modified: $($functionInfo.LastModified)" -ForegroundColor Cyan
    Write-Host "Code Size: $($functionInfo.CodeSize) bytes" -ForegroundColor Cyan
}
catch {
    Write-Host "Error updating Lambda function: $_" -ForegroundColor Red
    exit 1
}

Write-Host "Deployment complete! The updated pagination code is now live." -ForegroundColor Green
Write-Host "You can now test the teams sync from the AWS Console or admin dashboard." -ForegroundColor Yellow
