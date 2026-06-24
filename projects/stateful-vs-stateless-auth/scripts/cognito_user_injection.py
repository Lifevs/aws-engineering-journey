import boto3
import time

# ==========================================
# ⚠️ CONFIGURATION - FILL THIS IN ⚠️
# ==========================================
# Your User Pool ID (Find this in the Cognito console, looks like 'ap-south-1_xxxxxxxxx')
USER_POOL_ID = 'ap-south-1_qvnUB074o' 

# Do not change these if you want them to match the HTML file exactly
BASE_EMAIL = 'testuser'
STANDARD_PASSWORD = 'DevOpsTest!123'
NUM_USERS = 50
# ==========================================

client = boto3.client('cognito-idp', region_name='ap-south-1')

print(f"🚀 Injecting {NUM_USERS} confirmed users into Cognito...\n")

for i in range(1, NUM_USERS + 1):
    email = f"{BASE_EMAIL}{i}@example.com"
    
    try:
        # 1. Force create the user and instantly verify their email
        client.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=email,
            UserAttributes=[
                {'Name': 'email', 'Value': email}, 
                {'Name': 'email_verified', 'Value': 'true'}
            ],
            MessageAction='SUPPRESS' # Prevents AWS from sending 50 junk emails
        )
        
        # 2. Force set the password and mark it as Permanent 
        # (If Permanent=False, Cognito forces a password change on first login, which breaks automated tests)
        client.admin_set_user_password(
            UserPoolId=USER_POOL_ID,
            Username=email,
            Password=STANDARD_PASSWORD,
            Permanent=True
        )
        
        print(f"✅ Created & Confirmed: {email}")
        
        # A tiny delay prevents us from hitting AWS Admin API rate limits
        time.sleep(0.3) 
        
    except client.exceptions.UsernameExistsException:
        print(f"⚠️ Already exists (Skipping): {email}")
    except Exception as e:
        print(f"❌ Failed {email}: {str(e)}")

print("\n🎉 Database populated! All users are ready for the HTML Burst Test.")