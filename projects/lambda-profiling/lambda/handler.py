"""
Target Lambda function for the performance tuning ecosystem.

Simulates two realistic production characteristics so that AWS X-Ray traces
and CloudWatch metrics show a non-trivial, memory-sensitive performance
profile:

  1. CPU-bound work: a configurable number of PBKDF2-HMAC-SHA256 iterations
     (a real cryptographic primitive, not a synthetic busy-loop), whose wall
     time scales inversely with allocated memory because Lambda grants vCPU
     proportionally to MemorySize.
  2. Downstream I/O: a mocked dependency call wrapped in its own X-Ray
     subsegment, with randomized latency to emulate network/database jitter.

Both phases are wrapped in explicit X-Ray subsegments so the Service Graph
and trace timeline clearly separate compute time from I/O wait time.
"""

import hashlib
import json
import logging
import os
import random
import time
import uuid

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

# Patch supported libraries (requests, botocore, etc.) for automatic
# downstream X-Ray subsegments.
patch_all()

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

HASH_ITERATIONS = int(os.environ.get("HASH_ITERATIONS", "200000"))
DOWNSTREAM_LATENCY_MIN_MS = int(os.environ.get("DOWNSTREAM_LATENCY_MIN_MS", "50"))
DOWNSTREAM_LATENCY_MAX_MS = int(os.environ.get("DOWNSTREAM_LATENCY_MAX_MS", "250"))


def _run_cpu_bound_workload(payload_size_bytes: int = 4096) -> str:
    """
    CPU-bound phase: derive a key via PBKDF2-HMAC-SHA256.

    This is representative of real production CPU work (token signing,
    password hashing, payload checksums) and is sensitive to vCPU
    allocation, which AWS ties directly to MemorySize. Lower memory
    configurations will show measurably higher Duration for this phase.
    """
    subsegment = xray_recorder.begin_subsegment("cpu_bound_hash_workload")
    try:
        random_payload = os.urandom(payload_size_bytes)
        salt = uuid.uuid4().bytes
        start = time.perf_counter()
        derived_key = hashlib.pbkdf2_hmac(
            "sha256", random_payload, salt, HASH_ITERATIONS
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        subsegment.put_metadata("hash_iterations", HASH_ITERATIONS)
        subsegment.put_metadata("elapsed_ms", round(elapsed_ms, 2))
        logger.info(
            "cpu_bound_workload_complete",
            extra={"elapsed_ms": round(elapsed_ms, 2), "iterations": HASH_ITERATIONS},
        )
        return derived_key.hex()
    finally:
        xray_recorder.end_subsegment()


def _call_downstream_dependency() -> dict:
    """
    Downstream I/O phase: mocks a call to an external service or database.

    Wrapped in its own subsegment ('downstream_dependency') so the X-Ray
    Service Graph renders it as a distinct downstream node, separate from
    the function's own compute time. Latency is randomized within a
    configurable band to emulate realistic network jitter.
    """
    subsegment = xray_recorder.begin_subsegment("downstream_dependency")
    try:
        simulated_latency_ms = random.randint(
            DOWNSTREAM_LATENCY_MIN_MS, DOWNSTREAM_LATENCY_MAX_MS
        )
        subsegment.put_annotation("dependency_name", "mock-payment-gateway")
        subsegment.put_metadata("simulated_latency_ms", simulated_latency_ms)
        time.sleep(simulated_latency_ms / 1000)
        response = {
            "dependency": "mock-payment-gateway",
            "status": "OK",
            "latency_ms": simulated_latency_ms,
        }
        logger.info("downstream_dependency_complete", extra=response)
        return response
    finally:
        xray_recorder.end_subsegment()


def lambda_handler(event: dict, context) -> dict:
    """
    Entry point. Orchestrates the CPU-bound and downstream I/O phases and
    returns timing + metadata useful for the Performance Testing simulation
    script (Script A) to compare across MemorySize configurations.
    """
    invocation_start = time.perf_counter()

    xray_recorder.put_annotation("function_version", context.function_version)
    xray_recorder.put_annotation(
        "memory_limit_mb", context.memory_limit_in_mb
    )
    xray_recorder.put_annotation(
        "request_id", context.aws_request_id
    )

    derived_key_hex = _run_cpu_bound_workload()
    downstream_result = _call_downstream_dependency()

    total_elapsed_ms = (time.perf_counter() - invocation_start) * 1000
    remaining_ms = context.get_remaining_time_in_millis()

    response_body = {
        "request_id": context.aws_request_id,
        "memory_limit_mb": context.memory_limit_in_mb,
        "total_elapsed_ms": round(total_elapsed_ms, 2),
        "remaining_time_ms_at_completion": remaining_ms,
        "downstream_result": downstream_result,
        "derived_key_fingerprint": derived_key_hex[:16],
    }

    logger.info("invocation_complete", extra=response_body)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response_body),
    }
