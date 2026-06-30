# AWS Lambda Performance Tuning & Observability Ecosystem

Production-grade CloudFormation stack + simulation tooling for tuning and
monitoring AWS Lambda using AWS X-Ray and CloudWatch.

## Repository Layout

```
template.yaml              CloudFormation template (IAM role, Lambda, alarms, dashboard)
lambda/handler.py          Target function source (Python 3.12)
lambda/requirements.txt    Lambda dependencies (aws-xray-sdk)
scripts/performance_test.py  Script A — sequential memory-tier sweep
scripts/load_test.py         Script B — concurrent burst / throttle test
```

---

## 1. Packaging & Deployment

The template's `TargetFunction.Code.ZipFile` ships a 501 placeholder so the
stack is valid on first `create-stack` without external artifacts. Replace
it with the real package using `aws cloudformation package`, which uploads
your built artifact to S3 and rewrites the template's `Code` property
automatically — no manual ZipFile editing required.

```bash
# 1. Install dependencies into the deployment package directory
cd lambda
pip install -r requirements.txt -t build/
cp handler.py build/
cd build && zip -r ../function.zip . && cd ..

# 2. Package: uploads function.zip to an S3 bucket and rewrites template.yaml
#    references to point at it (requires an existing S3 bucket you own)
aws cloudformation package \
  --template-file ../template.yaml \
  --s3-bucket <YOUR_DEPLOYMENT_ARTIFACT_BUCKET> \
  --output-template-file ../packaged-template.yaml

# 3. Deploy
aws cloudformation deploy \
  --template-file ../packaged-template.yaml \
  --stack-name lambda-perf-lab \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      ProjectName=lambda-perf-lab \
      LambdaMemorySize=128 \
      ReservedConcurrencyLimit=10 \
      ConcurrencyAlarmThresholdPercent=80 \
      ConcurrencyAlarmThreshold=8 \
      AlarmNotificationEmail=you@example.com
```

> `aws cloudformation package` requires `Code` to reference a local path
> rather than an inline `ZipFile` for it to repackage. Replace the
> `ZipFile:` block in `template.yaml`'s `TargetFunction` resource with:
> `Code: { S3Bucket: ..., S3Key: ... }` is handled automatically if you
> instead set `Code: ./lambda/build` (a local directory) before running
> `package` — the inline `ZipFile` is provided purely so the template
> validates standalone; switch the `Code` property to a `CodeUri`-style
> local path before running the packaging step above.

Retrieve outputs after deploy:

```bash
aws cloudformation describe-stacks --stack-name lambda-perf-lab \
  --query 'Stacks[0].Outputs' --output table
```

---

## 2. AWS Lambda Power Tuning (Step Functions State Machine)

Deploy the open-source [`alexcasalboni/aws-lambda-power-tuning`](https://github.com/alexcasalboni/aws-lambda-power-tuning)
state machine from the Serverless Application Repository into the **same
region** as this stack, via AWS CLI (no console click-through required):

```bash
aws serverlessrepo create-cloud-formation-change-set \
  --application-id arn:aws:serverlessrepo:us-east-1:451282441545:applications/aws-lambda-power-tuning \
  --stack-name lambda-power-tuning \
  --capabilities CAPABILITY_IAM CAPABILITY_RESOURCE_POLICY \
  --parameter-overrides Name=lambdaMemoryValues,Value="128,256,512,1024,1536,2048,3008" \
  --semantic-version 4.3.3

# Retrieve the ChangeSetId from the previous command's output, then:
aws cloudformation execute-change-set --change-set-name <ChangeSetId>
```

Run a tuning execution against the deployed target function:

```bash
aws stepfunctions start-execution \
  --state-machine-arn <PowerTuningStateMachineArn-from-stack-outputs> \
  --input '{
      "lambdaARN": "<TargetFunctionArn-from-lambda-perf-lab-outputs>",
      "powerValues": [128, 256, 512, 1024, 1536, 2048, 3008],
      "num": 25,
      "payload": {"scenario": "power-tuning"},
      "parallelInvocation": true,
      "strategy": "balanced"
  }'
```

The execution returns a presigned S3 URL to an interactive HTML report
(via the [Lambda Power Tuning visualization tool](https://lambda-power-tuning.show/))
plotting cost vs. duration across every memory tier — use this to select
the production `LambdaMemorySize` value, then redeploy `template.yaml`
with that value via `--parameter-overrides LambdaMemorySize=<chosen>`.

---

## 3. Running the Simulation Scripts

Both scripts require `boto3` and credentials with `lambda:InvokeFunction`
(Script A additionally needs `lambda:UpdateFunctionConfiguration` and
`lambda:GetFunctionConfiguration` to sweep memory tiers).

```bash
pip install boto3
```

### Script A — Performance Testing (memory sweep)

```bash
python3 scripts/performance_test.py \
  --function-name lambda-perf-lab-target-function \
  --memory-configs 128 1024 \
  --invocations-per-config 10 \
  --region us-east-1
```

This reconfigures the function's `MemorySize` between tiers, waits for the
update to become `Active`/`Successful`, then runs sequential invocations
(well under the reserved concurrency limit, so nothing throttles) and
prints a min/max/mean/p50/stdev summary per tier.

### Script B — Load / Pressure Testing (forced throttling)

```bash
python3 scripts/load_test.py \
  --function-name lambda-perf-lab-target-function \
  --concurrent-requests 50 \
  --reserved-concurrency 10 \
  --region us-east-1
```

This fires 50 invocations released simultaneously via a thread `Barrier`
against a function reserved to 10 concurrent executions, forcing
`TooManyRequestsException` (HTTP 429) for the excess ~40 requests.

---

## 4. Verification Playbook

### Step 1 — Confirm baseline state
1. CloudFormation Console → Stacks → `lambda-perf-lab` → **Outputs** tab.
   Note `TargetFunctionName`, `DashboardURL`, `ThrottleAlarmName`.
2. CloudWatch Console → **Alarms** → confirm `lambda-perf-lab-throttle-alarm`
   and `lambda-perf-lab-concurrency-saturation-alarm` are both in `OK` state.

### Step 2 — Run Script A and inspect X-Ray timing
1. Run `performance_test.py` as shown above.
2. AWS X-Ray Console → **Traces** → filter:
   `service("lambda-perf-lab-target-function")` and time range "Last 30
   minutes".
3. Open a trace from the 128MB batch and one from the 1024MB batch. Expand
   the `cpu_bound_hash_workload` subsegment in each — the 128MB trace's
   subsegment will show measurably higher duration, since Lambda allocates
   vCPU proportionally to MemorySize.
4. CloudWatch Console → **Dashboards** → open the `DashboardURL` output.
   The **Duration (p50/p90/p99)** widget should show a visible step-down
   in p99 duration after the script transitions from invoking at 128MB to
   invoking at 1024MB.

### Step 3 — Run Script B and watch the Throttle alarm fire
1. Run `load_test.py` as shown above. Confirm the script's own summary
   reports `throttled` count > 0 (typically ~40 of 50 requests, since
   reserved concurrency is 10).
2. CloudWatch Console → **Alarms** → `lambda-perf-lab-throttle-alarm`.
   Within ~1–2 minutes of the burst, the alarm transitions `OK → ALARM`
   (1-minute evaluation period, `Throttles Sum > 0`). If you configured
   `AlarmNotificationEmail`, you will also receive an SNS email.
3. CloudWatch Console → **Alarms** → `lambda-perf-lab-concurrency-saturation-alarm`.
   Confirm it also enters `ALARM`, since `ConcurrentExecutions` will peak at
   the full reserved limit (10), exceeding the configured 80% threshold (8).
4. CloudWatch Console → **Dashboards** → `DashboardURL`. The **Throttles**
   widget shows a non-zero spike aligned with the burst; the
   **ConcurrentExecutions vs Reserved Limit** widget shows the metric
   plateau exactly at the `Reserved Concurrency Limit` annotation line —
   it will never exceed it, by definition of reserved concurrency.

### Step 4 — Prove throttled requests never appear in X-Ray
This is the key architectural insight the lab is designed to demonstrate:
**AWS Lambda rejects throttled invocations at the service control plane,
before your function code — and therefore the X-Ray SDK inside it — ever
executes.** A `TooManyRequestsException` is generated by the Lambda
service itself, not by your handler.

1. Note the exact start/end timestamps of the Script B burst run from your
   terminal output.
2. AWS X-Ray Console → **Traces** → set the time range to that exact
   window.
3. Count the traces returned. This count will equal the `success` count
   printed in Script B's summary (e.g. 10) — **not** the 50 total requests
   fired, and **not** the `throttled` count (e.g. 40).
4. AWS X-Ray Console → **Service Map**, same time window. The
   `lambda-perf-lab-target-function` node's request count badge will match
   the same successful-only number. There is no node, edge, error badge,
   or fault indicator anywhere on the Service Map representing the
   throttled requests, because X-Ray has no visibility into invocations
   that never reached the Lambda execution environment.
5. Cross-check via CloudWatch Logs Insights against the function's log
   group (`/aws/lambda/lambda-perf-lab-target-function`):
   ```
   fields @timestamp, @message
   | filter @message like /invocation_complete/
   | stats count() by bin(1m)
   ```
   The per-minute count will match the X-Ray trace count and the Script B
   `success` count — confirming throttled requests left no trace, log
   entry, or X-Ray segment of any kind, only the `Throttles` CloudWatch
   metric (emitted by the Lambda service control plane, not the function).

### Step 5 — Reset between test runs
Throttle and concurrency-saturation alarms self-clear (`OK Actions` are
configured) once `Throttles` returns to 0 and `ConcurrentExecutions` drops
back under threshold for a full evaluation period — no manual alarm reset
is required between Script A and Script B runs.
