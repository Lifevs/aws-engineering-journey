"""
End-to-end simulation for the AppSync + Step Functions order workflow.

What this exercises (and why it matters for DVA-C02):
  1. Calling an AppSync mutation via plain HTTPS + API key (no SDK needed --
     good to understand what the SDK/Amplify is doing under the hood).
  2. Polling a Query resolver to observe eventually-consistent state changes
     as the Step Functions workflow progresses asynchronously.
  3. Using boto3 stepfunctions.describe_execution / get_execution_history
     to see the actual state transitions, Retry attempts, and Catch behavior.
  4. Triggering the Catch/Fail path on purpose (invalid amount) so you can
     see NotifyFailure and the workflow's error handling in action.

Usage:
    pip install boto3 python-dotenv --break-system-packages
    python3 test_simulation.py
"""

import json
import os
import time
import urllib.request
import uuid

import boto3

# --- load .env written by deploy.sh -----------------------------------
def load_env(path=".env"):
    env = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k] = v
    return env


ENV = {**load_env(), **os.environ}
GRAPHQL_URL = ENV["GRAPHQL_URL"]
API_KEY = ENV["API_KEY"]
STATE_MACHINE_ARN = ENV["STATE_MACHINE_ARN"]
REGION = ENV.get("AWS_REGION", "us-east-1")

sfn = boto3.client("stepfunctions", region_name=REGION)


def graphql_request(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={"Content-Type": "application/json", "x-api-key": API_KEY},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def create_order(customer_id, items, amount):
    query = """
    mutation CreateOrder($input: CreateOrderInput!) {
        createOrder(input: $input) {
            orderId
            status
            statusMessage
            amount
        }
    }
    """
    result = graphql_request(query, {"input": {
        "customerId": customer_id, "items": items, "amount": amount
    }})
    if result.get("errors"):
        raise RuntimeError(result["errors"])
    return result["data"]["createOrder"]


def get_order(order_id):
    query = """
    query GetOrder($orderId: ID!) {
        getOrder(orderId: $orderId) {
            orderId status statusMessage updatedAt
        }
    }
    """
    result = graphql_request(query, {"orderId": order_id})
    return result["data"]["getOrder"]


def watch_order(order_id, timeout_s=30, poll_interval=1.5):
    """Poll getOrder until status reaches a terminal state or times out."""
    terminal = {"SHIPPED", "FAILED"}
    seen_statuses = []
    start = time.time()
    while time.time() - start < timeout_s:
        order = get_order(order_id)
        status = order["status"]
        if not seen_statuses or seen_statuses[-1] != status:
            elapsed = round(time.time() - start, 2)
            print(f"  [{elapsed:>5}s] {status:<20} {order.get('statusMessage','')}")
            seen_statuses.append(status)
        if status in terminal:
            return seen_statuses
        time.sleep(poll_interval)
    print("  !! timed out waiting for terminal state")
    return seen_statuses


def find_execution_for_order(order_id, lookback=5):
    """Find the Step Functions execution whose input contains this orderId."""
    resp = sfn.list_executions(stateMachineArn=STATE_MACHINE_ARN, maxResults=lookback)
    for ex in resp["executions"]:
        detail = sfn.describe_execution(executionArn=ex["executionArn"])
        if order_id in detail["input"]:
            return detail
    return None


def print_execution_history(execution_arn):
    print(f"  Execution: {execution_arn}")
    history = sfn.get_execution_history(
        executionArn=execution_arn, reverseOrder=False
    )["events"]
    for event in history:
        etype = event["type"]
        if etype in (
            "TaskStateEntered", "TaskStateExited", "TaskFailed",
            "TaskSucceeded", "ExecutionSucceeded", "ExecutionFailed",
            "ChoiceStateEntered",
        ):
            print(f"    {event['timestamp'].strftime('%H:%M:%S')}  {etype}")


def scenario_happy_path():
    print("\n=== Scenario 1: normal order (should reach SHIPPED) ===")
    order = create_order("cust-001", ["widget", "gadget"], 49.99)
    print(f"created order {order['orderId']} (initial status={order['status']})")
    watch_order(order["orderId"])
    execution = find_execution_for_order(order["orderId"])
    if execution:
        print_execution_history(execution["executionArn"])


def scenario_validation_failure():
    print("\n=== Scenario 2: invalid amount (should reach FAILED via Catch) ===")
    order = create_order("cust-002", ["broken-item"], -10.00)
    print(f"created order {order['orderId']} (initial status={order['status']})")
    watch_order(order["orderId"])
    execution = find_execution_for_order(order["orderId"])
    if execution:
        print_execution_history(execution["executionArn"])


def scenario_concurrent_orders(n=5):
    print(f"\n=== Scenario 3: {n} concurrent orders (throughput / eventual consistency) ===")
    orders = [create_order(f"cust-bulk-{i}", ["item"], 10.0 + i) for i in range(n)]
    for o in orders:
        print(f"created {o['orderId']}")
    print("watching all in parallel via repeated polling...")
    remaining = {o["orderId"] for o in orders}
    start = time.time()
    while remaining and time.time() - start < 30:
        for oid in list(remaining):
            status = get_order(oid)["status"]
            if status in ("SHIPPED", "FAILED"):
                print(f"  {oid} -> {status}")
                remaining.discard(oid)
        time.sleep(1.5)
    if remaining:
        print(f"  !! {len(remaining)} orders did not finish in time: {remaining}")


if __name__ == "__main__":
    scenario_happy_path()
    scenario_validation_failure()
    scenario_concurrent_orders()
