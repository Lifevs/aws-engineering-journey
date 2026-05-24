# ☁️ AWS Engineering Journey

> Building production-grade cloud systems, distributed architectures, AI-powered applications, and real-world AWS engineering projects — one system at a time.

---

# 🚀 About This Repository

This repository is my long-term cloud engineering lab focused on:

- AWS Certifications
- Real-world architecture implementation
- Distributed systems
- Serverless engineering
- Event-driven systems
- Performance engineering
- DevOps & CloudOps
- AI/ML & Generative AI
- Reliability engineering
- Scalability benchmarking
- Production-grade system design

Instead of only studying theory, every AWS skill is mapped to hands-on projects, experiments, architecture breakdowns, and benchmarking exercises.

---

# 🎯 Current Goals

- ✅ AWS Certified Cloud Practitioner
- 🚧 AWS Developer Associate (DVA-C02)
- 🚧 AWS Solutions Architect Associate (SAA-C03)
- 🚧 AWS SysOps Administrator Associate (SOA-C03)
- 🔜 AWS Machine Learning Associate
- 🔜 AWS Generative AI Engineer Professional
- 🎯 AWS Golden Jacket Journey
- 🎯 Build production-grade cloud engineering portfolio
- 🎯 Remote Cloud/DevOps/Platform Engineering opportunities

---

# 🧠 Core Engineering Areas

## ☁️ Cloud & Serverless
- AWS Lambda
- API Gateway
- Step Functions
- EventBridge
- SQS/SNS
- DynamoDB
- S3

## 🏗️ Architecture & System Design
- Event-driven systems
- Microservices
- High availability
- Fault tolerance
- Disaster recovery
- Scalability patterns
- Multi-region architectures

## ⚙️ DevOps & CloudOps
- CI/CD
- Infrastructure as Code
- Monitoring
- Observability
- Auto-remediation
- Load testing
- Cost optimization

## 🤖 AI / ML / Generative AI
- Bedrock
- SageMaker
- RAG pipelines
- AI agents
- Vector databases
- AI event-driven workflows

---

# 📂 Repository Structure

Below is the directory structure representing the active, implemented, and planned projects within this cloud engineering lab:

```bash
aws-engineering-journey/
├── README.md                          # Repository Index & Learning Goals
│
├── projects/                          # Production-grade Case Studies
│   ├── sync-vs-async-upload/          # Sync vs Decoupled SQS File Ingestion (Completed)
│   │   ├── README.md                  # Deployment & setup guide
│   │   ├── lambda/                    # AWS Lambda source code
│   │   │   ├── sync_lambda.py         # Sync parser Lambda
│   │   │   └── async_lambda.py        # SQS async consumer Lambda
│   │   ├── cloudformation/            # SAM Infrastructure-as-Code templates
│   │   │   └── template.yaml          # S3, SQS, Lambdas & API Gateway Direct integration
│   │   ├── load-testing/              # Stress-test benchmarks
│   │   │   ├── locustfile.py          # Combined Locust weight script
│   │   │   └── sample_test.jpg        # Standard test image
│   │   ├── frontend/                  # Unified Uploader Web Client
│   │   │   └── upload.html            # Premium glassmorphism client
│   │   └── docs/                      # Scientific documentation
│   │       ├── scaling-notes.md       # Ingestion boundaries research
│   │       └── cost-analysis.md       # Cost optimization comparison models
│   │
│   └── api-gateway-transformations/   # Edge request/response VTL mapping templates (Planned)
│
└── reusable/                          # Common Cloud Infrastructures
    ├── cloudformation/                # Standard VPC, IAM & KMS Skeletons (Planned)
    └── scripts/                       # Deployment pipelines and helper scripts (Planned)
```
