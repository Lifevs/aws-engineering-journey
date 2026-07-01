import hashlib
import json
import logging
import os
import random
import time
import uuid

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

HASH_ITERATIONS = int(os.environ.get("HASH_ITERATIONS", "200000"))
DOWNSTREAM_LATENCY_MIN_MS = int(os.environ.get("DOWNSTREAM_LATENCY_MIN_MS", "50"))
DOWNSTREAM_LATENCY_MAX_MS = int(os.environ.get("DOWNSTREAM_LATENCY_MAX_MS", "250"))


def _run_cpu_bound_workload(payload_size_bytes: int = 4096) -> str:
    with xray_recorder.in_subsegment("cpu_bound_hash_workload") as subsegment:
        random_payload = os.urandom(payload_size_bytes)
        salt = uuid.uuid4().bytes
        start = time.perf_counter()
        derived_key = hashlib.pbkdf2_hmac(
            "sha256", random_payload, salt, HASH_ITERATIONS
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        subsegment.put_metadata("hash_iterations", HASH_ITERATIONS)
        subsegment.put_metadata("elapsed_ms", round(elapsed_ms, 2))
        subsegment.put_annotation("phase", "cpu_bound")
        logger.info(json.dumps({
            "event": "cpu_workload_complete",
            "elapsed_ms": round(elapsed_ms, 2),
            "iterations": HASH_ITERATIONS
        }))
        return derived_key.hex()


def _call_downstream_dependency() -> dict:
    with xray_recorder.in_subsegment("downstream_dependency") as subsegment:
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
        logger.info(json.dumps({"event": "downstream_complete", **response}))
        return response


def lambda_handler(event: dict, context) -> dict:
    invocation_start = time.perf_counter()

    derived_key_hex = _run_cpu_bound_workload()
    downstream_result = _call_downstream_dependency()

    total_elapsed_ms = (time.perf_counter() - invocation_start) * 1000

    response_body = {
        "request_id": context.aws_request_id,
        "memory_limit_mb": context.memory_limit_in_mb,
        "total_elapsed_ms": round(total_elapsed_ms, 2),
        "remaining_time_ms_at_completion": context.get_remaining_time_in_millis(),
        "downstream_result": downstream_result,
        "derived_key_fingerprint": derived_key_hex[:16],
    }

    logger.info(json.dumps({"event": "invocation_complete", **response_body}))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response_body),
    }
