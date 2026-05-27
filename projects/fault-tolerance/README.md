# 🛡️ AWS Fault Tolerance & Resilience Patterns

This project demonstrates essential patterns for building resilient serverless applications on AWS, focusing on **Circuit Breakers**, **Idempotency**, and **Graceful Error Handling**.

---

## 🏗️ Resiliency Patterns

### 1. Circuit Breaker (via SSM)
- Prevents the system from attempting operations that are likely to fail during a downstream service outage.
- Managed via an **AWS SSM Parameter Store** value (`/orders/circuit-breaker-status`).
- If the status is `OPEN`, the Lambda fails fast, saving compute costs and preventing further stress on downstream systems.

### 2. Idempotent Processing (via DynamoDB)
- Ensures that the same message is not processed multiple times, even if SQS delivers it more than once (at-least-once delivery).
- Uses a DynamoDB `IdempotencyTable` with a `ConditionExpression` to track processed `idempotency_key`s.

### 3. Structured Logging
- Unified JSON logging format for enhanced observability in **Amazon CloudWatch**.
- Each processing stage is tagged (e.g., `INIT`, `CB-1`, `SQS-2`, `SUCCESS`) for easy filtering.

---

## 📂 Project Structure

```
fault-tolerance/
├── cloudformation/
│   └── build.yaml          # Infrastructure as Code
├── lambda/
│   └── lambda.py           # Resilient Processing Logic
└── screenshots/            # Implementation & CloudWatch Logs
```

---

## 🚀 Logic Flow

1. **Invoke**: SQS triggers Lambda with a batch of records.
2. **Circuit Check**: Lambda fetches status from SSM. If `OPEN`, it stops.
3. **Idempotency Check**: For each record, check if `idempotency_key` exists in DynamoDB.
4. **Execute**: Save order to `OrdersTable` and call mock downstream API.
5. **Acknowledge**: On success, the record is removed from the SQS queue.

---

## 🛠️ Deployment

1. **CloudFormation**: Deploy `cloudformation/build.yaml` to provision the SQS queue, DynamoDB tables, and SSM parameter.
2. **SSM Configuration**: Set `/orders/circuit-breaker-status` to `CLOSED` to begin processing.
3. **Test**: Push a message to the SQS queue with an `order_id` and `idempotency_key`.
