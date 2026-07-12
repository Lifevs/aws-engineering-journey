#!/bin/bash
set -euo pipefail
# Usage: OS_ENDPOINT=... OS_USER=labadmin OS_PASSWORD=... ./create-index.sh

curl -s -u "${OS_USER}:${OS_PASSWORD}" -X PUT "https://${OS_ENDPOINT}/products" \
  -H 'Content-Type: application/json' \
  -d '{
    "settings": { "number_of_shards": 1, "number_of_replicas": 0 },
    "mappings": {
      "properties": {
        "id":          { "type": "keyword" },
        "name":        { "type": "text" },
        "description": { "type": "text" },
        "category":    { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
        "price":       { "type": "float" },
        "tags":        { "type": "text" },
        "createdAt":   { "type": "date" }
      }
    }
  }' | python3 -m json.tool
