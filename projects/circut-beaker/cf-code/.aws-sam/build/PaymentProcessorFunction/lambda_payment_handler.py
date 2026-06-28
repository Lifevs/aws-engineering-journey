import json
import os
import time
import boto3
from botocore.exceptions import ClientError
import urllib.request
import urllib.error

# Initialize DynamoDB outside the handler for connection reuse (Exam Tip!)
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'CircuitBreakerState'))
FAILURE_THRESHOLD = int(os.environ.get('FAILURE_THRESHOLD', 3))
COOLDOWN_SECONDS = int(os.environ.get('COOLDOWN_SECONDS', 30))

def lambda_handler(event, context):
    service_name = "ExternalPaymentAPI"
    current_time = int(time.time())
    
    # 1. READ STATE FROM DYNAMODB
    try:
        response = table.get_item(Key={'ServiceName': service_name})
        circuit_state = response.get('Item', {})
    except ClientError as e:
        print(f"DynamoDB Error: {e}")
        circuit_state = {}

    state = circuit_state.get('State', 'CLOSED')
    next_retry = circuit_state.get('NextRetryTime', 0)
    
    # 2. CHECK CIRCUIT BREAKER LOGIC
    if state == 'OPEN':
        if current_time < next_retry:
            # FAIL FAST: We are in the cooling period. Do not call the API.
            print("Circuit is OPEN. Failing fast to save compute.")
            return {
                "statusCode": 503,
                "body": json.dumps({"error": "Payment service temporarily unavailable. Please try again later."})
            }
        else:
            # Cooling period passed. Switch to HALF_OPEN to test the waters.
            state = 'HALF_OPEN'
            print("Cooling period ended. Circuit is HALF_OPEN. Testing API...")

    # 3. ATTEMPT THE EXTERNAL API CALL
    try:
        # Mocking an external HTTP call. In reality, this would be requests.post()
        # For testing, you could point this to a URL that you can force to timeout.
        req = urllib.request.Request('https://httpstat.us/200') # Change to /503 to simulate failure
        urllib.request.urlopen(req, timeout=3)
        
        # 4A. SUCCESS LOGIC
        print("Payment API Call Succeeded.")
        if state != 'CLOSED':
            # Reset the circuit back to healthy
            table.put_item(Item={
                'ServiceName': service_name,
                'State': 'CLOSED',
                'FailureCount': 0
            })
            
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Payment processed successfully!"})
        }
        
    except (urllib.error.URLError, Exception) as e:
        # 4B. FAILURE LOGIC
        print(f"Payment API Call Failed: {e}")
        
        if state == 'HALF_OPEN':
            # If it fails during a test, snap it right back OPEN
            new_failures = FAILURE_THRESHOLD
        else:
            # Increment failure count
            new_failures = circuit_state.get('FailureCount', 0) + 1
            
        # Determine new state
        if new_failures >= FAILURE_THRESHOLD:
            new_state = 'OPEN'
            new_retry_time = current_time + COOLDOWN_SECONDS
            print(f"Threshold reached! Tripping circuit to OPEN for {COOLDOWN_SECONDS}s")
        else:
            new_state = 'CLOSED'
            new_retry_time = 0
            
        # Update DynamoDB with the new state
        table.put_item(Item={
            'ServiceName': service_name,
            'State': new_state,
            'FailureCount': new_failures,
            'NextRetryTime': new_retry_time,
            'ExpirationTime': current_time + 86400 # Clean up record after 24h
        })
        
        return {
            "statusCode": 502,
            "body": json.dumps({"error": "Bad Gateway: Upstream payment provider failed."})
        }