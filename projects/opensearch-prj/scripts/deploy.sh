#!/bin/bash
set -euo pipefail

STACK_NAME="dynamo-opensearch-lab"
REGION="${AWS_REGION:-us-east-1}"

if [ -z "${OS_MASTER_PASSWORD:-}" ]; then
  echo "Set OS_MASTER_PASSWORD env var first (8+ chars, upper/lower/number/symbol)"
  exit 1
fi

echo ">> Deploying CloudFormation stack (OpenSearch domain takes ~12-15 min)..."
aws cloudformation deploy \
  --template-file ../infrastructure.yaml \
  --stack-name "$STACK_NAME" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides MasterUserPassword="$OS_MASTER_PASSWORD" \
  --region "$REGION"

echo ">> Packaging indexer Lambda..."
cd ../lambda-indexer
zip -q -r /tmp/indexer.zip index.mjs
aws lambda update-function-code \
  --function-name "${STACK_NAME}-indexer" \
  --zip-file fileb:///tmp/indexer.zip \
  --region "$REGION" >/dev/null
cd ../lambda-search-api

echo ">> Packaging search API Lambda..."
zip -q -r /tmp/search-api.zip index.mjs
aws lambda update-function-code \
  --function-name "${STACK_NAME}-search-api" \
  --zip-file fileb:///tmp/search-api.zip \
  --region "$REGION" >/dev/null

echo ">> Done. Fetching outputs..."
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' \
  --region "$REGION" \
  --output table
