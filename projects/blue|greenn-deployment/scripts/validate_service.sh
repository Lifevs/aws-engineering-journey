#!/bin/bash
echo "=== Step 3: Validating Service Health ==="

# Define the target URL (localhost port 80) and max verification attempts
TARGET_URL="http://localhost:80/"
MAX_ATTEMPTS=5
SLEEP_TIME=5

for ((i=1; i<=MAX_ATTEMPTS; i++)); do
    echo "Checking health: Attempt $i of $MAX_ATTEMPTS..."
    
    # Send curl request, capture HTTP response status code
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 $TARGET_URL)
    
    if [ "$HTTP_STATUS" -eq 200 ]; then
        echo "Success: Web server is active and returning HTTP 200 OK!"
        exit 0
    fi
    
    echo "Warning: Received status $HTTP_STATUS. Retrying in $SLEEP_TIME seconds..."
    sleep $SLEEP_TIME
done

echo "Error: Service validation timed out or failed to return HTTP 200."
exit 1