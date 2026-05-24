import boto3
import time
import json
import urllib.request
import urllib.error
import concurrent.futures

# ==========================================
# ⚠️ CONFIGURATION - FILL ALL 3 IN ⚠️
# ==========================================
# 1. Your Pool ID (starts with ap-south-1_)
USER_POOL_ID = 'ap-south-1_qvnUB074o' 

# 2. Your Public SPA App Client ID (no secret)
CLIENT_ID = '4e21q49g49249qj6g0n13mbkcg'

# 3. Your full API Gateway URL for the protected route
API_URL = 'https://7hdqzn4qwh.execute-api.ap-south-1.amazonaws.com/dev/login/data'

# Test Parameters
BASE_EMAIL = 'testuser'
STANDARD_PASSWORD = 'DevOpsTest!123'
NUM_USERS = 50
# ==========================================

client = boto3.client('cognito-idp', region_name='ap-south-1')
valid_tokens = []

print(f"\n🚀 STARTING INTEGRATION TEST: {NUM_USERS} USERS\n")
print("--- PHASE 1: User Injection & Authentication ---")

for i in range(1, NUM_USERS + 1):
    email = f"{BASE_EMAIL}{i}@example.com"
    
    # Step 1A: Inject the user into the database
    try:
        client.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=email,
            UserAttributes=[{'Name': 'email', 'Value': email}, {'Name': 'email_verified', 'Value': 'true'}],
            MessageAction='SUPPRESS'
        )
        client.admin_set_user_password(
            UserPoolId=USER_POOL_ID,
            Username=email,
            Password=STANDARD_PASSWORD,
            Permanent=True
        )
    except client.exceptions.UsernameExistsException:
        pass # If they already exist from a previous test, just move on to login
    except Exception as e:
        print(f"❌ Failed to create {email}: {str(e)}")
        continue

    # Step 1B: Authenticate the user to get their JWT
    try:
        response = client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={'USERNAME': email, 'PASSWORD': STANDARD_PASSWORD}
        )
        token = response['AuthenticationResult']['IdToken']
        valid_tokens.append(token)
        print(f"✅ Auth Success: {email}")
    except Exception as e:
        print(f"❌ Auth Failed for {email}: {str(e)}")
    
    # Sleep slightly to avoid AWS rate limits during sequential login
    time.sleep(0.1)

print(f"\n✅ Phase 1 Complete. Collected {len(valid_tokens)} active JWTs.")

if len(valid_tokens) == 0:
    print("⚠️ No tokens collected. Aborting Phase 2.")
    exit()

print(f"\n--- PHASE 2: Firing {len(valid_tokens)} Concurrent Requests at API Gateway! ---\n")

# Step 2: The Concurrent Burst Function
def fire_api_request(token, user_num):
    # Construct the HTTP request with the standard Bearer header
    req = urllib.request.Request(API_URL, headers={'Authorization': token})
    
    try:
        # Fire the request
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            body_bytes = response.read()
            # Try to parse the response to prove Lambda decoded the email
            try:
                body = json.loads(body_bytes.decode('utf-8'))
                returned_email = body.get('email', 'Unknown Email')
                print(f"🟢 User {user_num:02d} (Email: {returned_email}): HTTP {status} OK!")
            except json.JSONDecodeError:
                print(f"🟢 User {user_num:02d}: HTTP {status} OK! (Non-JSON Response)")
                
    except urllib.error.HTTPError as e:
        print(f"🔴 User {user_num:02d}: FAILED (HTTP {e.code}) - {e.read().decode('utf-8')}")
    except urllib.error.URLError as e:
        print(f"🔴 User {user_num:02d}: Network Error ({e.reason})")

# Step 3: Execute the burst using a ThreadPool to hit the endpoint concurrently
with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_USERS) as executor:
    # We map the fire_api_request function across all our collected tokens
    futures = [executor.submit(fire_api_request, token, idx + 1) for idx, token in enumerate(valid_tokens)]
    
    # Wait for all 50 concurrent requests to finish
    concurrent.futures.wait(futures)

print("\n🎉 INTEGRATION TEST COMPLETE. If you see all green, your architecture is flawlessly scaling!")