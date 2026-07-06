#!/usr/bin/env zsh
# Run from the infra/ directory. Requires AWS CLI v2 configured for your account.
# Target region matches your els-cicd project: ap-south-1
set -e

REGION="ap-south-1"
DISTRIBUTION_ID="${1:-}"   # pass your existing CloudFront distribution ID as arg 1

echo "== 1. CloudFront cache policy =="
CACHE_POLICY_ID=$(aws cloudfront create-cache-policy \
  --cli-input-json file://cloudfront-cache-policy.json \
  --query 'CachePolicy.Id' --output text)
echo "Created cache policy: $CACHE_POLICY_ID"
echo "Attach it to a cache behavior via:"
echo "  aws cloudfront get-distribution-config --id $DISTRIBUTION_ID > dist-config.json"
echo "  (edit CacheBehaviors[].CachePolicyId to $CACHE_POLICY_ID, then update-distribution --if-match <ETag>)"

echo ""
echo "== 2. SNS topic =="
TOPIC_ARN=$(aws sns create-topic --name product-events --region $REGION \
  --query 'TopicArn' --output text)
echo "Created topic: $TOPIC_ARN"
echo "Set this as SNS_TOPIC_ARN in your app's .env file"

echo ""
echo "== 3. SNS subscription with a filter policy (price increases only) =="
# Replace with a real endpoint (SQS ARN, Lambda ARN, or email) before running for real.
SUBSCRIPTION_ARN=$(aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol email \
  --notification-endpoint "you@example.com" \
  --region $REGION \
  --query 'SubscriptionArn' --output text)

aws sns set-subscription-attributes \
  --subscription-arn "$SUBSCRIPTION_ARN" \
  --attribute-name FilterPolicy \
  --attribute-value '{"eventType":["price_updated"],"priceChangeType":["increase"]}' \
  --region $REGION
echo "Filter policy attached: subscriber only fires on eventType=price_updated AND priceChangeType=increase"

echo ""
echo "== 4. ElastiCache Redis cluster (single node, cost-optimized for learning) =="
echo "Replace SECURITY_GROUP_ID and SUBNET_GROUP with values from your VPC (same VPC as RDS):"
echo "  aws elasticache create-cache-subnet-group \\"
echo "    --cache-subnet-group-name myapp-redis-subnet \\"
echo "    --cache-subnet-group-description \"Redis subnet group\" \\"
echo "    --subnet-ids <subnet-1> <subnet-2> --region $REGION"
echo ""
echo "  aws elasticache create-cache-cluster \\"
echo "    --cache-cluster-id myapp-redis \\"
echo "    --engine redis --cache-node-type cache.t3.micro \\"
echo "    --num-cache-nodes 1 \\"
echo "    --cache-subnet-group-name myapp-redis-subnet \\"
echo "    --security-group-ids <SECURITY_GROUP_ID> \\"
echo "    --region $REGION"
echo ""
echo "Once available, grab the endpoint:"
echo "  aws elasticache describe-cache-clusters --cache-cluster-id myapp-redis \\"
echo "    --show-cache-node-info --query 'CacheClusters[0].CacheNodes[0].Endpoint' --region $REGION"

echo ""
echo "Done. Next: fill in REDIS_HOST and SNS_TOPIC_ARN in app/.env, then deploy the app."
