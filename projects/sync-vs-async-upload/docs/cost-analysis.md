# Serverless File Ingestion: Cost Analysis Model

This cost analysis compares the financial footprint of Synchronous (Direct Lambda Proxy) and Asynchronous (SQS Direct Integration Buffer) file upload pipelines on AWS at various operating scales.

---

## 1. AWS Service Pricing Structures

The cost calculation is based on current standard AWS prices in the `ap-south-1` (Mumbai) region:

1. **Amazon API Gateway (REST API)**:
   * \$3.50 per million API calls.
   * Plus data transfer out (if applicable).
2. **Amazon SQS**:
   * \$0.40 per million API actions (SendMessage is 1 action; batches of 1-10 messages pulled are 1 action).
3. **AWS Lambda**:
   * \$0.0000166667 per GB-second of execution (x86 architecture).
   * Free tier of 1M requests and 400,000 GB-seconds per month is excluded from this baseline comparison to show absolute cost curves.
   * Ingesting Lambdas are configured with **256 MB Memory** (\$0.0000041667 per second).
4. **Amazon S3**:
   * PUT Request pricing: \$0.005 per 1,000 requests.
   * Storage: \$0.023 per GB/month (not factored in as storage volumes are identical).

---

## 2. Ingestion Profile Assumptions

* **File Size**: 100 KB average.
* **Synchronous Lambda Ingestion Duration**: 850 ms (includes network latency overhead, validation, and S3 PUT write blocking time).
* **Asynchronous Ingestion (API GW -> SQS)**: No Lambda compute is executed at the front edge.
* **Asynchronous Lambda Consumer (SQS -> S3)**: Runs in batches of 10 messages. Average execution duration to process 10 messages, decode, and upload to S3 is 600 ms (effectively 60 ms per file).

---

## 3. Financial Comparison Tables

### Volume Level: 100,000 Uploads / Month

| Service Component | Synchronous Ingestion | Asynchronous (Decoupled SQS) Ingestion |
| :--- | :--- | :--- |
| **API Gateway** | \$0.35 | \$0.35 |
| **Amazon SQS** | \$0.00 | \$0.08 *(Queue Writes + Downstream Pulls)* |
| **Lambda Ingest Compute** | \$0.35 *(100k requests $\times$ 0.85s $\times$ \$0.00000417)* | \$0.00 |
| **Lambda Processing** | \$0.00 | \$0.03 *(10k batch executions $\times$ 0.6s $\times$ \$0.00000417)* |
| **S3 PUT Requests** | \$0.50 *(100k $\times$ \$0.005/1k)* | \$0.50 |
| **Total Monthly Cost** | **\$1.20** | **\$0.96** |

---

### Volume Level: 1,000,000 Uploads / Month

| Service Component | Synchronous Ingestion | Asynchronous (Decoupled SQS) Ingestion |
| :--- | :--- | :--- |
| **API Gateway** | \$3.50 | \$3.50 |
| **Amazon SQS** | \$0.00 | \$0.80 |
| **Lambda Ingest Compute** | \$3.54 | \$0.00 |
| **Lambda Processing** | \$0.00 | \$0.25 |
| **S3 PUT Requests** | \$5.00 | \$5.00 |
| **Total Monthly Cost** | **\$12.04** | **\$9.55** |

---

### Volume Level: 10,000,000 (10M) Uploads / Month

| Service Component | Synchronous Ingestion | Asynchronous (Decoupled SQS) Ingestion |
| :--- | :--- | :--- |
| **API Gateway** | \$35.00 | \$35.00 |
| **Amazon SQS** | \$0.00 | \$8.00 |
| **Lambda Ingest Compute** | \$35.42 | \$0.00 |
| **Lambda Processing** | \$0.00 | \$2.50 |
| **S3 PUT Requests** | \$50.00 | \$50.00 |
| **Total Monthly Cost** | **\$120.42** | **\$95.50** |

---

## 4. Key Financial Takeaways

1. **Batch Efficiency Gains**: The decoupled asynchronous model is **$\approx 20\%$ cheaper** even at small scales. This savings is driven by downstream Lambda batching. By processing 10 SQS messages in a single Lambda execution, cold-start and boot-overhead execution times are amortized.
2. **Lambda Billing Idle Reduction**: In the Synchronous pattern, the Lambda function remains active and billed while waiting for S3 to acknowledge the write. In the Decoupled pattern, API Gateway dumps payloads directly into SQS in under 30ms, completely avoiding edge compute charges.
3. **API Gateway Overhead Note**: In both serverless scenarios, API Gateway remains the largest fixed cost component (\$3.50/M). To scale beyond this price block, high-volume systems should bypass API Gateway for data transfers entirely and leverage **S3 Pre-signed URLs** directly, reducing intermediate routing costs to \$0.
