#!/usr/bin/env python3
"""
Script B — Load / Pressure Testing (concurrency burst, forces throttling)

Fires a burst of concurrent invocations (default: 50) against the target
Lambda function using a thread pool, deliberately exceeding the function's
ReservedConcurrentExecutions limit (default: 10) within the same ~1-second
window. This forces AWS Lambda to return TooManyRequestsException (HTTP 429)
for the excess requests, which:

  * Increments the AWS/Lambda 'Throttles' metric, firing the
    '<project>-throttle-alarm' CloudWatch Alarm within one 60s evaluation
    period.
  * Produces ZERO corresponding X-Ray traces for throttled invocations,
    because Lambda rejects them before the function (and therefore the
    X-Ray SDK inside it) ever executes. This script's output count of
    "throttled" responses should be cross-referenced against X-Ray Trace
    count for the same time window, which will only ever show successful
    invocations.

Usage:
    python3 load_test.py \
        --function-name lambda-perf-lab-target-function \
        --concurrent-requests 50 \
        --reserved-concurrency 10

Requires:
    boto3, AWS credentials with lambda:InvokeFunction permission.
"""

import argparse
import json
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

THROTTLE_ERROR_CODES = {"TooManyRequestsException"}


@dataclass
class BurstResult:
    index: int
    outcome: str  # "success" | "throttled" | "error"
    http_status: int
    detail: str
    elapsed_ms: float


def invoke_for_burst(lambda_client, function_name: str, index: int, start_barrier: threading.Barrier) -> BurstResult:
    """
    Each worker thread waits at a Barrier so all threads release their
    invocation calls within the same instant, maximizing the probability
    that concurrent execution count genuinely exceeds the reserved limit
    rather than trickling in sequentially.
    """
def invoke_for_burst(function_name: str, index: int, start_barrier: threading.Barrier, region: str) -> BurstResult:
    lambda_client = boto3.client("lambda", region_name=region, config=Config(retries={"max_attempts": 0}))
    payload = {"scenario": "load-burst", "index": index}
    start_barrier.wait()
    start = time.perf_counter()
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode("utf-8"),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        function_error = response.get("FunctionError")
        status_code = response.get("StatusCode", 0)

        if function_error:
            body_raw = response["Payload"].read()
            try:
                body = json.loads(body_raw)
                error_type = body.get("errorType", "UnknownFunctionError")
            except json.JSONDecodeError:
                error_type = "UnknownFunctionError"

            if error_type in THROTTLE_ERROR_CODES:
                return BurstResult(index, "throttled", status_code, error_type, round(elapsed_ms, 2))
            return BurstResult(index, "error", status_code, error_type, round(elapsed_ms, 2))

        return BurstResult(index, "success", status_code, "OK", round(elapsed_ms, 2))

    except ClientError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        error_code = exc.response.get("Error", {}).get("Code", "ClientError")
        if error_code in THROTTLE_ERROR_CODES:
            return BurstResult(index, "throttled", 429, error_code, round(elapsed_ms, 2))
        return BurstResult(index, "error", 0, f"{error_code}: {exc}", round(elapsed_ms, 2))


def run_burst(function_name: str, concurrent_requests: int, region: str) -> list:
    boto_config = Config(retries={"max_attempts": 0}, max_pool_connections=concurrent_requests + 10)
    lambda_client = boto3.client("lambda", region_name=region, config=boto_config)

    # +1 for the main thread releasing the barrier alongside workers is not
    # needed since the barrier only counts worker threads.
    start_barrier = threading.Barrier(concurrent_requests)

    results = []
    print(f"-> Launching {concurrent_requests} concurrent invocations against {function_name} ...")
    with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        futures = [
            executor.submit(invoke_for_burst, lambda_client, function_name, i, start_barrier)
            for i in range(1, concurrent_requests + 1)
        ]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"   request {result.index:03d} -> {result.outcome.upper():9s} "
                f"http_status={result.http_status} detail={result.detail} "
                f"elapsed={result.elapsed_ms}ms"
            )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Concurrent burst load test designed to exceed Lambda reserved concurrency."
    )
    parser.add_argument("--function-name", required=True, help="Target Lambda function name.")
    parser.add_argument(
        "--concurrent-requests",
        type=int,
        default=50,
        help="Number of simultaneous invocations to fire. Default: 50",
    )
    parser.add_argument(
        "--reserved-concurrency",
        type=int,
        default=10,
        help="Informational only: the ReservedConcurrentExecutions value configured on the "
        "function, printed in the summary for context. Default: 10",
    )
    parser.add_argument("--region", default=boto3.session.Session().region_name or "us-east-1")
    args = parser.parse_args()

    if args.concurrent_requests <= args.reserved_concurrency:
        print(
            f"WARNING: concurrent-requests ({args.concurrent_requests}) does not exceed "
            f"reserved-concurrency ({args.reserved_concurrency}). Throttling is unlikely to occur. "
            "Increase --concurrent-requests to reliably force 429 responses.",
            file=sys.stderr,
        )

    print(f"=== Burst Load Test: {args.function_name} ({args.region}) ===")
    print(f"    Reserved concurrency on function (expected): {args.reserved_concurrency}")
    print(f"    Concurrent requests fired: {args.concurrent_requests}\n")

    results = run_burst(args.function_name, args.concurrent_requests, args.region)

    outcome_counts = Counter(r.outcome for r in results)
    total = len(results)

    print("\n=== Burst Summary ===")
    print(json.dumps(dict(outcome_counts), indent=2))
    print(f"Total requests: {total}")
    print(f"Successful:     {outcome_counts.get('success', 0)}")
    print(f"Throttled (429):{outcome_counts.get('throttled', 0)}")
    print(f"Other errors:   {outcome_counts.get('error', 0)}")

    if outcome_counts.get("throttled", 0) > 0:
        print(
            "\nThrottling confirmed. Expected downstream effects within ~60 seconds:\n"
            "  1. CloudWatch Alarm '<project>-throttle-alarm' transitions to ALARM "
            "(AWS/Lambda Throttles Sum > 0 over 1 minute).\n"
            "  2. AWS/Lambda ConcurrentExecutions metric peaks at or near the reserved "
            "concurrency limit, but never above it.\n"
            "  3. AWS X-Ray will show a trace count equal to the 'success' count above -- "
            "NOT the total requests fired -- because throttled invocations never reach "
            "the function runtime and therefore never emit a trace segment."
        )
    else:
        print(
            "\nNo throttling observed. If this is unexpected, confirm the function's "
            "ReservedConcurrentExecutions is actually set to a low value (e.g. 10) and that "
            "--concurrent-requests sufficiently exceeds it."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
