# Case Study: Stateful Sessions vs. Stateless JWT Auth

This case study benchmarks and demonstrates **Stateless JWT Authorization** at scale using **Amazon Cognito**, **AWS Lambda**, and **Amazon API Gateway**, comparing it against traditional **Stateful Session** models.

It includes automated scripts to inject testing records into your live Cognito database and trigger concurrent multi-threaded integration bursts to stress-test your protected REST endpoints.

---

## 📂 Project Structure

```
stateful-vs-stateless-auth/
├── README.md                          # Case Study Blueprint
│
├── scripts/                           # Automated Testing Scripts
│   ├── cognito_user_injection.py      # Populates Cognito User Pool with active test accounts
│   └── integration_burst_test.py      # Authenticates and launches concurrent multi-threaded bursts
│
└── docs/
    └── architecture-notes.md          # Architectural scaling comparison (Stateful vs Stateless)
```

---

## ⚙️ Architecture Context

In modern cloud applications, managing user authorization at high scale requires a highly scalable validation tier.

### 1. Traditional Stateful Sessions
* **Flow**: Client requests resource $\rightarrow$ API Gateway queries session store (DynamoDB/ElastiCache) $\rightarrow$ validates session state $\rightarrow$ returns resource.
* **Bottleneck**: Every single incoming request triggers synchronous read operations on the session database. At high scale (e.g., 50k requests/sec), this results in severe I/O bottlenecks, high caching costs, and state synchronization replication delays across multiple regions.

### 2. Stateless JWT Authorization (Cognito)
* **Flow**: Client authenticates once with Cognito $\rightarrow$ receives a cryptographically signed **JSON Web Token (JWT)** $\rightarrow$ sends JWT in the `Authorization` header for subsequent requests $\rightarrow$ API Gateway / Lambda validates the cryptographic signature offline using Cognito's JSON Web Key Set (JWKS).
* **Benefit**: **Zero database reads** are required for token verification! The signature validation happens in memory within milliseconds, allowing the authorization tier to scale infinitely and linearly.

---

## 🚀 Deployed Test Specifications

The testing scripts interact with your active, live AWS resources:
* **Cognito User Pool ID**: `ap-south-1_qvnUB074o` (Mumbai Region)
* **App Client ID**: `4e21q49g49249qj6g0n13mbkcg`
* **Protected API URL**: `https://7hdqzn4qwh.execute-api.ap-south-1.amazonaws.com/dev/login/data`

---

## 🛠️ Step-by-Step Execution Guide

### 1. Install Dependencies
Ensure you have the AWS SDK for Python (`boto3`) installed:
```bash
pip install boto3
```

### 2. Phase 1: User Database Injection
Populate your active Cognito User Pool with 50 confirmed testing users. The script uses AWS Admin APIs to bypass standard email verification and set permanent passwords:
```bash
python scripts/cognito_user_injection.py
```
* **Bypassing Cognito Hurdles**: The script sets `MessageAction='SUPPRESS'` to prevent AWS from spamming 50 verification emails, and sets passwords as permanent to bypass the "Force Change Password" flow which typically breaks automated API test scripts.

### 3. Phase 2: Concurrent Integration Burst Test
Authenticate all 50 injected users, gather their active JSON Web Tokens (JWTs), and fire concurrent multi-threaded requests directly at your API Gateway protected endpoint to audit integration scalability:
```bash
python scripts/integration_burst_test.py
```
* **Multi-threaded Ingestion**: The script uses a Python `ThreadPoolExecutor` matching `max_workers=50` to hit the API Gateway routes *simultaneously*, replicating a real-world high-concurrency traffic spike.
* **Success Output**: If the signature checks are verified successfully by API Gateway, the screen will output green status indications showing decoded payloads.
