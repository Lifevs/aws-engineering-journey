#!/usr/bin/env python3
"""
Runs the SAME logical question two ways and prints timing + result shape,
so you can *feel* the difference between DynamoDB key-value access and
OpenSearch full-text/analytics access instead of just reading about it.

Usage:
    pip install boto3 requests --break-system-packages
    TABLE_NAME=... OS_ENDPOINT=... OS_USER=labadmin OS_PASSWORD=... python3 compare_access_patterns.py
"""
import os
import time
import boto3
import requests
import statistics

TABLE_NAME = os.environ["TABLE_NAME"]
OS_ENDPOINT = os.environ["OS_ENDPOINT"]
OS_USER = os.environ["OS_USER"]
OS_PASSWORD = os.environ["OS_PASSWORD"]
REGION = os.environ.get("AWS_REGION", "us-east-1")

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def timeit(fn, n=10):
    times = []
    result = None
    for _ in range(n):
        start = time.perf_counter()
        result = fn()
        times.append((time.perf_counter() - start) * 1000)
    return result, times


def dynamo_get_by_id(item_id):
    return table.get_item(Key={"id": item_id}).get("Item")


def dynamo_scan_by_keyword(keyword):
    # Deliberately naive: DynamoDB has no native full-text search.
    # This is the anti-pattern you're meant to observe the cost of.
    resp = table.scan(
        FilterExpression="contains(description, :kw) OR contains(#n, :kw)",
        ExpressionAttributeNames={"#n": "name"},
        ExpressionAttributeValues={":kw": keyword},
    )
    return resp.get("Items", [])


def opensearch_full_text(keyword):
    query = {
        "query": {
            "multi_match": {
                "query": keyword,
                "fields": ["name^2", "description", "tags"],
                "fuzziness": "AUTO",
            }
        },
        "size": 20,
    }
    resp = requests.post(
        f"https://{OS_ENDPOINT}/products/_search",
        json=query,
        auth=(OS_USER, OS_PASSWORD),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["hits"]["hits"]


def opensearch_aggregation_by_category():
    query = {
        "size": 0,
        "aggs": {"by_category": {"terms": {"field": "category.keyword"}}},
    }
    resp = requests.post(
        f"https://{OS_ENDPOINT}/products/_search",
        json=query,
        auth=(OS_USER, OS_PASSWORD),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["aggregations"]["by_category"]["buckets"]


def main():
    sample_id = dynamo_scan_by_keyword("camping")[0]["id"] if dynamo_scan_by_keyword("camping") else None

    print("\n=== 1. Key lookup: DynamoDB GetItem (the pattern DynamoDB is built for) ===")
    if sample_id:
        _, t = timeit(lambda: dynamo_get_by_id(sample_id), n=20)
        print(f"  avg={statistics.mean(t):.2f}ms  p95={sorted(t)[int(len(t)*0.95)]:.2f}ms")

    print("\n=== 2. Keyword search: DynamoDB Scan+contains() (the anti-pattern) ===")
    _, t = timeit(lambda: dynamo_scan_by_keyword("waterproof"), n=10)
    print(f"  avg={statistics.mean(t):.2f}ms  p95={sorted(t)[int(len(t)*0.95)]:.2f}ms")
    print("  -> Scans read every item and cost RCU proportional to table size,")
    print("     regardless of how many rows match. This gets worse as data grows.")

    print("\n=== 3. Keyword search: OpenSearch multi_match (the pattern it's built for) ===")
    _, t = timeit(lambda: opensearch_full_text("waterproof"), n=10)
    print(f"  avg={statistics.mean(t):.2f}ms  p95={sorted(t)[int(len(t)*0.95)]:.2f}ms")
    print("  -> Uses an inverted index; cost is roughly independent of table size.")

    print("\n=== 4. Analytics: OpenSearch aggregation (no DynamoDB equivalent without a scan) ===")
    buckets = opensearch_aggregation_by_category()
    for b in buckets:
        print(f"  {b['key']:<12} {b['doc_count']} items")

    print("\nTakeaway for the exam: DynamoDB gives you O(1) key access at any scale.")
    print("OpenSearch gives you O(1)-ish relevance search and aggregations that")
    print("DynamoDB cannot do natively. Streams + Lambda is the standard AWS")
    print("pattern for keeping a purpose-built search index in sync with your")
    print("system of record, without dual-writing from the application layer.")


if __name__ == "__main__":
    main()
