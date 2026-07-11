#!/usr/bin/env bash
# Deploys the CloudFormation stack and writes outputs to testing/.env
# so the Python/Node test scripts can pick them up automatically.
set -euo pipefail

STACK_NAME="${1:-appsync-order-workflow}"
REGION="${AWS_REGION:-$(aws configure get region)}"
TEMPLATE="../cloudformation/template.yaml"

echo ">> Deploying stack: $STACK_NAME (region: $REGION)"

aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file "$TEMPLATE" \
  --capabilities CAPABILITY_IAM \
  --region "$REGION"

echo ">> Fetching outputs..."

OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output json)

GRAPHQL_URL=$(echo "$OUTPUTS" | python3 -c "import json,sys; d=json.load(sys.stdin); print([o['OutputValue'] for o in d if o['OutputKey']=='GraphQLApiUrl'][0])")
REALTIME_URL=$(echo "$OUTPUTS" | python3 -c "import json,sys; d=json.load(sys.stdin); print([o['OutputValue'] for o in d if o['OutputKey']=='GraphQLRealtimeUrl'][0])")
API_KEY=$(echo "$OUTPUTS" | python3 -c "import json,sys; d=json.load(sys.stdin); print([o['OutputValue'] for o in d if o['OutputKey']=='GraphQLApiKeyOutput'][0])")
TABLE_NAME=$(echo "$OUTPUTS" | python3 -c "import json,sys; d=json.load(sys.stdin); print([o['OutputValue'] for o in d if o['OutputKey']=='OrdersTableName'][0])")
STATE_MACHINE_ARN=$(echo "$OUTPUTS" | python3 -c "import json,sys; d=json.load(sys.stdin); print([o['OutputValue'] for o in d if o['OutputKey']=='StateMachineArn'][0])")

cat > .env <<EOF
GRAPHQL_URL=$GRAPHQL_URL
REALTIME_URL=$REALTIME_URL
API_KEY=$API_KEY
TABLE_NAME=$TABLE_NAME
STATE_MACHINE_ARN=$STATE_MACHINE_ARN
AWS_REGION=$REGION
EOF

echo ">> Wrote testing/.env"
cat .env
