# AWS Engineering Journey

Welcome to the **AWS Engineering Journey** repository. This repository serves as a highly organized personal engineering catalog containing production-ready serverless architectures, infrastructural templates, load-testing benchmarks, and cost analysis case studies on Amazon Web Services.

The primary objective is to document advanced architectural solutions, comparative design performance, and deployment blueprints for microservices.

---

## 📂 Repository Structure

```
aws-engineering-journey/
├── README.md                          # Root Catalog & Repository Index
│
├── projects/                          # Case Study Implementations
│   └── sync-vs-async-upload/          # Synchronous vs SQS Decoupled File Ingestion
│       ├── lambda/                    # AWS Lambda Codebases
│       ├── cloudformation/            # Infrastructure-as-Code (SAM) templates
│       ├── load-testing/              # Comparative Locust Stress-Test scripts
│       ├── frontend/                  # Unified Performance Uploader Dashboard
│       └── docs/                      # Scaling & Cost mathematical models
│
└── reusable/                          # Common Infrastructure Blueprints
    ├── cloudformation/                # Standard VPC, IAM & KMS Skeletons (Planned)
    └── scripts/                       # Deployment pipelines and helper scripts (Planned)
```

---

## 🚀 Active Case Studies

### 1. [Sync vs. Async Ingestion Performance](file:///Users/emperor/Documents/aws-engineering-journey/projects/sync-vs-async-upload/README.md)
* **Goal**: Benchmark structural differences between standard synchronous direct Lambda uploads and asynchronous, non-blocking SQS ingestion.
* **Key Components**: S3 storage buckets, API Gateway direct service integrations, Amazon SQS buffering queues, concurrent Python Lambda batch processors, a stunning glassmorphism uploader client, and Locust load testing profiles.
* **Case Study Status**: **Completed & Fully Documented**.

---

## 🛠️ Future Case Studies (Planned)

These projects will be initialized and populated as they are built:

* **Lambda Error Handling & Resiliency**: Dead Letter Queues (DLQ), Lambda Destinations, and Step Functions error retries/fallbacks.
* **DynamoDB Hot Partitioning Mitigations**: Architectural strategies to resolve read/write throughput throttles on active key partitions.
* **API Gateway Transformations**: Edge request/response mapping templates using Apache Velocity Template Language (VTL) to decouple client schemas from internal models.
