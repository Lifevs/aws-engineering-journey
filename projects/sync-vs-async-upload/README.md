# Case Study: Sync vs SQS-Buffered Async Ingestion

This project compares two fundamental architectural patterns for serverless file ingestion: **Synchronous (Blocking)** and **Asynchronous (Decoupled SQS Buffer)**.

It provides deployable Infrastructure-as-Code (SAM), serverless Lambda functions in Python, a comparative Locust stress-test script, a unified dark-mode uploader dashboard, and architectural research papers on cost and scalability.

---

## 📂 Project Architecture & Contents

```
sync-vs-async-upload/
├── README.md                      # Case Study Blueprint
│
├── lambda/                        # Serverless Execution Logic
│   ├── sync_lambda.py             # Parses multipart payloads synchronously to S3
│   └── async_lambda.py            # Triggered by SQS to decode base64 streams to S3
│
├── cloudformation/
│   └── template.yaml              # Deployable AWS SAM Template
│
├── load-testing/
│   ├── locustfile.py              # Comparative Locust load testing script
│   └── sample_test.jpg            # Standardized load testing image asset
│
├── frontend/
│   └── upload.html                # Premium unified HTML Dashboard (with glassmorphism UI)
│
└── docs/
    ├── scaling-notes.md           # AWS Payload caps, timeouts, and bottleneck notes
    └── cost-analysis.md           # Mathematical cost curves at 100k, 1M, and 10M scales
```

---

## ⚙️ Architecture Pathways

### 1. Synchronous Route (Direct blocking)
* **Path**: `Client ──> API Gateway (POST /sync) ──> Lambda (Sync) ──> Amazon S3`
* **Mechanism**: Direct REST multipart transfer. The client remains blocked while S3 acknowledges the transaction.
* **Limitations**: Bound by Lambda's **6MB** payload limits, API Gateway's **10MB** limits, and intermediate network latency.

### 2. Asynchronous Route (Decoupled direct SQS)
* **Path**: `Client ──> API Gateway (POST /async) ──[Direct SQS Integration]──> Amazon SQS ──> Lambda (Async) ──> Amazon S3`
* **Mechanism**: API Gateway directly streams the client base64 request into Amazon SQS under **30ms**. The client terminates connection instantly. SQS triggers `async_lambda.py` in downstream batches of 10 to write to S3 asynchronously.
* **Limitations**: Bound by SQS **256KB** payload capacity.

---

## 🛠️ Deploying the Infrastructure

This pipeline is built using the **AWS Serverless Application Model (SAM)**. To build and deploy the stack:

1. **Prerequisites**: Ensure you have [AWS CLI](https://aws.amazon.com/cli/) and [AWS SAM CLI](https://docs.aws.amazon.com/serverless-utility/latest/developerguide/install-sam-cli.html) configured locally.
2. **Build the Stack**:
   ```bash
   cd projects/sync-vs-async-upload/cloudformation
   sam build
   ```
3. **Guided Deployment**:
   ```bash
   sam deploy --guided
   ```
   *Provide a stack name (e.g. `sync-vs-async-upload`), confirm the AWS region, and authorize IAM role creation.*

Once deployed, the terminal outputs will display:
* `S3BucketName`: The target S3 upload bucket name.
* `ApiEndpointUrl`: The base HTTP API Gateway Gateway URL.

---

## 🖥️ Running the Ingestion Client Dashboard

A premium unified dashboard is available in `frontend/upload.html`. It uses a dark-mode glassmorphic design and has both uploader pathways integrated.

1. Locate the file: `projects/sync-vs-async-upload/frontend/upload.html`
2. Open `upload.html` in your favorite web browser.
3. Select your desired strategy (Synchronous or Asynchronous).
4. Drag and drop any image or test file.
5. Click **Execute Upload Pipeline** and witness real-time execution times, API logs, and AWS response objects displayed directly on the system terminal console!

*Note: The frontend has the actual, active endpoints already built in for testing.*

---

## 📈 Running the Locust Load Tests

We have consolidated comparative tests inside a single `locustfile.py` script. It will concurrent-fire requests against both endpoints to audit performance metrics.

1. **Install Locust**:
   ```bash
   pip install locust
   ```
2. **Launch Locust UI**:
   Navigate to the load-testing folder and launch the runner:
   ```bash
   cd projects/sync-vs-async-upload/load-testing
   locust -f locustfile.py
   ```
3. **Run the Benchmark**:
   * Open `http://localhost:8089` in your browser.
   * Provide the target `ApiEndpointUrl` returned by your AWS SAM deployment.
   * Enter the number of users and spawn rate to begin stress-testing your serverless endpoints!
