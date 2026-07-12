# DynamoDB Streams -> Lambda -> OpenSearch (Project 19)

## Architecture

```
DynamoDB (products table, Streams: NEW_AND_OLD_IMAGES)
        |
        v
  Indexer Lambda  --(HTTPS, basic auth)-->  OpenSearch domain (single node)
                                                     ^
                                                     |
API Gateway HTTP API --(GET /search)--> Search API Lambda
```

## 1. Deploy

```bash
cd scripts
export OS_MASTER_PASSWORD='YourStr0ng!Pass'
./deploy.sh
```

This runs `aws cloudformation deploy` then overwrites the Lambda placeholder
code with the real handlers (CFN's inline `ZipFile` can't hold npm-style
modules, so the template ships a stub and `deploy.sh` patches it — this
two-step pattern itself is worth knowing, since the exam likes to test
"why did my Lambda not do what the code says" scenarios).

Domain creation takes ~12-15 minutes. Everything else is fast.

Grab the outputs (endpoint, API URL, table name) with:
```bash
aws cloudformation describe-stacks --stack-name dynamo-opensearch-lab \
  --query 'Stacks[0].Outputs' --output table
```

## 2. Create the index mapping

```bash
export OS_ENDPOINT=<OpenSearchEndpoint output>
export OS_USER=labadmin
export OS_PASSWORD=$OS_MASTER_PASSWORD
./create-index.sh
```

## 3. Seed data (this is also your integration test trigger)

```bash
export TABLE_NAME=dynamo-opensearch-lab-products
pip install boto3 --break-system-packages
python3 seed_data.py
```

Every `put_item` fires a stream record -> indexer Lambda -> OpenSearch write.

## Cost management (this is the part that actually matters for a lab)

The OpenSearch domain (`t3.small.search`, single node, 10GB gp3) is the only
component with a meaningful always-on cost — roughly $26-30/month if left
running continuously. Everything else (DynamoDB on-demand at this data
volume, Lambda, API Gateway HTTP API) is essentially free-tier.

**Keep it cheap:** don't leave the domain running between study sessions.

```bash
# tear down completely when done for the day
aws cloudformation delete-stack --stack-name dynamo-opensearch-lab
```

Redeploying costs you the ~12-15 min domain provisioning time each session —
that's a fair trade for paying for maybe 2 hours/month instead of 730.

---

## Testing modules

**Module 1 - Unit test the indexer logic (no AWS calls)**
Invoke `lambda-indexer/index.mjs`'s `handler` locally with a synthetic
DynamoDB Streams event (INSERT/MODIFY/REMOVE) and stub `fetch` to assert it
builds the right OpenSearch request bodies. Catches unmarshalling bugs
before you burn a deploy cycle.

**Module 2 - Integration test (real pipeline)**
1. Run `seed_data.py`.
2. Tail the indexer logs: `aws logs tail /aws/lambda/dynamo-opensearch-lab-indexer --follow`
3. Confirm doc count landed: `curl -u labadmin:$OS_PASSWORD https://$OS_ENDPOINT/products/_count`

**Module 3 - API test**
```bash
curl "https://<ApiEndpoint>?q=waterproof"
curl "https://<ApiEndpoint>?q=habits&category=books"
```
Check `opensearch_took_ms` vs `lambda_roundtrip_ms` in the response — the
gap is your network/Lambda cold-start overhead, a real DVA-C02 topic.

**Module 4 - Failure/edge-case test**
Delete an item directly from the DynamoDB console and confirm the doc
disappears from OpenSearch (`REMOVE` event handling). Then intentionally
break the indexer (e.g. wrong `INDEX_NAME`) and watch `MaximumRetryAttempts`
and `BisectBatchOnFunctionError` behavior in the Lambda's CloudWatch logs —
this is exactly the "DynamoDB Streams poison pill" scenario the exam asks
about.

**Module 5 - Access pattern comparison (the "gain experience" part)**
```bash
export TABLE_NAME=dynamo-opensearch-lab-products
export OS_ENDPOINT=<endpoint> OS_USER=labadmin OS_PASSWORD=$OS_MASTER_PASSWORD
pip install requests --break-system-packages
python3 compare_access_patterns.py
```
This runs a DynamoDB `GetItem`, a DynamoDB `Scan+contains()` (anti-pattern),
an OpenSearch `multi_match` query, and an OpenSearch aggregation — timed
side by side — so you observe directly why each store exists, rather than
memorizing it.

---

## Observability / "see all the patterns" playbook

**CloudWatch Logs Insights** (query across all indexer invocations):
```
fields @timestamp, @message
| filter @message like /Indexed|Deleted|error/
| sort @timestamp desc
| limit 50
```
Run this in the console under the indexer function's log group to watch
every stream record processed, in order, without reading raw logs one by one.

**OpenSearch Dashboards** (visual pattern exploration):
Go to `https://<endpoint>/_dashboards/`, log in with `labadmin` /
your password (fine-grained access control is enabled in the template).
Create an index pattern on `products`, then use Discover to browse every
document and Visualize to build a category/price breakdown — this is the
"analytics on top of DynamoDB data" story you'll want to be able to explain.

**X-Ray (optional, for tracing the full request path):**
Add `Tracing: Active` to both Lambda functions in the template and attach
the `AWSXRayDaemonWriteAccess` managed policy to their roles. You'll then
see a service map showing DynamoDB Streams -> Lambda -> HTTPS call to
OpenSearch as one connected trace, which is the clearest way to *see*
the architecture rather than infer it from logs.

**Direct index inspection at any time:**
```bash
curl -u labadmin:$OS_PASSWORD "https://$OS_ENDPOINT/_cat/indices?v"
curl -u labadmin:$OS_PASSWORD "https://$OS_ENDPOINT/products/_search?pretty&size=5"
```

---

## What this maps to on the DVA-C02 exam

- **Deployment**: CloudFormation with parameters, outputs, and the
  inline-code-placeholder + post-deploy patch pattern.
- **Security**: IAM roles scoped to exact stream/log actions, FGAC on
  OpenSearch, secrets passed as `NoEcho` parameters (note: for anything
  beyond a lab, move the OpenSearch password to Secrets Manager and have
  Lambda fetch it at runtime instead of plain env vars).
- **Development**: DynamoDB Streams event structure, event source mapping
  batching/retry/bisect behavior, HTTP API Lambda proxy integration.
- **Refactoring**: recognizing when a single data store (DynamoDB) is the
  wrong tool for a requirement (full-text search, aggregations) and adding
  a purpose-built secondary store without changing the system of record.
- **Monitoring/Troubleshooting**: CloudWatch Logs Insights, stream
  processing failures, poison-pill records, and (optionally) X-Ray tracing.
