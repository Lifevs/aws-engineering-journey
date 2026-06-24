# Architectural Notes: Stateful Sessions vs. Stateless JWT Auth

When designing authorization tiers for large-scale microservice architectures on AWS, the method used to validate user identity heavily impacts system latency, cross-region replication, database overhead, and financial footprints.

This document details the trade-offs between **Stateful Session Stores** and **Stateless JWT Authorization** inside API Gateway and Lambda environments.

---

## 1. Stateful Sessions

Traditional web architectures rely on stateful sessions where user state is stored centrally in a database.

```
Client ──[Session ID]──> API Gateway ──> Lambda ──> Cache (Redis/DynamoDB)
                                                        │
                                                        └── (Database Query)
```

### Flow
1. The client sends a unique `Session ID` (typically a random cookie string) on every request.
2. The web application or API Gateway interceptor makes a synchronous query to a fast memory cache (such as **Amazon ElastiCache for Redis**) or database (**Amazon DynamoDB**) to fetch the user session record.
3. Once the record is found and verified, the request proceeds to downstream services.

### Core Disadvantages
* **Database I/O Overhead**: Every API request triggers a database query. A system processing $50,000$ requests/sec requires a highly provisioned database cluster, leading to significant compute and licensing costs.
* **Scaling Bottlenecks**: As database connections increase, session stores become a single point of failure (SPOF).
* **Multi-Region Sync Latency**: If the application runs across multiple AWS regions (e.g. `ap-south-1` and `us-east-1`), session state must be continuously replicated globally with ultra-low latency, causing race conditions where users authenticate in one region but are rejected in another.

---

## 2. Stateless JSON Web Tokens (JWT)

Modern distributed architectures utilize stateless JWTs (like those issued by **Amazon Cognito**) to delegate authorization checks entirely to the edge.

```
Client ──[JWT Token]──> API Gateway ──> Downstream Microservices
                            │
              (Cryptographic Local Check)
```

### Flow
1. The client authenticates once with the Identity Provider (Cognito) and receives a cryptographically signed JWT.
2. For all subsequent requests, the client attaches the token in the `Authorization: Bearer <Token>` header.
3. API Gateway or a Lambda Authorizer intercepts the request, retrieves the token, and performs a local cryptographic signature validation using Cognito's **JSON Web Key Set (JWKS)**.
4. If the signature matches and parameters (expiry, audience, issuer) are valid, the request is authorized.

### Cryptographic Underpinnings
Cognito JWT signatures utilize public/private key cryptography (specifically RSA with SHA-256):
* **Private Key**: Kept secure within Amazon Cognito to sign tokens during authentication.
* **Public Key (JWKS)**: Exposed publicly at standard endpoints (e.g., `https://cognito-idp.ap-south-1.amazonaws.com/<user-pool-id>/.well-known/jwks.json`). Downstream decoders download these keys once, cache them, and use them locally to decrypt and verify the cryptographic signature on every incoming token.

### Core Advantages
* **Infinite Linear Scaling**: Because signature validation occurs locally in memory without any database queries, there is zero database I/O. The authorization tier scales 1-to-1 with CPU compute at no extra storage cost.
* **Millisecond Latencies**: Decrypting and validating a signature locally takes less than $1\text{ ms}$.
* **Zero Global Synchronization Needs**: Since the verification keys (JWKS) are public and standard, tokens issued in Mumbai (`ap-south-1`) can be immediately and securely validated in Virginia (`us-east-1`) offline, without any database synchronization.

---

## 3. High-Scale Best Practice Summary

| Feature | Stateful Sessions (Redis/DynamoDB) | Stateless JWT Auth (Cognito) |
| :--- | :--- | :--- |
| **Verification Overhead** | High (Requires DB/Cache connection) | Extremely Low (Local in-memory decrypt) |
| **Database Scalability** | Bound by DB connection limits & I/O | Infinitely scalable |
| **Replication Latency** | High (Requires global synchronization) | Zero (Public key signatures are static) |
| **Instant Revocation** | Simple (Delete record from Redis/DB) | Requires token blacklisting or short TTLs |

*Decoupling Recommendation*: For high-performance enterprise architectures, **Stateless JWTs** are the standard. To mitigate the challenge of instant token revocation, configure a short token lifespan (**Time-To-Live (TTL)** of 5–15 minutes) and implement lightweight token rotation schemes.
