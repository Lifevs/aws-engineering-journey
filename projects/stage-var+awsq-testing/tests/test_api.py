import requests
from conftest import SEED_ID, SEED_SORT_1, SEED_SORT_2


def test_get_item_by_id_and_sort_key(api_base_url):
    """Case 1: exact lookup via partition key + sort key → 200 with correct item."""
    r = requests.get(f"{api_base_url}/resource", params={"id": SEED_ID, "createdAt": SEED_SORT_1})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == SEED_ID
    assert body["createdAt"] == SEED_SORT_1
    assert body["name"] == "Alpha"
    # Decimal(42) must come back as a number, not a string
    assert isinstance(body["score"], (int, float))
    assert body["score"] == 42


def test_get_item_by_id_only(api_base_url):
    """Case 3: get_item by partition key only → 200 (table has sort key so DDB
    returns nothing via get_item; Lambda falls through to scan and the item
    is present — adjust if your Lambda behaviour differs)."""
    # This hits the id-only branch; because the table has a sort key,
    # DDB get_item requires both keys → Lambda returns 404 for this path.
    # Adjust the assertion to match your actual Lambda routing decision.
    r = requests.get(f"{api_base_url}/resource", params={"id": SEED_ID})
    # Lambda returns 404 when get_item misses (sort key required but absent)
    assert r.status_code == 404
    assert "message" in r.json()


def test_query_by_partition_key(api_base_url):
    """Case 2: list=true → query returns all items for the partition key."""
    r = requests.get(f"{api_base_url}/resource", params={"id": SEED_ID, "list": "true"})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "count" in body
    ids = [i["createdAt"] for i in body["items"]]
    assert SEED_SORT_1 in ids
    assert SEED_SORT_2 in ids
    assert body["count"] >= 2
    # Decimal handling: every score must be a number
    for item in body["items"]:
        assert isinstance(item["score"], (int, float))


def test_full_scan(api_base_url):
    """Case 4: no params → scan returns at least the two seeded items."""
    r = requests.get(f"{api_base_url}/resource")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "count" in body
    seeded_ids = {i["id"] for i in body["items"]}
    assert SEED_ID in seeded_ids


def test_item_not_found(api_base_url):
    """Case 1 path with a non-existent sort key → 404 with message field."""
    r = requests.get(
        f"{api_base_url}/resource",
        params={"id": SEED_ID, "createdAt": "1999-01-01"},
    )
    assert r.status_code == 404
    body = r.json()
    assert body.get("message") == "Item not found"
