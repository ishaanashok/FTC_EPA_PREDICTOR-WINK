# Lambda Deployment Script

This document explains how to use the `deploy-lambdas.sh` script to build and deploy only the Lambda functions, without touching the infrastructure.

## Prerequisites

1. **AWS CLI**: Installed and configured with appropriate credentials
2. **CloudFormation Stack**: The infrastructure must already be deployed using `deploy.sh`
3. **Python**: With `pip` for installing dependencies
4. **Project Structure**: Run from the project root directory

## Usage

```bash
# Basic usage (deploys to dev environment in us-east-1)
./deploy-lambdas.sh

# Specify environment
./deploy-lambdas.sh dev us-east-1

# Deploy to production
./deploy-lambdas.sh prod us-west-2

# Show help
./deploy-lambdas.sh --help
```

## What the Script Does

1. **Validates Prerequisites**: Checks AWS CLI, credentials, and project structure
2. **Gets Deployment Bucket**: Retrieves the S3 bucket from the CloudFormation stack
3. **Builds Dependencies Layer**: Creates a layer with common Python dependencies
4. **Builds Lambda Functions**: Packages all lambda functions with their code and dependencies
5. **Uploads to S3**: Uploads all packages to the deployment bucket
6. **Updates Lambda Code**: Updates the actual Lambda functions in AWS
7. **Updates Layer**: Publishes a new version of the dependencies layer
8. **Tests Functions**: (Dev only) Tests the data-sync function
9. **Cleanup**: Removes build artifacts

## Lambda Functions Deployed

The script deploys these Lambda functions:
- `ftc-data-sync-{environment}`
- `ftc-epa-api-{environment}`
- `ftc-teams-api-{environment}`
- `ftc-events-api-{environment}`
- `ftc-matches-api-{environment}`
- `ftc-alliance-matchmaker-{environment}`

## Example Output

```bash
$ ./deploy-lambdas.sh dev us-east-1
[2024-01-01 10:00:00] Starting FTC Predictor Lambda Deployment
[2024-01-01 10:00:00] Environment: dev
[2024-01-01 10:00:00] Region: us-east-1
[2024-01-01 10:00:00] Stack Name: ftc-predictor-dev
[2024-01-01 10:00:00] Checking prerequisites...
[2024-01-01 10:00:00] Prerequisites check passed
[2024-01-01 10:00:00] Getting deployment bucket from CloudFormation stack...
[2024-01-01 10:00:00] Using deployment bucket: ftc-lambda-deployment-dev-123456789012
[2024-01-01 10:00:00] Building common dependencies layer...
[2024-01-01 10:00:00] Installing Python dependencies...
[2024-01-01 10:00:00] Uploading dependencies layer to S3...
[2024-01-01 10:00:00] Dependencies layer built and uploaded successfully
[2024-01-01 10:00:00] Building and deploying Lambda functions...
[2024-01-01 10:00:00] Building data-sync Lambda function...
[2024-01-01 10:00:00] Uploading data-sync to S3...
[2024-01-01 10:00:00] data-sync Lambda function packaged and uploaded
...
[2024-01-01 10:00:00] Lambda deployment completed successfully!
```

## Error Handling

The script includes comprehensive error handling:
- **Missing Prerequisites**: Checks for AWS CLI, credentials, and required files
- **Stack Not Found**: Ensures the CloudFormation stack exists before proceeding
- **Missing Lambda Files**: Validates that all lambda function files exist
- **AWS Errors**: Proper error messages for AWS API failures

## Use Cases

### Development Workflow
When making changes to lambda functions during development:
```bash
# Make changes to lambda code
vim aws/lambda/data-sync/lambda_function.py

# Deploy only the lambdas (faster than full deployment)
./deploy-lambdas.sh dev

# Test the changes
aws lambda invoke --function-name ftc-data-sync-dev --payload '{"syncType": "teams", "season": 2024}' response.json
```

### Production Deployment
For production deployments:
```bash
# Deploy to production
./deploy-lambdas.sh prod us-west-2

# Monitor the deployment
aws logs tail /aws/lambda/ftc-data-sync-prod --follow
```

### Rollback
If you need to rollback to a previous version:
```bash
# This script always deploys the current code
# To rollback, you would need to:
# 1. Git checkout the previous version
# 2. Run the deployment script
git checkout previous-working-commit
./deploy-lambdas.sh prod
```

## Performance

The script is optimized for speed:
- **Parallel Processing**: Builds all functions concurrently
- **Incremental Updates**: Only updates what's changed
- **Efficient Packaging**: Uses quiet mode for faster zipping
- **Layer Caching**: Dependencies layer is reused across functions

## Troubleshooting

### Common Issues

1. **"Stack not found"**: Ensure you've deployed the infrastructure first with `deploy.sh`
2. **"Access denied"**: Check AWS credentials and IAM permissions
3. **"Lambda function not found"**: Verify the function was created during infrastructure deployment
4. **"Import errors"**: Check that all required dependencies are in the requirements.txt

### Debugging

To debug issues:
```bash
# Check CloudFormation stack status
aws cloudformation describe-stacks --stack-name ftc-predictor-dev

# Check Lambda function status
aws lambda get-function --function-name ftc-data-sync-dev

# View Lambda logs
aws logs tail /aws/lambda/ftc-data-sync-dev
```

## Comparison with Full Deployment

| Aspect | `deploy.sh` | `deploy-lambdas.sh` |
|--------|-------------|-------------------|
| **Speed** | Slower (5-10 min) | Faster (1-3 min) |
| **Scope** | Full infrastructure | Lambda functions only |
| **Use Case** | Initial setup, infrastructure changes | Code changes, updates |
| **Prerequisites** | AWS credentials | Existing CloudFormation stack |
| **Risk** | High (can affect infrastructure) | Low (code changes only) |

## Best Practices

1. **Test First**: Always test in dev environment before production
2. **Monitor Logs**: Check CloudWatch logs after deployment
3. **Version Control**: Commit changes before deployment
4. **Backup**: Keep track of working versions
5. **Documentation**: Update this file if you modify the script 