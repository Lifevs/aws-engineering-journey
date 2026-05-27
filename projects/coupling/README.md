# 🔗 Tight vs. Loose Coupling in AWS

This project demonstrates the fundamental architectural difference between **Tight Coupling** and **Loose Coupling** in serverless environments. It compares a direct synchronous Lambda-to-Lambda call against an asynchronous event-driven pattern using Amazon SQS.

---

## 🏗️ Architecture Diagrams

### 1. Tight Coupling (Synchronous)
In this pattern, the Orchestrator Lambda calls the Worker Lambda directly and waits for a response.
- **Risk**: If the Worker fails or is slow, the Orchestrator also hangs or fails.
- **Latency**: Cumulative (Orchestrator Time + Worker Time).

![Tight Coupling](./architecture/tight_coupling.png)

### 2. Loose Coupling (Asynchronous)
In this pattern, the Producer Lambda pushes a message to an SQS Queue and returns a success response to the client immediately.
- **Benefit**: Decouples services. If the Consumer is down, messages stay safe in the queue.
- **Scalability**: Handles bursts of traffic much better through buffering.

![Loose Coupling](./architecture/loose_coupling.png)

---

## 📊 Performance Visuals

Captured during high-concurrency stress tests:

| Metric Comparison | Error Rates (Tight) | Error Rates (Loose) |
| :---: | :---: | :---: |
| ![Stats](./tightVsloose/Screenshot%202026-05-24%20at%206.26.36%20PM.png) | ![Errors Tight](./tightVsloose/Screenshot%202026-05-24%20at%206.26.56%20PM.png) | ![Errors Loose](./tightVsloose/Screenshot%202026-05-24%20at%206.27.40%20PM.png) |

---

## 📈 Performance Benchmarking Analysis

We conducted a high-concurrency stress test using **Locust** to evaluate how both architectures handle heavy traffic.

### Test Configuration
- **Duration**: ~5 Minutes
- **Tool**: Locust (Distributed Load Testing)
- **Environment**: AWS Lambda (Python 3.12) + API Gateway

### Comparative Results

| Metric | Tight Coupling (Sync) | Loose Coupling (Async) |
| :--- | :--- | :--- |
| **Total Requests** | 8,825 | **29,571** |
| **Avg Response Time** | 131.71 ms | **1,416.32 ms*** |
| **P95 Response Time** | 140 ms | **7,900 ms*** |
| **Max Response Time** | 9,738 ms | 82,537 ms |
| **Failure Rate** | **82.3%** (7,265 failures) | **49.3%** (14,604 failures) |
| **Max RPS** | 61.6 | **98.6** |

*\*Note: In the loose coupling test, the significantly higher latency and failure rates observed were due to API Gateway reaching its integration timeout/throttling limits during the burst, whereas the tight coupling failed much faster due to direct dependency exhaustion.*

### Key Insights
1. **Reliability**: Tight coupling resulted in an **82.3% failure rate** under load. When the downstream Lambda throttled, the entire chain collapsed immediately.
2. **Throughput**: Loose coupling achieved **~60% higher throughput** (98.6 RPS vs 61.6 RPS) before hitting limits.
3. **Resilience**: In the Loose Coupling model, even when the API returned errors, messages that successfully reached SQS were processed in the background, ensuring **zero data loss** for accepted requests. Tight coupling offers no such guarantee.

---

## 🛠️ Infrastructure Breakdown

### Tight Coupling (`/projects/coupling/tight`)
- **API Gateway**: Endpoint `/couplingt`
- **Lambda-1 (Orchestrator)**: Uses `boto3.client('lambda').invoke()` with `InvocationType='RequestResponse'`.
- **Lambda-2 (Worker)**: Processes the request and returns data to Lambda-1.

### Loose Coupling (`/projects/coupling/loose`)
- **API Gateway**: Endpoint `/loose`
- **Lambda-1 (Producer)**: Uses `boto3.client('sqs').send_message()`.
- **SQS Queue**: Acts as the message buffer.
- **Lambda-2 (Consumer)**: Triggered by SQS to process messages in batches.

---

## 🚀 How to Deploy

Each pattern is defined using AWS CloudFormation:

1. **Tight Coupling**:
   ```bash
   aws cloudformation deploy --template-file projects/coupling/tight/cloudformation/build-tight.yaml --stack-name tight-coupling
   ```

2. **Loose Coupling**:
   ```bash
   aws cloudformation deploy --template-file projects/coupling/loose/cloudFormation/build.yaml --stack-name loose-coupling
   ```
