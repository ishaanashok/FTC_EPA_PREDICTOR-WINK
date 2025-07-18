# Lambda Deployment Bucket Configuration

## Overview

The CloudFormation template has been updated to support both creating a new S3 bucket for Lambda deployment packages or using an existing bucket. This prevents deployment failures when the bucket already exists.

## Parameters

### ExistingLambdaDeploymentBucket
- **Type**: String
- **Default**: Empty string
- **Description**: Optional name of existing S3 bucket for Lambda deployment packages
- **Usage**: If provided, the template will use this bucket instead of creating a new one

### CreateLambdaDeploymentBucket
- **Type**: String  
- **Default**: 'true'
- **Allowed Values**: [true, false]
- **Description**: Whether to create a new Lambda deployment bucket
- **Usage**: Set to 'false' when using an existing bucket

## Usage Scenarios

### Scenario 1: Create a New Bucket (Default)
Deploy with default parameters to create a new bucket:

```bash
aws cloudformation deploy \
  --template-file infrastructure/cloudformation-template.yaml \
  --stack-name ftc-predictor-dev \
  --parameter-overrides \
    Environment=dev \
    FTCApiUsername=your-username \
    FTCApiKey=your-api-key \
  --capabilities CAPABILITY_IAM
```

The template will create a bucket named: `ftc-lambda-deployment-dev-{AccountId}`

### Scenario 2: Use an Existing Bucket
Deploy using an existing S3 bucket:

```bash
aws cloudformation deploy \
  --template-file infrastructure/cloudformation-template.yaml \
  --stack-name ftc-predictor-dev \
  --parameter-overrides \
    Environment=dev \
    FTCApiUsername=your-username \
    FTCApiKey=your-api-key \
    ExistingLambdaDeploymentBucket=my-existing-bucket \
    CreateLambdaDeploymentBucket=false \
  --capabilities CAPABILITY_IAM
```

### Scenario 3: Bucket Already Exists (Update Deployment)
If you previously deployed and the bucket exists, you can either:

**Option A: Continue using the created bucket**
```bash
# No changes needed - template will use the existing bucket
aws cloudformation deploy \
  --template-file infrastructure/cloudformation-template.yaml \
  --stack-name ftc-predictor-dev \
  --parameter-overrides \
    Environment=dev \
    FTCApiUsername=your-username \
    FTCApiKey=your-api-key \
  --capabilities CAPABILITY_IAM
```

**Option B: Switch to using the bucket as "existing"**
```bash
aws cloudformation deploy \
  --template-file infrastructure/cloudformation-template.yaml \
  --stack-name ftc-predictor-dev \
  --parameter-overrides \
    Environment=dev \
    FTCApiUsername=your-username \
    FTCApiKey=your-api-key \
    ExistingLambdaDeploymentBucket=ftc-lambda-deployment-dev-123456789012 \
    CreateLambdaDeploymentBucket=false \
  --capabilities CAPABILITY_IAM
```

## How It Works

### Conditions
The template uses CloudFormation conditions to determine bucket usage:

```yaml
Conditions:
  CreateNewBucket: !And
    - !Equals [!Ref CreateLambdaDeploymentBucket, 'true']
    - !Equals [!Ref ExistingLambdaDeploymentBucket, '']
  
  UseExistingBucket: !Not [!Condition CreateNewBucket]
```

### Conditional Resources
The S3 bucket resource is only created when `CreateNewBucket` condition is true:

```yaml
LambdaDeploymentBucket:
  Type: AWS::S3::Bucket
  Condition: CreateNewBucket
  Properties:
    BucketName: !Sub 'ftc-lambda-deployment-${Environment}-${AWS::AccountId}'
    # ... other properties
```

### Dynamic References
All Lambda functions and layers use conditional references:

```yaml
S3Bucket: !If [CreateNewBucket, !Ref LambdaDeploymentBucket, !Ref ExistingLambdaDeploymentBucket]
```

## Bucket Requirements

### For New Buckets
- Automatically configured with:
  - Versioning enabled
  - Public access blocked
  - Appropriate naming convention

### For Existing Buckets
Ensure your existing bucket has:

1. **Proper Permissions**: Lambda execution role needs access
2. **Versioning**: Recommended for deployment rollbacks
3. **Structure**: Should contain these paths:
   ```
   layers/
     common-dependencies.zip
   functions/
     data-sync.zip
     teams-api.zip
     events-api.zip
     matches-api.zip
     epa-api.zip
     alliance-matchmaker.zip
   ```

## Deployment Script Updates

Update your deployment scripts to handle the bucket parameter:

```bash
#!/bin/bash

ENVIRONMENT=${1:-dev}
EXISTING_BUCKET=${2:-}

if [ -n "$EXISTING_BUCKET" ]; then
  echo "Using existing bucket: $EXISTING_BUCKET"
  BUCKET_PARAMS="ExistingLambdaDeploymentBucket=$EXISTING_BUCKET CreateLambdaDeploymentBucket=false"
else
  echo "Creating new bucket for environment: $ENVIRONMENT"
  BUCKET_PARAMS=""
fi

aws cloudformation deploy \
  --template-file infrastructure/cloudformation-template.yaml \
  --stack-name ftc-predictor-$ENVIRONMENT \
  --parameter-overrides \
    Environment=$ENVIRONMENT \
    FTCApiUsername=$FTC_USERNAME \
    FTCApiKey=$FTC_API_KEY \
    $BUCKET_PARAMS \
  --capabilities CAPABILITY_IAM
```

Usage:
```bash
# Create new bucket
./deploy.sh dev

# Use existing bucket  
./deploy.sh dev my-existing-bucket
```

## Troubleshooting

### Bucket Already Exists Error
If you get a "BucketAlreadyExists" error:

1. Set `ExistingLambdaDeploymentBucket` to the existing bucket name
2. Set `CreateLambdaDeploymentBucket` to `false`
3. Redeploy the stack

### Access Denied Errors
Ensure the existing bucket allows access from the Lambda execution role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT-ID:role/FTC-Lambda-Role-ENVIRONMENT"
      },
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion"
      ],
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    }
  ]
}
```

### Missing Deployment Packages
If Lambda functions fail to deploy:

1. Verify the S3 bucket contains the required ZIP files
2. Check that the file paths match what's expected in the template
3. Ensure the deployment script uploaded packages to the correct bucket

## Best Practices

1. **Use Consistent Naming**: If creating buckets manually, follow the naming convention
2. **Enable Versioning**: Always enable versioning for rollback capabilities  
3. **Monitor Costs**: Consider lifecycle policies for old deployment packages
4. **Security**: Never make deployment buckets public
5. **Documentation**: Document which bucket is used for each environment

## Migration from Previous Versions

If upgrading from a template version without this feature:

1. Note the current bucket name from the stack outputs
2. Update the stack with that bucket name as `ExistingLambdaDeploymentBucket`
3. Set `CreateLambdaDeploymentBucket` to `false`
4. Deploy the updated template

This ensures continuity with existing deployments while adding flexibility for future deployments. 