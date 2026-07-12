#!/bin/bash
# 02-test-isolation.sh
# Usage: ./02-test-isolation.sh <UserPoolId> <ClientId> <IdentityPoolId> <TableName> <Region>
set -e

USER_POOL_ID=$1
CLIENT_ID=$2
IDENTITY_POOL_ID=$3
TABLE_NAME=$4
REGION=$5

test_tenant() {
  TENANT=$1
  OTHER_TENANT=$2
  USERNAME="${TENANT}-user@example.com"
  PASSWORD="TenantPass123!"

  echo ""
  echo "############################################"
  echo "# Testing as $USERNAME (tenant_id=$TENANT)"
  echo "############################################"

  # 1. Authenticate -> get ID token
  AUTH=$(aws cognito-idp initiate-auth \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id "$CLIENT_ID" \
    --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" \
    --region "$REGION")
  ID_TOKEN=$(echo "$AUTH" | grep -o '"IdToken": *"[^"]*"' | sed 's/.*: *"//;s/"$//')

  # 2. Exchange ID token for a Cognito Identity Id
  LOGINS_KEY="cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}"
  ID_RESULT=$(aws cognito-identity get-id \
    --identity-pool-id "$IDENTITY_POOL_ID" \
    --logins "{\"$LOGINS_KEY\":\"$ID_TOKEN\"}" \
    --region "$REGION")
  IDENTITY_ID=$(echo "$ID_RESULT" | grep -o '"IdentityId": *"[^"]*"' | sed 's/.*: *"//;s/"$//')

  # 3. Get temporary IAM credentials tagged with tenant_id (ABAC)
  CREDS=$(aws cognito-identity get-credentials-for-identity \
    --identity-id "$IDENTITY_ID" \
    --logins "{\"$LOGINS_KEY\":\"$ID_TOKEN\"}" \
    --region "$REGION")

  AK=$(echo "$CREDS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['AccessKeyId'])")
  SK=$(echo "$CREDS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['SecretKey'])")
  ST=$(echo "$CREDS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['SessionToken'])")

  echo "-- [Expect SUCCESS] Query own partition ($TENANT) --"
  AWS_ACCESS_KEY_ID=$AK AWS_SECRET_ACCESS_KEY=$SK AWS_SESSION_TOKEN=$ST \
    aws dynamodb query --table-name "$TABLE_NAME" --region "$REGION" \
    --key-condition-expression "pk = :p" \
    --expression-attribute-values "{\":p\":{\"S\":\"$TENANT\"}}" \
    --query "Items[].sk.S" --output text

  echo "-- [Expect ACCESS DENIED] Query other tenant's partition ($OTHER_TENANT) --"
  set +e
  AWS_ACCESS_KEY_ID=$AK AWS_SECRET_ACCESS_KEY=$SK AWS_SESSION_TOKEN=$ST \
    aws dynamodb query --table-name "$TABLE_NAME" --region "$REGION" \
    --key-condition-expression "pk = :p" \
    --expression-attribute-values "{\":p\":{\"S\":\"$OTHER_TENANT\"}}" 2>&1
  set -e
}

test_tenant "tenant-1" "tenant-2"
test_tenant "tenant-2" "tenant-1"

echo ""
echo "If both cross-tenant queries returned AccessDeniedException, isolation is proven."
