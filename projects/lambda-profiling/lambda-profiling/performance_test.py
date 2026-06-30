#!/usr/bin/env python3
"""
Script A — Performance Testing (memory configuration sweep)

Invokes the deployed target Lambda function sequentially under two memory
configurations (128MB and 1024MB by default) so that AWS X-Ray traces and
CloudWatch Duration metrics show the measurable effect of vCPU allocation
(which scales with MemorySize) on the CPU-bound workload's execution time.

This script intentionally invokes SEQUENTIALLY and well within the
function's reserved concurrency limit, so every invocation succeeds and
every invocation produces a complete X-Ray trace -- there is no throttling
in this script by design. Contrast with Script B (load_test.py).

Usage:
    python3 performance_test.py \
        --function-name lambda-perf-lab-target-function \
        --invocations-per-config 10 \
        --memory-configs 128 1024

Requires:
    boto3, AWS credentials with lambda:InvokeFunction and
    lambda:UpdateFunctionConfiguration permissions on the target function.
"""

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

WAITER_POLL_SECONDS = 2
WAITER_MAX_ATTEMPTS = 30


@dataclass
class InvocationResult:
    memory_mb: int
    invocation_index: int
    client_observed_ms: float
    reported_duration_ms: float
    request_id: str
    status_code: int


@dataclass
class ConfigSummary:
    memory_mb: int
    results: list = field(default_factory=list)

    def add(self, result: InvocationResult) -> None:
        self.results.append(result)

    def durations(self) -> list:
        return [r.reported_duration_ms for r in self.results]

    def summary(self) -> dict:
        d = self.durations()
        if not d:
            return {"memory_mb": self.memory_mb, "count": 0}
        return {
            "memory_mb": self.memory_mb,
            "count": len(d),
            "min_ms": round(min(d), 2),
            "max_ms": round(max(d), 2),
            "mean_ms": round(statistics.mean(d), 2),
            "p50_ms": round(statistics.median(d), 2),
            "stdev_ms": round(statistics.pstdev(d), 2) if len(d) > 1 else 0.0,
        }


def wait_for_function_active(lambda_client, function_name: str) -> None:
    """Poll until LastUpdateStatus is Successful before invoking, avoiding
    ResourceConflictException during memory reconfiguration."""
    for attempt in range(WAITER_MAX_ATTEMPTS):
        response = lambda_client.get_function_configuration(FunctionName=function_name)
        state = response.get("State")
        update_status = response.get("LastUpdateStatus")
        if state == "Active" and update_status == "Successful":
            return
        time.sleep(WAITER_POLL_SECONDS)
    raise TimeoutError(
        f"Function {function_name} did not reach Active/Successful state "
        f"after {WAITER_MAX_ATTEMPTS * WAITER_POLL_SECONDS} seconds."
    )


def set_memory_configuration(lambda_client, function_name: str, memory_mb: int) -> None:
    print(f"-> Updating {function_name} MemorySize to {memory_mb}MB ...")
    lambda_client.update_function_configuration(
        FunctionName=function_name, MemorySize=memory_mb
    )
    wait_for_function_active(lambda_client, function_name)
    print(f"   Memory configuration update complete: {memory_mb}MB is now active.")


def invoke_once(lambda_client, function_name: str, memory_mb: int, index: int) -> InvocationResult:
    payload = {"scenario": "performance-sweep", "memory_mb": memory_mb, "index": index}
    start = time.perf_counter()
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    client_observed_ms = (time.perf_counter() - start) * 1000
    body_raw = response["Payload"].read()
    status_code = response.get("StatusCode", 0)

    try:
        body = json.loads(body_raw)
        inner_body = json.loads(body.get("body", "{}"))
        reported_duration_ms = inner_body.get("total_elapsed_ms", client_observed_ms)
        request_id = inner_body.get("request_id", response.get("ResponseMetadata", {}).get("RequestId", "unknown"))
    except (json.JSONDecodeError, AttributeError):
        reported_duration_ms = client_observed_ms
        request_id = response.get("ResponseMetadata", {}).get("RequestId", "unknown")

    return InvocationResult(
        memory_mb=memory_mb,
        invocation_index=index,
        client_observed_ms=round(client_observed_ms, 2),
        reported_duration_ms=round(reported_duration_ms, 2),
        request_id=request_id,
        status_code=status_code,
    )


def run_sweep(function_name: str, memory_configs: list, invocations_per_config: int, region: str) -> list:
    boto_config = Config(retries={"max_attempts": 0})  # no client-side retries; we want raw signal
    lambda_client = boto3.client("lambda", region_name=region, config=boto_config)

    summaries = []
    for memory_mb in memory_configs:
        set_memory_configuration(lambda_client, function_name, memory_mb)
        config_summary = ConfigSummary(memory_mb=memory_mb)

        print(f"-> Running {invocations_per_config} sequential invocations at {memory_mb}MB ...")
        for i in range(1, invocations_per_config + 1):
            try:
                result = invoke_once(lambda_client, function_name, memory_mb, i)
                config_summary.add(result)
                print(
                    f"   [{memory_mb}MB] invocation {i}/{invocations_per_config} "
                    f"-> reported_duration={result.reported_duration_ms}ms "
                    f"client_observed={result.client_observed_ms}ms "
                    f"request_id={result.request_id}"
                )
            except ClientError as exc:
                print(f"   [{memory_mb}MB] invocation {i} FAILED: {exc}", file=sys.stderr)

        summaries.append(config_summary)

    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description="Lambda memory configuration performance sweep.")
    parser.add_argument("--function-name", required=True, help="Target Lambda function name.")
    parser.add_argument(
        "--memory-configs",
        nargs="+",
        type=int,
        default=[128, 1024],
        help="List of MemorySize values (MB) to sweep through sequentially. Default: 128 1024",
    )
    parser.add_argument(
        "--invocations-per-config",
        type=int,
        default=10,
        help="Number of sequential invocations to run per memory configuration. Default: 10",
    )
    parser.add_argument("--region", default=boto3.session.Session().region_name or "us-east-1")
    args = parser.parse_args()

    print(f"=== Performance Sweep: {args.function_name} ({args.region}) ===")
    summaries = run_sweep(
        function_name=args.function_name,
        memory_configs=args.memory_configs,
        invocations_per_config=args.invocations_per_config,
        region=args.region,
    )

    print("\n=== Summary (compare against AWS X-Ray Service Map / Trace timelines) ===")
    for config_summary in summaries:
        print(json.dumps(config_summary.summary(), indent=2))

    print(
        "\nNext step: open the AWS X-Ray console -> Traces, filter by "
        f"service name '{args.function_name}', and compare the 'cpu_bound_hash_workload' "
        "subsegment duration across the two memory tiers. Lower memory should show "
        "visibly longer compute subsegments due to reduced vCPU allocation."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
