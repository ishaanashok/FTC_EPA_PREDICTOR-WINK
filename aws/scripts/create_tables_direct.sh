#!/bin/bash
# Create DynamoDB tables directly using AWS CLI (bypassing CloudFormation)

ENV="stage"

echo "Creating FTC DynamoDB tables for environment: $ENV"
echo "================================================"
echo ""

# Create Teams Table
echo "Creating FTC_Teams_$ENV..."
aws dynamodb create-table \
  --table-name "FTC_Teams_$ENV" \
  --attribute-definitions \
    AttributeName=teamNumber,AttributeType=N \
    AttributeName=season,AttributeType=N \
    AttributeName=country,AttributeType=S \
    AttributeName=homeRegion,AttributeType=S \
  --key-schema \
    AttributeName=teamNumber,KeyType=HASH \
    AttributeName=season,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --global-secondary-indexes \
    "[
      {
        \"IndexName\": \"SeasonIndex\",
        \"KeySchema\": [{\"AttributeName\":\"season\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"teamNumber\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"CountrySeasonIndex\",
        \"KeySchema\": [{\"AttributeName\":\"country\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"season\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"RegionSeasonIndex\",
        \"KeySchema\": [{\"AttributeName\":\"homeRegion\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"season\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      }
    ]" \
  --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
  --tags Key=Environment,Value=$ENV Key=Application,Value=FTC-Predictor \
  --no-cli-pager > /dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "✓ FTC_Teams_$ENV created"
else
  echo "✗ Failed to create FTC_Teams_$ENV"
fi

# Create Events Table
echo "Creating FTC_Events_$ENV..."
aws dynamodb create-table \
  --table-name "FTC_Events_$ENV" \
  --attribute-definitions \
    AttributeName=eventId,AttributeType=S \
    AttributeName=season,AttributeType=N \
    AttributeName=code,AttributeType=S \
    AttributeName=dateStart,AttributeType=S \
    AttributeName=regionCode,AttributeType=S \
  --key-schema \
    AttributeName=eventId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --global-secondary-indexes \
    "[
      {
        \"IndexName\": \"CodeSeasonIndex\",
        \"KeySchema\": [{\"AttributeName\":\"code\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"season\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"SeasonDateIndex\",
        \"KeySchema\": [{\"AttributeName\":\"season\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"dateStart\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"RegionSeasonIndex\",
        \"KeySchema\": [{\"AttributeName\":\"regionCode\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"season\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      }
    ]" \
  --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
  --tags Key=Environment,Value=$ENV Key=Application,Value=FTC-Predictor \
  --no-cli-pager > /dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "✓ FTC_Events_$ENV created"
else
  echo "✗ Failed to create FTC_Events_$ENV"
fi

# Create Matches Table
echo "Creating FTC_Matches_$ENV..."
aws dynamodb create-table \
  --table-name "FTC_Matches_$ENV" \
  --attribute-definitions \
    AttributeName=matchId,AttributeType=S \
    AttributeName=season,AttributeType=N \
    AttributeName=eventCode,AttributeType=S \
    AttributeName=eventCode_matchNumber,AttributeType=S \
  --key-schema \
    AttributeName=matchId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --global-secondary-indexes \
    "[
      {
        \"IndexName\": \"EventSeasonIndex\",
        \"KeySchema\": [{\"AttributeName\":\"eventCode\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"season\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"EventMatchNumberIndex\",
        \"KeySchema\": [{\"AttributeName\":\"eventCode_matchNumber\",\"KeyType\":\"HASH\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"SeasonIndex\",
        \"KeySchema\": [{\"AttributeName\":\"season\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"matchId\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      }
    ]" \
  --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
  --tags Key=Environment,Value=$ENV Key=Application,Value=FTC-Predictor \
  --no-cli-pager > /dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "✓ FTC_Matches_$ENV created"
else
  echo "✗ Failed to create FTC_Matches_$ENV"
fi

# Create TeamMatchEPA Table
echo "Creating FTC_TeamMatchEPA_$ENV..."
aws dynamodb create-table \
  --table-name "FTC_TeamMatchEPA_$ENV" \
  --attribute-definitions \
    AttributeName=teamNumber_matchId,AttributeType=S \
    AttributeName=teamNumber,AttributeType=N \
    AttributeName=season,AttributeType=N \
    AttributeName=eventCode,AttributeType=S \
    AttributeName=matchId,AttributeType=S \
    AttributeName=actualStartTime,AttributeType=S \
  --key-schema \
    AttributeName=teamNumber_matchId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --global-secondary-indexes \
    "[
      {
        \"IndexName\": \"TeamSeasonIndex\",
        \"KeySchema\": [{\"AttributeName\":\"teamNumber\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"season\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"TeamEventIndex\",
        \"KeySchema\": [{\"AttributeName\":\"teamNumber\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"eventCode\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"EventMatchIndex\",
        \"KeySchema\": [{\"AttributeName\":\"eventCode\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"matchId\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"TeamSeasonTimeIndex\",
        \"KeySchema\": [{\"AttributeName\":\"teamNumber\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"actualStartTime\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"SeasonIndex\",
        \"KeySchema\": [{\"AttributeName\":\"season\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"teamNumber_matchId\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      }
    ]" \
  --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
  --tags Key=Environment,Value=$ENV Key=Application,Value=FTC-Predictor \
  --no-cli-pager > /dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "✓ FTC_TeamMatchEPA_$ENV created"
else
  echo "✗ Failed to create FTC_TeamMatchEPA_$ENV"
fi

echo ""
echo "Waiting for tables to become ACTIVE..."
echo ""

# Wait for all tables to be active
aws dynamodb wait table-exists --table-name "FTC_Teams_$ENV"
aws dynamodb wait table-exists --table-name "FTC_Events_$ENV"
aws dynamodb wait table-exists --table-name "FTC_Matches_$ENV"
aws dynamodb wait table-exists --table-name "FTC_TeamMatchEPA_$ENV"

echo ""
echo "================================================"
echo "All tables created successfully!"
echo "================================================"
echo ""

# List the created tables
echo "Created tables:"
aws dynamodb list-tables --query "TableNames[?contains(@, 'FTC_') && contains(@, '_$ENV')]" --output table

echo ""
echo "You can now run: python3 load_all_data.py"


