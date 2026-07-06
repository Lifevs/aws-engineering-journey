# CloudFront Caching + SNS Filter Policies for Optimization

Maps to DVA-C02 domains: **caching strategies (ElastiCache/CloudFront)**,
**messaging/decoupling (SNS)**, and **monitoring/optimization (CloudWatch)**.

## What this demonstrates

1. **ElastiCache in front of RDS** — cache-aside (lazy-load) pattern: read
   from Redis first, fall back to Postgres/RDS on a miss, populate the
   cache with a TTL.
2. **CloudFront cache behavior** — a cache policy that forwards the
   `Accept-Language` header and `currency` query string, so CloudFront
   builds distinct cache keys per variant instead of caching everything
   as one blob or bypassing cache entirely.
3. **SNS subscription filter policies** — publish events with
   `MessageAttributes` (`eventType`, `priceChangeType`, `region`) so
   subscribers only get invoked for messages they actually care about,
   cutting downstream Lambda/SQS processing.
4. **Cache hit-rate measurement** — an in-app counter for local testing,
   plus the real CloudWatch metrics to check once deployed.

## Project layout

```
app/            Express backend (cache-aside + SNS publish)
tests/          Jest tests (mocked Redis, filter-policy matching)
infra/          AWS CLI commands + CloudFront cache policy JSON
docker-compose.yml   Local Postgres + Redis for testing before real AWS
```

## Step 1 — Run it locally first (no AWS costs yet)

```bash
cd cloudfront-sns-optimization
docker-compose up -d          # starts local Postgres + Redis
cd app
cp .env.example .env
npm install
npm start                     # server on :3000
```

Test the cache-aside behavior yourself:

```bash
# First call: MISS (hits Postgres), notice X-Cache-Source: database
curl -i http://localhost:3000/products/1

# Second call within 60s: HIT (served from Redis), X-Cache-Source: cache
curl -i http://localhost:3000/products/1

# Different query string = different cache key
curl -i "http://localhost:3000/products/1?currency=inr"

# Check the running hit rate
curl http://localhost:3000/metrics/cache
```

Update a price (invalidates cache + publishes SNS event if SNS_TOPIC_ARN is set):

```bash
curl -X PATCH http://localhost:3000/products/1/price \
  -H "Content-Type: application/json" \
  -d '{"price": 24.99, "region": "ap-south-1"}'

# Confirm invalidation worked - this should be a MISS again
curl -i http://localhost:3000/products/1
```

## Step 2 — Run the tests

```bash
cd app
npm test
```

This runs 7 tests covering:
- cache miss populates the cache
- cache hit skips the loader entirely
- invalidation forces a fresh miss
- hit-rate math is correct
- SNS message attributes are built correctly
- a subscriber's filter policy only matches the intended event types

## Step 3 — Provision the real AWS resources

```bash
cd infra
chmod +x create-resources.sh
./create-resources.sh <your-existing-cloudfront-distribution-id>
```

This will:
- Create a CloudFront cache policy (`cloudfront-cache-policy.json`) that
  whitelists the `Accept-Language` header and `currency` query string
- Create an SNS topic `product-events`
- Subscribe an endpoint with a filter policy: only
  `eventType=price_updated AND priceChangeType=increase` messages reach it
- Print the ElastiCache `create-cache-cluster` command (fill in your VPC's
  subnet/security group IDs — same VPC as your RDS instance so they can
  talk to each other privately)

Attach the cache policy to your distribution's cache behavior:
```bash
aws cloudfront get-distribution-config --id <DIST_ID> > dist-config.json
# edit dist-config.json: set CacheBehaviors.Items[0].CachePolicyId to the
# printed cache policy ID, then:
aws cloudfront update-distribution --id <DIST_ID> \
  --if-match <ETag from get-distribution-config output> \
  --distribution-config file://dist-config.json
```

## Step 4 — Point the app at real AWS resources

Edit `app/.env`:
```
PGHOST=<your RDS endpoint>
REDIS_HOST=<your ElastiCache endpoint>
SNS_TOPIC_ARN=<printed by create-resources.sh>
```

## Step 5 — Measure and verify

**CloudFront cache hit rate**: CloudFront console → your distribution →
Monitoring tab → "Cache hit rate" graph (or `GetDistribution` +
CloudWatch metric `CacheHitRate` under namespace `AWS/CloudFront`, which
requires additional metrics enabled on the distribution).

**ElastiCache hit rate**: CloudWatch → Metrics → ElastiCache →
`CacheHits` / `CacheMisses` for your cluster ID. Hit rate =
`CacheHits / (CacheHits + CacheMisses)`.

**SNS filter policy working correctly**: publish two test messages and
confirm only one reaches your subscriber:
```bash
aws sns publish --topic-arn <TOPIC_ARN> \
  --message '{"test":"increase"}' \
  --message-attributes '{"eventType":{"DataType":"String","StringValue":"price_updated"},"priceChangeType":{"DataType":"String","StringValue":"increase"}}'
# ^ should reach your subscriber

aws sns publish --topic-arn <TOPIC_ARN> \
  --message '{"test":"stock"}' \
  --message-attributes '{"eventType":{"DataType":"String","StringValue":"stock_updated"}}'
# ^ should NOT reach your subscriber - filtered out at the SNS level
```

## Common errors and fixes

| Error | Cause | Fix |
|---|---|---|
| `ECONNREFUSED` on app start | Redis/Postgres not running | `docker-compose up -d` first |
| SNS `InvalidParameterException` on subscribe | Email endpoint needs confirmation | Check your inbox, click the AWS confirmation link before publishing |
| Filter policy silently drops everything | Attributes on publish don't match policy keys exactly (case-sensitive) | Compare `MessageAttributes` keys in `sns.js` against the subscription's `FilterPolicy` JSON |
| CloudFront still serving stale content after policy change | Distribution not yet deployed (Status still "InProgress") | `aws cloudfront get-distribution --id <ID> --query 'Distribution.Status'` and wait for `Deployed` |
| ElastiCache cluster stuck in `creating` | Subnet group in wrong AZ or no route to RDS's VPC | Confirm `cache-subnet-group` uses subnets in the same VPC as RDS |
