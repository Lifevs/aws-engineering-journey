import os
import json

def lambda_handler(event, context):
    # Fetch the environment variable passed from CloudFormation
    current_env = os.environ.get('APP_ENV', 'unknown')
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Lambda successfully executed!",
            "environment": current_env
        })
    }