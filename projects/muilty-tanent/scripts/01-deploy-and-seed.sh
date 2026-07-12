#!/bin/bash
# 01-deploy-and-seed.sh
# Deploys the stack, creates 2 tenant users in Cognito, seeds sample DynamoDB rows.
set -e

STACK_NAME="mtsaas-lab"
REGION="ap-south-1"          # change to your region
TEMPLATE="multi-tenant-isolation.yaml"

echo "== 1. Deploying CloudFormation stack =="
aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file "$TEMPLATE" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION"

USER_POOL_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)
CLIENT_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" --output text)
IDENTITY_POOL_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='IdentityPoolId'].OutputValue" --output text)
TABLE_NAME=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='TableName'].OutputValue" --output text)

echo "UserPoolId=$USER_POOL_ID  ClientId=$CLIENT_ID  IdentityPoolId=$IDENTITY_POOL_ID  Table=$TABLE_NAME"

echo "== 2. Creating simulation users for two tenants =="
for TENANT in tenant-1 tenant-2; do
  USERNAME="${TENANT}-user@example.com"
  PASSWORD="TempPass123!"
  FINALPASS="TenantPass123!"

  aws cognito-idp admin-create-user \
    --user-pool-id "$USER_POOL_ID" \
    --username "$USERNAME" \
    --user-attributes Name=email,Value="$USERNAME" Name=email_verified,Value=true Name=custom:tenant_id,Value="$TENANT" \
    --temporary-password "$PASSWORD" \
    --message-action SUPPRESS \
    --region "$REGION" || echo "(user may already exist)"

  aws cognito-idp admin-set-user-password \
    --user-pool-id "$USER_POOL_ID" \
    --username "$USERNAME" \
    --password "$FINALPASS" \
    --permanent \
    --region "$REGION"

  echo "Created $USERNAME / password: $FINALPASS  tenant_id=$TENANT"
done

echo "== 3. Seeding sample DynamoDB rows for each tenant =="
for TENANT in tenant-1 tenant-2; do
  aws dynamodb put-item --table-name "$TABLE_NAME" --region "$REGION" --item "{
    \"pk\": {\"S\": \"$TENANT\"},
    \"sk\": {\"S\": \"ORDER#1001\"},
    \"amount\": {\"N\": \"249.99\"},
    \"status\": {\"S\": \"SHIPPED\"}
  }"
  aws dynamodb put-item --table-name "$TABLE_NAME" --region "$REGION" --item "{
    \"pk\": {\"S\": \"$TENANT\"},
    \"sk\": {\"S\": \"PROFILE#001\"},
    \"companyName\": {\"S\": \"$TENANT Inc.\"}
  }"
done

echo "== Done. =="
echo "Next: run 02-test-isolation.sh $USER_POOL_ID $CLIENT_ID $IDENTITY_POOL_ID $TABLE_NAME $REGION"
