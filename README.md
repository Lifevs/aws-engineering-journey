# ☁️ AWS Engineering Journey

> Building production-grade cloud systems, distributed architectures, AI-powered applications, and real-world AWS engineering projects — one system at a time.

---

# 🚀 Featured Projects

Detailed implementation of core cloud engineering patterns.

### 🛒 [Multi-Store CRUD Catalog](./projects/multi-store-crud-catalog)
**Polyglot Persistence in Action.** A central Lambda router managing data across S3 (images), DynamoDB (NoSQL metadata), and Aurora RDS (relational search). Includes diagrams-as-code and a frontend test harness.

### 🔗 [Tight vs. Loose Coupling](./projects/coupling)
**Performance Comparison.** Benchmarking synchronous direct Lambda calls vs. asynchronous SQS-buffered patterns using Locust. Proves resilience and throughput gains in event-driven designs.

### 🛡️ [Fault Tolerance & Resilience](./projects/fault-tolerance)
**Reliability Engineering.** Implements Circuit Breakers using SSM Parameter Store and Idempotency patterns with DynamoDB to ensure robust message processing from SQS.

### 🔐 [Stateful vs. Stateless Auth](./projects/stateful-vs-stateless-auth)
**Security at Scale.** Benchmarking Amazon Cognito's stateless JWT authorization against traditional session models. Includes multi-threaded burst testing scripts.

### 📤 [Sync vs. Async File Ingestion](./projects/sync-vs-async-upload)
**Optimization Case Study.** Comparing direct API Gateway uploads to SQS-buffered asynchronous processing. Features a premium glassmorphic dashboard and deep cost-analysis research.

---

# 🎯 Current Goals

- ✅ AWS Certified Cloud Practitioner
- 🚧 AWS Developer Associate (DVA-C02)
- 🚧 AWS Solutions Architect Associate (SAA-C03)
- 🚧 AWS SysOps Administrator Associate (SOA-C03)
- 🎯 AWS Golden Jacket Journey
- 🎯 Build production-grade cloud engineering portfolio

---

# 🧠 Core Engineering Areas

| Area | Technologies |
| :--- | :--- |
| **Cloud & Serverless** | Lambda, API Gateway, Step Functions, EventBridge, SQS/SNS, DynamoDB, S3 |
| **Architecture** | Event-driven systems, Microservices, Fault tolerance, Scalability patterns |
| **DevOps & CloudOps** | CI/CD, IaC (CloudFormation/SAM), Monitoring, Load testing (Locust) |
| **AI / ML / GenAI** | Bedrock, SageMaker, RAG pipelines, AI agents |

---

# 📂 Repository Structure

```bash
aws-engineering-journey/
├── projects/
│   ├── multi-store-crud-catalog/    # Polyglot Persistence Store
│   ├── coupling/                    # Tight vs Loose Comparison
│   ├── fault-tolerance/             # Circuit Breaker & Idempotency
│   ├── stateful-vs-stateless-auth/  # Cognito JWT vs Session Auth
│   ├── sync-vs-async-upload/        # SQS Buffered File Ingestion
│   └── api-gateway-transformations/ # VTL Mapping Templates (Planned)
└── reusable/                        # Common IAM & VPC skeletons
```
