# AWS Ingestion Performance: Scaling Notes

When designing serverless file ingestion architectures, engineers must choose between synchronous (direct proxy execution) and asynchronous (event-driven decoupled queues) pipelines based on payload sizes, execution latencies, and scaling profiles.

---

## 1. Physical Service Thresholds & Payload Limits

| AWS Service | Hard Payload Limit | Ingestion Profile | Key Constraints |
| :--- | :--- | :--- | :--- |
| **API Gateway (REST/HTTP)** | **10 MB** | Direct synchronous byte stream | Larger payloads yield HTTP 413 (Payload Too Large) and cannot be modified. |
| **AWS Lambda** | **6 MB** (Sync) / **256 KB** (Async) | Runtime memory execution buffer | Synchronous API integrations fail if the request body exceeds 6MB. |
| **Amazon SQS** | **256 KB** | Decoupled queue buffer | Exceeding 256KB requires caching data in S3 and passing references. |
| **Amazon S3** | **5 GB** (Single PUT) / **5 TB** (Multipart) | Direct object storage | Bypasses intermediate compute limits entirely. |

---

## 2. Ingestion Patterns & Trade-Offs

### Pattern A: Synchronous Upload (Direct Proxy)
`Client ──[Multipart]──> API Gateway ──[Base64 Proxy]──> Lambda ──[boto3 PUT]──> Amazon S3`

* **Latency Bottleneck**: The client connection remains open and blocked for the combined duration of:
  $$\text{Latency} = \text{Client Network Transfer} + \text{Lambda Cold Start/Compute} + \text{boto3 S3 PUT API write}$$
* **Concurrency Spikes**: Sudden traffic bursts map 1-to-1 to Lambda execution instances. If the account exceeds the regional concurrent execution limit (typically 1,000 by default), API Gateway will return HTTP 429 Throttle responses.
* **Payload Penalty**: Limited to a maximum of **6MB** due to Lambda's integration payload cap. Base64 encoding adds $\approx 33\%$ memory overhead, narrowing the operational limit to $\approx 4.5\text{MB}$ in practice.

---

### Pattern B: Asynchronous Upload (SQS Buffer)
`Client ──[JSON Base64]──> API Gateway ──[Direct Integration]──> Amazon SQS ──[Trigger]──> Lambda ──> Amazon S3`

* **Instant Absorption**: API Gateway communicates directly with Amazon SQS using an AWS Service Integration. No compute layer (Lambda) runs during the ingestion phase. The transaction terminates in $\approx 20\text{-}50\text{ms}$.
* **Load Leveling (Throttling Protection)**: High traffic spikes are absorbed by the SQS queue and stored securely. Downstream Lambda decoders pull messages in batches (default: 10). If downstream throttling occurs, messages stay in SQS without failing.
* **Decoupling Advantages**:
  * Decouples client network latency from back-end write latency.
  * Allows rate-limiting the backend processing by configuring SQS `ReservedConcurrency` on the downstream Lambda.
* **Size Constraint**: The payload is limited to **256KB** due to SQS body thresholds. In this model, base64 conversion is necessary, meaning this is ideal for small files (receipts, avatars, metadata).

---

## 3. High-Scale Best Practice: Direct S3 Pre-signed URLs

For standard production architectures handling files larger than 150KB-200KB, **both** of the above patterns become inefficient. The gold standard is:

`Client ──[Request URL]──> API Gateway ──> Lambda (Generator) ──[Pre-signed URL]──> Client ──[Direct PUT]──> Amazon S3`

1. **Get Pre-signed URL**: Client requests a temporary upload URL from a lightweight Lambda ($\approx 10\text{ms}$ duration).
2. **Direct PUT**: Client uploads the binary file directly to S3 via HTTP PUT using the pre-signed URL.
3. **Downstream Event Processing**: S3 triggers a downstream Lambda asynchronously via S3 Event Notifications (or SQS) to process the object *after* it lands safely.

*Benefits*: Fully bypasses API Gateway and Lambda payload limits (up to 5GB per single upload), eliminates middle-tier compute costs for data transfers, and offers maximum throughput.
